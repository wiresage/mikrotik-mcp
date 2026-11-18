# Usage with Claude Code

## Quick Setup

```bash
claude mcp add --transport stdio mikrotik \
  -- uvx mcp-server-mikrotik \
  --host <HOST> --username <USERNAME> --password <PASSWORD>
```

## Setup with Environment Variables (recommended)

Keeps credentials out of the command line:

```bash
claude mcp add --transport stdio mikrotik \
  --env MIKROTIK_HOST=192.168.88.1 \
  --env MIKROTIK_USERNAME=admin \
  --env MIKROTIK_PASSWORD=your_password \
  -- uvx mcp-server-mikrotik
```

## Setup with SSH Key

1. Generate a dedicated key:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/mcp-server-mikrotik -N "" -C "mcp-server-mikrotik"
   ```

2. Copy the public key to your MikroTik router:

   ```bash
   # Upload the key file
   scp ~/.ssh/mcp-server-mikrotik.pub admin@192.168.88.1:/

   # Import it on the router
   ssh admin@192.168.88.1 "/user ssh-keys import public-key-file=mcp-server-mikrotik.pub user=admin"
   ```

3. Add the server to Claude Code:

   ```bash
   claude mcp add --transport stdio mikrotik \
     -- uvx mcp-server-mikrotik \
     --host 192.168.88.1 --username admin --key-filename ~/.ssh/mcp-server-mikrotik
   ```

## Verify

Inside Claude Code, run `/mcp` to check that the server is connected and all tools are listed.

## Troubleshooting

**`missing required argument 'commandOrUrl'` on Windows.** PowerShell drops a bare `--` when it runs the
`claude` command, so `uvx mcp-server-mikrotik` is swallowed by the preceding `--env` option. Write the
separator as `'--'`, or run the command from Git Bash or cmd. The server name goes before the `--env` options.

**`Failed to connect` with error `-32022`.** The first start through `uvx` can take several seconds: it
downloads the package, and importing the MCP SDK alone takes a couple of seconds. Claude Code probes a stdio
server for about two seconds before it falls back, and a server that answers the probe late then rejects the
`initialize` request that follows. Checked with Claude Code 2.1.278. Add `MCP_PROTOCOL_NEGOTIATION=legacy` to
the server's environment so that Claude Code skips the probe:

```bash
claude mcp add --transport stdio mikrotik \
  --env MCP_PROTOCOL_NEGOTIATION=legacy \
  --env MIKROTIK_HOST=192.168.88.1 \
  --env MIKROTIK_USERNAME=admin \
  --env MIKROTIK_PASSWORD=your_password \
  -- uvx mcp-server-mikrotik
```

## Manage

```bash
claude mcp list            # list all configured servers
claude mcp get mikrotik    # show server details
claude mcp remove mikrotik # remove the server
```
