# IPsec

Read-only views over `/ip ipsec`: whether tunnels are up, and whether they
carry traffic. Peer configuration and secrets are not exposed.

## `get_ipsec_installed_sa`

Lists the installed IPsec security associations (child/phase 2 SAs). Runs
`/ip ipsec installed-sa print detail`.

- Parameters:
  - `src_address_filter` (optional): substring match on the SA endpoints
    (the tunnel endpoints, not the encapsulated subnets)
  - `dst_address_filter` (optional): substring match

- Example:
  ```
  get_ipsec_installed_sa()
  get_ipsec_installed_sa(src_address_filter="203.0.113.")
  ```

The Flags legend is the point of this view: `S` means SEEN-TRAFFIC, the SA
has carried packets, and it is the only field that separates an SA carrying
traffic from one that is merely installed.

Two things this does NOT tell you:

- **A missing `S` can mean idle, not broken.** Put traffic over the selector
  before concluding anything.
- **Per-SA counters do not map onto policies** once a peer has several child
  SAs; watch which counters move under traffic you control instead.

## `get_ipsec_active_peers`

Lists the IPsec peers with a live IKE session, with `state`, `uptime`,
`last-seen` and the byte counters. Runs `/ip ipsec active-peers print detail`.

- Parameters:
  - `remote_address_filter` (optional): exact match
  - `state_filter` (optional): exact match

- Example:
  ```
  get_ipsec_active_peers()
  ```

A peer can sit here `established` while its child SAs carry nothing — use
`get_ipsec_installed_sa` to tell the difference.

## `list_ipsec_peers`

Lists the configured IPsec peers. Runs `/ip ipsec peer print detail`.

- Parameters:
  - `name_filter` (optional): substring match
  - `address_filter` (optional): substring match

- Example:
  ```
  list_ipsec_peers(name_filter="office")
  ```

Secrets live on `/ip ipsec identity` and are not exposed by any tool in this
server.

## `list_ipsec_policies`

Lists the IPsec policies, with their phase 2 state. Runs
`/ip ipsec policy print detail`.

- Parameters:
  - `peer_filter` (optional): substring match on the peer name
  - `src_address_filter` (optional): substring match on the policy selectors
  - `dst_address_filter` (optional): substring match

- Example:
  ```
  list_ipsec_policies(peer_filter="office")
  ```

A policy whose selectors do not match the far end's is the usual cause of a
tunnel that comes up and passes nothing.

## `list_ipsec_profiles`

Lists the IPsec profiles (phase 1 proposal: DH group, hash, lifetime, DPD).
Runs `/ip ipsec profile print detail`.

- Parameters:
  - `name_filter` (optional): substring match

- Example:
  ```
  list_ipsec_profiles()
  ```

The phase 1 `lifetime` must be LONGER than the phase 2 lifetime on
`/ip ipsec proposal`, so the child SA rekeys inside a live parent SA; equal
lifetimes tear the tunnel down on every rekey.

## `list_ipsec_proposals`

Lists the IPsec proposals (phase 2: encryption, auth, PFS, lifetime). Runs
`/ip ipsec proposal print detail`.

- Parameters:
  - `name_filter` (optional): substring match

- Example:
  ```
  list_ipsec_proposals()
  ```

Compare `lifetime` against the phase 1 lifetime on `/ip ipsec profile`, and
against whatever the far end proposes.
