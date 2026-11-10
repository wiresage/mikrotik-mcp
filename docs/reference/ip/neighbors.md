# Neighbor Management

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
