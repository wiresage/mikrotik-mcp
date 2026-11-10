# NAT Rules Management

## `mikrotik_create_nat_rule`
Creates a NAT rule on MikroTik device.
- Parameters:
  - `chain` (required): Chain type ("srcnat" or "dstnat")
  - `action` (required): Action type
  - `src_address` (optional): Source address
  - `dst_address` (optional): Destination address
  - `src_port` (optional): Source port
  - `dst_port` (optional): Destination port
  - `protocol` (optional): Protocol
  - `in_interface` (optional): Input interface
  - `out_interface` (optional): Output interface
  - `to_addresses` (optional): Translation addresses
  - `to_ports` (optional): Translation ports
  - `comment` (optional): Description
  - `disabled` (optional): Disable rule
  - `log` (optional): Enable logging
  - `log_prefix` (optional): Log prefix
  - `place_before` (optional): Rule placement
- Example:
  ```
  mikrotik_create_nat_rule(chain="srcnat", action="masquerade", out_interface="ether1")
  ```

## `mikrotik_list_nat_rules`
Lists NAT rules on MikroTik device.
- Parameters:
  - `chain_filter` (optional): Filter by chain
  - `action_filter` (optional): Filter by action
  - `src_address_filter` (optional): Filter by source address
  - `dst_address_filter` (optional): Filter by destination address
  - `protocol_filter` (optional): Filter by protocol
  - `interface_filter` (optional): Filter by interface
  - `disabled_only` (optional): Show only disabled rules
  - `invalid_only` (optional): Show only invalid rules
- Example:
  ```
  mikrotik_list_nat_rules(chain_filter="srcnat")
  ```

## `mikrotik_get_nat_rule`
Gets detailed information about a specific NAT rule.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_get_nat_rule(rule_id="*1")
  ```

## `mikrotik_update_nat_rule`
Updates an existing NAT rule.
- Parameters:
  - `rule_id` (required): Rule ID
  - All parameters from `create_nat_rule` (optional)
- Example:
  ```
  mikrotik_update_nat_rule(rule_id="*1", comment="Updated NAT rule")
  ```

## `mikrotik_remove_nat_rule`
Removes a NAT rule from MikroTik device.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_remove_nat_rule(rule_id="*1")
  ```

## `mikrotik_move_nat_rule`
Moves a NAT rule to a different position.
- Parameters:
  - `rule_id` (required): Rule ID
  - `destination` (required): New position
- Example:
  ```
  mikrotik_move_nat_rule(rule_id="*1", destination=0)
  ```

## `mikrotik_enable_nat_rule`
Enables a NAT rule.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_enable_nat_rule(rule_id="*1")
  ```

## `mikrotik_disable_nat_rule`
Disables a NAT rule.
- Parameters:
  - `rule_id` (required): Rule ID
- Example:
  ```
  mikrotik_disable_nat_rule(rule_id="*1")
  ```
