# System

Read-only views over `/system`: what the board is, how it is doing, and which
RouterOS it runs.

## `get_system_resource`

Reports uptime, RouterOS version, board name, architecture, CPU and memory.
Runs `/system resource print`.

- Example:
  ```
  get_system_resource()
  ```

`free-memory` against `total-memory` and `cpu-load` are the two numbers worth
reading before blaming the network for a slow device.

## `get_system_health`

Reports the board sensors: voltage, temperature, fan and PSU state. Runs
`/system health print`.

- Example:
  ```
  get_system_health()
  ```

Many boards carry no sensors at all and legitimately report nothing; an empty
answer means "this model does not measure it", not "the reading failed".

## `get_system_clock`

Reports the device clock, time zone and DST setting. Runs
`/system clock print`.

- Example:
  ```
  get_system_clock()
  ```

Log timestamps are only as trustworthy as this.

## `get_system_routerboard`

Reports the model, serial number and bootloader firmware revision. Runs
`/system routerboard print`.

- Example:
  ```
  get_system_routerboard()
  ```

`current-firmware` against `upgrade-firmware` is the RouterBOOT bootloader,
which is upgraded separately from RouterOS and is easy to leave behind after
a package upgrade.

## `list_system_packages`

Lists the installed RouterOS packages and which are disabled. Runs
`/system package print`.

- Example:
  ```
  list_system_packages()
  ```

## `get_system_package_update`

Reports the installed RouterOS version against the latest on its channel.
Runs `/system package update print`.

- Example:
  ```
  get_system_package_update()
  ```

This reads the stored result of the last check; it does not contact
MikroTik. `latest-version` can therefore be stale or empty on a device that
has never checked or cannot reach the update server.
