# Wireless

Wireless interface management. RouterOS 7 has replaced the old
`/interface wireless` menu with `/interface wifi`, and the tool names and
security model changed with it. The interface tools detect which of the two
menus your device has and translate automatically; run
`check_wireless_support` first to see which one applies.

> RouterOS 7 configures WiFi security on the interface itself, so use
> `set_wireless_passphrase` instead of the old security-profile tools.

## `check_wireless_support`

Checks if the device supports wireless and reports the RouterOS version and
the wireless menu in use.

- Example:
  ```
  check_wireless_support()
  ```

## `create_wireless_interface`

Creates a wireless interface.

- Parameters:
  - `name` (required)
  - `ssid` (optional)
  - `comment` (optional)
  - `disabled` (optional, default `False`)
  - On legacy (`/interface wireless`) devices only: `radio_name` (required
    there), `mode`, `frequency`, `band`, `channel_width`, `security_profile`

- Example:
  ```
  create_wireless_interface(name="home-wifi", ssid="HomeNetwork", comment="Main")
  ```

## `list_wireless_interfaces`

Lists wireless interfaces.

- Parameters:
  - `name_filter` (optional): substring match
  - `disabled_only`, `running_only` (optional, default `False`)

- Example:
  ```
  list_wireless_interfaces()
  list_wireless_interfaces(disabled_only=True)
  ```

## `get_wireless_interface`

Gets detailed information about one wireless interface.

- Parameters:
  - `name` (required): exact interface name

- Example:
  ```
  get_wireless_interface(name="wlan1")
  ```

## `update_wireless_interface`

Updates an existing wireless interface's name, SSID, enabled state or
comment.

- Parameters:
  - `name` (required): the interface to update
  - `new_name`, `ssid`, `disabled`, `comment` (optional)

- Example:
  ```
  update_wireless_interface(name="wlan1", ssid="NewNetwork")
  ```

## `set_wireless_passphrase`

Sets the WiFi passphrase directly on a RouterOS v7 wireless interface.

- Parameters:
  - `name` (required): the interface
  - `passphrase` (required)
  - `authentication_types` (optional): e.g. `wpa2-psk`

- Example:
  ```
  set_wireless_passphrase(name="wlan1", passphrase="change-me", authentication_types="wpa2-psk")
  ```

## `enable_wireless_interface` / `disable_wireless_interface`

Enables or disables a wireless interface.

- Parameters:
  - `name` (required): exact interface name

## `remove_wireless_interface`

Removes a wireless interface.

- Parameters:
  - `name` (required): exact interface name

## `scan_wireless_networks`

Scans for nearby wireless networks using the specified interface. The
command blocks for the scan duration (seconds, default 5).

- Parameters:
  - `interface` (required)
  - `duration` (optional, default 5)

- Example:
  ```
  scan_wireless_networks(interface="wlan1", duration=10)
  ```

## `get_wireless_registration_table`

Gets the wireless registration table (connected clients).

- Parameters:
  - `interface` (optional): filter to one interface

- Example:
  ```
  get_wireless_registration_table(interface="wlan1")
  ```

## `monitor_wireless_interface`

Monitors real-time wireless status, frequency, CCQ, noise floor, and client
counts for an interface (single snapshot via `once`).

- Parameters:
  - `interface` (required): wireless interface name
  - `device` (optional): target device

- Example:
  ```
  monitor_wireless_interface(interface="wlan1")
  ```

## `monitor_wireless_frequency`

Monitors wireless frequency usage and noise floor across channels on legacy
wireless interfaces (`/interface wireless frequency-monitor`). Running
`frequency-monitor` briefly interrupts connected wireless clients on the
monitored radio during the scan.

- Parameters:
  - `interface` (required): wireless interface name
  - `duration` (optional, 1–30s, default 5)
  - `device` (optional): target device

- Example:
  ```
  monitor_wireless_frequency(interface="wlan1", duration=5)
  ```

## Legacy tools

`create_wireless_security_profile`, `list_wireless_security_profiles`,
`get_wireless_security_profile`, `remove_wireless_security_profile`,
`set_wireless_security_profile`, `create_wireless_access_list`,
`list_wireless_access_list` and `remove_wireless_access_list_entry` are
placeholders for the RouterOS v6 features they are named after. They return
an explanatory message and change nothing on the device.
