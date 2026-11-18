# Netwatch Monitoring

A read-only view over `/tool netwatch`. A configuration export shows which
probes exist; it cannot show whether a monitored host is up right now. This
tool returns both: the configuration, and the live state.

## `list_netwatch`

Lists the netwatch probes with their live status and measurements. Runs
`/tool netwatch print detail`, then reads the live state with a second command
(`print detail` returns no read-only argument but `status`).

- Parameters:
  - `host_filter` (optional): Filter by host (substring match)
  - `comment_filter` (optional): Filter by comment (substring match)
  - `status_filter` (optional): Filter by status, for example `down` to list
    only what is currently failing (exact match)
  - `type_filter` (optional): Filter by probe type, for example `icmp` (exact match)
  - `include_source` (optional, default `False`): Include the `up-script`,
    `down-script` and `test-script` properties
- Notes:
  - The answer has two blocks. The configuration comes first, then a
    `LIVE STATE` block with `status`, `since` (the time of the last transition)
    and, on an ICMP probe, the last test's numbers: `rtt-avg`, `loss-percent`
    and `failed-tests`. Match the two blocks by `host`, or by the `.id` the live
    block carries. If the live state cannot be read, the configuration is still
    returned.
  - The three scripts are withheld by default. A probe fires commands on every
    transition, and those commands are a common place to find a credential in
    clear text, such as a bot token inside a webhook URL or an SMTP `password=`
    on an alert mail. Set `include_source=True` only when you intend to read
    them; the output is passed through the server's redaction either way, but
    redaction is pattern-based and is not a guarantee.
  - A probe with no `src-address` follows whichever WAN is active, so it keeps
    reporting across a failover; one pinned to a source address reports that
    path only.
  - Answers "No netwatch probes found matching the criteria." when nothing matches.
- Examples:
  ```
  list_netwatch(status_filter="down")
  list_netwatch(host_filter="1.1.1.1", type_filter="icmp")
  ```
