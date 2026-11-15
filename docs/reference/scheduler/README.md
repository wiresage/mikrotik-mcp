# Scheduler and Scripts

Read-only views over `/system scheduler` and `/system script`.

Script bodies and the `on-event` commands of a scheduler are withheld by
default. A stored RouterOS script is a common place to find a credential in
clear text, such as an FTP password for a backup job or an SMTP login for an
alert, so a read tool that dumps every body by default turns one careless
script into an exposure. Pass `include_source=True` when you need the code; the
output is then passed through the server's redaction, which only recognises
labelled secrets and is not a guarantee.

## `list_schedulers`

Lists the scheduled tasks with their interval, next run and run count. Runs
`/system scheduler print detail`.

- Parameters:
  - `name_filter` (optional): Filter by name (substring match)
  - `include_source` (optional, default `False`): Include the `on-event`
    commands, which can carry a bot token or a password inside a URL
- Notes:
  - Read `next-run` together with `interval`. A scheduler whose `run-count` is
    not advancing is firing into a script that errors out. RouterOS does not
    surface that here; it shows up in the log under the `script` topic.
  - Answers "No schedulers found matching the criteria." when nothing matches.
- Examples:
  ```
  list_schedulers()
  list_schedulers(name_filter="backup", include_source=True)
  ```

## `list_scripts`

Lists the stored scripts: owner, policy, run count and last start. Runs
`/system script print detail`.

- Parameters:
  - `name_filter` (optional): Filter by name (substring match)
  - `include_source` (optional, default `False`): Include the script body
- Notes:
  - `policy` is what the script may do when it runs, which can exceed what the
    user who scheduled it may do interactively.
  - Answers "No scripts found matching the criteria." when nothing matches.
- Examples:
  ```
  list_scripts()
  list_scripts(name_filter="failover", include_source=True)
  ```
