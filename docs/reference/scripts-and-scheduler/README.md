# Scripts and Schedulers

Tools for managing and executing RouterOS stored scripts, active script jobs, environment variables, and scheduled tasks (`/system script` and `/system scheduler`).

## Stored Scripts (`/system script`)

### `list_scripts`
Lists stored scripts with metadata (name, owner, policy, run count, last started). By default, script bodies are withheld to prevent credential exposure unless `include_source=True` is explicitly passed.

- Parameters:
  - `name_filter` (optional): Filter scripts by substring in name
  - `include_source` (optional): Include script source code (default: `False`)
  - `device` (optional): Target device

### `get_script`
Retrieves full details, execution statistics, security policies, and source code of a specific script by name.

- Parameters:
  - `name`: Script name
  - `device` (optional): Target device

### `run_script`
Executes a stored RouterOS script by name and returns its output (or confirms execution if silent).

- Parameters:
  - `name`: Script name to run
  - `device` (optional): Target device

### `create_script`
Creates a new stored RouterOS script with code and security policies.

- Parameters:
  - `name`: Script name
  - `source`: Script source code
  - `policy` (optional): Policy string (e.g. `"read,write,policy,test"`)
  - `dont_require_permissions` (optional): Run without checking permissions (default: `False`)
  - `comment` (optional): Script comment
  - `device` (optional): Target device

### `update_script`
Updates an existing script's code, policies, or permissions.

- Parameters:
  - `name`: Script name
  - `source` (optional): Updated script source code
  - `policy` (optional): Updated policies
  - `dont_require_permissions` (optional): Update permissions flag
  - `comment` (optional): Updated comment
  - `device` (optional): Target device

### `remove_script`
Removes a stored script from the router.

- Parameters:
  - `name`: Script name to remove
  - `device` (optional): Target device

---

## Script Jobs and Environment

### `list_script_jobs`
Lists currently running background script jobs, start time, and owner.

- Parameters:
  - `device` (optional): Target device

### `remove_script_job`
Stops and terminates a running script job by ID (useful for killing hung or looping scripts).

- Parameters:
  - `job_id`: Job ID (e.g. `"*1"` or `"0"`)
  - `device` (optional): Target device

### `list_script_environment`
Lists active RouterOS global variables and environment entries stored in memory.

- Parameters:
  - `device` (optional): Target device

### `remove_script_environment`
Removes a global variable from the RouterOS script environment.

- Parameters:
  - `name`: Variable name to remove
  - `device` (optional): Target device

---

## Scheduled Tasks (`/system scheduler`)

### `list_schedulers`
Lists scheduled tasks with interval, next run, and run count. `on-event` code is withheld unless `include_source=True` is provided.

- Parameters:
  - `name_filter` (optional): Filter tasks by name substring
  - `include_source` (optional): Include on-event code (default: `False`)
  - `device` (optional): Target device

### `get_scheduler`
Retrieves full details, interval, next run, and on-event code of a specific scheduler.

- Parameters:
  - `name`: Scheduler name
  - `device` (optional): Target device

### `create_scheduler`
Creates a new scheduled task in RouterOS.

- Parameters:
  - `name`: Scheduler name
  - `on_event`: RouterOS command or script to execute
  - `interval`: Repetition interval (e.g. `"1d"`, `"1h"`, `"00:10:00"`, default: `"1d"`)
  - `start_date` (optional): Start date
  - `start_time` (optional): Start time
  - `policy` (optional): Policy string
  - `comment` (optional): Comment
  - `disabled` (optional): Create in disabled state (default: `False`)
  - `device` (optional): Target device

### `update_scheduler`
Updates interval, on-event commands, timing, or comment of an existing scheduler.

- Parameters:
  - `name`: Scheduler name
  - `on_event` (optional): Updated event code
  - `interval` (optional): Updated interval
  - `start_date` (optional): Updated start date
  - `start_time` (optional): Updated start time
  - `policy` (optional): Updated policies
  - `comment` (optional): Updated comment
  - `disabled` (optional): Update enabled/disabled state
  - `device` (optional): Target device

### `enable_scheduler`
Enables a scheduled task.

- Parameters:
  - `name`: Scheduler name
  - `device` (optional): Target device

### `disable_scheduler`
Disables a scheduled task without deleting it.

- Parameters:
  - `name`: Scheduler name
  - `device` (optional): Target device

### `remove_scheduler`
Deletes a scheduled task.

- Parameters:
  - `name`: Scheduler name
  - `device` (optional): Target device
