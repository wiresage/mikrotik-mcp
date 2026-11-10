### Firewall Filter Rules Management

#### `mikrotik_create_filter_rule`
Creates a firewall filter rule on MikroTik device.
- Parameters:
  - `chain` (required): Chain type ("input", "forward", "output")
  - `action` (required): Action type
  - `src_address` (optional): Source address
  - `dst_address` (optional): Destination address
  - `src_port` (optional): Source port
  - `dst_port` (optional): Destination port
  - `protocol` (optional): Protocol
  - `in_interface` (optional): Input interface
  - `out_interface` (optional): Output interface
  - `connection_state` (optional): Connection state
  - `connection_nat_state` (optional): Connection NAT state
  - `src_address_list` (optional): Source address list
  - `dst_address_list` (optional): Destination address list
  - `limit` (optional): Rate limit
  - `tcp_flags` (optional): TCP flags
  - `comment` (optional): Description
  - `disabled` (optional): Disable rule
  - `log` (optional): Enable logging
  - `log_prefix` (optional): Log prefix
  - `place_before` (optional): Rule placement
- Example:
  ```
  mikrotik_create_filter_rule(chain="input", action="accept", protocol="tcp", dst_port="22", src_address="192.168.1.0/24")
  ```

#### `mikrotik_list_filter_rules`
Lists firewall filter rules on MikroTik device.
- Parameters:
  - `chain_filter` (optional): Filter by chain
  - `action_filter` (optional): Filter by action
  - `src_address_filter` (optional): Filter by source address
  - `dst_address_filter` (optional): Filter by destination address
  - `protocol_filter` (optional): Filter by protocol
  - `interface_filter` (optional): Filter by interface
  - `disabled_only` (optional): Show only disabled rules
  - `invalid_only` (optional): Show only invalid rules
  - `dynamic_only` (optional): Show only dynamic rules
- Example:
  ```
  mikrotik_list_filter_rules(chain_filter="input")
  ```

#### `mikrotik_get_filter_rule`
Gets detailed information about a specific firewall filter rule.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_get_filter_rule(rule_id="*1")
  ```

#### `mikrotik_update_filter_rule`
Updates an existing firewall filter rule.
- Parameters:
  - `rule_id` (required): Rule ID
  - All parameters from `create_filter_rule` (optional)
- Example:
  ```
  mikrotik_update_filter_rule(rule_id="*1", comment="Updated rule")
  ```

#### `mikrotik_remove_filter_rule`
Removes a firewall filter rule from MikroTik device.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_remove_filter_rule(rule_id="*1")
  ```

#### `mikrotik_move_filter_rule`
Moves a firewall filter rule to a different position.
- Parameters:
  - `rule_id` (required): Rule ID
  - `destination` (required): New position
- Example:
  ```
  mikrotik_move_filter_rule(rule_id="*1", destination=0)
  ```

#### `mikrotik_enable_filter_rule`
Enables a firewall filter rule.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_enable_filter_rule(rule_id="*1")
  ```

#### `mikrotik_disable_filter_rule`
Disables a firewall filter rule.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_disable_filter_rule(rule_id="*1")
  ```

#### `mikrotik_create_basic_firewall_setup`
Creates a basic firewall setup with common security rules.
- Parameters: None
- Example:
  ```
  mikrotik_create_basic_firewall_setup()
  ```

