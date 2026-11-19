# PoE (Power over Ethernet) Monitoring

Read-only tools for inspecting Power-over-Ethernet status and configuration on
PoE-capable MikroTik devices, under `/interface ethernet poe`.

> PoE is a hardware feature — these tools return data only on devices with
> PoE-out ports. On hardware without PoE (e.g. CHR/virtual routers) they report
> that no PoE data is available.

## `get_poe_monitor`

Reads **real-time** PoE monitor data (PoE-out status, voltage, current, power)
for one or more ethernet interfaces. Runs
`/interface ethernet poe monitor <interfaces> once`.

- Parameters:
  - `interfaces` (required): comma-separated ethernet interface name(s)

- Examples:
  ```
  get_poe_monitor(interfaces="ether1")
  get_poe_monitor(interfaces="ether9-ap,ether10-ap,ether11-ap,ether12-ap")
  ```

## `list_poe`

Lists the PoE-out configuration (PoE-out mode, priority) of PoE-capable
ethernet interfaces. Runs `/interface ethernet poe print`.

- Parameters:
  - `interface_filter` (optional): partial name match, e.g. `"ether"`

- Examples:
  ```
  list_poe()                          # all PoE-capable interfaces
  list_poe(interface_filter="ether")  # interfaces whose name contains "ether"
  ```

## `get_poe_settings`

Gets the detailed PoE-out settings of a specific ethernet interface. Runs
`/interface ethernet poe print detail where name=<name>`.

- Parameters:
  - `name` (required): exact ethernet interface name

- Example:
  ```
  get_poe_settings(name="ether1")
  ```
