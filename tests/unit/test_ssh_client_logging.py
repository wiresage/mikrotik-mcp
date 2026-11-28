"""A connection that fails inside paramiko leaves one line in the server log, not a traceback.

paramiko's transport thread logs a failed connection at ERROR, one record per traceback line, and
then hands the same exception to the caller, which logs it in one line. The health check of 0.30.0
found that traceback in the server log for a device that accepts TCP but never sends an SSH banner.
"""

import logging
import socket
import threading

import paramiko
import pytest

import mcp_mikrotik.mikrotik_ssh_client as ssh_client
from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient


@pytest.fixture()
def no_banner_port():
    """A port that accepts TCP and never says anything (no SSH banner)."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    held = []
    threading.Thread(target=lambda: held.append(listener.accept()), daemon=True).start()
    yield listener.getsockname()[1]
    listener.close()
    for connection, _ in held:
        connection.close()


def test_no_banner_logs_one_error_line_and_no_traceback(no_banner_port, monkeypatch, caplog):
    monkeypatch.setattr(ssh_client, "CONNECT_TIMEOUT", 1.0)
    with caplog.at_level(logging.INFO):
        assert MikroTikSSHClient("127.0.0.1", "admin", "", None, no_banner_port).connect() is False
        # The same timeout guards the banner and paramiko's wait for it, so the caller can give up
        # first ("No existing session") while the transport thread is still reading; it logs then.
        for thread in threading.enumerate():
            if isinstance(thread, paramiko.Transport):
                thread.join(5)

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert [r.name for r in errors] == ["mcp_mikrotik.mikrotik_ssh_client"]
    assert errors[0].getMessage().startswith("Failed to connect to MikroTik: ")
    assert not [r for r in caplog.records if r.name.startswith("paramiko")]
    assert not any("Traceback" in r.getMessage() for r in caplog.records)


def test_paramiko_transport_errors_are_kept_at_debug(caplog):
    with caplog.at_level(logging.DEBUG, logger="paramiko.transport"):
        logging.getLogger("paramiko.transport").error("Exception (client): Error reading SSH protocol banner")

    records = [r for r in caplog.records if r.name == "paramiko.transport"]
    assert [(r.levelname, r.getMessage()) for r in records] == [
        ("DEBUG", "Exception (client): Error reading SSH protocol banner"),
    ]


def test_paramiko_transport_info_and_warnings_are_untouched(caplog):
    with caplog.at_level(logging.INFO, logger="paramiko.transport"):
        logging.getLogger("paramiko.transport").info("Connected (version 2.0, client ROSSSH)")
        logging.getLogger("paramiko.transport").warning("Oops, unhandled type 3 ('unimplemented')")

    records = [r for r in caplog.records if r.name == "paramiko.transport"]
    assert [(r.levelname, r.getMessage()) for r in records] == [
        ("INFO", "Connected (version 2.0, client ROSSSH)"),
        ("WARNING", "Oops, unhandled type 3 ('unimplemented')"),
    ]
