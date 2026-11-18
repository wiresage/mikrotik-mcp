# IP Pool Management

## `create_ip_pool`
Creates an IP pool on MikroTik device.
- Parameters:
  - `name` (required): Pool name
  - `ranges` (required): IP ranges
  - `next_pool` (optional): Next pool name
  - `comment` (optional): Description
- Example:
  ```
  create_ip_pool(name="pool1", ranges="192.168.1.100-192.168.1.200")
  ```

## `list_ip_pools`
Lists IP pools on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `ranges_filter` (optional): Filter by ranges
  - `include_used` (optional): Include used addresses
- Example:
  ```
  list_ip_pools()
  ```

## `get_ip_pool`
Gets detailed information about a specific IP pool.
- Parameters:
  - `name` (required): Pool name
- Example:
  ```
  get_ip_pool(name="pool1")
  ```

## `update_ip_pool`
Updates an existing IP pool.
- Parameters:
  - `name` (required): Current pool name
  - `new_name` (optional): New name
  - `ranges` (optional): New ranges
  - `next_pool` (optional): New next pool
  - `comment` (optional): New description
- Example:
  ```
  update_ip_pool(name="pool1", ranges="192.168.1.100-192.168.1.250")
  ```

## `remove_ip_pool`
Removes an IP pool from MikroTik device.
- Parameters:
  - `name` (required): Pool name
- Example:
  ```
  remove_ip_pool(name="pool1")
  ```

## `list_ip_pool_used`
Lists used addresses from IP pools.
- Parameters:
  - `pool_name` (optional): Filter by pool name
  - `address_filter` (optional): Filter by address
  - `mac_filter` (optional): Filter by MAC address
  - `info_filter` (optional): Filter by info
- Example:
  ```
  list_ip_pool_used(pool_name="pool1")
  ```

## `expand_ip_pool`
Expands an existing IP pool by adding more ranges.
- Parameters:
  - `name` (required): Pool name
  - `additional_ranges` (required): Additional IP ranges
- Example:
  ```
  expand_ip_pool(name="pool1", additional_ranges="192.168.1.251-192.168.1.254")
  ```
