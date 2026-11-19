# Inventory (multiple devices)

MikroTik MCP can manage a fleet of devices from one server. Devices are
declared in an **inventory**; each entry has a unique `title`, which is the
identifier tools use to target that device.
x
With no inventory configured the server can start with **no devices at all**:
ask the agent to enroll one with `add_device` and it persists for the next
start. A single device built from `MIKROTIK_HOST` / `MIKROTIK_USERNAME` / … is
still used whenever any of those settings is supplied, and a configured
inventory always wins.

## Configuring the inventory

The inventory is written in **YAML**. Two sources are supported:

| Variable | Purpose |
|---|---|
| `MIKROTIK_INVENTORY_FILE` | path to a YAML file holding the inventory (recommended) |
| `MIKROTIK_INVENTORY` | the inventory written inline |

When both are set, **the inline `MIKROTIK_INVENTORY` wins** and the file is
ignored. When neither is set, the flat single-device settings apply.

A broken inventory (missing file, bad YAML, invalid entry) stops the server at
startup with one clear message, so mistakes surface immediately rather than at
the first tool call.

### The YAML file (recommended)

A ready-to-copy template ships at the repository root:
[`inventory.example.yml`](../../../inventory.example.yml).

`inventory.yaml`:

```yaml
- title: TitleA
  host: 127.0.0.1
  port: 22
  username: admin
  password: admin
  tags: [tag1, tag2]
  region: NL

- title: TitleB
  host: 192.168.88.1
  port: 22
  username: admin
  key_filename: /keys/id_ed25519
  tags: [tag1, tag3]
  region: DE
```

Point the server at it from the MCP client config — these belong in the
server's **`env`** block, which is the channel a client forwards to the
spawned process:

```json
{
  "mcpServers": {
    "mikrotik-mcp-server": {
      "command": "uvx",
      "args": ["mcp-server-mikrotik"],
      "env": {
        "MIKROTIK_INVENTORY_FILE": "/etc/mikrotik/inventory.yaml"
      }
    }
  }
}
```

A file keeps the config readable and the secrets out of the client config.

### Inline, without a file

To skip the file entirely, put the inventory itself in `MIKROTIK_INVENTORY`.
Environment values are single strings, so a nested object cannot appear under
`env` directly — but YAML's inline (flow) syntax gives the same structure with
no escaped quotes:

```json
{
  "mcpServers": {
    "mikrotik-mcp-server": {
      "command": "uvx",
      "args": ["mcp-server-mikrotik"],
      "env": {
        "MIKROTIK_INVENTORY": "[{title: TitleA, host: 127.0.0.1, username: admin, password: admin, region: NL, tags: [tag1]}, {title: TitleB, host: 192.168.88.1, username: admin, region: DE}]"
      }
    }
  }
}
```

JSON is a subset of YAML, so a plain JSON array (quotes escaped) is accepted
here too — existing configs keep working unchanged.

### Device fields

| Field | Required | Notes |
|---|---|---|
| `title` | yes | Unique identifier the LLM passes as `device`. Matching is case-insensitive. |
| `host` | yes | IP or hostname |
| `port` | no | SSH port, default `22` |
| `username` | no | default `admin` |
| `password` | no | omit when using `key_filename` |
| `key_filename` | no | path to an SSH private key (preferred over a password) |
| `allow_ssh_agent` | no | authenticate with keys offered by the SSH agent through `SSH_AUTH_SOCK`; default `false` |
| `ssh_agent_key` | no | restrict agent authentication to the matching key: a full public-key line, its base64 blob, or a `SHA256:` fingerprint; requires `allow_ssh_agent: true` |
| `tags` | no | free-form labels, e.g. `[branch, eu]` |
| `region` | no | free-form label, e.g. `NL` |

## Selecting a device

Every device-scoped tool accepts an optional `device` argument:

- **No device configured** — `list_devices` says so and, when dynamic
  management is available, points the agent at `add_device`.
- **One device configured** — omit `device`; that device is used.
- **More than one** — pass the `title`. Omitting it returns an error that lists
  the available devices, as does an unknown title, so the caller can correct
  itself immediately.

```
list_devices()                                  # discover the fleet
list_interfaces(device="TitleA")                # target one device
create_vlan_interface(device="TitleB", name="vlan100", vlan_id=100, interface="ether1")
```

## `list_devices`

Lists the devices this server manages — title, host, port, username, tags,
region and whether the device came from configuration or a runtime enrollment.
**Credentials are never returned.** With no devices configured it explains how
to add one.

```
list_devices()
```

## Runtime device management

**On by default.** The agent can discover adjacent routers with
[`list_mikrotik_neighbors`](../neighbors/README.md), enroll one, use it, and
remove it again — no YAML edit, no restart:

```
list_devices()                                             # empty on a fresh server
list_mikrotik_neighbors()                                  # what is adjacent
add_device(title="BranchA", host="10.0.0.1", username="admin",
           password="...", tags=["branch"])
list_interfaces(device="BranchA")                          # now it is reachable
remove_device(title="BranchA")                             # forget it again
```

| Variable / flag | Purpose |
|---|---|
| `MIKROTIK_ALLOW_DYNAMIC_DEVICES` (`--allow-dynamic-devices` / `--no-allow-dynamic-devices`) | register `add_device` and `remove_device`; default `true` |
| `MIKROTIK_DYNAMIC_INVENTORY_FILE` (`--dynamic-inventory-file`) | state file enrollments are written to; default `$XDG_CONFIG_HOME/mikrotik-mcp/dynamic-inventory.yaml` (`~/.config/...` without XDG) |

Enrollments are written to the state file atomically with mode `600`, and the
file's directory is created `700` when missing. The file is the same YAML list
shape as `MIKROTIK_INVENTORY_FILE`, is read at startup, and enrolled devices
therefore survive a restart. Keep it out of version control; the repository's
`.gitignore` already covers `dynamic-inventory.yaml`.

- `list_devices` marks every device as `source: config` (inventory or settings)
  or `source: runtime` (enrolled by the agent).
- **Only runtime devices can be removed.** A `config` device is refused with a
  message saying it comes from the inventory file or settings, so the agent
  cannot delete configuration a human owns.
- `--read-only` hides both tools and stops `list_devices` from mentioning them.
  `--no-allow-dynamic-devices` removes them from the catalogue entirely.
- The password goes into the state file only. It never appears in a tool
  result, a notification or a log line — but the agent receives it in the tool
  call, so it is in the client's conversation transcript. Prefer
  `key_filename` or SSH-agent authentication when that matters.
- `host` is an IPv4 address or a hostname. IPv6 and any other syntax are
  refused before anything is written.
- A title already in the inventory is refused, at enrollment and again at load.
- A device that cannot be reached is **still enrolled** and reported as
  unreachable — enrollment and connectivity are independent.

## Docker

When running the image, the inventory YAML file **must be mounted into the
container as a volume** — the file lives on your host, and the container can
only see what is mounted in. The image ships `/config` as the mount point:

```bash
docker run --rm -i \
  -v "$PWD/inventory.yaml:/config/inventory.yaml:ro" \
  -e MIKROTIK_INVENTORY_FILE=/config/inventory.yaml \
  ghcr.io/wiresage/mikrotik-mcp:latest
```

Or with Compose:

```yaml
services:
  mikrotik-mcp:
    image: ghcr.io/wiresage/mikrotik-mcp:latest
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./inventory.yaml:/config/inventory.yaml:ro
    environment:
      MIKROTIK_INVENTORY_FILE: "/config/inventory.yaml"
      MIKROTIK_MCP__TRANSPORT: "streamable-http"
```

The entrypoint also takes `--inventory '<yaml>'` and `--inventory-file <path>`.

Once `add_device` works in the container, mount `/config` as a writable volume:
the entrypoint defaults `MIKROTIK_DYNAMIC_INVENTORY_FILE` to
`/config/dynamic-inventory.yaml`, so one volume keeps both the static inventory
and the agent's enrollments across a container replacement. Without a volume,
enrollments live only inside the container's writable layer and disappear when
it is recreated.

A mounted file is preferable to inline `MIKROTIK_INVENTORY`: environment values
are visible in `docker inspect`, file contents are not. Two traps the
entrypoint catches with an explicit error instead of starting a broken server:

- The container runs as **uid 1000** (`mcpuser`), so the mounted file must be
  readable by that uid — `chmod 644 inventory.yaml` is usually enough.
- If the host file does not exist when the container starts, Docker silently
  creates a **directory** at both ends of the mount. Create the YAML file
  before `docker run` / `docker compose up`.

When an inventory is configured it wins, so `MIKROTIK_HOST` /
`MIKROTIK_USERNAME` / `MIKROTIK_PASSWORD` / `MIKROTIK_PORT` /
`MIKROTIK_ALLOW_SSH_AGENT` / `MIKROTIK_SSH_AGENT_KEY` are ignored and can be
dropped.

See [Installation](../../getting-started/installation.md) for the full Docker
setup.

## Connections are per command

Every command opens its own SSH connection to the target device and closes it
when the command finishes. Connections are never pooled or shared.

This matters when more than one client session talks to the same server
process: a shared connection would mean shared fate, so one session
disconnecting, timing out or failing to authenticate would break a command
another session was running against the same device. With a connection per
command the sessions cannot disturb each other.

The trade-off is one SSH handshake per command. On a LAN that is a few tens of
milliseconds; if the device is far away or heavily loaded, expect commands to
cost noticeably more than the RouterOS work alone.

## Safe mode is per device

Safe mode holds a persistent session, and each device has its own. Enabling it
on one device does not affect any other:

```
enable_safe_mode(device="TitleA")
create_filter_rule(device="TitleA", chain="forward", action="drop", ...)
commit_safe_mode(device="TitleA")     # or rollback_safe_mode(device="TitleA")
```

## Two-device test environment

`routeros-docker/docker-compose.yml` starts two RouterOS instances for testing:

| Container | SSH | Suggested title |
|---|---|---|
| `routeros-a` | `127.0.0.1:2222` | RouterA |
| `routeros-b` | `127.0.0.1:2223` | RouterB |

```bash
docker-compose -f routeros-docker/docker-compose.yml up -d
python tests/smoke_multi_device.py
```

> Both routers boot inside QEMU and need roughly two minutes before SSH answers.

## Security

Credentials live in the inventory, so the whole inventory is a secret. Prefer
`key_filename` over `password`, keep the YAML in a file with restricted
permissions rather than inline in a client config, and remember that values
passed as environment variables are visible via `docker inspect` — see
[SECURITY.md](../../../SECURITY.md).

Validation errors never echo the inventory's contents back: a malformed entry
is reported by position and field name only, so a typo cannot leak a password
into a log line or a tool result.
