# Inventory (multiple devices)

MikroTik MCP can manage a fleet of devices from one server. Devices are
declared in an **inventory**; each entry has a unique `title`, which is the
identifier tools use to target that device.

With no inventory configured the server behaves exactly as before: a single
device built from `MIKROTIK_HOST` / `MIKROTIK_USERNAME` / … , and the `device`
argument can be omitted everywhere.

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
      "command": "python",
      "args": ["-m", "mcp_mikrotik.server"],
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
      "command": "python",
      "args": ["-m", "mcp_mikrotik.server"],
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

Lists the devices this server manages — title, host, port, username, tags and
region. **Credentials are never returned.**

```
list_devices()
```

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
