#!/usr/bin/env python3
"""Generate and check the declared RouterOS API coverage.

The manifest in ``docs/api-coverage.yml`` is the source of truth for what the
MCP intends to cover. This script turns it into the human-readable
``docs/api-coverage.md`` checklist and, when given a downloaded
``llms-full.txt``, compares the declared coverage with the manual.

It never downloads anything. The manually triggered GitHub workflow
``check-api-coverage.yml`` downloads the corpus into the CI runner and calls
this script with ``--manual``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Literal, TypedDict

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs/api-coverage.yml"
DEFAULT_LOCK = ROOT / "docs/manual.lock.yml"
DEFAULT_OUTPUT = ROOT / "docs/api-coverage.md"

# Stable ordering for the generated checklist. Unknown commands sort last.
COMMAND_ORDER = (
    "add",
    "print",
    "set",
    "remove",
    "enable",
    "disable",
    "move",
    "export",
    "import",
    "save",
    "load",
    "flush",
    "monitor",
    "scan",
    "check",
    "make-static",
    "sign",
)
COMMAND_ORDER_INDEX = {name: index for index, name in enumerate(COMMAND_ORDER)}

# Arguments that may be declared in the manifest even when the manual's
# ArgTable omits them (tool-level or positional values). Used only by the
# missing-parameter check; the unmapped-argument check still reports a manual
# argument that the manifest does not declare.
MISSING_PARAM_EXEMPTIONS = frozenset(
    {
        "device",
        "interfaces",
        "duration",
        "file",
        "interface",
        "mac-address",
        "active-host-name",
        "active-class-id",
        "public-key-file",
        "password-file",
        "run-after-reset",
    },
)

# RouterOS arguments that are valid on nearly every menu and are often left
# out of the generated ArgTable. They are not coverage gaps.
UNIVERSAL_PARAMS = frozenset(
    {
        "comment",
        "disabled",
        "place-before",
        "running",
        "invalid",
        "dynamic",
        "active",
        "static",
        "all",
        "global",
        "link-local",
        "password",
    },
)

# Values that appear as flags or placeholders in the manual's tables rather
# than as configurable arguments.
IGNORED_MANUAL_ARGS = frozenset({"*", "-"})

# Root command pages in llms-full.txt have headings without a slash, e.g.
# "## import" or "## log". They are still RouterOS menus for our purposes.
ROOT_MENUS = frozenset(
    {
        "certificate",
        "export",
        "file",
        "import",
        "interface",
        "log",
        "user",
    },
)

# Compiled once: the manual corpus can be large, and these patterns are
# applied to every page of it.
_MANUAL_PAGE_SEPARATOR_LINE_RE = re.compile(r"^[ \t]*---[ \t]*$")
_MANUAL_FENCE_START_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})")
_MANUAL_FENCE_END_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[ \t]*$")
_MANUAL_FENCED_CODE_RE = re.compile(r"(?P<fence>`{3,}|~{3,}).*?(?P=fence)", re.DOTALL)
_MANUAL_MENU_RE = re.compile(r"^\s*#{1,3}\s+(/?[A-Za-z0-9_./() -]+)\s*$", re.MULTILINE)
_MANUAL_ARG_RE = re.compile(
    r"""<ArgTableRow\b[^>]*\sarg\s*=\s*(?:"([^"]+)"|'([^']+)')""",
)
_MANUAL_TABLE_RE = re.compile(
    r"""<ArgTable\b[^>]*\sc1\s*=\s*(?:"([^"]+)"|'([^']+)')[^>]*>(.*?)</ArgTable>""",
    re.DOTALL,
)
_MANUAL_SUBMENU_RE = re.compile(r"\*\*Sub-menu:\*\*\s*`([^`]+)`")
_MANUAL_ROOT_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


class ManualLock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    url: str
    etag: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    built_at: str


Status = Literal["implemented", "partial", "planned", "legacy", "not_applicable"]


class CommandCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    tools: list[str] = Field(default_factory=list)
    params: list[str] = Field(default_factory=list)
    accepted_gaps: list[str] = Field(default_factory=list)
    notes: str | None = None


class MenuCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    section: str
    notes: str | None = None
    # Some RouterOS menus are documented as separate command pages rather than
    # one parent page (for example /system/backup/save and /system/backup/load).
    manual_paths: list[str] = Field(default_factory=list)
    # A few commands (/export) are documented outside the CLI-reference pages.
    allow_missing_manual: bool = False
    commands: dict[str, CommandCoverage]


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    menus: list[str]


class ServerTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["server", "interactive", "local", "composite", "sftp", "command"]
    note: str | None = None


class ExcludedMenu(BaseModel):
    model_config = ConfigDict(extra="forbid")

    menu: str
    reason: str


class CoverageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[Section]
    menus: dict[str, MenuCoverage]
    server_tools: dict[str, ServerTool]
    excluded: list[ExcludedMenu]


@dataclass(frozen=True, slots=True)
class DriftResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    new_menus: tuple[str, ...]
    unmapped_args: Mapping[str, tuple[str, ...]]
    missing_params: tuple[str, ...]
    manual_sha256: str
    manual_changed: bool

    @property
    def has_drift(self) -> bool:
        return bool(
            self.errors
            or self.warnings
            or self.new_menus
            or self.unmapped_args
            or self.missing_params,
        )


class _UniqueKeyLoader(yaml.SafeLoader):
    """A SafeLoader that rejects duplicate mapping keys instead of dropping them."""


def _reject_duplicate_keys(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> None:
    seen: set[object] = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        seen.add(key)


def _construct_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    # Detect duplicates before expanding merge keys: an explicit key may
    # legitimately override a key inherited through `<<`.
    _reject_duplicate_keys(loader, node, deep)
    loader.flatten_mapping(node)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _load_yaml(path: Path) -> object:
    """Load *path* as YAML, rejecting duplicate mapping keys."""
    # yaml.load is safe here: _UniqueKeyLoader subclasses yaml.SafeLoader.
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)


def load_lock(path: Path) -> ManualLock:
    data = _load_yaml(path)
    if not isinstance(data, dict) or "manual" not in data:
        raise ValueError(f"{path}: expected a top-level 'manual' mapping")
    return ManualLock.model_validate(data["manual"])


def load_manifest(path: Path) -> CoverageManifest:
    data = _load_yaml(path)
    return CoverageManifest.model_validate(data)


def _path_error(path: str, label: str) -> str | None:
    """Return a structural error when *path* is not a slash-separated menu path."""
    if not path.startswith("/"):
        return f"{label} {path!r} must start with '/'"
    if any(character.isspace() for character in path):
        return f"{label} {path!r} must be slash-separated"
    if path.endswith("/"):
        return f"{label} {path!r} must not end with '/'"
    return None


def _has_text(*values: str | None) -> bool:
    """True when at least one value contains non-whitespace text."""
    return any(value and value.strip() for value in values)


def _validate_sections(
    manifest: CoverageManifest,
) -> tuple[list[str], set[str], set[str]]:
    """Validate section titles, membership and menu/section agreement."""
    errors: list[str] = []
    section_titles = {section.title for section in manifest.sections}
    if len(section_titles) != len(manifest.sections):
        errors.append("section titles must be unique")
    seen: set[str] = set()
    for section in manifest.sections:
        if not section.title.strip():
            errors.append("section title must not be blank")
        if not section.menus:
            errors.append(f"section {section.title!r} has no menus")
        for path in section.menus:
            error = _path_error(path, "section menu")
            if error:
                errors.append(error)
            if path in seen:
                errors.append(f"{path}: listed more than once in sections")
            seen.add(path)
            menu = manifest.menus.get(path)
            if menu is None:
                errors.append(
                    f"{path}: listed in section {section.title!r} "
                    "but missing from menus",
                )
            elif menu.section != section.title:
                errors.append(
                    f"{path}: menu.section is {menu.section!r}, "
                    f"but it is listed under {section.title!r}",
                )
    return errors, seen, section_titles


def _validate_command_name(path: str, command: str) -> list[str]:
    """Validate the command key itself."""
    if not command.strip():
        return [f"{path}: command name must not be blank"]
    if any(character.isspace() for character in command):
        return [f"{path}: command name must not contain whitespace"]
    return []


def _validate_command_status(
    path: str,
    command: str,
    coverage: CommandCoverage,
) -> list[str]:
    """Validate the status/tool relationship."""
    errors: list[str] = []
    if coverage.status in {"implemented", "partial", "legacy"} and not coverage.tools:
        errors.append(f"{path} {command}: {coverage.status} requires at least one tool")
    if coverage.status == "planned" and coverage.tools:
        errors.append(f"{path} {command}: planned commands must not list tools")
    return errors


def _validate_name_list(
    path: str,
    command: str,
    names: list[str],
    singular: str,
    plural: str,
) -> list[str]:
    """Validate a list of tool/param/gap names."""
    errors: list[str] = []
    if len(names) != len(set(names)):
        errors.append(f"{path} {command}: duplicate {plural}")
    if any(not name.strip() for name in names):
        errors.append(f"{path} {command}: {singular} name must not be blank")
    elif any(character.isspace() for name in names for character in name):
        errors.append(f"{path} {command}: {singular} name must not contain whitespace")
    return errors


def _validate_command_notes(
    path: str,
    command: str,
    coverage: CommandCoverage,
    menu_notes: str | None,
) -> list[str]:
    """Validate the notes requirement for incomplete statuses."""
    if coverage.status in {"partial", "legacy", "not_applicable"} and not _has_text(
        coverage.notes,
        menu_notes,
    ):
        return [f"{path} {command}: {coverage.status} requires notes"]
    return []


def _validate_command(
    path: str,
    command: str,
    coverage: CommandCoverage,
    menu_notes: str | None,
) -> list[str]:
    """Validate one command declaration."""
    errors = _validate_command_name(path, command)
    errors.extend(_validate_command_status(path, command, coverage))
    errors.extend(_validate_name_list(path, command, coverage.tools, "tool", "tools"))
    errors.extend(
        _validate_name_list(path, command, coverage.params, "param", "params"),
    )
    errors.extend(
        _validate_name_list(
            path,
            command,
            coverage.accepted_gaps,
            "accepted_gap",
            "accepted_gaps",
        ),
    )
    overlap = set(coverage.params) & set(coverage.accepted_gaps)
    if overlap:
        errors.append(
            f"{path} {command}: params and accepted_gaps overlap: "
            + ", ".join(sorted(overlap)),
        )
    errors.extend(_validate_command_notes(path, command, coverage, menu_notes))
    return errors


def _validate_menus(
    manifest: CoverageManifest,
    seen: set[str],
    section_titles: set[str],
) -> tuple[list[str], set[str]]:
    """Validate menu paths, section links and their commands."""
    errors: list[str] = []
    menu_tools: set[str] = set()
    for path, menu in manifest.menus.items():
        error = _path_error(path, "menu")
        if error:
            errors.append(error)
        if not menu.title.strip():
            errors.append(f"{path}: menu title must not be blank")
        if path not in seen:
            errors.append(f"{path}: menu is not listed in any section")
        if menu.section not in section_titles:
            errors.append(f"{path}: unknown section {menu.section!r}")
        if not menu.commands:
            errors.append(f"{path}: menu has no commands")
        if len(menu.manual_paths) != len(set(menu.manual_paths)):
            errors.append(f"{path}: duplicate manual_paths")
        for candidate in menu.manual_paths:
            error = _path_error(candidate, "manual_path")
            if error:
                errors.append(f"{path}: {error}")
        for command, coverage in menu.commands.items():
            menu_tools.update(coverage.tools)
            errors.extend(_validate_command(path, command, coverage, menu.notes))
    return errors, menu_tools


def _validate_server_tools(
    manifest: CoverageManifest,
    menu_tools: set[str],
) -> list[str]:
    """Validate server-level tool names and menu-tool collisions."""
    errors: list[str] = []
    for name in manifest.server_tools:
        if not name.strip():
            errors.append("server tool name must not be blank")
        elif any(character.isspace() for character in name):
            errors.append("server tool name must not contain whitespace")
        if name in menu_tools:
            errors.append(f"{name}: listed as a server tool and as a menu command")
    return errors


def _validate_excluded(
    manifest: CoverageManifest,
    seen: set[str],
) -> list[str]:
    """Validate out-of-scope menu declarations."""
    errors: list[str] = []
    seen_excluded: set[str] = set()
    for excluded in manifest.excluded:
        error = _path_error(excluded.menu, "excluded menu")
        if error:
            errors.append(error)
        if not excluded.reason.strip():
            errors.append(f"{excluded.menu}: excluded menu has no reason")
        if excluded.menu in seen_excluded:
            errors.append(f"{excluded.menu}: excluded menu listed more than once")
        seen_excluded.add(excluded.menu)
        if excluded.menu in manifest.menus:
            errors.append(f"{excluded.menu}: excluded menu is also in menus")
        if excluded.menu in seen:
            errors.append(f"{excluded.menu}: excluded menu is listed in a section")
        for path in manifest.menus:
            if path.startswith(excluded.menu + "/"):
                errors.append(
                    f"{excluded.menu}: excluded menu has in-scope child {path}",
                )
    return errors


def validate_manifest(manifest: CoverageManifest) -> list[str]:
    """Return structural errors in the manifest itself."""
    errors: list[str] = []
    if not manifest.sections:
        errors.append("manifest has no sections")
    if not manifest.menus:
        errors.append("manifest has no menus")
    section_errors, seen, section_titles = _validate_sections(manifest)
    errors.extend(section_errors)
    menu_errors, menu_tools = _validate_menus(manifest, seen, section_titles)
    errors.extend(menu_errors)
    errors.extend(_validate_server_tools(manifest, menu_tools))
    errors.extend(_validate_excluded(manifest, seen))
    return errors


def manifest_tool_names(manifest: CoverageManifest) -> set[str]:
    names = set(manifest.server_tools)
    for menu in manifest.menus.values():
        for coverage in menu.commands.values():
            names.update(coverage.tools)
    return names


@contextmanager
def _prepend_sys_path(path: Path) -> Iterator[None]:
    """Temporarily put *path* first on ``sys.path``."""
    old = list(sys.path)
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path[:] = old


def load_tool_names() -> set[str]:
    """Return the live MCP tool names."""
    with _prepend_sys_path(ROOT / "src"):
        from mcp_mikrotik.app import mcp  # imported here so --help does not need it

        return {tool.name for tool in asyncio.run(mcp.list_tools())}


def check_tool_contract(
    manifest: CoverageManifest,
    live: set[str],
    manifest_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    declared = manifest_tool_names(manifest)
    label = str(manifest_path) if manifest_path else "the manifest"

    missing = sorted(live - declared)
    unknown = sorted(declared - live)
    if missing:
        errors.append(f"registered tools missing from {label}: " + ", ".join(missing))
    if unknown:
        errors.append(f"{label} lists unknown tools: " + ", ".join(unknown))
    return errors


def _normalise_menu_path(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    # The manual uses slash-separated paths; accept the CLI's space-separated
    # form too so a heading like "/ip firewall filter" still matches.
    value = re.sub(r"\s+", "/", value)
    value = re.sub(r"/+", "/", value)
    return "/" + value.strip("/")


def _collect_headings(page: str) -> list[tuple[int, str]]:
    """Return sorted (position, menu path) headings for one manual page."""
    headings: list[tuple[int, str]] = []
    for match in _MANUAL_MENU_RE.finditer(page):
        # Root command pages are titled "## import", "## log", etc. Strip
        # the generated "(Cli-reference)" suffix before matching.
        value = _MANUAL_ROOT_SUFFIX_RE.sub("", match.group(1).strip()).strip()
        if "/" in value:
            headings.append((match.start(), _normalise_menu_path(value)))
        elif value in ROOT_MENUS:
            headings.append((match.start(), "/" + value))
    for match in _MANUAL_SUBMENU_RE.finditer(page):
        headings.append((match.start(), _normalise_menu_path(match.group(1))))
    headings.sort()
    return headings


def _collect_row_kinds(page: str) -> dict[int, str]:
    """Map each ArgTableRow offset to its table kind."""
    row_kind: dict[int, str] = {}
    for table_match in _MANUAL_TABLE_RE.finditer(page):
        kind = (table_match.group(1) or table_match.group(2)).strip().casefold()
        base = table_match.start(3)
        for row_match in _MANUAL_ARG_RE.finditer(table_match.group(3)):
            row_kind[base + row_match.start()] = kind
    return row_kind


def _assign_args(
    page: str,
    headings: list[tuple[int, str]],
    row_kind: dict[int, str],
    full_menus: dict[str, set[str]],
    writable_menus: dict[str, set[str]],
) -> None:
    """Assign each ArgTableRow to the nearest preceding heading."""
    for arg_match in _MANUAL_ARG_RE.finditer(page):
        arg = arg_match.group(1) or arg_match.group(2)
        if len(arg) == 1 and arg.isupper():
            continue
        if arg in IGNORED_MANUAL_ARGS:
            continue
        path = None
        for position, candidate in headings:
            if position <= arg_match.start():
                path = candidate
            else:
                break
        if path is None:
            continue
        full_menus[path].add(arg)
        if row_kind.get(arg_match.start(), "") not in {
            "read-only argument",
            "flag",
        }:
            writable_menus[path].add(arg)


def _normalise_newlines(text: str) -> str:
    """Normalise CRLF and CR line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_pages(text: str) -> list[str]:
    """Split the corpus on ``---`` lines that are not inside fenced code."""
    pages: list[str] = []
    current: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if fence is None:
            if _MANUAL_PAGE_SEPARATOR_LINE_RE.match(stripped):
                pages.append("".join(current))
                current = []
                continue
            match = _MANUAL_FENCE_START_RE.match(stripped)
            if match:
                fence = match.group("fence")
        else:
            match = _MANUAL_FENCE_END_RE.match(stripped)
            if (
                match
                and match.group("fence")[0] == fence[0]
                and len(match.group("fence")) >= len(fence)
            ):
                fence = None
        current.append(line)
    pages.append("".join(current))
    return pages


def _parse_manual_text(
    text: str,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return the full and writable menu/argument views in one pass.

    The full view keeps every ``ArgTableRow``; the writable view drops rows
    from ``Read-only Argument`` and ``Flag`` tables. Both views list every
    menu heading found in the corpus, even when a menu has no arguments.
    """
    full_menus: dict[str, set[str]] = {}
    writable_menus: dict[str, set[str]] = {}

    for raw_page in _split_pages(text):
        # Headings inside fenced examples are documentation, not menu pages.
        page = _MANUAL_FENCED_CODE_RE.sub("", raw_page)
        headings = _collect_headings(page)
        if not headings:
            continue
        # Keep menus whose tables contain only read-only fields: they still
        # exist in the manual and must not be reported as missing.
        for _, candidate in headings:
            full_menus.setdefault(candidate, set())
            writable_menus.setdefault(candidate, set())
        row_kind = _collect_row_kinds(page)
        _assign_args(page, headings, row_kind, full_menus, writable_menus)

    return (
        {path: sorted(args) for path, args in full_menus.items()},
        {path: sorted(args) for path, args in writable_menus.items()},
    )


def parse_manual(path: Path, include_read_only: bool = True) -> dict[str, list[str]]:
    """Extract menu paths and ArgTableRow arguments from llms-full.txt.

    The corpus is a concatenation of MDX pages separated by ``---``. A page can
    carry one or more RouterOS menu headings plus a ``**Sub-menu:**`` value.
    Each ``ArgTableRow arg="..."`` is assigned to the nearest preceding menu
    heading on the page, so a page with several menu sections does not
    attribute every argument to every menu.

    With ``include_read_only=False`` rows in a ``Read-only Argument`` or
    ``Flag`` table are skipped. Those rows describe what a ``print`` returns;
    they are valid ``print where`` filters but not writable parameters, so the
    drift report uses this mode for the unmapped-argument check while keeping
    the full list for mapped-parameter lookup.
    """
    text = _normalise_newlines(path.read_text(encoding="utf-8-sig"))
    full, writable = _parse_manual_text(text)
    return full if include_read_only else writable


def _resolve_manual_paths(
    path: str,
    menu: MenuCoverage,
    spec: dict[str, list[str]],
) -> tuple[list[str], list[str], str | None]:
    """Resolve the manual pages for one menu.

    Returns the found paths, advisory warnings, and an optional error.
    """
    candidate_paths = menu.manual_paths or [path]
    found_paths = [candidate for candidate in candidate_paths if candidate in spec]
    if not found_paths:
        if menu.allow_missing_manual or all(
            coverage.status == "not_applicable" for coverage in menu.commands.values()
        ):
            return [], [f"{path}: no standalone manual page (allowed)"], None
        return [], [], f"{path}: menu not found in the manual"
    warnings = [
        f"{path}: manual path {candidate} not found"
        for candidate in candidate_paths
        if candidate not in spec
    ]
    return found_paths, warnings, None


def _missing_params(
    path: str,
    menu: MenuCoverage,
    args: set[str],
) -> set[str]:
    """Return mapped parameters that the manual does not declare."""
    missing: set[str] = set()
    for command, coverage in menu.commands.items():
        if coverage.status in {"legacy", "not_applicable"}:
            continue
        for param in coverage.params:
            if (
                param in MISSING_PARAM_EXEMPTIONS
                or param in UNIVERSAL_PARAMS
                or "." in param
            ):
                continue
            if param not in args:
                missing.add(f"{path} {command}: {param}")
    return missing


def _mapped_params(menu: MenuCoverage) -> set[str]:
    """Return every manual argument the menu claims to cover."""
    mapped: set[str] = set()
    for coverage in menu.commands.values():
        mapped.update(coverage.params)
        mapped.update(coverage.accepted_gaps)
    return mapped


def _unmapped_args(
    menu: MenuCoverage,
    writable_args: set[str],
) -> tuple[str, ...] | None:
    """Return writable manual args not declared by the manifest."""
    if all(
        coverage.status in {"legacy", "not_applicable", "planned"}
        for coverage in menu.commands.values()
    ):
        return None
    gaps = sorted(writable_args - _mapped_params(menu) - UNIVERSAL_PARAMS)
    return tuple(gaps) if gaps else None


def _find_new_menus(
    manifest: CoverageManifest,
    spec: dict[str, list[str]],
    excluded_menus: set[str],
) -> tuple[str, ...]:
    """Return new direct children of implemented or partial menus."""
    active_parents = {
        path
        for path, menu in manifest.menus.items()
        if any(
            coverage.status in {"implemented", "partial"}
            for coverage in menu.commands.values()
        )
    }
    documented_paths = {
        candidate for menu in manifest.menus.values() for candidate in menu.manual_paths
    }
    return tuple(
        sorted(
            path
            for path in spec
            if path.rsplit("/", 1)[0] in active_parents
            and path not in manifest.menus
            and path not in documented_paths
            and path not in excluded_menus
        ),
    )


def _aggregate_drift_warnings(
    missing_params: set[str],
    unmapped_args: dict[str, tuple[str, ...]],
    new_menus: tuple[str, ...],
    manual_changed: bool,
) -> list[str]:
    """Build the aggregate drift warnings."""
    warnings: list[str] = []
    if missing_params:
        warnings.append(
            f"{len(missing_params)} mapped parameter(s) were not found in the manual",
        )
    if unmapped_args:
        warnings.append(
            f"{len(unmapped_args)} in-scope menu(s) have manual arguments "
            "not declared in the manifest",
        )
    if new_menus:
        warnings.append(f"{len(new_menus)} new submenu(s) found under in-scope menus")
    if manual_changed:
        warnings.append("the downloaded corpus does not match the pinned SHA-256")
    return warnings


def _compare_menu(
    path: str,
    menu: MenuCoverage,
    spec: dict[str, list[str]],
    writable_spec: dict[str, list[str]],
    missing_params: set[str],
    unmapped_args: dict[str, tuple[str, ...]],
) -> tuple[list[str], list[str]]:
    """Compare one menu and update the drift accumulators.

    Returns the errors and warnings for this menu.
    """
    found_paths, warnings, error = _resolve_manual_paths(path, menu, spec)
    if error is not None:
        return [error], warnings

    # A menu documented outside the CLI-reference pages has nothing to
    # compare; its parameters cannot be validated against a missing page.
    if not found_paths:
        return [], warnings

    args = set().union(*(spec[candidate] for candidate in found_paths))
    writable_args = set().union(
        *(writable_spec.get(candidate, ()) for candidate in found_paths),
    )
    missing_params.update(_missing_params(path, menu, args))
    gap = _unmapped_args(menu, writable_args)
    if gap is not None:
        unmapped_args[path] = gap
    return [], warnings


def compare_manual(
    manifest: CoverageManifest,
    lock: ManualLock,
    manual_path: Path,
) -> DriftResult:
    """Compare the manifest with a downloaded manual corpus."""
    # Read once: hash the raw bytes and parse the decoded text. Text-mode
    # read_text() normalises newlines, so reproduce that here.
    raw = manual_path.read_bytes()
    manual_sha256 = hashlib.sha256(raw).hexdigest()
    manual_changed = manual_sha256 != lock.sha256
    text = _normalise_newlines(raw.decode("utf-8-sig"))
    spec, writable_spec = _parse_manual_text(text)

    errors: list[str] = []
    warnings: list[str] = []
    missing_params: set[str] = set()
    unmapped_args: dict[str, tuple[str, ...]] = {}
    excluded_menus = {entry.menu for entry in manifest.excluded}

    for path, menu in manifest.menus.items():
        menu_errors, menu_warnings = _compare_menu(
            path,
            menu,
            spec,
            writable_spec,
            missing_params,
            unmapped_args,
        )
        errors.extend(menu_errors)
        warnings.extend(menu_warnings)

    new_menus = _find_new_menus(manifest, spec, excluded_menus)
    warnings.extend(
        _aggregate_drift_warnings(
            missing_params,
            unmapped_args,
            new_menus,
            manual_changed,
        ),
    )

    return DriftResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        new_menus=new_menus,
        unmapped_args=unmapped_args,
        missing_params=tuple(sorted(missing_params)),
        manual_sha256=manual_sha256,
        manual_changed=manual_changed,
    )


def _command_sort_key(name: str) -> tuple[int, str]:
    return (COMMAND_ORDER_INDEX.get(name, len(COMMAND_ORDER)), name)


def _menu_status(menu: MenuCoverage) -> Status:
    statuses = {coverage.status for coverage in menu.commands.values()}
    applicable = statuses - {"not_applicable"}
    if not applicable:
        return "not_applicable"
    if applicable == {"implemented"}:
        return "implemented"
    if applicable == {"planned"}:
        return "planned"
    if applicable == {"legacy"}:
        return "legacy"
    return "partial"


def _checkbox(status: Status) -> str:
    return "[x]" if status in {"implemented", "not_applicable"} else "[ ]"


def _one_line(text: str) -> str:
    """Collapse whitespace so generated Markdown stays one line per item."""
    return " ".join(text.split())


def _table_cell(text: str) -> str:
    """Escape a value for a Markdown table cell."""
    return _one_line(text).replace("\\", "\\\\").replace("|", r"\|")


def _command_suffix(coverage: CommandCoverage) -> str:
    parts: list[str] = []
    if coverage.tools:
        parts.append(", ".join(f"`{tool}`" for tool in coverage.tools))
    match coverage.status:
        case "partial":
            parts.append("partial")
        case "planned":
            parts.append("not implemented")
        case "legacy":
            parts.append("legacy v6 path")
        case "not_applicable":
            parts.append("not applicable on RouterOS 7")
    if coverage.notes:
        parts.append(_one_line(coverage.notes))
    return " — ".join(parts)


@dataclass(frozen=True, slots=True)
class _CoverageCounts:
    total: int
    implemented: int
    partial: int
    planned: int
    legacy: int
    not_applicable: int
    percent: int


def _coverage_counts(manifest: CoverageManifest) -> _CoverageCounts:
    """Count commands by status for the checklist header."""
    statuses = [
        coverage.status
        for menu in manifest.menus.values()
        for coverage in menu.commands.values()
    ]
    total = sum(1 for status in statuses if status != "not_applicable")
    implemented = statuses.count("implemented")
    return _CoverageCounts(
        total=total,
        implemented=implemented,
        partial=statuses.count("partial"),
        planned=statuses.count("planned"),
        legacy=statuses.count("legacy"),
        not_applicable=statuses.count("not_applicable"),
        percent=round(100 * implemented / total) if total else 0,
    )


def _render_header(lock: ManualLock, counts: _CoverageCounts) -> list[str]:
    """Render the checklist title and summary block."""
    return [
        "<!-- Generated by scripts/api_coverage.py; do not edit. -->",
        "# RouterOS API Coverage",
        "",
        f"Manual: **RouterOS {_one_line(lock.version)}**",
        f"Built: {_one_line(lock.built_at)}",
        f"Source ETag: `{_one_line(lock.etag)}`",
        f"SHA-256: `{lock.sha256}`",
        "",
        (
            f"**Progress:** {counts.implemented}/{counts.total} in-scope "
            f"commands implemented ({counts.percent}%) · "
            f"**Partial:** {counts.partial} · **Planned:** {counts.planned} · "
            f"**Legacy:** {counts.legacy} · "
            f"**Not applicable:** {counts.not_applicable}"
        ),
        "",
        (
            "Legend: `[x]` implemented/mapped or not applicable · `[ ]` not "
            "implemented, partial or legacy."
        ),
        "",
        "Legacy v6 commands count as not implemented for RouterOS 7.",
        (
            "A checked command means the tool exists and its declared parameters "
            "map to the manual;"
        ),
        "it does not prove runtime correctness on every RouterOS version.",
        "",
    ]


def _render_menu(path: str, menu: MenuCoverage) -> list[str]:
    """Render one menu and its commands."""
    lines = [
        f"- {_checkbox(_menu_status(menu))} **{_one_line(menu.title)}** (`{path}`)",
    ]
    if menu.notes:
        lines.append(f"  - {_one_line(menu.notes)}")
    for command in sorted(menu.commands, key=_command_sort_key):
        coverage = menu.commands[command]
        suffix = _command_suffix(coverage)
        line = f"  - {_checkbox(coverage.status)} `{command}`"
        if suffix:
            line += f" — {suffix}"
        lines.append(line)
    return lines


def _render_server_tools(manifest: CoverageManifest) -> list[str]:
    """Render the server-level tools section."""
    lines = [
        "## Server-level tools",
        "",
        "These tools do not map to a single RouterOS menu command.",
        "",
    ]
    for name, tool in manifest.server_tools.items():
        note = f" — {_one_line(tool.note)}" if tool.note else ""
        lines.append(f"- [x] `{name}` — {tool.kind}{note}")
    lines.append("")
    return lines


def _render_excluded(manifest: CoverageManifest) -> list[str]:
    """Render the excluded/out-of-scope table."""
    lines = [
        "## Excluded / out of scope",
        "",
        "| Menu | Reason |",
        "|---|---|",
    ]
    for excluded in manifest.excluded:
        lines.append(f"| `{excluded.menu}` | {_table_cell(excluded.reason)} |")
    lines.append("")
    return lines


def generate_markdown(manifest: CoverageManifest, lock: ManualLock) -> str:
    """Generate the checked/unchecked API coverage checklist."""
    counts = _coverage_counts(manifest)
    lines = _render_header(lock, counts)
    for section in manifest.sections:
        lines.append(f"## {_one_line(section.title)}")
        lines.append("")
        for path in section.menus:
            lines.extend(_render_menu(path, manifest.menus[path]))
        lines.append("")
    lines.extend(_render_server_tools(manifest))
    lines.extend(_render_excluded(manifest))
    return "\n".join(lines).rstrip() + "\n"


def _drift_header(lock: ManualLock, result: DriftResult) -> list[str]:
    """Render the drift report title and counts."""
    return [
        "# API coverage drift report",
        "",
        f"Manual: **RouterOS {_one_line(lock.version)}**",
        f"Locked ETag: `{_one_line(lock.etag)}`",
        f"Locked SHA-256: `{lock.sha256}`",
        f"Downloaded SHA-256: `{result.manual_sha256}`",
        f"Corpus changed: {'yes' if result.manual_changed else 'no'}",
        "",
        (
            f"**Errors:** {len(result.errors)} · **Warnings:** "
            f"{len(result.warnings)} · **New submenus:** {len(result.new_menus)} · "
            f"**Menus with unmapped args:** {len(result.unmapped_args)} · "
            f"**Missing mapped params:** {len(result.missing_params)}"
        ),
        "",
    ]


def _drift_errors(result: DriftResult) -> list[str]:
    """Render the errors section."""
    if not result.errors:
        return []
    lines = ["## Errors", ""]
    lines.extend(f"- {_one_line(error)}" for error in result.errors)
    lines.append("")
    return lines


def _drift_warnings(result: DriftResult) -> list[str]:
    """Render the warnings section."""
    if not result.warnings:
        return []
    lines = ["## Warnings", ""]
    lines.extend(f"- {_one_line(warning)}" for warning in result.warnings)
    lines.append("")
    return lines


def _drift_new_menus(result: DriftResult) -> list[str]:
    """Render the new-submenus section."""
    if not result.new_menus:
        return []
    lines = [
        "## New submenus under in-scope menus",
        "",
        (
            "Only direct children of implemented or partial menus are listed; "
            "new top-level areas are a scope decision, not drift."
        ),
        "",
    ]
    lines.extend(f"- `{path}`" for path in result.new_menus[:50])
    if len(result.new_menus) > 50:
        lines.append(f"- … and {len(result.new_menus) - 50} more")
    lines.append("")
    return lines


def _drift_unmapped_args(result: DriftResult) -> list[str]:
    """Render the unmapped-argument section."""
    if not result.unmapped_args:
        return []
    lines = ["## Manual arguments not declared in the manifest", ""]
    for path, args in result.unmapped_args.items():
        shown = ", ".join(f"`{arg}`" for arg in args[:30])
        suffix = f" … and {len(args) - 30} more" if len(args) > 30 else ""
        lines.append(f"- `{path}`: {shown}{suffix}")
    lines.append("")
    return lines


def _drift_missing_params(result: DriftResult) -> list[str]:
    """Render the missing-parameter section."""
    if not result.missing_params:
        return []
    lines = ["## Mapped parameters not found in the manual", ""]
    lines.extend(f"- `{item}`" for item in result.missing_params[:100])
    if len(result.missing_params) > 100:
        lines.append(f"- … and {len(result.missing_params) - 100} more")
    lines.append("")
    return lines


def _drift_no_drift(result: DriftResult) -> list[str]:
    """Render the no-drift notice when every section is empty."""
    if result.has_drift:
        return []
    return ["No drift detected.", ""]


def _drift_instructions() -> list[str]:
    """Render the action checklist."""
    return [
        "## How to act on this report",
        "",
        (
            "1. Review new submenus and new arguments; decide whether they belong "
            "in scope."
        ),
        "2. Update `docs/api-coverage.yml` (status, tools, params, accepted gaps).",
        "3. Update `docs/manual.lock.yml` if the corpus changed.",
        (
            "4. Run `python scripts/api_coverage.py --write` and commit the "
            "generated checklist."
        ),
        "",
    ]


def build_drift_report(lock: ManualLock, result: DriftResult) -> str:
    """Build the Markdown drift report."""
    lines = _drift_header(lock, result)
    lines.extend(_drift_errors(result))
    lines.extend(_drift_warnings(result))
    lines.extend(_drift_new_menus(result))
    lines.extend(_drift_unmapped_args(result))
    lines.extend(_drift_missing_params(result))
    lines.extend(_drift_no_drift(result))
    lines.extend(_drift_instructions())
    return "\n".join(lines).rstrip() + "\n"


class _ManualJson(TypedDict):
    version: str
    url: str
    etag: str
    built_at: str
    locked_sha256: str
    downloaded_sha256: str
    changed: bool


class _JsonReport(TypedDict):
    manual: _ManualJson
    has_drift: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    new_menus: tuple[str, ...]
    unmapped_args: Mapping[str, tuple[str, ...]]
    missing_params: tuple[str, ...]


def build_json_report(
    lock: ManualLock,
    result: DriftResult,
) -> _JsonReport:
    """Build the structured JSON drift report."""
    return {
        "manual": {
            "version": lock.version,
            "url": lock.url,
            "etag": lock.etag,
            "built_at": lock.built_at,
            "locked_sha256": lock.sha256,
            "downloaded_sha256": result.manual_sha256,
            "changed": result.manual_changed,
        },
        "has_drift": result.has_drift,
        "errors": result.errors,
        "warnings": result.warnings,
        "new_menus": result.new_menus,
        "unmapped_args": result.unmapped_args,
        "missing_params": result.missing_params,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _print_manifest_errors(errors: list[str]) -> None:
    print("manifest errors:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manual", type=Path, help="downloaded llms-full.txt")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="write the generated checklist",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail if the checklist is stale",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="write the drift report as Markdown",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="write the drift report as JSON",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on warnings as well as errors",
    )
    return parser


def _load_inputs(
    args: argparse.Namespace,
) -> tuple[ManualLock, CoverageManifest]:
    """Load the pinned lockfile and the coverage manifest."""
    return load_lock(args.lock), load_manifest(args.manifest)


def _check_output(args: argparse.Namespace, markdown: str) -> int:
    """Write, check or print the generated checklist."""
    if args.write:
        try:
            write_text(args.output, markdown)
        except OSError as exc:
            print(
                f"error: cannot write {args.output}: {exc}",
                file=sys.stderr,
            )
            return 2
        print(f"wrote {args.output}")
        return 0
    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(
                f"error: cannot read {args.output}: {exc}",
                file=sys.stderr,
            )
            return 1
        if current != markdown:
            diff = unified_diff(
                current.splitlines(keepends=True),
                markdown.splitlines(keepends=True),
                fromfile=str(args.output),
                tofile="generated",
            )
            sys.stdout.writelines(diff)
            print(
                f"error: {args.output} is stale; run "
                "`python scripts/api_coverage.py --write`",
                file=sys.stderr,
            )
            return 1
        return 0
    sys.stdout.write(markdown)
    return 0


def _write_manual_reports(
    args: argparse.Namespace,
    lock: ManualLock,
    result: DriftResult,
) -> None:
    """Write the Markdown and/or JSON drift reports."""
    if args.report:
        write_text(args.report, build_drift_report(lock, result))
        print(f"wrote {args.report}")
    if args.json:
        write_text(
            args.json,
            json.dumps(build_json_report(lock, result), indent=2) + "\n",
        )
        print(f"wrote {args.json}")


def _run_manual_check(
    args: argparse.Namespace,
    manifest: CoverageManifest,
    lock: ManualLock,
    manual_path: Path,
) -> int:
    """Compare the manifest with the manual and write reports."""
    try:
        result = compare_manual(manifest, lock, manual_path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        _write_manual_reports(args, lock, result)
    except OSError as exc:
        print(
            f"error: cannot write the report: {exc}",
            file=sys.stderr,
        )
        return 2
    print(
        f"manual check: {len(result.errors)} error(s), "
        f"{len(result.warnings)} warning(s), "
        f"{len(result.new_menus)} new submenu(s)",
    )
    if result.errors or (args.strict and result.warnings):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the coverage generator/checker CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.manual is None and (args.report or args.json or args.strict):
        parser.error("--report, --json and --strict require --manual")

    try:
        lock, manifest = _load_inputs(args)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors = validate_manifest(manifest)
    if errors:
        _print_manifest_errors(errors)
        return 1

    try:
        live = load_tool_names()
    except (ImportError, AttributeError, RuntimeError, ValueError, OSError) as exc:
        print(
            f"error: could not load the MCP tool catalogue: {exc}",
            file=sys.stderr,
        )
        return 2

    errors = check_tool_contract(manifest, live, args.manifest)
    if errors:
        _print_manifest_errors(errors)
        return 1

    markdown = generate_markdown(manifest, lock)
    exit_code = _check_output(args, markdown)
    if exit_code == 2:
        return 2
    if args.manual is not None:
        exit_code = max(
            exit_code,
            _run_manual_check(args, manifest, lock, args.manual),
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
