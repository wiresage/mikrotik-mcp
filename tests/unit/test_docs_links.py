"""Relative links in the documentation must resolve, so moving or renaming a page cannot leave dead links behind.

Only links to files and folders are checked (not `#anchors`), and links inside fenced code blocks are examples, not links.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"```.*?```", re.S)
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _pages():
    return sorted(REPO.glob("*.md")) + sorted((REPO / "docs").rglob("*.md"))


def test_the_documentation_is_found():
    """The parametrized test below runs once per page: an empty scan would pass without checking anything."""
    assert len(_pages()) >= 30


@pytest.mark.parametrize("page", _pages(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_relative_links_resolve(page):
    text = FENCE.sub("", page.read_text(encoding="utf-8"))
    dead = []
    for target in LINK.findall(text):
        if SCHEME.match(target) or target.startswith("#"):
            continue
        path = target.split("#")[0]
        if path and not (page.parent / path).resolve().exists():
            dead.append(target)
    assert not dead, f"{page.relative_to(REPO).as_posix()}: links that do not resolve: {dead}"
