# Scheduler and Scripts

Read-only views over `/system scheduler` and `/system script`: what runs,
when it runs next, and how often it has run.

## `list_schedulers`

Lists the scheduled tasks with their interval, next run and run count.

- Parameters:
  - `name_filter` (optional): substring match
  - `include_source` (optional, default `False`)

- Example:
  ```
  list_schedulers(name_filter="backup")
  ```

Read `next-run` together with `interval`: a scheduler whose `run-count` is
not advancing is firing into a script that errors out, which RouterOS does
not surface here — it shows up in the log under the `script` topic.

> `include_source=False` (the default) omits `on-event`, because a scheduler
> can carry commands inline, and those routinely hold a bot token or a
> password inside a URL. Set it to `True` only when you intend to read the
> commands; the output is redacted either way.

## `list_scripts`

Lists the stored scripts: owner, policy, run count and last start.

- Parameters:
  - `name_filter` (optional): substring match
  - `include_source` (optional, default `False`)

- Example:
  ```
  list_scripts(name_filter="backup")
  ```

`policy` is what the script may do when it runs, which can exceed what the
user who scheduled it may do interactively.

> `include_source=False` (the default) omits the script body: bodies
> routinely hold credentials in clear text. Set it to `True` only when you
> intend to read the code; the output is redacted either way.
