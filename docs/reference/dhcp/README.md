# DHCP Server Management

## `create_dhcp_server`
Creates a DHCP server on MikroTik device.
- Parameters:
  - `name` (required): DHCP server name
  - `interface` (required): Interface to bind to
  - `lease_time` (optional): Lease time (default: "1d")
  - `address_pool` (optional): IP pool name
  - `disabled` (optional): Disable server
  - `authoritative` (optional): Authoritative mode
  - `delay_threshold` (optional): Delay threshold
  - `comment` (optional): Description
- Example:
  ```
  create_dhcp_server(name="dhcp-vlan100", interface="vlan100", address_pool="pool-vlan100")
  ```

## `list_dhcp_servers`
Lists DHCP servers on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `interface_filter` (optional): Filter by interface
  - `disabled_only` (optional): Show only disabled servers
  - `invalid_only` (optional): Show only invalid servers
- Example:
  ```
  list_dhcp_servers()
  ```

## `get_dhcp_server`
Gets detailed information about a specific DHCP server.
- Parameters:
  - `name` (required): DHCP server name
- Example:
  ```
  get_dhcp_server(name="dhcp-vlan100")
  ```

## `list_dhcp_leases`
Lists raw detailed IPv4 DHCP leases. Identity filters use the active lease fields.
- Parameters:
  - `address_filter` (optional): Filter active address
  - `mac_filter` (optional): Filter active MAC address
  - `client_id_filter` (optional): Filter active client ID
  - `server_filter` (optional): Filter active DHCP server
  - `status_filter` (optional): Filter lease status
  - `lease_time_filter` (optional): Filter configured lease time
  - `last_seen_within` (optional): Include leases seen within a duration such as `1h` or `24h`
  - `hostname_filter` (optional): Filter active hostname
  - `class_id_filter` (optional): Filter active class ID
- Notes:
  - Address and identity filters use substring matching; server, status, and lease time use exact matching.
  - `lease_time_filter` matches the RouterOS `lease-time` field.
- Example:
  ```
  list_dhcp_leases(status_filter="bound", last_seen_within="24h")
  ```

## `list_dhcpv6_bindings`
Lists raw detailed DHCPv6 bindings.
- Parameters:
  - `address_filter` (optional): Filter assigned address or prefix
  - `duid_filter` (optional): Filter DUID
  - `iaid_filter` (optional): Filter IAID
  - `server_filter` (optional): Filter DHCPv6 server
  - `status_filter` (optional): Filter binding status
  - `lease_time_filter` (optional): Filter configured `life-time`
  - `last_seen_within` (optional): Include bindings seen within a duration such as `1h` or `24h`
- Notes:
  - Address and DUID filters use substring matching; IAID, server, status, and lease time use exact matching.
  - `lease_time_filter` matches the RouterOS `life-time` field.
- Example:
  ```
  list_dhcpv6_bindings(status_filter="bound", last_seen_within="1h")
  ```

## `create_dhcp_network`
Creates a DHCP network configuration.
- Parameters:
  - `network` (required): Network address
  - `gateway` (required): Gateway address
  - `netmask` (optional): Network mask
  - `dns_servers` (optional): DNS server list
  - `domain` (optional): Domain name
  - `wins_servers` (optional): WINS server list
  - `ntp_servers` (optional): NTP server list
  - `dhcp_option` (optional): DHCP options
  - `comment` (optional): Description
- Example:
  ```
  create_dhcp_network(network="192.168.1.0/24", gateway="192.168.1.1", dns_servers=["8.8.8.8", "8.8.4.4"])
  ```

## `update_dhcp_network`
Updates fields on an existing DHCP network entry.
- Parameters:
  - `network` (required): Network address of the entry to update
  - `gateway` (optional): Gateway address
  - `netmask` (optional): Network mask
  - `dns_servers` (optional): DNS server list
  - `domain` (optional): Domain name
  - `wins_servers` (optional): WINS server list
  - `ntp_servers` (optional): NTP server list
  - `dhcp_option` (optional): DHCP options
  - `comment` (optional): Description
- Notes:
  - Pass an empty list for `dns_servers`, `wins_servers`, `ntp_servers` or `dhcp_option` (or `""` for `domain`) to clear that field.
  - Answers "DHCP network '<network>' not found." when no entry has that network address, and "No updates specified." when no field is given.
- Example:
  ```
  update_dhcp_network(network="192.168.1.0/24", dns_servers=["1.1.1.1"])
  ```

## `remove_dhcp_network`
Removes a DHCP network configuration.
- Parameters:
  - `network` (required): Network address of the entry to remove
- Example:
  ```
  remove_dhcp_network(network="192.168.1.0/24")
  ```

## `create_dhcp_pool`
Creates a DHCP address pool.
- Parameters:
  - `name` (required): Pool name
  - `ranges` (required): IP ranges
  - `next_pool` (optional): Next pool name
  - `comment` (optional): Description
- Example:
  ```
  create_dhcp_pool(name="pool-vlan100", ranges="192.168.1.10-192.168.1.250")
  ```

## `remove_dhcp_server`
Removes a DHCP server from MikroTik device.
- Parameters:
  - `name` (required): DHCP server name
- Example:
  ```
  remove_dhcp_server(name="dhcp-vlan100")
  ```
