# Using MCPO with MikroTik MCP Server

This guide shows how to expose your MikroTik MCP server as a RESTful API using MCPO (MCP-to-OpenAPI proxy).

## Prerequisites

- Python 3.10+
- MikroTik MCP server already set up
- `uv` package manager (recommended) or `pip`

## Installation

```bash
# Using uvx (no installation needed)
uvx mcpo --help

# Or using pip
pip install mcpo
mcpo --help
```

## Configuration

Create a `mcp-config.json` file in your project directory:

```json
{
  "mcpServers": {
    "mikrotik-mcp-server": {
      "command": "uvx",
      "args": [
        "mcp-server-mikrotik",
        "--password", "admin",
        "--host", "192.168.88.1",
        "--port", "22",
        "--username", "admin"
      ],
      "env": {}
    }
  }
}
```

**Note:** Adjust the MikroTik connection parameters (`host`, `username`, `password`, `port`) according to your setup.

<details>
<summary>Alternative: using pip/python</summary>

If you installed `mcp-server-mikrotik` with pip instead of uv, use `python -m` in the config:

```json
{
  "mcpServers": {
    "mikrotik-mcp-server": {
      "command": "python",
      "args": [
        "-m", "mcp_mikrotik",
        "--password", "admin",
        "--host", "192.168.88.1",
        "--port", "22",
        "--username", "admin"
      ],
      "env": {}
    }
  }
}
```

</details>

## Starting the MCPO Server

```bash
# Start MCPO with API key authentication
uvx mcpo --port 8000 --api-key "your-secret-key" --config ./mcp-config.json

# Or without authentication (not recommended for production)
uvx mcpo --port 8000 --config ./mcp-config.json

# Using pip-installed mcpo
mcpo --port 8000 --api-key "your-secret-key" --config ./mcp-config.json
```

The server will start and display:
- Server running on `http://0.0.0.0:8000`
- Interactive API docs available at `http://localhost:8000/docs`

### cURL Examples

**List IP Addresses:**
```bash
curl -X POST http://localhost:8000/mikrotik-mcp-server/mikrotik_list_ip_addresses \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{}'
```

