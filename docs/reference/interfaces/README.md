# Interface Management

Tools for listing, monitoring, and managing **all** interfaces on a MikroTik device — ethernet, bridge, WireGuard, PPPoE, VLAN, WiFi, SFP, LTE, loopback, and any other type. This is the equivalent of `/interface` in RouterOS.

> For type-specific management (create, remove, update) use the dedicated tool categories:
> [VLAN](../vlan/README.md) · [WireGuard](../wireguard/README.md) · [Wireless](../../integrations/README.md)

## `list_interfaces`

Lists all interfaces on the device, with optional filtering and cumulative statistics.

- Parameters:
  - `type_filter` (optional): Filter by interface type — `"ether"`, `"bridge"`, `"vlan"`, `"wg"`, `"pppoe-out"`, `"wifi"`, `"lte"`, `"loopback"`, etc.
  - `name_filter` (optional): Partial name match e.g. `"ether"` matches `ether1`, `ether2` …
  - `running_only` (optional): Return only currently running interfaces
  - `disabled_only` (optional): Return only disabled interfaces
  - `stats` (optional): When `True`, returns cumulative byte and packet counters (`RX-BYTE`, `TX-BYTE`, `RX-PACKET`, `TX-PACKET`)

- Examples:
  ```
  list_interfaces()                              # all interfaces
  list_interfaces(stats=True)                    # all interfaces with cumulative byte/packet counters
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

## `monitor_interface_traffic`

Takes a single real-time snapshot of traffic rates (bps, pps, drops, errors) on a specific interface using `/interface monitor-traffic once`.

- Parameters:
  - `name` (required): Exact interface name e.g. `"ether1"`, `"eth2-tavan-uplink2"`, `"wlan2.4"`

- Example:
  ```
  monitor_interface_traffic(name="ether1-wan")
  ```

## `monitor_ethernet_interface`

Monitors the physical Ethernet port link status, negotiated speed (e.g., 1Gbps vs 100Mbps), duplex mode, and link-partner capabilities using `/interface ethernet monitor once`.

- Parameters:
  - `name` (required): Exact Ethernet interface name e.g. `"ether1"`, `"ether2"`

- Example:
  ```
  monitor_ethernet_interface(name="ether1")
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
