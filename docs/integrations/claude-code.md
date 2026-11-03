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

## Manage

```bash
claude mcp list            # list all configured servers
claude mcp get mikrotik    # show server details
claude mcp remove mikrotik # remove the server
```
