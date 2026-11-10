# Safe Mode Management

MikroTik Safe Mode protects against accidental misconfigurations by holding all changes in memory only. If the session drops or you explicitly roll back, the router reverts every change automatically. Only a deliberate commit writes changes to permanent storage.

## How Safe Mode Works

1. **Enable** — opens a persistent SSH shell and sends Ctrl+X to the router
2. **Make changes** — every subsequent tool call is routed through the same session
3. **Commit or Rollback** — send a second Ctrl+X to persist, or close the session to revert

> **Important:** While safe mode is active, all MCP tool calls execute inside the persistent interactive shell. A dropped connection (network outage, MCP server crash, etc.) automatically reverts all pending changes.

---

## Tools

### `safe_mode_status`

Returns whether Safe Mode is currently active.

- **Annotation:** `READ`
- **Parameters:** none
- **Returns:** Current state description

**Example response (inactive):**
```
Safe mode is NOT active. Changes take effect and persist immediately.
```

**Example response (active):**
```
Safe mode is ACTIVE. Changes are pending — they are NOT yet persisted.
Call commit_safe_mode to persist or rollback_safe_mode to revert.
```

---

### `enable_safe_mode`

Opens a persistent SSH shell session and activates MikroTik Safe Mode.

- **Annotation:** `WRITE`
- **Parameters:** none
- **Returns:** Confirmation or error message

**Behaviour while active:**
- All subsequent tool calls run inside the same shell session
- Changes are NOT written to flash/NVRAM
- Rebooting the router or dropping the connection reverts everything

**Example response:**
```
Safe mode ENABLED. All changes are temporary — they will be reverted
automatically if the connection drops or you call rollback_safe_mode.
Call commit_safe_mode to make changes permanent.
```

**Error cases:**
- SSH connection failure → returns an `Error: ...` string
- Router does not confirm `<SAFE>` prompt → returns an `Error: ...` string

---

### `commit_safe_mode`

Persists all pending Safe Mode changes and exits Safe Mode.

- **Annotation:** `WRITE`
- **Parameters:** none
- **Returns:** Confirmation or error message

Sends a second Ctrl+X to the router, which exits Safe Mode and writes all in-memory changes to persistent storage (flash/NVRAM). The persistent SSH session is then closed.

**Example response:**
```
Changes committed successfully. Safe mode DISABLED.
```

**Error cases:**
- Safe mode not active → returns "Safe mode is not active. Nothing to commit."

---

### `rollback_safe_mode`

Discards all pending Safe Mode changes by dropping the SSH session.

- **Annotation:** `WRITE`
- **Parameters:** none
- **Returns:** Confirmation message

MikroTik automatically reverts every change from the session when the controlling terminal disconnects. No Ctrl+X is sent — the session is simply dropped, triggering the router's built-in rollback.

**Example response:**
```
Safe mode session closed. MikroTik has reverted all uncommitted changes automatically.
```

**Error cases:**
- Safe mode not active → returns "Safe mode is not active. Nothing to roll back."

---

## Typical Workflow

```
# 1. Check current state
safe_mode_status()

# 2. Enable safe mode before making changes
enable_safe_mode()

# 3. Make changes (routed through persistent session automatically)
create_simple_queue(name="limit-guest", target="192.168.10.0/24", max_limit="5M/5M")
create_filter_rule(chain="input", action="drop", src_address="10.0.0.0/8")

# 4a. If satisfied — persist
commit_safe_mode()

# 4b. If not — revert everything
rollback_safe_mode()
```

---

## Thread Safety

The `SafeModeManager` singleton uses a threading lock internally. Concurrent tool calls while safe mode is active are serialised through the same lock, so parallel MCP requests are safe.

## Connector Integration

When safe mode is active, `execute_mikrotik_command` in `connector.py` automatically detects the active session and routes commands through `SafeModeManager.execute()` instead of opening a new per-command SSH connection. No change to individual tool implementations is required.
