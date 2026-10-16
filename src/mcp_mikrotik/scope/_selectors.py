import re


_ID_RE = re.compile(r"\*[0-9A-Fa-f]+")


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


async def move_to_position(menu, item_id, destination, ctx, device, execute):
    """Moves ``item_id`` so that it ends up at the 0-based ``destination`` position of ``menu``.

    Returns the router's reply to the move, which is empty on success, or a message when the move is
    impossible. ``move X destination=N`` cannot be used as it is: RouterOS reads a bare number as the
    N-th item in creation order, not as a position in the current list, so "move to 0" fails with
    "can not move object before itself" (or lands somewhere else) as soon as the list has been
    reordered or an item removed. A destination given as an internal id is placed before that item,
    and a move without a destination goes to the end, so the position is turned into one of those.
    """
    listing = (await execute(f":put [{menu} find]", ctx, device=device)).strip()
    ids = [i for i in listing.replace(",", ";").split(";") if i]
    if item_id not in ids:
        return "no such item"
    if destination < 0 or destination >= len(ids):
        return f"destination {destination} is out of range, the list has positions 0 to {len(ids) - 1}"

    current = ids.index(item_id)
    if destination == current:
        return ""  # already there
    if destination < current:
        before = ids[destination]  # moving up: go in front of the item that holds the position now
    elif destination + 1 < len(ids):
        before = ids[destination + 1]  # moving down: that item shifts up by one once ours leaves
    else:
        return await execute(f"{menu} move {item_id}", ctx, device=device)  # the last position
    return await execute(f"{menu} move {item_id} destination={before}", ctx, device=device)
