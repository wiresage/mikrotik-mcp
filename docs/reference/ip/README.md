# IP

The `/ip` and `/ipv6` menus that have no area of their own: addresses, pools, ARP and neighbors, and the IP services.
Source: [`src/mcp_mikrotik/scope/ip/`](../../../src/mcp_mikrotik/scope/ip/).

| Module | What it covers | Reference |
|---|---|---|
| `address` | IPv4 addresses (`/ip address`) | [IP Address](address.md) |
| `ipv6_address` | IPv6 addresses (`/ipv6 address`) | [IPv6 Address](ipv6-address.md) |
| `pool` | IP pools (`/ip pool`) | [IP Pool](pool.md) |
| `neighbors` | The ARP table and IPv6 neighbors | [Neighbors](neighbors.md) |
| `services` | The router's IP services (`/ip service`) | _no page yet_ |

DHCP and DNS have their own areas: [DHCP](../dhcp/README.md) and [DNS](../dns/README.md).
The tools of a module without a page are listed in the [API coverage checklist](../../api-coverage.md).
