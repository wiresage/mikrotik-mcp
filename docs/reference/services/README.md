# IP Services

A read-only view over `/ip service`: which management services answer, on which
port, and from where. This is the device's remote-management attack surface in
one table.

## `list_ip_services`

Lists the management services with their port and address restriction. Runs
`/ip service print detail`.

- Parameters:
  - `name_filter` (optional): Filter by service name, for example `winbox`,
    `ssh`, `api`, `www`, `www-ssl`, `ftp` or `telnet` (substring match)
  - `enabled_only` (optional, default `False`): Hide the disabled services,
    which is the list that actually describes exposure
- Notes:
  - An empty address restriction (the `address` property, printed as
    `available-from` on RouterOS 7.25) means the service is unrestricted. On a
    router whose WAN holds a public address that means the service is published
    to the internet, whether or not the port was changed from its default.
  - Dynamic entries for the sessions that are open right now (flag `c`) are
    listed too.
  - `ftp` deserves its own look: RouterOS also serves SFTP file transfers
    through the SSH service to users whose group holds the `ftp` policy, so the
    two are not the same control.
  - Answers "No IP services found matching the criteria." when nothing matches.
- Examples:
  ```
  list_ip_services(enabled_only=True)
  list_ip_services(name_filter="winbox")
  ```
