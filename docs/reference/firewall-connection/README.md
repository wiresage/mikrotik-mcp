# Firewall Connection Tracking

Tools for inspecting and managing the RouterOS connection tracking table and its global settings (`/ip firewall connection`).

Connection tracking monitors all active connections through the router, including TCP state, UDP timeouts, NAT mappings, and packet/byte counters.

## `get_connection_tracking_settings`

Reports global connection tracking settings, timeouts, and table capacity.

- Parameters:
  - `device` (optional): Target device title in multi-device setups

- Example:
  ```
  get_connection_tracking_settings()
  ```

## `update_connection_tracking_settings`

Updates global connection tracking settings such as timeouts, maximum table capacity, and state handling.

- Parameters:
  - `enabled` (optional): `"yes"`, `"no"`, or `"auto"`
  - `tcp_established_timeout` (optional): e.g. `"1d"`, `"12h"`, `"30m"`
  - `tcp_syn_sent_timeout` (optional): e.g. `"5s"`
  - `tcp_close_wait_timeout` (optional): e.g. `"10s"`
  - `udp_timeout` (optional): e.g. `"30s"`
  - `udp_stream_timeout` (optional): e.g. `"3m"`
  - `icmp_timeout` (optional): e.g. `"10s"`
  - `generic_timeout` (optional): e.g. `"10m"`
  - `max_entries` (optional): Maximum connection table size (integer)
  - `loose_tcp_tracking` (optional): `"yes"` or `"no"`

- Example:
  ```
  update_connection_tracking_settings(tcp_established_timeout="12h", max_entries=100000)
  ```

## `get_connection_tracking_count`

Reports the total number of tracked firewall connections matching optional criteria without returning full connection listings.

- Parameters:
  - `protocol` (optional): `"tcp"`, `"udp"`, `"icmp"`, `"gre"`, `"ipsec-esp"`, `"all"`
  - `tcp_state` (optional): `"established"`, `"time-wait"`, `"close"`, `"syn-sent"`, `"syn-received"`, `"fin-wait"`, `"close-wait"`, `"last-ack"`
  - `src_address` (optional): Filter by source IP or subnet
  - `dst_address` (optional): Filter by destination IP or subnet
  - `src_port` (optional): Filter by source port (1-65535)
  - `dst_port` (optional): Filter by destination port (1-65535)

- Examples:
  ```
  get_connection_tracking_count()                                    # total connections
  get_connection_tracking_count(protocol="tcp", tcp_state="established")
  get_connection_tracking_count(dst_port=443)                        # active HTTPS flows
  ```

## `list_firewall_connections`

Lists active firewall connections with addresses, ports, protocol states, and transfer counters.

- Parameters:
  - Same filtering options as `get_connection_tracking_count`
  - Output is capped to 150 lines to conserve LLM context

- Examples:
  ```
  list_firewall_connections(src_address="192.168.1.100")
  list_firewall_connections(protocol="tcp", dst_port=80)
  ```

## `remove_firewall_connections`

Terminates active firewall connections matching specific address, port, or protocol filters.

> **Safety:** At least one filter (`src_address`, `dst_address`, `src_port`, `dst_port`, `protocol`) must be specified to prevent accidental deletion of all connection entries.

- Parameters:
  - `src_address` (optional): Source IP or subnet
  - `dst_address` (optional): Destination IP or subnet
  - `src_port` (optional): Source port (1-65535)
  - `dst_port` (optional): Destination port (1-65535)
  - `protocol` (optional): Protocol e.g. `"tcp"`, `"udp"`

- Examples:
  ```
  remove_firewall_connections(src_address="192.168.1.50")            # reset connections from host
  remove_firewall_connections(dst_port=8080)                         # terminate connections to port
  ```
