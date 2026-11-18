# Installation

## Prerequisites

- Python 3.10 or newer
- A MikroTik RouterOS device reachable over SSH (RouterOS 7 is the tested version)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for the `uvx` install and for
  running from source; the `pip` and Docker installs do not need it

## Add it to your MCP client

Most clients start the server themselves, so this is the only step you need.

**Claude Code:**

```bash
claude mcp add --transport stdio mikrotik \
  --env MIKROTIK_HOST=192.168.88.1 \
  --env MIKROTIK_USERNAME=admin \
  --env MIKROTIK_PASSWORD=your_password \
  -- uvx mcp-server-mikrotik
```

> **Windows PowerShell:** PowerShell drops a bare `--` when it runs the `claude` command, which then fails with
> `missing required argument 'commandOrUrl'`. Write the separator as `'--'`, or run the command from Git Bash or cmd.
> If the server then shows `Failed to connect` with error `-32022`, see
> [Claude Code](../integrations/claude-code.md#troubleshooting).

**Clients configured with JSON** (Claude Desktop, Cursor and others):

```json
{
  "mcpServers": {
    "mikrotik": {
      "command": "uvx",
      "args": ["mcp-server-mikrotik"],
      "env": {
        "MIKROTIK_HOST": "192.168.88.1",
        "MIKROTIK_USERNAME": "admin",
        "MIKROTIK_PASSWORD": "your_password"
      }
    }
  }
}
```

See the [integration guides](../integrations/README.md) for SSH keys and client-specific
steps, and [Inventory](../reference/inventory/README.md) to manage several devices.

### MCP Registry

The server is listed on the [MCP Registry](https://registry.modelcontextprotocol.io) as
`io.github.wiresage/mikrotik-mcp`. That name identifies the listing and is not something
`claude mcp add` can install: `claude mcp add io.github.wiresage/mikrotik-mcp` fails with
`missing required argument 'commandOrUrl'`. Use the command above instead.

## Install from PyPI

### uvx (recommended)

Run the published package directly — `uvx` fetches `mcp-server-mikrotik` and its
dependencies into an isolated, cached environment, so there is nothing to install
into your system Python or clean up afterwards:

```bash
# Run the server (stdio, default)
uvx mcp-server-mikrotik

# Run with SSE transport
uvx mcp-server-mikrotik --mcp.transport sse

# Run with streamable HTTP transport
uvx mcp-server-mikrotik --mcp.transport streamable-http
```

Without connection settings the server targets `127.0.0.1` as `admin` with an empty
password. Set your router with the [options below](#cli-options) or the matching
`MIKROTIK_*` [environment variables](#environment-variables):

```bash
uvx mcp-server-mikrotik --host 192.168.88.1 --username admin --password your_password
```

<details>
<summary>Alternative: using pip</summary>

For a persistent install, install the published package from PyPI and launch it
as a module:

```bash
# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install the published package
pip install mcp-server-mikrotik

# Run the server (stdio, default)
python -m mcp_mikrotik

# Run with SSE transport
python -m mcp_mikrotik --mcp.transport sse

# Run with streamable HTTP transport
python -m mcp_mikrotik --mcp.transport streamable-http
```

</details>

## Run from source (contributors)

```bash
# Clone the repository
git clone https://github.com/wiresage/mikrotik-mcp.git
cd mikrotik-mcp

# Provision the exact locked environment (creates .venv automatically)
uv sync --frozen

# Run the server
uv run mcp-server-mikrotik
```

`uv sync --frozen` installs the versions pinned in `uv.lock`, plus the test tooling.
See the [Contributing Guide](../../CONTRIBUTING.md#development-setup) for running the
tests and changing dependencies.

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--host` | MikroTik device IP/hostname | `127.0.0.1` |
| `--username` | SSH username | `admin` |
| `--password` | SSH password | _(empty)_ |
| `--key-filename` | Path to an SSH private key | _(none)_ |
| `--allow-ssh-agent` | Authenticate with keys offered by the SSH agent through `SSH_AUTH_SOCK` | `false` |
| `--ssh-agent-key` | Restrict agent authentication to the matching key: a full public-key line, its base64 blob, or a `SHA256:` fingerprint; requires `--allow-ssh-agent` | _(none)_ |
| `--port` | SSH port | `22` |
| `--inventory` | Multiple devices, as an inline YAML or JSON list; takes precedence over `--inventory-file` and the single-device options | _(empty)_ |
| `--inventory-file` | Path to a YAML file holding the inventory | _(none)_ |
| `--read-only` | Expose only tools that do not modify RouterOS or its file store | `false` |
| `--sensitive-hiding` | Redact credentials and private key material from client-visible output | `false` |
| `--command-timeout` | Seconds a command may wait for the device before the call fails (`MIKROTIK_COMMAND_TIMEOUT`) | `180` |
| `--mcp.transport` | Transport type: `stdio`, `sse`, `streamable-http` | `stdio` |
| `--mcp.host` | HTTP server listen address | `0.0.0.0` |
| `--mcp.port` | HTTP server listen port | `8000` |
| `--mcp.allowed-hosts` | Comma-separated `Host` header allowlist for HTTP transports | _(empty)_ |
| `--mcp.allowed-origins` | Comma-separated `Origin` header allowlist for HTTP transports | _(empty)_ |
| `--mcp.allowed-ips` | Comma-separated client IP addresses and CIDR networks allowed to use HTTP transports | _(empty)_ |

`--read-only` limits the MCP tool catalogue only. Use a restricted RouterOS
account for actual write protection.

`--sensitive-hiding` redacts recognized passwords, passphrases, private and
preshared keys, authentication and encryption keys, tokens, secrets, and SNMP
communities from tool results, MCP notifications, exceptions, and server logs.
It also omits `download_file` and `generate_wireguard_client_config`, whose
payloads cannot be safely field-redacted, and prevents export tools from using
RouterOS `show-sensitive`. Public keys, addresses, usernames, and SSIDs remain
visible. Arbitrary unlabelled secrets in free-form log messages or comments
cannot be identified reliably.

HTTP-based transports (`sse`, `streamable-http`) expose a `GET /health` endpoint for health checks. This endpoint is **not available** in `stdio` mode.

## Docker Installation

Use Docker when you want an isolated runtime or a long-running HTTP service.

### Official prebuilt image (GitHub Container Registry)

A multi-arch image (`linux/amd64` + `linux/arm64`) is published to GHCR, so you
can pull it directly instead of building from source:

```bash
# Latest release
docker pull ghcr.io/wiresage/mikrotik-mcp:latest

# A specific version (matches the git tag, without the leading v)
docker pull ghcr.io/wiresage/mikrotik-mcp:<version>
```

| Tag | Points to |
|-----|-----------|
| `latest` | The most recent release |
| `X.Y.Z` | A specific released version; the matching PyPI version is `X.Y.Z.0` |
| `X.Y` | The latest patch of a minor line |
| `sha-<short>` | A specific commit |

In the examples below, substitute `ghcr.io/wiresage/mikrotik-mcp:latest` for
`mikrotik-mcp` to use the prebuilt image instead of a locally built one.

### Build from source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/wiresage/mikrotik-mcp.git
   cd mikrotik-mcp
   ```

2. **Build the Docker image:**
   ```bash
   docker build -t mikrotik-mcp .
   ```

   The image installs the runtime dependencies from `uv.lock` (no test tooling), so a
   rebuild gives the same versions every time.

3. **Run with stdio (default, for IDE integration):**

   Add this to your `~/.cursor/mcp.json`:
   ```json
   {
     "mcpServers": {
       "mikrotik-mcp-server": {
         "command": "docker",
         "args": [
           "run",
           "--rm",
           "-i",
           "-e", "MIKROTIK_HOST=192.168.88.1",
           "-e", "MIKROTIK_USERNAME=sshuser",
           "-e", "MIKROTIK_PASSWORD=your_password",
           "-e", "MIKROTIK_PORT=22",
           "mikrotik-mcp"
         ]
       }
     }
   }
   ```

4. **Run with SSE or streamable HTTP transport:**

   ```bash
   docker run --rm -p 8000:8000 \
     -e MIKROTIK_HOST=192.168.88.1 \
     -e MIKROTIK_USERNAME=sshuser \
     -e MIKROTIK_PASSWORD=your_password \
     -e MIKROTIK_MCP__TRANSPORT=sse \
     mikrotik-mcp
   ```

   The server will be available at `http://localhost:8000/sse` (SSE) or `http://localhost:8000/mcp` (streamable HTTP).

   The image's entrypoint takes `--transport`, not `--mcp.transport`. Prefer the
   environment variables below for other settings.

   #### Environment Variables

   These apply outside Docker too. The defaults shown are the image's; without
   Docker, `MIKROTIK_HOST` defaults to `127.0.0.1`.

   | Variable | Description | Default |
   |----------|-------------|---------|
   | `MIKROTIK_HOST` | MikroTik device IP/hostname | `192.168.88.1` |
   | `MIKROTIK_USERNAME` | SSH username | `admin` |
   | `MIKROTIK_PASSWORD` | SSH password | _(empty)_ |
   | `MIKROTIK_KEY_FILENAME` | Path to an SSH private key; in Docker, a path inside the container | _(none)_ |
   | `MIKROTIK_ALLOW_SSH_AGENT` | Set to `true` to authenticate with keys offered by the SSH agent through `SSH_AUTH_SOCK` | `false` |
   | `MIKROTIK_SSH_AGENT_KEY` | Restrict agent authentication to the matching key: a full public-key line, its base64 blob, or a `SHA256:` fingerprint. Requires `MIKROTIK_ALLOW_SSH_AGENT=true` | _(empty)_ |
   | `MIKROTIK_PORT` | SSH port | `22` |
   | `MIKROTIK_READ_ONLY` | Set to `true` to expose only tools that do not modify RouterOS or its file store | `false` |
   | `MIKROTIK_SENSITIVE_HIDING` | Set to `true` to redact recognized credentials and private key material | `false` |
   | `MIKROTIK_COMMAND_TIMEOUT` | Seconds a command may wait for the device before the call fails | `180` |
   | `MIKROTIK_INVENTORY` | Multiple devices, written inline in YAML (or its JSON subset). Takes precedence over `MIKROTIK_INVENTORY_FILE` and the flat single-device settings above. See [Inventory](../reference/inventory/README.md). | _(empty)_ |
   | `MIKROTIK_INVENTORY_FILE` | Path **inside the container** to a YAML file holding the inventory — mount it as a volume | _(empty)_ |
   | `MIKROTIK_MCP__TRANSPORT` | Transport type: `stdio`, `sse`, `streamable-http` | `stdio` |
   | `MIKROTIK_MCP__HOST` | HTTP server listen address | `0.0.0.0` |
   | `MIKROTIK_MCP__PORT` | HTTP server listen port | `8000` |
   | `MIKROTIK_MCP__ALLOWED_HOSTS` | Comma-separated `Host` header allowlist for the HTTP transports (DNS-rebinding protection). Set to your domain behind a reverse proxy; `*` disables the check. | _(empty)_ |
   | `MIKROTIK_MCP__ALLOWED_ORIGINS` | Comma-separated `Origin` header allowlist for the HTTP transports. | _(empty)_ |
   | `MIKROTIK_MCP__ALLOWED_IPS` | Comma-separated client IP addresses and CIDR networks allowed to use HTTP transports | _(empty; unrestricted)_ |

   > **Read-only deployments:** Set `MIKROTIK_READ_ONLY=true` to keep modifying
   > tools out of the MCP tool catalogue. Also use a RouterOS account with only
   > the permissions it needs (ideally read-only): this is the enforcement layer
   > that protects the router if another SSH client or a server defect bypasses
   > the MCP catalogue.

### Docker Compose

For a long-running, self-hosted setup, use an HTTP-based transport
(`sse` or `streamable-http`) so MCP clients can connect over the network. The
`stdio` transport is meant for direct IDE integration where the client attaches
to the process's stdin/stdout, not for a standalone background service.

```yaml
services:
  mikrotik-mcp:
    image: ghcr.io/wiresage/mikrotik-mcp:latest
    container_name: mikrotik-mcp
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      MIKROTIK_HOST: "192.168.88.1"
      MIKROTIK_USERNAME: "admin"
      MIKROTIK_PASSWORD: "change-me"
      MIKROTIK_PORT: "22"                      # SSH port of the RouterOS device
      MIKROTIK_MCP__TRANSPORT: "streamable-http"
      MIKROTIK_MCP__HOST: "0.0.0.0"
      MIKROTIK_MCP__PORT: "8000"
```

```bash
docker compose up -d
```

#### Managing several devices

To manage a fleet, give the container an **inventory** instead of the flat
single-device settings. The inventory is a YAML file on your host, and it
**must be mounted into the container as a volume** — the image ships `/config`
as the mount point. A mounted file is also the safer channel: unlike an
environment variable, its contents do not show up in `docker inspect`.

`inventory.yaml` (a ready-to-copy template ships at the repository root as
[`inventory.example.yml`](../../inventory.example.yml)):

```yaml
- title: TitleA
  host: 192.168.88.1
  port: 22
  username: admin
  password: change-me
  region: NL
  tags: [branch]

- title: TitleB
  host: 192.168.89.1
  port: 22
  username: admin
  key_filename: /config/keys/id_ed25519
```

With `docker run`:

```bash
docker run --rm -i \
  -v "$PWD/inventory.yaml:/config/inventory.yaml:ro" \
  -e MIKROTIK_INVENTORY_FILE=/config/inventory.yaml \
  ghcr.io/wiresage/mikrotik-mcp:latest
```

With Docker Compose:

```yaml
services:
  mikrotik-mcp:
    image: ghcr.io/wiresage/mikrotik-mcp:latest
    container_name: mikrotik-mcp
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./inventory.yaml:/config/inventory.yaml:ro
    environment:
      MIKROTIK_INVENTORY_FILE: "/config/inventory.yaml"
      MIKROTIK_MCP__TRANSPORT: "streamable-http"
      MIKROTIK_MCP__HOST: "0.0.0.0"
      MIKROTIK_MCP__PORT: "8000"
```

A `key_filename` is a path inside the container, so mount that key as well and
make it readable by uid 1000.

If a mount is inconvenient, the inventory can go inline in
`MIKROTIK_INVENTORY` using YAML flow syntax (no escaped quotes; JSON also
works, since it is a YAML subset), or via the `--inventory` /
`--inventory-file` entrypoint arguments. Inline always wins over the file.

> Two traps the entrypoint catches with an explicit error rather than starting
> a server with no devices:
>
> - The container runs as **uid 1000** (`mcpuser`), so the mounted file must
>   be readable by that uid — `chmod 644 inventory.yaml` is usually enough.
> - If `inventory.yaml` does not exist on the host when the container starts,
>   Docker silently creates a **directory** in its place. Create the file
>   before starting the container.

When an inventory is set it takes precedence and `MIKROTIK_HOST` /
`MIKROTIK_USERNAME` / `MIKROTIK_PASSWORD` / `MIKROTIK_PORT` /
`MIKROTIK_ALLOW_SSH_AGENT` / `MIKROTIK_SSH_AGENT_KEY` are ignored, so you
can drop them. The entrypoint also stops applying its `192.168.88.1` default
in that case, rather than injecting a host nobody asked for. Tools then take
a `device` argument naming the title to target; see
[Inventory](../reference/inventory/README.md).

The server is then reachable at `http://localhost:8000/mcp` (streamable HTTP)
or `http://localhost:8000/sse` (if you set `MIKROTIK_MCP__TRANSPORT: sse`), and
`GET http://localhost:8000/health` returns `OK`.

#### Behind a reverse proxy (or any non-localhost access)

The HTTP transports (`sse` / `streamable-http`) can apply DNS-rebinding
protection, which validates the request's `Host` header. On a non-localhost bind,
including the default `0.0.0.0`, the check stays off until you set an allowlist,
and the server logs a warning. Set one for any deployment reached by a domain or
through a reverse proxy. Requests to `/mcp` with an unlisted host then get
**HTTP 421 "Invalid Host header"**, while `/health` still works because it is exempt:

```yaml
    environment:
      MIKROTIK_MCP__TRANSPORT: "streamable-http"
      MIKROTIK_MCP__HOST: "0.0.0.0"
      # Allowlist the Host header(s) clients use to reach the server:
      MIKROTIK_MCP__ALLOWED_HOSTS: "mcp.example.com"
      # Allowlist the Origin header(s) for browser-based clients:
      MIKROTIK_MCP__ALLOWED_ORIGINS: "https://app.example.com"
```

Both accept a **comma-separated** list, e.g.:

```yaml
      MIKROTIK_MCP__ALLOWED_HOSTS: "mcp.example.com, mcp.example.com:*, 192.168.1.50:8000"
      MIKROTIK_MCP__ALLOWED_ORIGINS: "https://app.example.com, https://admin.example.com"
```

- Append `:*` to a host (e.g. `mcp.example.com:*`) to allow it on any port.
- Set `MIKROTIK_MCP__ALLOWED_HOSTS: "*"` to disable the host check entirely.
- Always set `MIKROTIK_MCP__ALLOWED_HOSTS` together with
  `MIKROTIK_MCP__ALLOWED_ORIGINS`. Origins alone turn the protection on with an
  empty host list, which rejects every request.
- On a localhost bind with no allowlist, only localhost hosts and origins are accepted.

#### Restricting client IP addresses

`MIKROTIK_MCP__ALLOWED_IPS` limits all HTTP endpoints, including `/mcp`,
`/sse`, `/messages/`, and `/health`, to specific IPv4 or IPv6 addresses and
networks. Requests from other addresses receive HTTP 403. Leave it unset to
preserve unrestricted access:

```yaml
    environment:
      MIKROTIK_MCP__TRANSPORT: "streamable-http"
      MIKROTIK_MCP__ALLOWED_IPS: "192.168.1.50, 10.20.0.0/16, 2001:db8::/48"
```

Addresses and CIDR networks are validated at startup. CIDRs must use a network
address, so use `10.0.0.0/8`, not `10.0.0.1/8`.

The allowlist uses the client address supplied by Uvicorn. For direct
connections, no additional configuration is needed. Behind a reverse proxy,
set Uvicorn's `FORWARDED_ALLOW_IPS` environment variable to the proxy address
or network so the allowlist sees the original address from `X-Forwarded-For`:

```yaml
    environment:
      MIKROTIK_MCP__ALLOWED_IPS: "192.168.1.0/24"
      FORWARDED_ALLOW_IPS: "172.18.0.0/16"
```

Only trust addresses controlled by your proxy. Setting `FORWARDED_ALLOW_IPS=*`
allows direct clients to spoof their source address through forwarded headers.

> ⚠️ Passing `MIKROTIK_PASSWORD` as an environment variable makes it visible via
> `docker inspect`. See [SECURITY.md](../../SECURITY.md) for safer alternatives.
