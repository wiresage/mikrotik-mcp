"""Relative links in the documentation must resolve, so moving or renaming a page cannot leave dead links behind.

Only links to files and folders are checked (not `#anchors`), and links inside fenced code blocks are examples, not links.
"""

from pathlib import Path

import pytest

from tests.unit.md_links import relative_targets

REPO = Path(__file__).resolve().parents[2]


def _pages():
    return sorted(REPO.glob("*.md")) + sorted((REPO / "docs").rglob("*.md"))


def test_the_documentation_is_found():
    """The parametrized test below runs once per page: an empty scan would pass without checking anything."""
    assert len(_pages()) >= 30


@pytest.mark.parametrize("page", _pages(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_relative_links_resolve(page):
    dead = [path for path in relative_targets(page.read_text(encoding="utf-8")) if not (page.parent / path).resolve().exists()]
    assert not dead, f"{page.relative_to(REPO).as_posix()}: links that do not resolve: {dead}"


def test_the_link_scan_ignores_what_is_not_a_link():
    text = "[a](x.md) [b](y.md#part) [c](#top) [d](https://example.com/z.md) ![i](img.png)\n```\n[e](z.md)\n```\n[f](dir/)"
    assert relative_targets(text) == ["x.md", "y.md", "dir/"]
