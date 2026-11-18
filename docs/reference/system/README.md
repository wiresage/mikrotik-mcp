# System Information

Read-only views over `/system`: what the board is, how it is doing and which
RouterOS it runs. They answer the questions an export header only hints at
(model, serial, version) and the ones it cannot carry at all: uptime, CPU and
memory load, board voltage and temperature, and whether a newer release is
available. None of these tools takes a parameter.

## `get_system_resource`

Reports uptime, RouterOS version, board name, architecture, CPU and memory.
Runs `/system resource print`.

- Notes:
  - `free-memory` against `total-memory`, and `cpu-load`, are the two numbers
    worth reading before blaming the network for a slow device. On the
    low-power boards a single packet-sniffing tool can saturate the CPU on its
    own.
- Example:
  ```
  get_system_resource()
  ```

## `get_system_health`

Reports the board sensors: voltage, temperature, fan and PSU state. Runs
`/system health print`.

- Notes:
  - Many boards carry no sensors at all and legitimately report nothing. The
    tool then answers that no health sensors were reported, which means "this
    model does not measure it", not "the reading failed".
- Example:
  ```
  get_system_health()
  ```

## `get_system_clock`

Reports the device clock, time zone and DST setting. Runs `/system clock print`.

- Notes:
  - Log timestamps are only as trustworthy as this. A device without a working
    time source dates its own evidence wrongly, which matters when correlating
    an incident across sites.
- Example:
  ```
  get_system_clock()
  ```

## `get_system_routerboard`

Reports the model, serial number and bootloader firmware revision. Runs
`/system routerboard print`.

- Notes:
  - `current-firmware` against `upgrade-firmware` is the RouterBOOT bootloader,
    which is upgraded separately from RouterOS and is easy to leave behind after
    a package upgrade.
  - Devices that are not a RouterBOARD, such as CHR or other virtual routers,
    answer that no RouterBOARD information is available.
- Example:
  ```
  get_system_routerboard()
  ```

## `list_system_packages`

Lists the installed RouterOS packages and which are disabled. Runs
`/system package print`.

- Example:
  ```
  list_system_packages()
  ```

## `get_system_package_update`

Reports the installed RouterOS version against the latest on its update
channel. Runs `/system package update print`.

- Notes:
  - This reads the stored result of the last check; it does not contact
    MikroTik. `latest-version` can therefore be stale or empty on a device that
    has never checked or cannot reach the update server.
- Example:
  ```
  get_system_package_update()
  ```
