### User Management

#### `add_user`
Adds a new user to MikroTik device.
- Parameters:
  - `name` (required): Username
  - `password` (required): Password
  - `group` (optional): User group
  - `address` (optional): Allowed address
  - `comment` (optional): Description
  - `disabled` (optional): Disable user
- Example:
  ```
  add_user(name="john", password="secure123", group="full")
  ```

#### `list_users`
Lists users on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `group_filter` (optional): Filter by group
  - `disabled_only` (optional): Show only disabled users
  - `active_only` (optional): Show only active users
- Example:
  ```
  list_users(group_filter="full")
  ```

#### `get_user`
Gets detailed information about a specific user.
- Parameters:
  - `name` (required): Username
- Example:
  ```
  get_user(name="john")
  ```

#### `update_user`
Updates an existing user on MikroTik device.
- Parameters:
  - `name` (required): Current username
  - `new_name` (optional): New username
  - `password` (optional): New password
  - `group` (optional): New group
  - `address` (optional): New allowed address
  - `comment` (optional): New description
  - `disabled` (optional): Enable/disable user
- Example:
  ```
  update_user(name="john", group="read")
  ```

#### `remove_user`
Removes a user from MikroTik device.
- Parameters:
  - `name` (required): Username
- Example:
  ```
  remove_user(name="john")
  ```

#### `disable_user`
Disables a user account.
- Parameters:
  - `name` (required): Username
- Example:
  ```
  disable_user(name="john")
  ```

#### `enable_user`
Enables a user account.
- Parameters:
  - `name` (required): Username
- Example:
  ```
  enable_user(name="john")
  ```

#### `add_user_group`
Adds a new user group to MikroTik device.
- Parameters:
  - `name` (required): Group name
  - `policy` (required): Policy list
  - `skin` (optional): UI skin
  - `comment` (optional): Description
- Example:
  ```
  add_user_group(name="operators", policy=["read", "write", "reboot"])
  ```

#### `list_user_groups`
Lists user groups on MikroTik device.
- Parameters:
  - `name_filter` (optional): Filter by name
  - `policy_filter` (optional): Filter by policy
- Example:
  ```
  list_user_groups()
  ```

#### `get_user_group`
Gets detailed information about a specific user group.
- Parameters:
  - `name` (required): Group name
- Example:
  ```
  get_user_group(name="operators")
  ```

#### `update_user_group`
Updates an existing user group on MikroTik device.
- Parameters:
  - `name` (required): Current group name
  - `new_name` (optional): New name
  - `policy` (optional): New policy list
  - `skin` (optional): New UI skin
  - `comment` (optional): New description
- Example:
  ```
  update_user_group(name="operators", policy=["read", "write"])
  ```

#### `remove_user_group`
Removes a user group from MikroTik device.
- Parameters:
  - `name` (required): Group name
- Example:
  ```
  remove_user_group(name="operators")
  ```

#### `get_active_users`
Gets currently active/logged-in users.
- Parameters: None
- Example:
  ```
  get_active_users()
  ```

#### `disconnect_user`
Disconnects an active user session.
- Parameters:
  - `user_id` (required): User session ID
- Example:
  ```
  disconnect_user(user_id="*1")
  ```

#### `export_user_config`
Exports user configuration to a file.
- Parameters:
  - `filename` (optional): Export filename
- Example:
  ```
  export_user_config(filename="users.rsc")
  ```

#### `set_user_ssh_keys`
Sets SSH public keys for a user.
- Parameters:
  - `username` (required): Username
  - `key_file` (required): SSH key filename
- Example:
  ```
  set_user_ssh_keys(username="john", key_file="id_rsa.pub")
  ```

#### `list_user_ssh_keys`
Lists SSH keys for a specific user.
- Parameters:
  - `username` (required): Username
- Example:
  ```
  list_user_ssh_keys(username="john")
  ```

#### `remove_user_ssh_key`
Removes an SSH key.
- Parameters:
  - `key_id` (required): SSH key ID
- Example:
  ```
  remove_user_ssh_key(key_id="*1")
  ```

