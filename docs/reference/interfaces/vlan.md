# VLAN Interface Management

## `mikrotik_create_vlan_interface`
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
  mikrotik_create_vlan_interface(name="vlan100", vlan_id=100, interface="ether1")
  ```

## `mikrotik_list_vlan_interfaces`
Lists VLAN interfaces on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `vlan_id_filter` (optional): Filter by VLAN ID
  - `interface_filter` (optional): Filter by parent interface
  - `disabled_only` (optional): Show only disabled interfaces
- Example:
  ```
  mikrotik_list_vlan_interfaces(vlan_id_filter=100)
  ```

## `mikrotik_get_vlan_interface`
Gets detailed information about a specific VLAN interface.
- Parameters:
  - `name` (required): VLAN interface name
- Example:
  ```
  mikrotik_get_vlan_interface(name="vlan100")
  ```

## `mikrotik_update_vlan_interface`
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
  mikrotik_update_vlan_interface(name="vlan100", comment="Production VLAN")
  ```

## `mikrotik_remove_vlan_interface`
Removes a VLAN interface from MikroTik device.
- Parameters:
  - `name` (required): VLAN interface name
- Example:
  ```
  mikrotik_remove_vlan_interface(name="vlan100")
  ```
