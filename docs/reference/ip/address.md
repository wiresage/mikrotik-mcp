# IP Address Management

## `mikrotik_add_ip_address`
Adds an IP address to an interface.
- Parameters:
  - `address` (required): IP address with CIDR notation
  - `interface` (required): Interface name
  - `network` (optional): Network address
  - `broadcast` (optional): Broadcast address
  - `comment` (optional): Description
  - `disabled` (optional): Disable address
- Example:
  ```
  mikrotik_add_ip_address(address="192.168.1.1/24", interface="vlan100")
  ```

## `mikrotik_list_ip_addresses`
Lists IP addresses on MikroTik device.
- Parameters:
  - `interface_filter` (optional): Filter by interface
  - `address_filter` (optional): Filter by address
  - `network_filter` (optional): Filter by network
  - `disabled_only` (optional): Show only disabled addresses
  - `dynamic_only` (optional): Show only dynamic addresses
- Example:
  ```
  mikrotik_list_ip_addresses(interface_filter="vlan100")
  ```

## `mikrotik_get_ip_address`
Gets detailed information about a specific IP address.
- Parameters:
  - `address_id` (required): Address ID
- Example:
  ```
  mikrotik_get_ip_address(address_id="*1")
  ```

## `mikrotik_remove_ip_address`
Removes an IP address from MikroTik device.
- Parameters:
  - `address_id` (required): Address ID
- Example:
  ```
  mikrotik_remove_ip_address(address_id="*1")
  ```
