# Devices

The managed devices themselves: which devices the server knows about, and the per-device safe-mode session.
Source: [`src/mcp_mikrotik/scope/devices/`](../../../src/mcp_mikrotik/scope/devices/).

| Module | What it covers | Reference |
|---|---|---|
| `inventory` | The configured devices (`list_devices`) | [Inventory](inventory.md) |
| `safe_mode` | Enter, commit and roll back a safe-mode session on a device | [Safe Mode](safe-mode.md) |
