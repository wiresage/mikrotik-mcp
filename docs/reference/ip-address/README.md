# IP Address Management

## `add_ip_address`
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
  add_ip_address(address="192.168.1.1/24", interface="vlan100")
  ```

## `list_ip_addresses`
Lists IP addresses on MikroTik device.
- Parameters:
  - `interface_filter` (optional): Filter by interface
  - `address_filter` (optional): Filter by address
  - `network_filter` (optional): Filter by network
  - `disabled_only` (optional): Show only disabled addresses
  - `dynamic_only` (optional): Show only dynamic addresses
- Example:
  ```
  list_ip_addresses(interface_filter="vlan100")
  ```

## `get_ip_address`
Gets detailed information about a specific IP address.
- Parameters:
  - `address_id` (required): Address ID
- Example:
  ```
  get_ip_address(address_id="*1")
  ```

## `remove_ip_address`
Removes an IP address from MikroTik device.
- Parameters:
  - `address_id` (required): Address ID
- Example:
  ```
  remove_ip_address(address_id="*1")
  ```
