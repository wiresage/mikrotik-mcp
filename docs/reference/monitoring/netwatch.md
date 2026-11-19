# Netwatch

Read-only view over `/tool netwatch`: which probes exist and, on an ICMP
probe, whether the monitored host is actually answering right now.

## `list_netwatch`

Lists the netwatch probes with their configuration, then a LIVE STATE block
with `status`, `since` (the timestamp of the last transition) and, on an ICMP
probe, the last test's numbers: `rtt-avg`, `loss-percent`, `failed-tests`.
Match the two blocks by `host`, or by the `.id` the live one carries.

- Parameters:
  - `host_filter` (optional): substring match, e.g. `"10.0.0."`
  - `comment_filter` (optional): substring match
  - `status_filter` (optional): exact match; `"down"` lists what is failing
  - `type_filter` (optional): exact match (`icmp`, `tcp`, `http`, `dns`, `simple`)
  - `include_source` (optional, default `False`)

- Example:
  ```
  list_netwatch(status_filter="down")
  list_netwatch(host_filter="uplink")
  ```

> `include_source=False` (the default) omits `up-script`, `down-script` and
> `test-script`: a probe that alerts through a webhook or e-mail usually
> carries its token or password inline. Set it to `True` only when you intend
> to read those commands; the output is redacted either way, but redaction is
> pattern-based and is not a guarantee.
