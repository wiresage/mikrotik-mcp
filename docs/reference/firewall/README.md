# Firewall

`/ip firewall` and `/ipv6 firewall`: filter, NAT, raw and address lists, IPv4 and IPv6 side by side.
Source: [`src/mcp_mikrotik/scope/firewall/`](../../../src/mcp_mikrotik/scope/firewall/).

| Module | What it covers | Reference |
|---|---|---|
| `filter` | IPv4 filter rules (`/ip firewall filter`) and the basic firewall setup | [Filter rules](filter.md) |
| `ipv6_filter` | IPv6 filter rules (`/ipv6 firewall filter`) | [IPv6 filter rules](ipv6-filter.md) |
| `nat` | NAT rules (`/ip firewall nat`) | [NAT](nat.md) |
| `raw`, `ipv6_raw` | Raw rules, applied before connection tracking (`/ip firewall raw`, `/ipv6 firewall raw`) | [Raw rules](raw.md) |
| `address_list` | IPv4 and IPv6 address lists, one set of tools for both families | [Address lists](address-list.md) |
