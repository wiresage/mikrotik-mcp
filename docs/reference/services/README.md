# IP Services

Read-only view over `/ip service`: which management services answer, on which
port, and from where. This is the device's remote-management attack surface
in one table.

## `list_ip_services`

Lists the management services with their port and address restriction. Runs
`/ip service print detail`.

- Parameters:
  - `name_filter` (optional): substring match (`winbox`, `ssh`, `api`, `www`,
    `www-ssl`, `ftp`, `telnet`)
  - `enabled_only` (optional, default `False`)

- Example:
  ```
  list_ip_services()
  list_ip_services(enabled_only=True)
  ```

An empty `address` means unrestricted. Read that together with how the device
is reached: unrestricted on a router whose WAN holds a public address means
the service is published to the internet, whether or not the port was changed
from its default.

`ftp` deserves its own look: RouterOS also serves SFTP file transfers through
the SSH service to users whose group holds the `ftp` policy, so the two are
not the same control.
