# Neighbor Management

Tools for inspecting IPv4 ARP entries, IPv6 Neighbor Discovery, and LLDP/CDP/MNDP neighbor discovery protocols and settings.

## `mikrotik_list_arp_entries`
Lists raw detailed IPv4 ARP entries.
- Parameters:
  - `address_filter` (optional): Filter IP address
  - `mac_filter` (optional): Filter MAC address
  - `interface_filter` (optional): Filter interface
  - `status_filter` (optional): Filter neighbor status
- Notes:
  - Address and MAC filters use substring matching; interface and status use exact matching.
- Example:
  ```
  mikrotik_list_arp_entries(interface_filter="bridge", status_filter="reachable")
  ```

## `mikrotik_list_ipv6_neighbors`
Lists raw detailed IPv6 Neighbor Discovery entries.
- Parameters:
  - `address_filter` (optional): Filter IPv6 address
  - `mac_filter` (optional): Filter MAC address
  - `interface_filter` (optional): Filter interface
  - `status_filter` (optional): Filter neighbor status
- Notes:
  - Address and MAC filters use substring matching; interface and status use exact matching.
- Example:
  ```
  mikrotik_list_ipv6_neighbors(address_filter="fe80", interface_filter="bridge")
  ```

## `mikrotik_list_discovered_neighbors`
Lists neighbor devices discovered via MNDP, CDP, and LLDP protocols.
- Parameters:
  - `interface_filter` (optional): Filter by interface name (e.g. `bridge-LAN`)
  - `identity_filter` (optional): Filter by system identity substring (e.g. `Tavan`)
  - `mac_filter` (optional): Filter by MAC address substring
  - `protocol_filter` (optional): Filter by discovery protocol (`cdp`, `lldp`, `mndp`)
- Example:
  ```
  mikrotik_list_discovered_neighbors(identity_filter="Tavan", protocol_filter="mndp")
  ```

## `mikrotik_get_discovered_neighbor`
Retrieves full details for a discovered neighbor identified by MAC address, identity, or row ID.
- Parameters:
  - `identifier` (required): MAC address, identity, or internal item ID / list index
- Example:
  ```
  mikrotik_get_discovered_neighbor(identifier="CC:2D:E0:2B:F2:96")
  ```

## `mikrotik_get_neighbor_discovery_settings`
Retrieves neighbor discovery protocol configuration including interface lists, intervals, and active protocols.
- Parameters:
  - `device` (optional): Device selector
- Example:
  ```
  mikrotik_get_neighbor_discovery_settings()
  ```

## `mikrotik_update_neighbor_discovery_settings`
Configures neighbor discovery settings including allowed interface list, active discovery protocols, and broadcast mode.
- Parameters:
  - `discover_interface_list` (optional): Interface list permitted to send/receive discovery packets (e.g. `LAN`, `none`)
  - `protocol` (optional): Comma-separated list of protocols (e.g. `cdp,lldp,mndp`)
  - `mode` (optional): Broadcast mode (`tx-and-rx`, `rx-only`, `tx-only`, `none`)
  - `discover_interval` (optional): Interval between discovery packets (e.g. `30s`, `1m`)
  - `lldp_med` (optional): Enable or disable LLDP-MED support
- Example:
  ```
  mikrotik_update_neighbor_discovery_settings(discover_interface_list="LAN", mode="tx-and-rx", discover_interval="30s")
  ```
