# Diagnostics

Bounded diagnostic commands run on the router: ping, traceroute, torch, a quick
packet capture and a CPU profile. None of them changes the configuration, so
all are annotated READ and stay available with `--read-only`. The four that
reach outside the router or observe live traffic are also marked open-world.

They need RouterOS user policies beyond `read`:

| Tool | Command | Policy |
|---|---|---|
| `ping` | `/ping` | `test` |
| `traceroute` | `/tool traceroute` | `test` |
| `torch` | `/tool torch` | `sniff` |
| `sniff_packets` | `/tool sniffer quick` | `sniff` |
| `profile_cpu` | `/tool profile` | `read` |

A group for an assistant that may diagnose but not change anything:

```
/user group add name=mcp policy=ssh,read,api,test,sniff
```

Without the policy the router answers `not enough permissions`, which the tool
returns as a failure.

## How the output is produced

- Every command ends on its own: ping and traceroute take a bounded `count`,
  and torch, the sniffer and the profiler a `duration` of 1 to 30 seconds.
- Without a terminal, RouterOS prints a new copy of the table on every
  refresh. Only the last one is returned: the text after the last
  `Columns: ...` line, which RouterOS 7 prints at the top of each frame and
  whose content can change between frames.
- Without a terminal, RouterOS also lays tables out for 80 columns and drops
  the columns that do not fit. Torch would lose its destination and rate
  columns, so these tools connect with RouterOS's console login option
  `<user>+250w`, available to any tool through
  `execute_mikrotik_command(..., terminal_width=N)`. Other tools are unchanged.
- Output is capped at 300 lines.

## `ping`

- `address` (required): IPv4/IPv6 address or host name
- `count`: 1 to 20, default 4
- `size`, `interval` (e.g. `200ms`, `1s`), `src_address`, `interface`,
  `routing_table`, `ttl`
- `do_not_fragment`: combine with `size` to probe the path MTU
- `arp_ping`: send ARP requests instead of ICMP (needs `interface`)

## `traceroute`

- `address` (required), `count` (probes per hop, 1 to 5), `max_hops` (default 30)
- `protocol`: `icmp` (default) or `udp`, with `port` for UDP
- `size`, `timeout` (per probe, e.g. `500ms`), `src_address`, `interface`,
  `routing_table`, `use_dns` (default off)

## `torch`

- `interface` (required), `duration` (1 to 30 s, default 5)
- `src_address`, `dst_address`, `src_address6`, `dst_address6`, `ip_protocol`,
  `port` (one port or `any`), `mac_protocol`, `vlan_id`, `dscp`

Each filter both filters and breaks the table down by that field: `0.0.0.0/0`
(or `::/0`) lists every address and `any` every protocol, port, VLAN or DSCP.
With no filter, flows are broken down by IPv4 source and destination address
and by IP protocol. While torch runs, RouterOS turns fasttrack off, which
raises CPU load on a busy router.

## `sniff_packets`

- `interface` (all interfaces when omitted), `duration` (1 to 30 s, default 5)
- `ip_address` (source or destination), `ip_protocol`, `port` (`53`,
  `80,443` or `1000-2000`), `mac_address`

Shows headers only (interface, direction, MACs, VLAN, addresses and ports,
protocol, size, CPU). Nothing is saved on the router.

## `profile_cpu`

- `duration` (1 to 30 s, default 5)
- `cpu`: `total` (default), `all` for one column per core, or a core number

## Input validation

Interface and routing-table names are sent quoted and escaped. Addresses,
ports, protocols, MACs and durations must match narrow patterns, so a value
such as `1.1.1.1; /system reboot` is refused before anything is sent.
