# API Reference

Complete reference documentation for all MikroTik MCP tools, grouped by feature area.

The areas are the same ones as the packages under `src/mcp_mikrotik/scope/`, so the code, its unit tests
(`tests/unit/scope/<area>/`) and its reference pages (`docs/reference/<area>/`) are easy to find from one another.
An area with several modules has an overview page (its `README.md`) that lists the modules and their pages; in an
area with a single module the `README.md` is the page itself. See
[Project Structure](../../CONTRIBUTING.md#project-structure) for how the areas are laid out and where a new module goes.

## Available Tool Categories

### [Devices](devices/README.md)

- **[Inventory](devices/inventory.md)** - Managing multiple MikroTik devices
- **[Safe Mode](devices/safe-mode.md)** - Safe Mode Session Management

### [DHCP](dhcp/README.md)

- **[DHCP](dhcp/README.md)** - DHCP Server Management

### [DNS](dns/README.md)

- **[DNS](dns/README.md)** - DNS Management

### [Firewall](firewall/README.md)

- **[Filter rules](firewall/filter.md)** - Firewall Filter Rules Management
- **[IPv6 filter rules](firewall/ipv6-filter.md)** - IPv6 Firewall Filter Rules Management
- **[NAT](firewall/nat.md)** - NAT Rules Management
- **[Raw rules](firewall/raw.md)** - IPv4 and IPv6 Firewall Raw Rules (pre-conntrack)
- **[Address Lists](firewall/address-list.md)** - IPv4 and IPv6 Firewall Address Lists

### [Interfaces](interfaces/README.md)

- **[Interfaces](interfaces/generic.md)** - All Interface Management (ethernet, bridge, PPPoE, SFP, LTE …)
- **[VLAN](interfaces/vlan.md)** - VLAN Interface Management
- **[Bridge](interfaces/bridge.md)** - Bridge VLAN Table and Bridge Port PVID Management
- **[WireGuard](interfaces/wireguard.md)** - WireGuard VPN Management
- **[PoE](interfaces/poe.md)** - Power over Ethernet monitoring

### [IP](ip/README.md)

- **[IP Address](ip/address.md)** - IPv4 Address Management
- **[IPv6 Address](ip/ipv6-address.md)** - IPv6 Address Management
- **[IP Pool](ip/pool.md)** - IP Pool Management
- **[Neighbors](ip/neighbors.md)** - ARP and IPv6 Neighbor Discovery

### [Monitoring](monitoring/README.md)

- **[Logs](monitoring/logs.md)** - Log Management

### [Queue](queue/README.md)

- **[Queue](queue/README.md)** - Queue Types, Trees, and Simple Queues

### [Routing](routing/README.md)

- **[Routing](routing/README.md)** - Route Management

### [System](system/README.md)

- **[Backup](system/backup.md)** - Backup and Export Management

### [Users](users/README.md)

- **[Users](users/README.md)** - User Management

### [VPN](vpn/README.md)

No reference pages yet.

## Modules without a reference page yet

These modules register tools but have no page here yet; their tools are listed in the
[API coverage checklist](../api-coverage.md): `interfaces/wireless`, `ip/services`, `monitoring/netwatch`,
`system/info`, `system/scheduler` and `vpn/ipsec`.
