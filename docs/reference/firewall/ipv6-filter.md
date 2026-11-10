# IPv6 Firewall Filter Rules Management

Tools for managing IPv6 firewall filter rules, under the RouterOS
`/ipv6 firewall filter` command tree. This is the IPv6 counterpart of the
[Firewall](filter.md) (IPv4) scope.

> IPv6 lives in a separate command tree from IPv4 (`/ipv6 …` vs `/ip …`), so
> the IPv4 firewall tools do not see or touch these rules. Two differences bite
> most often: the ICMP protocol is spelled `icmpv6` here, and addresses are
> IPv6 prefixes such as `2001:db8::/64`.

## `create_ipv6_filter_rule`

Creates an IPv6 firewall filter rule. Runs `/ipv6 firewall filter add …`.

- Parameters:
  - `chain` (required): `"input"`, `"forward"` or `"output"`
  - `action` (required): `"accept"`, `"drop"`, `"reject"`, `"jump"`, `"log"`,
    `"passthrough"`, `"return"` or `"tarpit"`
  - `jump_target` (optional): chain to jump to; only used with `action="jump"`
  - `src_address` / `dst_address` (optional): IPv6 address or prefix
  - `src_port` / `dst_port` (optional): port, list or range
  - `protocol` (optional): e.g. `tcp`, `udp`, `icmpv6`
  - `in_interface` / `out_interface` (optional): interface name
  - `connection_state` (optional): comma-separated, e.g. `established,related`
  - `src_address_list` / `dst_address_list` (optional): address list name
  - `src_address_type` / `dst_address_type` (optional): e.g. `unicast`, `multicast`, `local`
  - `icmp_options` (optional): ICMPv6 `type:code`, e.g. `128:0` for echo request
  - `hop_limit` (optional): hop-limit expression, e.g. `equal:255`
  - `headers` (optional): extension-header match, e.g. `hop` or `!hop`
  - `limit` (optional): rate/burst string, e.g. `10,5:packet`
  - `tcp_flags` (optional): flag expression, e.g. `syn,!ack`
  - `comment` (optional), `disabled` (optional), `log` (optional), `log_prefix` (optional)
  - `place_before` (optional): rule number or ID to insert before

- Examples:
  ```
  create_ipv6_filter_rule(chain="input", action="accept", protocol="icmpv6")
  create_ipv6_filter_rule(chain="input", action="accept", protocol="tcp", dst_port="22", src_address="2001:db8::/64")
  create_ipv6_filter_rule(chain="input", action="accept", protocol="icmpv6", icmp_options="133:0", hop_limit="equal:255")
  ```

## `list_ipv6_filter_rules`

Lists IPv6 firewall filter rules. Runs `/ipv6 firewall filter print [where …]`.

- Parameters:
  - `chain_filter` (optional): exact chain match
  - `action_filter` (optional): exact action match
  - `src_address_filter` / `dst_address_filter` (optional): **partial** match on
    the address, e.g. `"2001:db8"` matches every rule whose address begins with it
  - `protocol_filter` (optional): exact protocol match — use `icmpv6`, not `icmp`
  - `interface_filter` (optional): matches either `in-interface` or `out-interface`
  - `disabled_only` / `invalid_only` / `dynamic_only` (optional)

- Examples:
  ```
  list_ipv6_filter_rules()
  list_ipv6_filter_rules(chain_filter="forward")
  list_ipv6_filter_rules(protocol_filter="icmpv6")
  ```

## `get_ipv6_filter_rule`

Gets one rule in detail. Runs `/ipv6 firewall filter print detail where .id=…`.

- Parameters:
  - `rule_id` (required): a RouterOS internal id, e.g. `*1`. The positional
    numbers shown by `print` are per-session and do not resolve here.

- Example:
  ```
  get_ipv6_filter_rule(rule_id="*3")
  ```

## `update_ipv6_filter_rule`

Updates an existing rule. Runs `/ipv6 firewall filter set …`.

Takes `rule_id` plus any of the `create_ipv6_filter_rule` fields. Pass an empty
string to clear an optional field (e.g. `src_address=""`).

- Example:
  ```
  update_ipv6_filter_rule(rule_id="*3", comment="tightened", src_address="")
  ```

## `remove_ipv6_filter_rule`

Removes a rule. Runs `/ipv6 firewall filter remove …`.

- Example:
  ```
  remove_ipv6_filter_rule(rule_id="*3")
  ```

## `move_ipv6_filter_rule`

Moves a rule to another position. Runs `/ipv6 firewall filter move …`.

- Parameters:
  - `rule_id` (required), `destination` (required): 0-based target index

- Example:
  ```
  move_ipv6_filter_rule(rule_id="*3", destination=0)
  ```

## `enable_ipv6_filter_rule` / `disable_ipv6_filter_rule`

Toggles a rule without removing it.

- Example:
  ```
  disable_ipv6_filter_rule(rule_id="*3")
  ```
