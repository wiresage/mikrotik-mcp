# Backup and Export Management

## `mikrotik_create_backup`
Creates a system backup on MikroTik device.
- Parameters:
  - `name` (optional): Backup filename
  - `dont_encrypt` (optional): Don't encrypt backup
  - `include_password` (optional): Include passwords
  - `comment` (optional): Description
- Example:
  ```
  mikrotik_create_backup(name="backup-2024-01-01")
  ```

## `mikrotik_list_backups`
Lists backup files on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `include_exports` (optional): Include export files
- Example:
  ```
  mikrotik_list_backups()
  ```

## `mikrotik_create_export`
Creates a configuration export on MikroTik device.
- Parameters:
  - `name` (optional): Export filename
  - `file_format` (optional): Format ("rsc", "json", "xml")
  - `export_type` (optional): Type ("full", "compact", "verbose")
  - `hide_sensitive` (optional): Hide sensitive data
  - `verbose` (optional): Verbose output
  - `compact` (optional): Compact output
  - `comment` (optional): Description
- Example:
  ```
  mikrotik_create_export(name="config-export", file_format="rsc")
  ```

## `mikrotik_export_section`
Returns a configuration section as an export script, straight from the device.
A genuine read: nothing is written to device storage, so it works on
read-only accounts (`policy=ssh,read`). To produce an export *file* on the
device, use `mikrotik_create_export` instead.
- Parameters:
  - `section` (required): Menu path without leading slash, e.g. `ip firewall filter`
  - `hide_sensitive` (optional): Keep secrets out of the output (default true)
  - `compact` (optional): Compact output
- Example:
  ```
  mikrotik_export_section(section="ip firewall filter")
  ```

## `mikrotik_download_file`
Downloads a file from MikroTik device.
- Parameters:
  - `filename` (required): Filename to download
  - `file_type` (optional): File type ("backup" or "export")
- Example:
  ```
  mikrotik_download_file(filename="backup-2024-01-01.backup")
  ```

## `mikrotik_upload_file`
Uploads a file to MikroTik device.
- Parameters:
  - `filename` (required): Filename
  - `content_base64` (required): Base64 encoded content
- Example:
  ```
  mikrotik_upload_file(filename="config.rsc", content_base64="...")
  ```

## `mikrotik_restore_backup`
Restores a system backup on MikroTik device.
- Parameters:
  - `filename` (required): Backup filename
  - `password` (optional): Backup password
- Example:
  ```
  mikrotik_restore_backup(filename="backup-2024-01-01.backup")
  ```

## `mikrotik_import_configuration`
Imports a configuration script file.
- Parameters:
  - `filename` (required): Script filename
  - `run_after_reset` (optional): Run after reset
  - `verbose` (optional): Verbose output
- Example:
  ```
  mikrotik_import_configuration(filename="config.rsc")
  ```

## `mikrotik_remove_file`
Removes a file from MikroTik device.
- Parameters:
  - `filename` (required): Filename to remove
- Example:
  ```
  mikrotik_remove_file(filename="old-backup.backup")
  ```

## `mikrotik_backup_info`
Gets detailed information about a backup file.
- Parameters:
  - `filename` (required): Backup filename
- Example:
  ```
  mikrotik_backup_info(filename="backup-2024-01-01.backup")
  ```
