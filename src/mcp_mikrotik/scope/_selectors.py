import re


_ID_RE = re.compile(r"\*[0-9A-Fa-f]+")

# `print detail` numbers every item it prints (" 0  R  name=..." or " 0    ;;; comment"). The Flags legend that
# RouterOS prints even when nothing matches (it can run over several lines) never starts with a number.
_ITEM_ROW_RE = re.compile(r"^\s*\d+\s", re.MULTILINE)


def has_item_rows(output):
    """True when ``print detail`` output contains at least one item, not just the Flags legend."""
    return bool(output) and _ITEM_ROW_RE.search(output) is not None


async def resolve_item_id(menu, item_id, ctx, device, execute):
    """Accept internal IDs or resolve a print position without RouterOS number maps."""
    item_id = item_id.strip()
    if _ID_RE.fullmatch(item_id):
        return item_id
    if not item_id.isascii() or not item_id.isdecimal():
        return None
    result = await execute(f":put [:pick [{menu} find] {int(item_id)}]", ctx, device=device)
    resolved = result.strip()
    return resolved if _ID_RE.fullmatch(resolved) else None


async def item_count(menu, item_id, ctx, device, execute):
    return (await execute(f"{menu} print count-only where .id={item_id}", ctx, device=device)).strip()


async def item_at_position(menu, position, ctx, device, execute):
    return (await execute(f":put [:pick [{menu} find] {position}]", ctx, device=device)).strip()
