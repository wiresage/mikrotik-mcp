"""Module entry point so ``python -m mcp_mikrotik`` launches the server.

Delegates to the same ``mcp_mikrotik.server:main`` used by the
``mcp-server-mikrotik`` console script (and ``uvx mcp-server-mikrotik``), so
every documented launch path goes through one entry point.
"""

from mcp_mikrotik.server import main

if __name__ == "__main__":
    main()
