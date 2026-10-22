#!/bin/sh
set -e

usage() {
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Single device:"
    echo "  --host HOST           MikroTik device IP/hostname"
    echo "  --username USERNAME   SSH username"
    echo "  --password PASSWORD   SSH password"
    echo "  --allow-ssh-agent     Authenticate with keys offered by the SSH agent"
    echo "  --ssh-agent-key KEY   Restrict agent authentication to the matching key"
    echo "  --port PORT           SSH port (default: 22)"
    echo ""
    echo "Multiple devices (inventory) — takes precedence over the options above:"
    echo "  --inventory YAML      Inventory as a YAML (or JSON) list of devices"
    echo "  --inventory-file PATH Path to a YAML file holding the inventory"
    echo ""
    echo "Other:"
    echo "  --read-only           Expose only read-only tools"
    echo "  --sensitive-hiding    Hide credentials and private key material"
    echo "  --transport TYPE      Transport: stdio, sse, streamable-http (default: stdio)"
    echo "  --help                Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  MIKROTIK_HOST            MikroTik device IP/hostname"
    echo "  MIKROTIK_USERNAME        SSH username"
    echo "  MIKROTIK_PASSWORD        SSH password"
    echo "  MIKROTIK_ALLOW_SSH_AGENT Authenticate with keys offered by the SSH agent (default: false)"
    echo "  MIKROTIK_SSH_AGENT_KEY   Restrict agent authentication to the matching key"
    echo "  MIKROTIK_PORT            SSH port (default: 22)"
    echo "  MIKROTIK_INVENTORY       Inventory as a YAML (or JSON) list of devices"
    echo "  MIKROTIK_INVENTORY_FILE  Path to a YAML file holding the inventory"
    echo "  MIKROTIK_READ_ONLY       Expose only read-only tools (default: false)"
    echo "  MIKROTIK_SENSITIVE_HIDING Hide credentials and private key material (default: false)"
    echo "  MIKROTIK_MCP__TRANSPORT  Transport type (default: stdio)"
    echo ""
    echo "Examples:"
    echo "  $0 --host 192.168.88.1 --username admin --password admin123"
    echo "  $0 --host 192.168.88.1 --username admin --password admin123 --transport sse"
    echo "  MIKROTIK_HOST=192.168.88.1 MIKROTIK_MCP__TRANSPORT=sse $0"
    echo "  $0 --inventory-file /config/inventory.yaml --transport streamable-http"
    exit 1
}

MIKROTIK_MCP__TRANSPORT="${MIKROTIK_MCP__TRANSPORT:-stdio}"

while [ $# -gt 0 ]; do
    case $1 in
        --host)
            MIKROTIK_HOST="$2"
            shift 2
            ;;
        --username)
            MIKROTIK_USERNAME="$2"
            shift 2
            ;;
        --password)
            MIKROTIK_PASSWORD="$2"
            shift 2
            ;;
        --allow-ssh-agent)
            MIKROTIK_ALLOW_SSH_AGENT=true
            shift
            ;;
        --ssh-agent-key)
            MIKROTIK_SSH_AGENT_KEY="$2"
            shift 2
            ;;
        --port)
            MIKROTIK_PORT="$2"
            shift 2
            ;;
        --inventory)
            MIKROTIK_INVENTORY="$2"
            shift 2
            ;;
        --inventory-file)
            MIKROTIK_INVENTORY_FILE="$2"
            shift 2
            ;;
        --read-only)
            MIKROTIK_READ_ONLY=true
            shift
            ;;
        --sensitive-hiding)
            MIKROTIK_SENSITIVE_HIDING=true
            shift
            ;;
        --transport)
            MIKROTIK_MCP__TRANSPORT="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            break
            ;;
    esac
done

export MIKROTIK_MCP__TRANSPORT
[ -n "${MIKROTIK_ALLOW_SSH_AGENT:-}" ] && export MIKROTIK_ALLOW_SSH_AGENT
[ -n "${MIKROTIK_SSH_AGENT_KEY:-}" ] && export MIKROTIK_SSH_AGENT_KEY
[ -n "${MIKROTIK_READ_ONLY:-}" ] && export MIKROTIK_READ_ONLY
[ -n "${MIKROTIK_SENSITIVE_HIDING:-}" ] && export MIKROTIK_SENSITIVE_HIDING

# An inventory describes the whole fleet, so it takes precedence over the
# single-device settings. Don't fall back to the 192.168.88.1 default in that
# case: inventing a host nobody asked for reads as if it still applied. Values
# the user passed with `docker run -e` are already in the environment and stay
# there; they are simply ignored by the config layer.
if [ -n "${MIKROTIK_INVENTORY:-}" ] || [ -n "${MIKROTIK_INVENTORY_FILE:-}" ]; then
    # -f as well as -r: when the host file named in a bind mount does not
    # exist, Docker silently creates a DIRECTORY at both ends — which is
    # readable, and would sail past a bare -r check.
    if [ -n "${MIKROTIK_INVENTORY_FILE:-}" ] && { [ ! -f "$MIKROTIK_INVENTORY_FILE" ] || [ ! -r "$MIKROTIK_INVENTORY_FILE" ]; }; then
        if [ -d "$MIKROTIK_INVENTORY_FILE" ]; then
            echo "Error: '$MIKROTIK_INVENTORY_FILE' is a directory, not a file." >&2
            echo "" >&2
            echo "This usually means the host file named in the -v mount did not exist," >&2
            echo "so Docker created a directory in its place. Create the YAML file on" >&2
            echo "the host first, then recreate the container." >&2
        else
            echo "Error: inventory file '$MIKROTIK_INVENTORY_FILE' is not readable inside the container." >&2
            echo "" >&2
            echo "Mount it, for example:" >&2
            echo "  -v \"\$PWD/inventory.yaml:/config/inventory.yaml:ro\"" >&2
            echo "" >&2
            echo "The container runs as uid 1000 (mcpuser), so the file on the host must be" >&2
            echo "readable by that uid — 'chmod 644 inventory.yaml' is usually enough." >&2
        fi
        exit 1
    fi
    [ -n "${MIKROTIK_INVENTORY:-}" ] && export MIKROTIK_INVENTORY
    [ -n "${MIKROTIK_INVENTORY_FILE:-}" ] && export MIKROTIK_INVENTORY_FILE
else
    MIKROTIK_HOST="${MIKROTIK_HOST:-192.168.88.1}"
    MIKROTIK_USERNAME="${MIKROTIK_USERNAME:-admin}"
    MIKROTIK_PASSWORD="${MIKROTIK_PASSWORD:-}"
    MIKROTIK_PORT="${MIKROTIK_PORT:-22}"
    export MIKROTIK_HOST
    export MIKROTIK_USERNAME
    export MIKROTIK_PASSWORD
    export MIKROTIK_PORT
fi

if [ $# -eq 0 ]; then
    exec mcp-server-mikrotik
else
    exec "$@"
fi
