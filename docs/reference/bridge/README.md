# Bridge VLAN Management

## `mikrotik_list_bridge_vlans`
Lists bridge VLAN table entries (tagged/untagged port membership per VLAN).
- Parameters:
  - `bridge_filter` (optional): Filter by bridge name
  - `vlan_ids_filter` (optional): Filter by VLAN IDs
  - `dynamic_only` (optional): Show only dynamic entries
- Example:
  ```
  mikrotik_list_bridge_vlans(bridge_filter="bridge1")
  ```

## `mikrotik_add_bridge_vlan`
Adds an entry to the bridge VLAN table.
- Parameters:
  - `bridge` (required): Bridge name
  - `vlan_ids` (required): VLAN ID, comma list, or range (e.g. "10", "10,20", "100-199")
  - `tagged` (optional): Comma-separated ports carrying these VLANs tagged
  - `untagged` (optional): Comma-separated ports carrying these VLANs untagged
  - `comment` (optional): Description
  - `disabled` (optional): Disable entry
- Example:
  ```
  mikrotik_add_bridge_vlan(bridge="bridge1", vlan_ids="10", tagged="ether1,ether2", untagged="ether3")
  ```

## `mikrotik_update_bridge_vlan`
Updates an existing bridge VLAN table entry.
- Parameters:
  - `bridge` (required): Bridge name
  - `vlan_ids` (required): Current VLAN IDs (must match the stored value exactly)
  - `new_vlan_ids` (optional): New VLAN IDs
  - `tagged` (optional): New tagged port list (pass "" to clear)
  - `untagged` (optional): New untagged port list (pass "" to clear)
  - `comment` (optional): New description
  - `disabled` (optional): Enable/disable entry
- Example:
  ```
  mikrotik_update_bridge_vlan(bridge="bridge1", vlan_ids="10", tagged="ether1,ether2,ether4")
  ```

## `mikrotik_remove_bridge_vlan`
Removes an entry from the bridge VLAN table.
- Parameters:
  - `bridge` (required): Bridge name
  - `vlan_ids` (required): VLAN IDs (must match the stored value exactly)
- Example:
  ```
  mikrotik_remove_bridge_vlan(bridge="bridge1", vlan_ids="10")
  ```

## `mikrotik_list_bridge_ports`
Lists bridge ports, including each port's PVID.
- Parameters:
  - `bridge_filter` (optional): Filter by bridge name
  - `interface_filter` (optional): Filter by interface name
- Example:
  ```
  mikrotik_list_bridge_ports(bridge_filter="bridge1")
  ```

## `mikrotik_update_bridge_port`
Updates per-port VLAN settings (PVID, frame types, ingress filtering) on a bridge port.
- Parameters:
  - `interface` (required): Port's interface name
  - `pvid` (optional): VLAN ID for untagged ingress traffic (1-4094)
  - `frame_types` (optional): admit-all, admit-only-untagged-and-priority-tagged, or admit-only-vlan-tagged
  - `ingress_filtering` (optional): Drop frames for VLANs the port is not a member of
- Example:
  ```
  mikrotik_update_bridge_port(interface="ether3", pvid=10, frame_types="admit-only-untagged-and-priority-tagged")
  ```
