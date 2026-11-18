### Log Management

#### `get_logs`
Gets logs from MikroTik device with filtering options.
- Parameters:
  - `topics` (optional): Log topics
  - `time_filter` (optional): Time filter
  - `message_filter` (optional): Message filter
  - `prefix_filter` (optional): Prefix filter
  - `limit` (optional): Result limit
  - `print_as` (optional): Output format: `plain` (default), `detail` or `terse`
- Example:
  ```
  get_logs(topics="firewall", limit=100)
  ```

#### `get_logs_by_severity`
Gets logs filtered by severity level.
- Parameters:
  - `severity` (required): Severity level ("debug", "info", "warning", "error", "critical")
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  get_logs_by_severity(severity="error", limit=50)
  ```

#### `get_logs_by_topic`
Gets logs for a specific topic/facility.
- Parameters:
  - `topic` (required): Log topic
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  get_logs_by_topic(topic="system")
  ```

#### `search_logs`
Searches logs for a specific term.
- Parameters:
  - `search_term` (required): Search term
  - `time_filter` (optional): Time filter
  - `case_sensitive` (optional): Case sensitive search
  - `limit` (optional): Result limit
- Example:
  ```
  search_logs(search_term="login failed")
  ```

#### `get_system_events`
Gets system-related log events.
- Parameters:
  - `event_type` (optional): Event type
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  get_system_events(event_type="reboot")
  ```

#### `get_security_logs`
Gets security-related log entries.
- Parameters:
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  get_security_logs(limit=100)
  ```

#### `clear_logs`
Clears all logs from MikroTik device.
- Parameters: None
- Example:
  ```
  clear_logs()
  ```

#### `get_log_statistics`
Gets statistics about log entries.
- Parameters: None
- Example:
  ```
  get_log_statistics()
  ```

#### `export_logs`
Exports logs to a `.txt` file on the MikroTik device.
- Parameters:
  - `filename` (optional): Export filename (default `logs_export_<timestamp>`; RouterOS adds `.txt`)
  - `topics` (optional): Log topics
  - `time_filter` (optional): Time filter
- Example:
  ```
  export_logs(filename="security-logs.txt", topics="firewall")
  ```

#### `monitor_logs`
Watches for new log entries for a limited duration and returns the ones that arrived.
- Parameters:
  - `topics` (optional): Log topics
  - `duration` (optional, default `10`): Seconds to wait for new entries, capped at 60
- Example:
  ```
  monitor_logs(topics="firewall", duration=30)
  ```

