# Neighbor Management

## `list_arp_entries`
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
  list_arp_entries(interface_filter="bridge", status_filter="reachable")
  ```

## `list_ipv6_neighbors`
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
  list_ipv6_neighbors(address_filter="fe80", interface_filter="bridge")
  ```

## `mikrotik_list_mikrotik_neighbors`
Lists the MikroTik neighbors the target router has discovered through MNDP —
identity, address, platform, version, board name and the interface they were
heard on. This is the discovery step for enrolling a fleet at runtime.
- Parameters:
  - `identity_filter` (optional): Filter neighbor identity
  - `address_filter` (optional): Filter announced address
  - `interface_filter` (optional): Filter interface
- Notes:
  - Identity and address filters use substring matching; interface uses exact matching.
- Example:
  ```
  mikrotik_list_mikrotik_neighbors(identity_filter="branch", interface_filter="ether1")
  ```
