# Managing a Whole MikroTik Fleet from One MCP Server

> Originally published on Medium:
> [Managing a Whole MikroTik Fleet from One MCP Server](https://medium.com/@sir.jeff.nasseri/managing-a-whole-mikrotik-fleet-from-one-mcp-server-60245de07073)
> by [@jeff-nasseri](https://medium.com/@sir.jeff.nasseri)

For a long time, [mikrotik-mcp](https://github.com/wiresage/mikrotik-mcp) could talk to exactly one router. You gave it a host, a username and a password, and your AI assistant could manage that single device over SSH. That was fine for a home lab, but the moment you have a second router (a branch office, a datacenter box, a test bench), you had to run a second server instance with its own configuration.

Not anymore. mikrotik-mcp now supports a device **inventory**: one server, one configuration file, and as many MikroTik devices as you want. The LLM discovers the fleet on its own, targets devices by name, and gets a helpful error (not silent misbehavior) when it points at a device that does not exist.

In this article I will walk through how to configure the inventory YAML file, how to wire it up so the MCP server connects to multiple devices, and some example prompts to get you started.

## The inventory YAML file

The inventory is a plain YAML list. Each entry is one device. Network engineers live in YAML anyway, so this should feel familiar:

```yaml
- title: office-core
  host: 192.168.88.1
  port: 22
  username: admin
  password: change-me
  tags: [office, core]
  region: NL

- title: branch-berlin
  host: 10.20.0.1
  username: admin
  key_filename: /config/keys/id_ed25519
  tags: [branch]
  region: DE
```

There is a ready-to-copy template in the repository root: [`inventory.example.yml`](https://github.com/wiresage/mikrotik-mcp/blob/master/inventory.example.yml).

Only two fields are required:

| Field | Required | What it does |
|---|---|---|
| `title` | yes | The unique name the LLM uses to target this device. Matching is case-insensitive. |
| `host` | yes | IP address or hostname |
| `port` | no | SSH port, defaults to `22` |
| `username` | no | Defaults to `admin` |
| `password` | no | Skip it when you use `key_filename` |
| `key_filename` | no | Path to an SSH private key. Prefer this over a password. |
| `allow_ssh_agent` | no | Authenticate with keys offered by the SSH agent through `SSH_AUTH_SOCK`. |
| `ssh_agent_key` | no | Restrict agent authentication to the matching key; requires `allow_ssh_agent: true`. |
| `tags` | no | Free-form labels, like `[branch, eu]` |
| `region` | no | Free-form label, like `NL` |

A few things worth knowing:

- **`title` is the whole targeting story.** Pick names you would naturally use in a prompt, like `office-core` or `branch-berlin`, because that is literally what you will type.
- **Titles must be unique**, and the server checks that at startup, case-insensitively.
- **The file is a secret.** It holds credentials for your whole fleet, so `chmod 600` it, keep it out of version control, and prefer SSH keys over passwords. Validation errors never echo the file contents back, so a typo cannot leak a password into a log, but the file itself is still yours to protect.
- **Broken inventories fail fast.** A missing file, a YAML syntax error or an invalid entry stops the server at startup with one clear message naming the position and field. You will not discover a typo three tool calls deep.
- JSON still works too. JSON is a subset of YAML, so if you already have an `inventory.json` from an earlier setup, it keeps loading unchanged.

## Connecting the MCP server to multiple devices

There are two ways to hand the inventory to the server, and they cover different situations.

### Option 1: point at the file (recommended)

Set `MIKROTIK_INVENTORY_FILE` in the `env` block of your MCP client configuration (Claude Desktop, Cursor, or whatever client you use):

```json
{
  "mcpServers": {
    "mikrotik": {
      "command": "python",
      "args": ["-m", "mcp_mikrotik.server"],
      "env": {
        "MIKROTIK_INVENTORY_FILE": "/etc/mikrotik/inventory.yaml"
      }
    }
  }
}
```

This keeps your client config short and your credentials out of it.

### Option 2: inline, no file at all

If you would rather keep everything in one place, put the inventory itself in `MIKROTIK_INVENTORY`. Environment values have to be strings, so you cannot nest a real JSON object there, but YAML flow syntax gives you the same structure with zero escaped quotes:

```json
{
  "mcpServers": {
    "mikrotik": {
      "command": "python",
      "args": ["-m", "mcp_mikrotik.server"],
      "env": {
        "MIKROTIK_INVENTORY": "[{title: office-core, host: 192.168.88.1, username: admin, password: change-me}, {title: branch-berlin, host: 10.20.0.1, username: admin}]"
      }
    }
  }
}
```

When both are set, the inline inventory wins and the file is ignored. And if you configure neither, nothing changes for you: the classic single-device variables (`MIKROTIK_HOST`, `MIKROTIK_USERNAME`, `MIKROTIK_PASSWORD`, `MIKROTIK_PORT`) keep working exactly as before.

### Running in Docker

If you run mikrotik-mcp from the Docker image, the inventory file lives on your host, so you have to **mount it into the container as a volume**. The image ships `/config` as the mount point:

```bash
docker run --rm -i \
  -v "$PWD/inventory.yaml:/config/inventory.yaml:ro" \
  -e MIKROTIK_INVENTORY_FILE=/config/inventory.yaml \
  ghcr.io/wiresage/mikrotik-mcp:latest
```

Or with Docker Compose, for a long-running setup:

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

Two classic traps, both of which the container now catches with an explicit error instead of starting a broken server:

1. The container runs as uid 1000, so the mounted file must be readable by that uid. `chmod 644 inventory.yaml` is usually enough.
2. If `inventory.yaml` does not exist on the host when you start the container, Docker silently creates a directory in its place. Create the file first, then start the container.

A mounted file is also safer than the inline environment variable in Docker, because environment values show up in `docker inspect` and file contents do not.

## How the LLM actually uses the fleet

Once the server is up, three things make multi-device work smooth:

1. **A `list_devices` tool.** The model can ask the server what it manages and gets back the titles, hosts, tags and regions. Credentials are never returned.
2. **A `device` argument on every tool.** All of the existing tools (interfaces, VLANs, firewall, DNS, DHCP, WireGuard, backups and so on) accept an optional `device` parameter naming the title to target.
3. **Self-correcting errors.** With one device configured, `device` can be omitted and everything works like the old single-device setup. With several devices, omitting it (or typo-ing a title) returns an error that lists the valid titles, so the model fixes itself on the next call instead of quietly running your command on the wrong router.

Each command opens its own SSH connection and closes it when done, so parallel sessions cannot step on each other. And safe mode is tracked per device: enabling safe mode on one router does not touch the others.

## Example prompts

Here are some prompts I actually use. Notice that once you name your devices well, the prompts read like you are talking to a network engineer, not an API.

**Discover the fleet:**

> Which MikroTik devices do you manage? Show me their hosts and tags.

**Read from one device:**

> List the interfaces on office-core and tell me which ones are actually running.

**Configure one device:**

> On branch-berlin, create VLAN 30 on ether2, name it vlan30-guests, and give it the address 10.30.0.1/24.

**Compare devices:**

> Compare the firewall filter rules on office-core and branch-berlin and summarize what is different.

**Work across the fleet:**

> Add a static DNS record printer.lan pointing to 192.168.88.50 on every device tagged office.

**Make risky changes safely:**

> Enable safe mode on office-core first. Then add a forward-chain drop rule for 203.0.113.50. Show me the rule, and if it looks right, commit the safe mode session.

That last one deserves a note: MikroTik safe mode means the changes are held in memory and revert automatically if the session drops before you commit. Having the LLM work inside safe mode gives you an undo button for AI-driven changes, per device, which is exactly where you want one.

## Wrapping up

The inventory turns mikrotik-mcp from a single-router tool into a fleet tool: one YAML file, one server, and natural-language control over every MikroTik device you own. Point `MIKROTIK_INVENTORY_FILE` at your inventory, ask "which devices do you manage?", and go from there.

The project lives at [github.com/wiresage/mikrotik-mcp](https://github.com/wiresage/mikrotik-mcp). Issues and pull requests are welcome, and if you try it against your own fleet, I would love to hear how it goes.
