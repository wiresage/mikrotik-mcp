# Installation

## MCP Registry (Recommended)

MikroTik MCP is listed on the [MCP Registry](https://registry.modelcontextprotocol.io) — a community-driven catalog of MCP servers. Registry-aware clients (Claude Desktop, VS Code, Cursor) can install it in one command without manual config file editing.

```bash
claude mcp add io.github.wiresage/mikrotik-mcp
```

The client fetches the server metadata from the registry, installs `mcp-server-mikrotik` from PyPI, and prompts you for the required environment variables (`MIKROTIK_HOST`, `MIKROTIK_USERNAME`, `MIKROTIK_PASSWORD`).

> **PyPI install only:** If your client does not support registry-based install, use one of the manual methods below.

---

## Prerequisites
- Python 3.10+
- MikroTik RouterOS device with API access enabled
- Python dependencies (routeros-api or similar)

## Manual Installation

```bash
# Clone the repository
git clone https://github.com/wiresage/mikrotik-mcp.git
cd mikrotik-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run the server (stdio, default)
mcp-server-mikrotik

# Run with SSE transport
mcp-server-mikrotik --mcp.transport sse

# Run with streamable HTTP transport
mcp-server-mikrotik --mcp.transport streamable-http
```

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--host` | MikroTik device IP/hostname | from config |
| `--username` | SSH username | from config |
| `--password` | SSH password | from config |
| `--key-filename` | SSH key filename | from config |
| `--port` | SSH port | `22` |
| `--read-only` | Expose only tools that do not modify RouterOS or its file store | `false` |
| `--sensitive-hiding` | Redact credentials and private key material from client-visible output | `false` |
| `--command-timeout` | Seconds a command may wait for the device before the call fails (`MIKROTIK_COMMAND_TIMEOUT`) | `180` |
| `--mcp.transport` | Transport type: `stdio`, `sse`, `streamable-http` | `stdio` |
| `--mcp.host` | HTTP server listen address | `0.0.0.0` |
| `--mcp.port` | HTTP server listen port | `8000` |
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

The easiest way to run the MCP MikroTik server is using Docker.

### Official prebuilt image (GitHub Container Registry)

A multi-arch image (`linux/amd64` + `linux/arm64`) is published to GHCR, so you
can pull it directly instead of building from source:

```bash
# Latest release
docker pull ghcr.io/wiresage/mikrotik-mcp:latest

# A specific version (matches the PyPI / git tag version)
docker pull ghcr.io/wiresage/mikrotik-mcp:<version>
```

| Tag | Points to |
|-----|-----------|
| `latest` | The most recent release |
| `X.Y.Z` | A specific released version, aligned with the PyPI release |
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

   **Environment Variables:**

   | Variable | Description | Default |
   |----------|-------------|---------|
   | `MIKROTIK_HOST` | MikroTik device IP/hostname | `192.168.88.1` |
   | `MIKROTIK_USERNAME` | SSH username | `admin` |
   | `MIKROTIK_PASSWORD` | SSH password | _(empty)_ |
   | `MIKROTIK_ALLOW_AGENT` | Set to `true` to authenticate with keys offered by the SSH agent at `SSH_AUTH_SOCK` | `false` |
   | `MIKROTIK_AGENT_KEY` | Use only a matching agent key: a full public-key line, its base64 blob, or a `SHA256:` fingerprint. Requires `MIKROTIK_ALLOW_AGENT=true` | _(empty)_ |
    | `MIKROTIK_PORT` | SSH port | `22` |
    | `MIKROTIK_READ_ONLY` | Set to `true` to expose only tools that do not modify RouterOS or its file store | `false` |
    | `MIKROTIK_SENSITIVE_HIDING` | Set to `true` to redact recognized credentials and private key material | `false` |
   | `MIKROTIK_INVENTORY` | Multiple devices, written inline in YAML (or its JSON subset). Takes precedence over `MIKROTIK_INVENTORY_FILE` and the four variables above. See [Inventory](../reference/inventory/README.md). | _(empty)_ |
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

To manage a fleet, give the container an **inventory** instead of the four
single-device variables. The inventory is a YAML file on your host, and it
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
`MIKROTIK_USERNAME` / `MIKROTIK_PASSWORD` / `MIKROTIK_PORT` are ignored, so you
can drop them. The entrypoint also stops applying its `192.168.88.1` default in
that case, rather than injecting a host nobody asked for. Tools then take a
`device` argument naming the title to target; see
[Inventory](../reference/inventory/README.md).

The server is then reachable at `http://localhost:8000/mcp` (streamable HTTP)
or `http://localhost:8000/sse` (if you set `MIKROTIK_MCP__TRANSPORT: sse`), and
`GET http://localhost:8000/health` returns `OK`.

#### Behind a reverse proxy (or any non-localhost access)

The HTTP transports (`sse` / `streamable-http`) apply DNS-rebinding protection,
which validates the request's `Host` header. When the server is reached on a
custom domain or a non-localhost IP — e.g. through a reverse proxy — you must
allowlist that host, otherwise requests to `/mcp` are rejected with **HTTP 421
"Invalid Host header"** (while `/health` still works, since it is exempt):

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
- If you leave it unset on a non-localhost bind, the check is auto-disabled (a
  warning is logged) so the server still works out of the box.

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
