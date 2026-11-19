"""The relative links of a markdown page, for the tests that check the documentation (test_docs_links, scope/test_layout)."""

import re

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"```.*?```", re.S)
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def relative_targets(text: str) -> list[str]:
    """The path of every link to a file or a folder, in the order written.

    Not included: URLs, `#anchors` (a link such as `page.md#part` gives `page.md`) and anything inside a fenced code block,
    where a link is an example, not a link.
    """
    targets = []
    for target in LINK.findall(FENCE.sub("", text)):
        if SCHEME.match(target) or target.startswith("#"):
            continue
        path = target.split("#")[0]
        if path:
            targets.append(path)
    return targets
