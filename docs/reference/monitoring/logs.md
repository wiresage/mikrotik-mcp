### Log Management

#### `mikrotik_get_logs`
Gets logs from MikroTik device with filtering options.
- Parameters:
  - `topics` (optional): Log topics
  - `action` (optional): Log action
  - `time_filter` (optional): Time filter
  - `message_filter` (optional): Message filter
  - `prefix_filter` (optional): Prefix filter
  - `limit` (optional): Result limit
  - `follow` (optional): Follow logs
  - `print_as` (optional): Output format
- Example:
  ```
  mikrotik_get_logs(topics="firewall", limit=100)
  ```

#### `mikrotik_get_logs_by_severity`
Gets logs filtered by severity level.
- Parameters:
  - `severity` (required): Severity level ("debug", "info", "warning", "error", "critical")
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  mikrotik_get_logs_by_severity(severity="error", limit=50)
  ```

#### `mikrotik_get_logs_by_topic`
Gets logs for a specific topic/facility.
- Parameters:
  - `topic` (required): Log topic
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  mikrotik_get_logs_by_topic(topic="system")
  ```

#### `mikrotik_search_logs`
Searches logs for a specific term.
- Parameters:
  - `search_term` (required): Search term
  - `time_filter` (optional): Time filter
  - `case_sensitive` (optional): Case sensitive search
  - `limit` (optional): Result limit
- Example:
  ```
  mikrotik_search_logs(search_term="login failed")
  ```

#### `mikrotik_get_system_events`
Gets system-related log events.
- Parameters:
  - `event_type` (optional): Event type
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  mikrotik_get_system_events(event_type="reboot")
  ```

#### `mikrotik_get_security_logs`
Gets security-related log entries.
- Parameters:
  - `time_filter` (optional): Time filter
  - `limit` (optional): Result limit
- Example:
  ```
  mikrotik_get_security_logs(limit=100)
  ```

#### `mikrotik_clear_logs`
Clears all logs from MikroTik device.
- Parameters: None
- Example:
  ```
  mikrotik_clear_logs()
  ```

#### `mikrotik_get_log_statistics`
Gets statistics about log entries.
- Parameters: None
- Example:
  ```
  mikrotik_get_log_statistics()
  ```

#### `mikrotik_export_logs`
Exports logs to a file on the MikroTik device.
- Parameters:
  - `filename` (optional): Export filename
  - `topics` (optional): Log topics
  - `time_filter` (optional): Time filter
  - `format` (optional): Export format ("plain" or "csv")
- Example:
  ```
  mikrotik_export_logs(filename="security-logs.txt", topics="firewall")
  ```

#### `mikrotik_monitor_logs`
Monitors logs in real-time for a specified duration.
- Parameters:
  - `topics` (optional): Log topics
  - `action` (optional): Log action
  - `duration` (optional): Monitor duration in seconds
- Example:
  ```
  mikrotik_monitor_logs(topics="firewall", duration=30)
  ```

