"""The initialize response names the server's version, so a client can show which release it talks to."""

import mcp_mikrotik
from mcp_mikrotik.app import mcp


def test_server_info_carries_the_package_version():
    options = mcp._lowlevel_server.create_initialization_options()
    assert options.server_version == mcp_mikrotik.__version__
    assert options.server_version
