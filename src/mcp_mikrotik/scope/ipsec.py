"""Read-only views over the IPsec subsystem.

Deliberately omits `/ip ipsec identity`: its `print detail` output carries
`secret=` in clear text, and no read tool should be able to surface a
pre-shared key. Peers, policies, profiles and proposals expose the same
topology without the credential.
"""

from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, annotate
from ..connector import execute_mikrotik_command


async def _print_detail(
    ctx: Context,
    command: str,
    heading: str,
    empty_message: str,
    data_marker: str,
    filters: list,
    device: Optional[str],
) -> str:
    """Run a `print detail` and return it verbatim under *heading*.

    The output is never reformatted. The Flags legend that RouterOS prints
    above the rows is part of the answer here — `installed-sa` reports
    SEEN-TRAFFIC only as the `S` flag, so dropping the legend would discard
    the one field that distinguishes a tunnel carrying traffic from one that
    is merely established.
    """
    if filters:
        command += " where " + " ".join(filters)

    result = await execute_mikrotik_command(command, ctx, device=device)
    # `print detail` prints the Flags legend (non-empty) even when no row
    # matches, so emptiness is decided by real entry data, not by length.
    if not result or data_marker not in result:
        return empty_message
    return f"{heading}:\n\n{result}"


@mcp.tool(name="get_ipsec_installed_sa", annotations=annotate(READ, "IPsec Installed SAs"))
async def mikrotik_get_ipsec_installed_sa(
    ctx: Context,
    src_address_filter: Optional[str] = None,
    dst_address_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the installed IPsec security associations (child/phase 2 SAs).

    The Flags legend is the point of this view. On RouterOS 7 it reads:

        S - SEEN-TRAFFIC  the SA has carried packets
        H - HW-AEAD       the cipher is running in hardware
        E - ESP

    `S` is the only field that separates an SA carrying traffic from one that
    is merely installed. A remote end reporting the connection as up, or its
    own byte counters growing, does not contradict a missing `S`: those count
    what the far side sent, not what arrived.

    Two things this does NOT tell you, both easy to get wrong:

    - **A missing `S` can mean idle, not broken.** An SA nothing has used
      looks exactly like one that is failing, and RouterOS withholds
      `addtime` and `expires-in` until traffic appears, which makes it look
      half installed. Put traffic over the selector before concluding
      anything.

    - **Per-SA counters do not map onto policies once a peer has several
      child SAs.** Traffic picks among them, so one SA can carry the outbound
      side of two policies while another sits frozen at the counter it had
      minutes after install. Pairing SAs by hand — by install time, by
      address, by lifetime — invents a structure that is not there. Watch
      which counters move under traffic you control instead.

    Notes:
        Address filters are exact matches on the SA endpoints, which are the
        tunnel endpoints (public addresses), not the encapsulated subnets.
    """
    await ctx.info("Listing installed IPsec security associations")
    filters = []
    if src_address_filter:
        filters.append(f'src-address="{src_address_filter}"')
    if dst_address_filter:
        filters.append(f'dst-address="{dst_address_filter}"')
    return await _print_detail(
        ctx, "/ip ipsec installed-sa print detail", "IPSEC INSTALLED SAs",
        "No installed IPsec security associations found matching the criteria.",
        "spi=", filters, device,
    )


@mcp.tool(name="get_ipsec_active_peers", annotations=annotate(READ, "IPsec Active Peers"))
async def mikrotik_get_ipsec_active_peers(
    ctx: Context,
    remote_address_filter: Optional[str] = None,
    state_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the IPsec peers with a live IKE session, with uptime and counters.

    Shows the parent (phase 1) side: `state`, `uptime`, `last-seen` and the
    byte counters. A peer can sit here `established` while its child SAs
    carry nothing — use `get_ipsec_installed_sa` to tell the difference.

    Notes:
        Both filters are exact matches.
    """
    await ctx.info("Listing active IPsec peers")
    filters = []
    if remote_address_filter:
        filters.append(f'remote-address="{remote_address_filter}"')
    if state_filter:
        filters.append(f'state="{state_filter}"')
    return await _print_detail(
        ctx, "/ip ipsec active-peers print detail", "IPSEC ACTIVE PEERS",
        "No active IPsec peers found matching the criteria.",
        "remote-address=", filters, device,
    )


@mcp.tool(name="list_ipsec_peers", annotations=annotate(READ, "List IPsec Peers"))
async def mikrotik_list_ipsec_peers(
    ctx: Context,
    name_filter: Optional[str] = None,
    address_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the configured IPsec peers.

    Notes:
        Filters are substring matches. Secrets live on `/ip ipsec identity`
        and are not exposed by any tool in this server.
    """
    await ctx.info("Listing IPsec peers")
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if address_filter:
        filters.append(f'address~"{address_filter}"')
    return await _print_detail(
        ctx, "/ip ipsec peer print detail", "IPSEC PEERS",
        "No IPsec peers found matching the criteria.",
        "name=", filters, device,
    )


@mcp.tool(name="list_ipsec_policies", annotations=annotate(READ, "List IPsec Policies"))
async def mikrotik_list_ipsec_policies(
    ctx: Context,
    peer_filter: Optional[str] = None,
    src_address_filter: Optional[str] = None,
    dst_address_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the IPsec policies, with their phase 2 state.

    The Flags legend distinguishes configured policies from the ones a peer
    generated at runtime (`D` dynamic), and `ph2-state` says whether the
    child SA is established. A policy whose selectors do not match the far
    end's is the usual cause of a tunnel that comes up and passes nothing.

    Notes:
        `peer_filter` is a substring match on the peer name; the address
        filters are substring matches on the policy selectors, which are the
        encapsulated subnets, not the tunnel endpoints.
    """
    await ctx.info("Listing IPsec policies")
    filters = []
    if peer_filter:
        filters.append(f'peer~"{peer_filter}"')
    if src_address_filter:
        filters.append(f'src-address~"{src_address_filter}"')
    if dst_address_filter:
        filters.append(f'dst-address~"{dst_address_filter}"')
    return await _print_detail(
        ctx, "/ip ipsec policy print detail", "IPSEC POLICIES",
        "No IPsec policies found matching the criteria.",
        "dst-address=", filters, device,
    )


@mcp.tool(name="list_ipsec_profiles", annotations=annotate(READ, "List IPsec Profiles"))
async def mikrotik_list_ipsec_profiles(
    ctx: Context,
    name_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the IPsec profiles (phase 1 proposal: DH group, hash, lifetime, DPD).

    Notes:
        `lifetime` here is phase 1. It must be LONGER than the phase 2
        lifetime on `/ip ipsec proposal`, so the child SA rekeys inside a
        live parent SA; equal lifetimes tear the tunnel down on every
        rekey. `dpd-interval` multiplied by `dpd-maximum-failures` is how
        many seconds of silence the peer tolerates.
    """
    await ctx.info("Listing IPsec profiles")
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    return await _print_detail(
        ctx, "/ip ipsec profile print detail", "IPSEC PROFILES",
        "No IPsec profiles found matching the criteria.",
        "name=", filters, device,
    )


@mcp.tool(name="list_ipsec_proposals", annotations=annotate(READ, "List IPsec Proposals"))
async def mikrotik_list_ipsec_proposals(
    ctx: Context,
    name_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the IPsec proposals (phase 2: encryption, auth, PFS, lifetime).

    Notes:
        Compare `lifetime` against the phase 1 lifetime on
        `/ip ipsec profile`, and against whatever the far end proposes — a
        cloud provider's own SA lifetime counts as a third value in that
        comparison.
    """
    await ctx.info("Listing IPsec proposals")
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    return await _print_detail(
        ctx, "/ip ipsec proposal print detail", "IPSEC PROPOSALS",
        "No IPsec proposals found matching the criteria.",
        "name=", filters, device,
    )
