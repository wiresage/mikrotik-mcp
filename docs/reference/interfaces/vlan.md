# VLAN Interface Management

## `create_vlan_interface`
Creates a VLAN interface on MikroTik device.
- Parameters:
  - `name` (required): VLAN interface name
  - `vlan_id` (required): VLAN ID (1-4094)
  - `interface` (required): Parent interface
  - `comment` (optional): Description
  - `disabled` (optional): Disable interface
  - `mtu` (optional): MTU size
  - `use_service_tag` (optional): Use service tag
  - `arp` (optional): ARP mode
  - `arp_timeout` (optional): ARP timeout
- Example:
  ```
  create_vlan_interface(name="vlan100", vlan_id=100, interface="ether1")
  ```

## `list_vlan_interfaces`
Lists VLAN interfaces on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `vlan_id_filter` (optional): Filter by VLAN ID
  - `interface_filter` (optional): Filter by parent interface
  - `disabled_only` (optional): Show only disabled interfaces
- Example:
  ```
  list_vlan_interfaces(vlan_id_filter=100)
  ```

## `get_vlan_interface`
Gets detailed information about a specific VLAN interface.
- Parameters:
  - `name` (required): VLAN interface name
- Example:
  ```
  get_vlan_interface(name="vlan100")
  ```

## `update_vlan_interface`
Updates an existing VLAN interface.
- Parameters:
  - `name` (required): Current VLAN interface name
  - `new_name` (optional): New name
  - `vlan_id` (optional): New VLAN ID
  - `interface` (optional): New parent interface
  - `comment` (optional): New description
  - `disabled` (optional): Enable/disable interface
  - `mtu` (optional): New MTU size
  - `use_service_tag` (optional): Use service tag
  - `arp` (optional): ARP mode
  - `arp_timeout` (optional): ARP timeout
- Example:
  ```
  update_vlan_interface(name="vlan100", comment="Production VLAN")
  ```

## `remove_vlan_interface`
Removes a VLAN interface from MikroTik device.
- Parameters:
  - `name` (required): VLAN interface name
- Example:
  ```
  remove_vlan_interface(name="vlan100")
  ```
