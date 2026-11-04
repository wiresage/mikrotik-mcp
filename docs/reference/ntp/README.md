# NTP & System Clock Management

Tools for inspecting and configuring Network Time Protocol (NTP/SNTP) synchronization, upstream time servers, the local NTP broadcast server, and timezone settings.

## `mikrotik_get_ntp_status`
Retrieves current NTP client synchronization status, active peer, offset, and frequency drift.
- Parameters:
  - `device` (optional): Device selector
- Example:
  ```
  mikrotik_get_ntp_status()
  ```

## `mikrotik_check_clock_sync`
Performs a healthcheck on router clock synchronization and reports current time, timezone, and offset.
- Parameters:
  - `device` (optional): Device selector
- Example:
  ```
  mikrotik_check_clock_sync()
  ```

## `mikrotik_get_ntp_client_settings`
Retrieves NTP client configuration and configured upstream NTP servers.
- Parameters:
  - `device` (optional): Device selector
- Example:
  ```
  mikrotik_get_ntp_client_settings()
  ```

## `mikrotik_update_ntp_client`
Configures NTP client operation mode, administrative state, and VRF binding.
- Parameters:
  - `enabled` (optional): Enable or disable the NTP client daemon
  - `mode` (optional): Mode (`unicast`, `broadcast`, `multicast`)
  - `vrf` (optional): Routing table/VRF binding
- Example:
  ```
  mikrotik_update_ntp_client(enabled=True, mode="unicast")
  ```

## `mikrotik_add_ntp_server`
Adds an upstream NTP server address with optional polling intervals and iburst acceleration.
- Parameters:
  - `address` (required): Hostname or IP address (e.g. `time.cloudflare.com`, `161.53.123.5`)
  - `iburst` (optional, default: `True`): Send burst of packets when server is unreachable
  - `min_poll` (optional): Minimum poll interval exponent (4 to 17)
  - `max_poll` (optional): Maximum poll interval exponent (4 to 17)
- Example:
  ```
  mikrotik_add_ntp_server(address="time.cloudflare.com", iburst=True)
  ```

## `mikrotik_remove_ntp_server`
Removes an upstream NTP server by its hostname or IP address.
- Parameters:
  - `address` (required): Server IP address or hostname
- Example:
  ```
  mikrotik_remove_ntp_server(address="161.53.123.5")
  ```

## `mikrotik_get_ntp_server_settings`
Retrieves local NTP server settings for serving time to LAN clients.
- Parameters:
  - `device` (optional): Device selector
- Example:
  ```
  mikrotik_get_ntp_server_settings()
  ```

## `mikrotik_update_ntp_server`
Configures the local NTP server daemon to distribute time across the network.
- Parameters:
  - `enabled` (optional): Enable or disable local NTP server
  - `broadcast` (optional): Send broadcast NTP packets
  - `multicast` (optional): Send multicast NTP packets
  - `manycast` (optional): Respond to manycast NTP requests
  - `use_local_clock` (optional): Serve local unsynchronized clock if upstream is lost
  - `local_clock_stratum` (optional): Stratum level to report when serving local clock
- Example:
  ```
  mikrotik_update_ntp_server(enabled=True, broadcast=True)
  ```

## `mikrotik_update_system_clock`
Configures router timezone name and automatic timezone detection.
- Parameters:
  - `time_zone_name` (optional): Timezone string (e.g. `Europe/Zagreb`, `UTC`)
  - `time_zone_autodetect` (optional): Enable or disable automatic timezone detection
- Example:
  ```
  mikrotik_update_system_clock(time_zone_name="Europe/Zagreb", time_zone_autodetect=False)
  ```
