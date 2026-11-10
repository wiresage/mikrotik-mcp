# Contributing to MikroTik MCP

Thank you for your interest in contributing to the MikroTik MCP server! This guide will help you understand the project structure and contribution process.

## Overview

This MCP (Model Context Protocol) server provides tools for managing MikroTik RouterOS devices. Contributors can extend functionality by adding tools to a feature area, or by adding a new feature area.

## Project Structure

```
src/mcp_mikrotik/
├── scope/          # The tools: one package per feature area (see "Feature areas" below)
│   ├── _shared/    #   helpers used by several areas (quoting, selectors)
│   ├── firewall/   #   an area: __init__.py, filter.py, nat.py, raw.py, ...
│   └── ...
├── app.py          # MCPServer instance, ToolAnnotation constants, one import per area
├── config.py       # Configuration (pydantic-settings, CLI args, env vars)
├── connector.py    # SSH connection handling
├── server.py       # Entry point — starts the server
└── mikrotik_ssh_client.py  # Low-level SSH client

tests/
├── integration/    # Integration tests using testcontainers
└── unit/
    ├── scope/      # Tests of the tools: scope/<area>/ for one area, scope/ for tests that span areas
    └── ...         # Everything else: connector, config, ssh, app, ...

docs/reference/     # Reference pages, one folder per feature area (the same areas as scope/)
```

### Feature areas

Everything for one feature lives in one place: a package under `src/mcp_mikrotik/scope/`, its tests under
`tests/unit/scope/<area>/` and its reference pages under `docs/reference/<area>/`.

| Area | What belongs in it | Modules |
|---|---|---|
| `devices` | The managed devices themselves: the inventory and the safe-mode session | `inventory`, `safe_mode` |
| `dhcp` | `/ip dhcp-server` and `/ipv6 dhcp-server` | `dhcp` |
| `dns` | `/ip dns` | `dns` |
| `firewall` | `/ip firewall` and `/ipv6 firewall`, IPv4 and IPv6 side by side | `filter`, `ipv6_filter`, `nat`, `raw`, `ipv6_raw`, `address_list` |
| `interfaces` | `/interface`, any type | `generic`, `vlan`, `bridge`, `wireguard`, `wireless`, `poe` |
| `ip` | `/ip` and `/ipv6` menus that have no area of their own | `address`, `ipv6_address`, `pool`, `neighbors`, `services` |
| `monitoring` | Logs, Netwatch and other ways to observe a device | `logs`, `netwatch` |
| `queue` | `/queue` | `queue` |
| `routing` | Routes and routing tables | `routes` |
| `system` | `/system`: resource information, scheduler and scripts, backups and files | `info`, `scheduler`, `backup` |
| `users` | `/user` | `users` |
| `vpn` | VPN protocols other than WireGuard (an `/interface` type, so it lives in `interfaces`) | `ipsec` |

The rules:

- **Find the area** whose RouterOS menu your feature extends and put the module there. If none fits, add an area (see "Register Your Module" below).
- **Name a module** after the RouterOS menu it manages, without repeating the area: `firewall/raw.py`, not `firewall/firewall_raw.py`. An area with a single module names it after the area (`dns/dns.py`), so a second module can sit next to it later.
- **Helpers**: a helper used by one area is a module with a leading underscore in that area (`firewall/_raw_common.py`); a helper used by several areas goes in `scope/_shared/`.
- **Areas never import each other.** What two areas need goes to `_shared`.
- `tests/unit/scope/test_layout.py` checks these rules and says what to fix when one is broken.

## Development Setup

The project uses [uv](https://docs.astral.sh/uv/) as its single Python toolchain;
[install uv](https://docs.astral.sh/uv/getting-started/installation/) first. After
that, provisioning a working environment is **two commands**:

```bash
git clone https://github.com/wiresage/mikrotik-mcp.git
cd mikrotik-mcp
uv sync --frozen
```

`uv sync --frozen` installs the exact versions pinned in `uv.lock` (including the
`dev` dependency group) without re-resolving, so a clean checkout gets the same
environment CI uses. `uv` creates and manages the `.venv` for you.

### Running the tests

```bash
uv run pytest                        # full suite
uv run pytest -m "not integration"   # unit tests only (no Docker needed)
uv run pytest -m integration         # integration tests (needs Docker)
```

No manual dependency install is needed — `uv run` executes against the locked
environment.

### Changing dependencies (regenerating the lockfile)

When you add, remove, or change a dependency in `pyproject.toml`, regenerate and
commit the lockfile **in the same PR**:

```bash
uv lock    # update uv.lock to match pyproject.toml
uv sync    # apply it to your environment
```

CI runs a **lockfile-drift gate** (`uv lock --check`): a PR that changed
`pyproject.toml` without a matching `uv.lock` fails with a plain-language message
saying the lockfile is out of date. Commit the updated `uv.lock` and the gate passes.

Keep these in mind when you touch dependencies:

- `pyproject.toml` declares the version **ranges** users get (`pip`, `uvx`); `uv.lock`
  pins the exact versions used by CI, the release build's tests and the Docker image.
  Never edit `uv.lock` by hand.
- Test tooling (`pytest`, `testcontainers`) lives in the `dev` dependency group, not in
  `dependencies`, so it is not shipped in the wheel or the Docker image.
- `uv.lock` counts as a shipped file: a merged change to it releases a new version,
  because the Docker image installs from it.
- Do not edit the `version` line in `pyproject.toml`; the release workflow writes it.

## Contributing New Features

To add a new MikroTik feature to the project, follow these steps:

### 1. Create the Tool Module

Find the area for your feature in the table above and create a new Python file in that package, for example
`src/mcp_mikrotik/scope/firewall/mangle.py`. If no area fits, create a new package for it (see step 3).

Your module should:
- Import `mcp`, the appropriate `ToolAnnotations` constant, **and `annotate`** from `...app` (three dots: a module sits two packages below `mcp_mikrotik`)
- Import `execute_mikrotik_command` from `...connector`
- Import shared helpers from `.._shared`, for example `from .._shared.selectors import resolve_item_id`
- Register tools using `@mcp.tool()` decorators — **always use `annotate(BASE, "Title")`** (never a bare constant)
- Follow the existing naming convention: `mikrotik_<action>_<resource>`
- Use type hints for all parameters (including `Literal` for fixed-value params)
- Keep docstrings **concise** — a single sentence is ideal; avoid re-documenting every parameter
- Handle errors gracefully and return meaningful messages

**Example structure** (`src/mcp_mikrotik/scope/my_area/my_feature.py`):
```python
from typing import Optional
from mcp.server.mcpserver import Context
from ...connector import execute_mikrotik_command
from ...app import mcp, READ, WRITE, annotate

@mcp.tool(name="create_my_resource", annotations=annotate(WRITE, "Create My Resource"))
async def mikrotik_create_my_resource(
    ctx: Context,
    name: str,
    required_param: str,
    optional_param: Optional[str] = None,
    comment: Optional[str] = None
) -> str:
    """Creates a new resource on the MikroTik device."""
    await ctx.info(f"Creating resource: name={name}")

    cmd = f"/my/feature add name={name} param={required_param}"

    if optional_param:
        cmd += f" optional-param={optional_param}"
    if comment:
        cmd += f' comment="{comment}"'

    result = await execute_mikrotik_command(cmd, ctx)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create resource: {result}"

    return f"Resource created successfully:\n\n{result}"
```

### 2. Choose the Right Tool Annotation

Import the appropriate annotation constant from `app.py` and pass it via `@mcp.tool(annotations=...)`:

| Constant | Use for |
|---|---|
| `READ` | Read-only queries (print, list, get, export) |
| `WRITE` | Non-idempotent writes (add, create) |
| `WRITE_IDEMPOTENT` | Idempotent writes (set, update, enable, disable) |
| `DESTRUCTIVE` | Idempotent destructive operations (remove, flush) |
| `DANGEROUS` | Non-idempotent destructive operations (reset, bulk create) |

### 3. Register Your Module

Add the module's name to the `from . import ...` line of its area's `__init__.py`:

```python
# src/mcp_mikrotik/scope/firewall/__init__.py
from . import address_list, filter, ipv6_filter, ipv6_raw, mangle, nat, raw  # noqa: F401
```

The import triggers the `@mcp.tool()` decorators, which register your tools with the MCP server. A module its area does
not import registers nothing, so `tests/unit/scope/test_layout.py` fails if you forget this step.

**A new area** is a new package: create `src/mcp_mikrotik/scope/my_area/__init__.py` with a docstring that says what
belongs in the area and the `from . import ...` line, then add the package to the import list in
`src/mcp_mikrotik/app.py` (one name per line, in alphabetical order, so two pull requests that add areas rarely conflict):

```python
from mcp_mikrotik.scope import (  # noqa: F401, E402
    devices,
    ...
    my_area,
    ...
)
```

A new area also gets a folder for its tests (`tests/unit/scope/my_area/` with an `__init__.py`) and one for its reference
pages (`docs/reference/my_area/`).

### 4. Write Tests and Documentation

Create unit tests in `tests/unit/scope/<area>/test_<module>.py` (a test that spans several areas goes in
`tests/unit/scope/`) and integration tests in `tests/integration/`. The smoke test (`tests/unit/scope/test_smoke.py`)
finds your module by itself, so there is no list to update.

Add a reference page, `docs/reference/<area>/<module>.md` (in an area with a single module the page is the area's
`README.md`), and link it from the area's overview page and from `docs/reference/README.md`.

Integration tests should:
- Use testcontainers to spin up a real MikroTik RouterOS container
- Follow the existing test structure and naming conventions
- Test complete workflows (create, read, update, delete operations)
- Include proper cleanup to ensure tests are isolated
- Use the `@pytest.mark.integration` decorator

**Example structure** (based on `test_mikrotik_user_integration.py`):
```python
"""Integration tests for MikroTik my feature using testcontainers."""

import pytest
from mcp_mikrotik.scope.my_area.my_feature import (
    mikrotik_create_my_resource,
    mikrotik_list_my_resources
)

@pytest.mark.integration
class TestMikroTikMyFeatureIntegration:
    def test_01_create_resource(self, mikrotik_container):
        result = mikrotik_create_my_resource(
            name="test_resource",
            required_param="test_value"
        )
        assert "failed" not in result.lower()
        assert "test_resource" in result

    def test_02_list_resources(self, mikrotik_container):
        result = mikrotik_list_my_resources()
        assert "test_resource" in result
```

### 5. Test Your Implementation

Before submitting, ensure your implementation works:

1. **Run integration tests**: `uv run pytest tests/integration/test_my_feature_integration.py -v`
2. **Use MCP Inspector**: Test your tools interactively using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
   ```bash
   # Test your MCP server (stdio transport)
   npx @modelcontextprotocol/inspector uv run mcp-server-mikrotik
   ```
3. **Manual testing**: Test with a real MikroTik device to ensure commands work correctly

## Transport Modes

The server supports three transport modes:

- **stdio** (default) — standard input/output, used by most MCP clients
- **sse** — Server-Sent Events over HTTP (exposes `/health` endpoint)
- **streamable-http** — HTTP with streaming support (exposes `/health` endpoint)

Configure via CLI (`--mcp.transport`) or environment variable (`MIKROTIK_MCP__TRANSPORT`).

## Development Guidelines

### Code Style
- Follow existing code patterns and naming conventions
- Use type hints for all function parameters and return values
- Use `Literal` types for parameters with a fixed set of valid values
- Use `Annotated[..., Field(...)]` for numeric constraints (e.g., VLAN IDs)
- Handle errors gracefully with meaningful error messages
- Log important operations using `ctx.info()` / `ctx.error()` for client-visible logging

### MikroTik Command Guidelines
- Always validate command syntax against MikroTik documentation
- Use proper escaping for string parameters (wrap in quotes when needed)
- Implement both creation and listing/querying functionality
- Consider implementing filtering options where appropriate
- Test commands on actual RouterOS before implementation

### Testing Requirements
- Write tests that cover the main functionality
- Ensure tests are isolated and clean up after themselves
- Use descriptive test names that explain what is being tested
- Include edge cases and error conditions in your tests

### API Coverage

`docs/api-coverage.yml` is the source of truth for the RouterOS menus and commands the MCP intends to cover. `docs/api-coverage.md` is generated from it; never edit it by hand. The generated checklist is the checked/unchecked progress view for developers and users.

When adding or changing a tool:

1. Update `docs/api-coverage.yml`:
   - `status`: `implemented`, `partial`, `planned`, `legacy` or `not_applicable`.
   - `tools`: registered MCP tool names for `implemented`, `partial` and `legacy`. `not_applicable` may also list the tool that explains it; `planned` commands must not list tools.
   - `params`: manual argument names (`vlan-id`, not `vlan_id`; `configuration.ssid` for nested arguments).
   - `accepted_gaps`: intentional omissions of manual arguments. Read-only fields and flags are excluded from the unmapped-argument check automatically, so do not add them just to silence warnings.
   - `notes`: explain `partial`, `legacy`, `not_applicable`, or a non-obvious caveat. Menu-level `notes` explain the scope; do not repeat the tool docstring.
   - `manual_paths`: menus documented as separate command pages. Include the parent page when it has arguments.
   - `allow_missing_manual`: only for commands with no standalone manual page.
   - `server_tools`: tools that do not map to one menu command (`kind` + note).
   - top-level `excluded`: out-of-scope menus, with a reason.
2. Run `uv run python scripts/api_coverage.py --write`.
3. Run `uv run python scripts/api_coverage.py --check`; CI runs the same check.
4. Run `uv run pytest -m "not integration"`.
5. Commit `docs/api-coverage.yml`, the regenerated `docs/api-coverage.md`, and the tool code/tests/docs.

If the tool's parameters change, update its page under `docs/reference/<area>/`.

The **Check API coverage** workflow does not update the lockfile (`docs/manual.lock.yml`) or manifest (`docs/api-coverage.yml`): review the `api-coverage-report` artifact, then update `docs/manual.lock.yml` and the manifest deliberately, run `--write`, and commit. Use `--strict` (or the workflow's `strict` input) when warnings should fail the run. The corpus is not committed; only the lockfile metadata is.

## Commit Message Format and Versioning

This project uses [GitVersion](https://gitversion.net/) for automatic semantic versioning based on commit messages. We follow [Conventional Commits](https://www.conventionalcommits.org/) specification.

All pull requests merge directly to `master`. There are no `develop` or `release` branches. Every merge that contains a non-`docs` commit will publish a new package version automatically.

### Version Format

Published versions use a **4-part** format: `MAJOR.MINOR.PATCH.BUILD`

| Position | Label | Incremented by |
|---|---|---|
| 1 (MAJOR) | `x.0.0.0` | **Never** — frozen at `0` |
| 2 (MINOR) | `0.x.0.0` | `feat:` commits |
| 3 (PATCH) | `0.0.x.0` | `fix:`, `chore:`, and other change commits |
| 4 (BUILD) | `0.0.0.x` | Auto — commit count since last version tag |
| — | no change | `docs:` commits |

### Quick Reference Table

| Commit prefix | Example | Version change |
|---|---|---|
| `feat:` | `feat: add queue management tools` | Minor bump: `0.5.0 → 0.6.0` |
| `fix:` | `fix: handle empty SSH response` | Patch bump: `0.5.0 → 0.5.1` |
| `chore:` | `chore: update dependencies` | Patch bump: `0.5.0 → 0.5.1` |
| `refactor:` | `refactor: simplify connector` | Patch bump: `0.5.0 → 0.5.1` |
| `perf:` | `perf: cache SSH connection` | Patch bump: `0.5.0 → 0.5.1` |
| `ci:` | `ci: add Python 3.13 to matrix` | Patch bump: `0.5.0 → 0.5.1` |
| `test:` | `test: add queue smoke tests` | Patch bump: `0.5.0 → 0.5.1` |
| `docs:` | `docs: update safe mode guide` | **No bump** |
| `doc:` | `doc: fix typo` | **No bump** |
| (untyped) | `update something` | Patch bump (fallback) |
| `+semver: breaking` | footer tag | Major bump (emergency only) |

> **Major version is intentionally frozen at `0`.** Never use `+semver: breaking` or `+semver: major` without explicit approval.

### Commit Message Structure

```
<type>[optional scope]: <description>

[optional body]
```

#### Types

| Type | Description | Version effect |
|---|---|---|
| `feat` | New feature or tool | Minor bump |
| `fix` | Bug fix | Patch bump |
| `chore` | Dependency updates, tooling | Patch bump |
| `refactor` | Code restructuring | Patch bump |
| `perf` | Performance improvement | Patch bump |
| `ci` | CI/CD pipeline changes | Patch bump |
| `test` | Test additions or updates | Patch bump |
| `style` | Code formatting | Patch bump |
| `build` | Build system changes | Patch bump |
| `revert` | Reverting a previous commit | Patch bump |
| `docs` / `doc` | Documentation only | **No bump** |

#### Scopes (optional)

Scopes help indicate which area of the codebase is affected:
- Feature areas: the area (`firewall`, `interfaces`, `ip`, `dhcp`, `dns`, `routing`, `queue`, `users`, `system`, `monitoring`, `devices`, `vpn`) or, for something narrower, its module (`wireless`, `wireguard`, `backup`, `safe-mode`, etc.)
- Infrastructure: `api`, `cli`, `config`, `ssh`, `connector`

### Examples

#### Example 1: New Feature → Minor Bump

```bash
git commit -m "feat(queue): add simple queue and queue tree management

Implements create, list, get, update, remove, enable, and disable
operations for queue types, queue trees, and simple queues."
```
**Result:** `0.5.0.0 → 0.6.0.0`

#### Example 2: Bug Fix → Patch Bump

```bash
git commit -m "fix(safe-mode): handle ANSI escape sequences in <SAFE> prompt detection"
```
**Result:** `0.5.0.0 → 0.5.1.0`

#### Example 3: Chore / Maintenance → Patch Bump

```bash
git commit -m "chore: bump paramiko to 3.5.1 for CVE-2024-xxxx"
```
**Result:** `0.5.0.0 → 0.5.1.0`

#### Example 4: Documentation → No Bump

```bash
git commit -m "docs: add queue and safe-mode reference pages"
```
**Result:** version unchanged — pipeline skips PyPI publish

#### Example 5: Mixed PR (feat + docs commits)

When a PR contains both `feat:` and `docs:` commits, GitVersion picks the **highest** increment across all commits. The result is a Minor bump.

### Version Release Process

1. PR is merged to `master`
2. GitVersion calculates the new version from commit history
3. GitHub Actions builds the package with the calculated version
4. Unit tests run across Python 3.10 / 3.11 / 3.12
5. Package is published to PyPI (`skip-existing: true` — duplicate versions are silently skipped, never fail the pipeline)
6. Git tag and GitHub Release are created automatically

You never need to manually bump version numbers or create tags.

### Best Practices

1. **Be intentional with commit types** — `feat:` and `fix:` trigger **minor** version bumps automatically
2. **Default is minor bump** — Any commit to master without `+semver:` tags will bump the minor version
3. **Use `+semver: none` or `+semver: skip`** — To prevent version bumps for CI/CD, tests, or internal changes
4. **Use `+semver: patch`** — For documentation, formatting, or minor non-functional changes that should only bump patch version
5. **Use `+semver: breaking` or `+semver: major`** — For breaking changes that require major version bump
6. **Write clear commit messages** — They become part of the release history and changelog
7. **One logical change per commit** — Makes version history clearer and easier to track
8. **Test before committing** — Failed builds don't get published

## Branching Strategy

Branches for new pull requests carry the issue number they address:

```
<type>/issue-<number>-<short-description>
```

- `<type>` is one of the conventional commit types above (`feat`, `fix`, `docs`, …)
- `<number>` is the GitHub issue number the branch addresses
- when the change has **no issue**, put `#` in place of the number
- `<short-description>` is a few kebab-case words describing the change

### Examples

```
feat/issue-123-branch-one
fix/issue-#-branch-two
```

This makes every branch self-documenting: the type tells reviewers what kind
of change to expect, and the issue number links the work back to its context
(or `#` states explicitly that no issue exists, rather than leaving reviewers
to search for one).

## Submitting a Pull Request

1. **Fork the repository** and create your feature branch from `master`,
   named according to the [branching strategy](#branching-strategy) above
2. **Implement your changes** following the guidelines above
3. **Run all tests** to ensure nothing is broken
4. **Test with MCP Inspector** to verify tools work correctly
5. **Write descriptive commit messages** following the format above
6. **Submit a pull request** with:
   - Clear description of what you've added
   - Reference to any related issues
   - Screenshots or examples if applicable
   - Confirmation that tests pass
   - Indication of version bump impact (minor, major, patch, or none)
7. **Assign the pull request to yourself.** Use *Assignees* in the sidebar, or open it with
   `gh pr create --assignee @me`. GitHub only lets people with write access set assignees; if you
   cannot, a maintainer assigns the pull request to you, so every contribution is listed under the
   contributor's name.

## Getting Help

- Look at an existing area for reference, for example `src/mcp_mikrotik/scope/firewall/`
- Review the MikroTik RouterOS documentation for command syntax
- Look at existing tests for testing patterns
- Open an issue if you need clarification on implementation details

## Code Review Process

All contributions go through code review to ensure:
- Code follows project conventions and patterns
- MikroTik commands are correct and safe
- Tests provide adequate coverage
- Documentation is clear and complete
- Integration with existing codebase is smooth
- Commit messages follow versioning guidelines

Thank you for contributing to MikroTik MCP! Your additions help make RouterOS management more accessible through the Model Context Protocol.