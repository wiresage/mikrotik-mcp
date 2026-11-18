# IPsec Monitoring

Read-only views over the IPsec subsystem (`/ip ipsec`): which peers, policies,
profiles and proposals are configured, and the live state of the tunnels. The
output is returned as RouterOS prints it, including the `Flags` legend, and
every tool answers "No ... found matching the criteria." when nothing matches.

> `/ip ipsec identity` is deliberately not exposed. Its `print detail` output
> carries `secret=` in clear text, and no read tool should be able to surface a
> pre-shared key. Peers, policies, profiles and proposals show the same
> topology without the credential.

## `list_ipsec_peers`

Lists the configured IPsec peers. Runs `/ip ipsec peer print detail`.

- Parameters:
  - `name_filter` (optional): Filter by peer name (substring match)
  - `address_filter` (optional): Filter by peer address (substring match)
- Example:
  ```
  list_ipsec_peers(name_filter="branch")
  ```

## `list_ipsec_policies`

Lists the IPsec policies with their phase 2 state. Runs
`/ip ipsec policy print detail`.

- Parameters:
  - `peer_filter` (optional): Filter by peer name (substring match)
  - `src_address_filter` (optional): Filter by source selector (substring match)
  - `dst_address_filter` (optional): Filter by destination selector (substring match)
- Notes:
  - The address filters match the policy selectors, which are the encapsulated
    subnets, not the tunnel endpoints.
  - The `Flags` legend separates configured policies from the ones a peer
    generated at runtime (`D`, dynamic), and `ph2-state` says whether the child
    SA is established. A policy whose selectors do not match the far end's is
    the usual cause of a tunnel that comes up and passes nothing.
- Example:
  ```
  list_ipsec_policies(dst_address_filter="10.20.0.0/24")
  ```

## `list_ipsec_profiles`

Lists the IPsec profiles (phase 1: DH group, hash, encryption, lifetime, DPD).
Runs `/ip ipsec profile print detail`.

- Parameters:
  - `name_filter` (optional): Filter by profile name (substring match)
- Notes:
  - `lifetime` here is phase 1. It must be longer than the phase 2 lifetime on
    the proposal, so the child SA rekeys inside a live parent SA; equal
    lifetimes tear the tunnel down on every rekey.
  - `dpd-interval` multiplied by `dpd-maximum-failures` is how many seconds of
    silence the peer tolerates.
- Example:
  ```
  list_ipsec_profiles()
  ```

## `list_ipsec_proposals`

Lists the IPsec proposals (phase 2: encryption, authentication, PFS, lifetime).
Runs `/ip ipsec proposal print detail`.

- Parameters:
  - `name_filter` (optional): Filter by proposal name (substring match)
- Notes:
  - Compare `lifetime` against the phase 1 lifetime on the profile, and against
    whatever the far end proposes. A cloud provider's own SA lifetime counts as
    a third value in that comparison.
- Example:
  ```
  list_ipsec_proposals(name_filter="default")
  ```

## `get_ipsec_active_peers`

Lists the peers with a live IKE session, with uptime and counters. Runs
`/ip ipsec active-peers print detail`.

- Parameters:
  - `remote_address_filter` (optional): Filter by remote address (exact match)
  - `state_filter` (optional): Filter by session state, for example
    `established` (exact match)
- Notes:
  - This is the parent (phase 1) side: `state`, `uptime`, `last-seen` and the
    byte counters. A peer can sit here `established` while its child SAs carry
    nothing; use `get_ipsec_installed_sa` to tell the difference.
- Example:
  ```
  get_ipsec_active_peers(state_filter="established")
  ```

## `get_ipsec_installed_sa`

Lists the installed security associations (child, phase 2 SAs). Runs
`/ip ipsec installed-sa print detail`.

- Parameters:
  - `src_address_filter` (optional): Filter by SA source endpoint (substring match)
  - `dst_address_filter` (optional): Filter by SA destination endpoint (substring match)
- Notes:
  - The `Flags` legend is the point of this view. On RouterOS 7 it reads
    `S` (SEEN-TRAFFIC: the SA has carried packets), `H` (HW-AEAD: the cipher
    runs in hardware) and `E` (ESP). `S` is the only field that separates an SA
    carrying traffic from one that is merely installed.
  - A missing `S` can mean idle, not broken. An SA nothing has used looks
    exactly like one that is failing, and RouterOS withholds `addtime` and
    `expires-in` until traffic appears. Put traffic over the selector before
    concluding anything.
  - Once a peer has several child SAs, per-SA counters do not map onto
    policies: traffic picks among them. Watch which counters move under traffic
    you control instead of pairing SAs by hand.
  - The address filters match the SA endpoints, which are the tunnel endpoints
    (public addresses), not the encapsulated subnets. Behind NAT-T the
    endpoints carry the port (`198.51.100.2:4500`), which is why this is a
    substring match.
- Example:
  ```
  get_ipsec_installed_sa(dst_address_filter="198.51.100.2")
  ```
