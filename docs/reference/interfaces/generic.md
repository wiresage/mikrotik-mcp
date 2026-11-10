# Interface Management

Tools for listing and managing **all** interfaces on a MikroTik device — ethernet, bridge, WireGuard, PPPoE, VLAN, WiFi, SFP, LTE, loopback, and any other type. This is the equivalent of `/interface print` in RouterOS.

> For type-specific management (create, remove, update) use the dedicated tool categories:
> [VLAN](vlan.md) · [Bridge](bridge.md) · [WireGuard](wireguard.md) · [PoE](poe.md)

## `list_interfaces`

Lists all interfaces on the device, with optional filtering.

- Parameters:
  - `type_filter` (optional): Filter by interface type — `"ether"`, `"bridge"`, `"vlan"`, `"wg"`, `"pppoe-out"`, `"wifi"`, `"lte"`, `"loopback"`, etc.
  - `name_filter` (optional): Partial name match e.g. `"ether"` matches `ether1`, `ether2` …
  - `running_only` (optional): Return only currently running interfaces
  - `disabled_only` (optional): Return only disabled interfaces

- Examples:
  ```
  list_interfaces()                              # all interfaces
  list_interfaces(type_filter="ether")           # ethernet ports only
  list_interfaces(type_filter="bridge")          # bridge interfaces only
  list_interfaces(running_only=True)             # only interfaces that are up
  list_interfaces(name_filter="ether")           # any interface whose name contains "ether"
  ```

## `get_interface`

Gets detailed information about a single interface by exact name.

- Parameters:
  - `name` (required): Exact interface name e.g. `"ether1"`, `"bridge"`, `"pppoe-out1"`, `"wg0"`

- Example:
  ```
  get_interface(name="ether1-wan")
  get_interface(name="pppoe-out1")
  ```

## `enable_interface`

Enables a disabled interface.

- Parameters:
  - `name` (required): Exact interface name

- Example:
  ```
  enable_interface(name="ether4")
  ```

## `disable_interface`

Disables an interface (takes it down without removing it).

- Parameters:
  - `name` (required): Exact interface name

- Example:
  ```
  disable_interface(name="ether4")
  ```
