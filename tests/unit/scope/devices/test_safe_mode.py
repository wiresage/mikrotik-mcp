"""Unit tests for the safe_mode scope tools.

The safe_mode scope calls get_safe_mode_manager() directly (no
execute_mikrotik_command), so we mock the manager singleton rather
than patching the SSH executor.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from mcp_mikrotik.scope.devices.safe_mode import (
    mikrotik_safe_mode_status,
    mikrotik_enable_safe_mode,
    mikrotik_commit_safe_mode,
    mikrotik_rollback_safe_mode,
)


@pytest.fixture()
def mock_manager():
    manager = MagicMock()
    manager.is_active = False
    manager.status.return_value = "Safe mode is NOT active."
    manager.enable.return_value = "Safe mode ENABLED."
    manager.commit.return_value = "Changes committed successfully. Safe mode DISABLED."
    manager.rollback.return_value = "Safe mode session closed."
    return manager


def test_safe_mode_status_returns_string(ctx, mock_manager):
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_safe_mode_status(ctx))
    assert isinstance(result, str)
    assert "active" in result.lower()
    mock_manager.status.assert_called_once()


def test_safe_mode_status_active(ctx, mock_manager):
    mock_manager.status.return_value = "Safe mode is ACTIVE. Changes are pending."
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_safe_mode_status(ctx))
    assert "ACTIVE" in result


def test_enable_safe_mode_returns_string(ctx, mock_manager):
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_enable_safe_mode(ctx))
    assert isinstance(result, str)
    assert "ENABLED" in result
    mock_manager.enable.assert_called_once()


def test_commit_safe_mode_returns_string(ctx, mock_manager):
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_commit_safe_mode(ctx))
    assert isinstance(result, str)
    assert "committed" in result.lower()
    mock_manager.commit.assert_called_once()


def test_rollback_safe_mode_returns_string(ctx, mock_manager):
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_rollback_safe_mode(ctx))
    assert isinstance(result, str)
    assert "closed" in result.lower()
    mock_manager.rollback.assert_called_once()


def test_enable_safe_mode_error_propagates(ctx, mock_manager):
    mock_manager.enable.return_value = "Error: Failed to connect to MikroTik device for safe mode session."
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_enable_safe_mode(ctx))
    assert "Error" in result


def test_commit_safe_mode_when_not_active(ctx, mock_manager):
    mock_manager.commit.return_value = "Safe mode is not active. Nothing to commit."
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_commit_safe_mode(ctx))
    assert "not active" in result.lower()


def test_rollback_safe_mode_when_not_active(ctx, mock_manager):
    mock_manager.rollback.return_value = "Safe mode is not active. Nothing to roll back."
    with patch("mcp_mikrotik.scope.devices.safe_mode.get_safe_mode_manager", return_value=mock_manager):
        result = asyncio.run(mikrotik_rollback_safe_mode(ctx))
    assert "not active" in result.lower()
