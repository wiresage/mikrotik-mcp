# Firewall Raw Rules Management (IPv4 and IPv6)

Tools for the RouterOS raw tables, `/ip firewall raw` and `/ipv6 firewall raw`.
Raw rules run **before connection tracking**, in the `prerouting` and `output`
chains. They are used to drop unwanted traffic cheaply (for example traffic
from a blocklist, or bogons on the WAN) and to exempt traffic from connection
tracking with `action=notrack`.

Each tool exists twice, with the same parameters: `*_raw_rule(s)` for IPv4 and
`*_ipv6_raw_rule(s)` for IPv6. The only parameter that differs is the TTL
matcher, `ttl` for IPv4 and `hop_limit` for IPv6. In IPv6 the ICMP protocol is
spelled `icmpv6`.

Raw rules see no connection state, so there is no `connection_state` matcher.

| IPv4 | IPv6 | Annotation |
|---|---|---|
| `list_raw_rules` | `list_ipv6_raw_rules` | READ |
| `get_raw_rule` | `get_ipv6_raw_rule` | READ |
| `create_raw_rule` | `create_ipv6_raw_rule` | WRITE |
| `update_raw_rule` | `update_ipv6_raw_rule` | WRITE_IDEMPOTENT |
| `enable_raw_rule` / `disable_raw_rule` | `enable_ipv6_raw_rule` / `disable_ipv6_raw_rule` | WRITE_IDEMPOTENT |
| `move_raw_rule` | `move_ipv6_raw_rule` | WRITE_IDEMPOTENT |
| `remove_raw_rule` | `remove_ipv6_raw_rule` | DESTRUCTIVE |

With `--read-only`, only `list_*` and `get_*` are exposed.

## `list_raw_rules` / `list_ipv6_raw_rules`

Runs `<menu> print [stats] [where …]`.

- `chain_filter`, `action_filter`, `protocol_filter`: exact match
- `src_address_filter`, `dst_address_filter`: **partial** match
- `interface_filter`: partial match on in/out interface and in/out interface list
- `comment_filter`: partial match on the comment
- `disabled_only`, `invalid_only`, `dynamic_only`
- `stats`: show byte and packet counters (`print stats`)

## `get_raw_rule` / `get_ipv6_raw_rule`

Runs `<menu> print detail where .id=…`. `rule_id` is an internal id (`*1A`) or
a print position (`0`), which is resolved to an id first.

## `create_raw_rule` / `create_ipv6_raw_rule`

Runs `:put [<menu> add …]` and reports the new internal id.

- `chain` (required): `prerouting`, `output`, or a custom chain reached by a jump
- `action` (required): `accept`, `drop`, `notrack`, `jump`, `return`, `log`,
  `passthrough`, `add-src-to-address-list`, `add-dst-to-address-list`
- `jump_target`: required with `action="jump"`
- `address_list`, `address_list_timeout` (e.g. `1d`, `12h`, `00:30:00`):
  `address_list` is required with the `add-*-to-address-list` actions
- Matchers: `src_address`, `dst_address`, `src_port`, `dst_port`, `port`,
  `protocol`, `in_interface`, `out_interface`, `in_interface_list`,
  `out_interface_list`, `src_address_list`, `dst_address_list`,
  `src_address_type`, `dst_address_type`, `tcp_flags`, `icmp_options`,
  `packet_size`, `dscp`, `limit`, and `ttl` (IPv4) or `hop_limit` (IPv6).
  Prefix a value with `!` to negate it.
- `comment`, `disabled`, `log`, `log_prefix`
- `place_before`: internal id or print position of the rule to insert before

Names and free text (interfaces, lists, comments, log prefix) are sent quoted
and escaped. Other matcher values may contain only letters, digits and
`_ . : / , ! -`, so a value that would change the command is refused before
anything is sent. A rule with no matcher is created, with a warning: in raw it
applies to every packet before connection tracking.

- Examples:
  ```
  create_raw_rule(chain="prerouting", action="drop", in_interface_list="WAN", src_address_list="blocklist")
  create_raw_rule(chain="prerouting", action="notrack", protocol="udp", dst_port="53", dst_address_type="local")
  create_ipv6_raw_rule(chain="prerouting", action="drop", in_interface_list="WAN", src_address="fc00::/7")
  ```

## `update_raw_rule` / `update_ipv6_raw_rule`

Runs `<menu> set <id> …`. Takes the same parameters as create, all optional.
Pass `""` to clear a matcher (for example `src_address=""` sends `!src-address`).
Any output from `set` is reported as a refusal, for example
`not enough permissions (9)` for a read-only account.

## `enable_*`, `disable_*`, `move_*`, `remove_*`

- `enable_raw_rule` / `disable_raw_rule`: `set <id> disabled=no|yes`
- `move_raw_rule(rule_id, destination)`: moves the rule to the 0-based
  `destination` position, by id, then checks it landed there
- `remove_raw_rule(rule_id)`: removes the rule and checks it is gone
