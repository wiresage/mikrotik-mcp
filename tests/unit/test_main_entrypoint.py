"""Smoke test for the ``python -m mcp_mikrotik`` module entry point (T3 / AC-07).

The console script ``mcp-server-mikrotik`` and ``uvx mcp-server-mikrotik`` both
resolve to ``mcp_mikrotik.server:main``. The pip-alternative install path
documented in installation.md launches via ``python -m mcp_mikrotik``, which
requires a ``__main__`` module that delegates to the same entry point.
"""

import subprocess
import sys


def test_python_m_module_entry_point_resolves():
    """``python -m mcp_mikrotik --help`` starts via server:main and exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "mcp_mikrotik", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"`python -m mcp_mikrotik --help` exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "mcp-server-mikrotik" in result.stdout or "usage" in result.stdout.lower()


def test_main_module_delegates_to_server_main():
    """The ``__main__`` module reuses the exact console-script entry point."""
    import importlib

    main_module = importlib.import_module("mcp_mikrotik.__main__")
    from mcp_mikrotik.server import main

    assert main_module.main is main
