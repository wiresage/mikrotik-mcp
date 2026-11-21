# PPP and VPN Tunnels

Tools for managing PPP, Point-to-Point VPN tunnels (SSTP, OpenVPN, L2TP), VPN user secrets, profiles, and active connections.

## Active Sessions (`/ppp active`)

### `list_ppp_active`
Lists active PPP and VPN sessions with usernames, assigned IPs, remote caller IDs, uptime, and cipher encodings.

- Parameters:
  - `service` (optional): Filter by service (`"any"`, `"sstp"`, `"ovpn"`, `"l2tp"`, `"pptp"`, `"pppoe"`)
  - `name` (optional): Filter by username substring
  - `device` (optional): Target device

### `get_ppp_active`
Retrieves detailed status, uptime, session ID, and packet/byte counters for a specific active user session.

- Parameters:
  - `name`: Username of the active session
  - `device` (optional): Target device

### `disconnect_ppp_session`
Terminates and disconnects an active VPN connection session by username (useful for resetting stale or hung tunnel sessions).

- Parameters:
  - `name`: Username of the active session to disconnect
  - `device` (optional): Target device

---

## User Accounts (`/ppp secret`)

### `list_ppp_secrets`
Lists configured VPN accounts and their assigned addresses and service limits. Passwords are automatically withheld.

- Parameters:
  - `service` (optional): Filter by service (`"any"`, `"sstp"`, `"ovpn"`, `"l2tp"`, `"pptp"`, `"pppoe"`)
  - `device` (optional): Target device

### `get_ppp_secret`
Retrieves detailed configuration for a specific VPN account (profile, local/remote address, service).

- Parameters:
  - `name`: Username
  - `device` (optional): Target device

### `create_ppp_secret`
Creates a new VPN user account with credentials and address properties.

- Parameters:
  - `name`: Username
  - `password`: Account password (redacted from logs)
  - `service` (optional): Allowed service (`"any"`, `"sstp"`, `"ovpn"`, `"l2tp"`, `"pptp"`, `"pppoe"`, default: `"any"`)
  - `profile` (optional): Associated PPP profile
  - `local_address` (optional): Tunnel server address
  - `remote_address` (optional): Tunnel client address
  - `comment` (optional): Comment
  - `disabled` (optional): Create in disabled state (default: `False`)
  - `device` (optional): Target device

### `update_ppp_secret`
Updates credentials, assigned addresses, profile, or enabled state of an existing account.

- Parameters:
  - `name`: Username
  - `password` (optional): New password
  - `service` (optional): Service restriction
  - `profile` (optional): PPP profile
  - `local_address` (optional): Local IP
  - `remote_address` (optional): Remote IP
  - `comment` (optional): Comment
  - `disabled` (optional): Enabled/disabled state
  - `device` (optional): Target device

### `remove_ppp_secret`
Removes a configured VPN account.

- Parameters:
  - `name`: Username to delete
  - `device` (optional): Target device

### `list_ppp_profiles`
Lists PPP profiles specifying encryption requirements, DNS servers, rate limits, and bridge assignments.

- Parameters:
  - `device` (optional): Target device

---

## Outgoing Client Tunnels (`/interface sstp/ovpn/l2tp-client`)

### `list_vpn_clients`
Lists configured outgoing VPN client tunnel interfaces of the specified protocol.

- Parameters:
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `device` (optional): Target device

### `monitor_vpn_client`
Takes a real-time status snapshot of an outgoing VPN client connection (`status: connected`, `uptime`, `encoding`, `local-address`, `remote-address`).

- Parameters:
  - `name`: Interface name
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `device` (optional): Target device

### `create_vpn_client`
Creates a new outgoing VPN client tunnel interface.

- Parameters:
  - `name`: Interface name
  - `connect_to`: Remote VPN gateway host or IP
  - `user`: Username
  - `password`: Password
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `port` (optional): Port number
  - `profile` (optional): Associated PPP profile
  - `comment` (optional): Comment
  - `disabled` (optional): Create disabled (default: `False`)
  - `device` (optional): Target device

### `update_vpn_client`
Updates destination host, port, credentials, or profile of an existing VPN client interface.

- Parameters:
  - `name`: Interface name
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `connect_to` (optional): New remote gateway
  - `user` (optional): New username
  - `password` (optional): New password
  - `port` (optional): Port number
  - `profile` (optional): PPP profile
  - `comment` (optional): Comment
  - `disabled` (optional): Enabled/disabled state
  - `device` (optional): Target device

### `remove_vpn_client`
Deletes an outgoing VPN client tunnel interface.

- Parameters:
  - `name`: Interface name
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `device` (optional): Target device

---

## VPN Server Settings (`/interface sstp/ovpn/l2tp-server server`)

### `get_vpn_server_settings`
Inspects listening configuration, enabled state, ciphers, and port of the specified VPN server.

- Parameters:
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `device` (optional): Target device

### `update_vpn_server_settings`
Enables, disables, or updates port, certificate, and default profile for the VPN server.

- Parameters:
  - `vpn_type`: Protocol type (`"sstp"`, `"ovpn"`, or `"l2tp"`, default: `"sstp"`)
  - `enabled` (optional): Enable or disable server
  - `port` (optional): Listening port
  - `default_profile` (optional): Default profile
  - `certificate` (optional): TLS certificate name
  - `device` (optional): Target device
