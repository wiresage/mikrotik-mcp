"""docker-entrypoint.sh: --help is a request, so it prints the usage and exits 0 (it used to exit 1, which scripts read as a failure)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[2] / "docker-entrypoint.sh"
SH = shutil.which("sh")


@pytest.mark.skipif(SH is None, reason="needs a POSIX sh")
def test_help_prints_the_usage_and_exits_zero():
    result = subprocess.run([SH, str(ENTRYPOINT), "--help"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "Usage:" in result.stdout and "--inventory-file" in result.stdout
