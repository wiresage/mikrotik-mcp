### DNS Management

#### `set_dns_servers`
Sets DNS server configuration on MikroTik device.
- Parameters:
  - `servers` (required): DNS server list
  - `allow_remote_requests` (optional): Allow remote requests
  - `max_udp_packet_size` (optional): Max UDP packet size
  - `max_concurrent_queries` (optional): Max concurrent queries
  - `cache_size` (optional): Cache size
  - `cache_max_ttl` (optional): Max cache TTL
  - `use_doh` (optional): Use DNS over HTTPS
  - `doh_server` (optional): DoH server URL
  - `verify_doh_cert` (optional): Verify DoH certificate
- Example:
  ```
  set_dns_servers(servers=["8.8.8.8", "8.8.4.4"], allow_remote_requests=true)
  ```

#### `get_dns_settings`
Gets current DNS configuration.
- Parameters: None
- Example:
  ```
  get_dns_settings()
  ```

#### `add_dns_static`
Adds a static DNS entry.
- Parameters:
  - `name` (required): DNS name
  - `address` (optional): IP address
  - `cname` (optional): CNAME record
  - `mx_preference` (optional): MX preference
  - `mx_exchange` (optional): MX exchange
  - `text` (optional): TXT record
  - `srv_priority` (optional): SRV priority
  - `srv_weight` (optional): SRV weight
  - `srv_port` (optional): SRV port
  - `srv_target` (optional): SRV target
  - `ttl` (optional): Time to live
  - `comment` (optional): Description
  - `disabled` (optional): Disable entry
  - `regexp` (optional): Regular expression
- Example:
  ```
  add_dns_static(name="router.local", address="192.168.1.1")
  ```

#### `list_dns_static`
Lists static DNS entries.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `address_filter` (optional): Filter by address
  - `type_filter` (optional): Filter by type
  - `disabled_only` (optional): Show only disabled entries
  - `regexp_only` (optional): Show only regexp entries
- Example:
  ```
  list_dns_static()
  ```

#### `get_dns_static`
Gets details of a specific static DNS entry.
- Parameters:
  - `entry_id` (required): Entry ID
- Example:
  ```
  get_dns_static(entry_id="*1")
  ```

#### `update_dns_static`
Updates an existing static DNS entry.
- Parameters:
  - `entry_id` (required): Entry ID
  - All parameters from `add_dns_static` (optional)
- Example:
  ```
  update_dns_static(entry_id="*1", address="192.168.1.2")
  ```

#### `remove_dns_static`
Removes a static DNS entry.
- Parameters:
  - `entry_id` (required): Entry ID
- Example:
  ```
  remove_dns_static(entry_id="*1")
  ```

#### `enable_dns_static`
Enables a static DNS entry.
- Parameters:
  - `entry_id` (required): Entry ID
- Example:
  ```
  enable_dns_static(entry_id="*1")
  ```

#### `disable_dns_static`
Disables a static DNS entry.
- Parameters:
  - `entry_id` (required): Entry ID
- Example:
  ```
  disable_dns_static(entry_id="*1")
  ```

#### `get_dns_cache`
Gets the current DNS cache.
- Parameters: None
- Example:
  ```
  get_dns_cache()
  ```

#### `flush_dns_cache`
Flushes the DNS cache.
- Parameters: None
- Example:
  ```
  flush_dns_cache()
  ```

#### `get_dns_cache_statistics`
Gets DNS cache statistics.
- Parameters: None
- Example:
  ```
  get_dns_cache_statistics()
  ```

#### `add_dns_regexp`
Adds a DNS regexp entry for pattern matching.
- Parameters:
  - `regexp` (required): Regular expression
  - `address` (required): IP address
  - `ttl` (optional): Time to live
  - `comment` (optional): Description
  - `disabled` (optional): Disable entry
- Example:
  ```
  add_dns_regexp(regexp="^ad[0-9]*\\.doubleclick\\.net$", address="127.0.0.1")
  ```

#### `test_dns_query`
Tests a DNS query.
- Parameters:
  - `name` (required): DNS name to query
  - `server` (optional): DNS server to use
  - `type` (optional): Query type; accepted values: `A`/`ipv4` (default), `AAAA`/`ipv6`, `any`, `any6` (record-type queries such as MX/TXT are not supported by RouterOS `:resolve`)
- Example:
  ```
  test_dns_query(name="google.com")
  ```

#### `export_dns_config`
Exports DNS configuration to a file.
- Parameters:
  - `filename` (optional): Export filename
- Example:
  ```
  export_dns_config(filename="dns-config.rsc")
  ```

