import base64
import inspect
import sys
from pathlib import Path
import typing
from typing import Any, Callable, get_args, get_origin
from unittest.mock import AsyncMock, MagicMock

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if _SRC_ROOT.exists():
    sys.path.insert(0, str(_SRC_ROOT))


@pytest.fixture()
def ctx():
    c = MagicMock()
    c.info = AsyncMock()
    c.debug = AsyncMock()
    c.warning = AsyncMock()
    c.error = AsyncMock()
    return c


class FakeExecutor:
    """
    Heuristic fake for execute_mikrotik_command.

    - count-only queries return "1" (exists)
    - print/detail queries return a non-empty payload
    - mutating commands return "" (success)
    """

    def __init__(self):
        self.commands: list[str] = []
        self.devices: list[Any] = []

    async def __call__(self, command: str, _ctx: Any, device: Any = None,
                       redact: Any = None) -> str:
        self.commands.append(command)
        self.devices.append(device)

        cmd = command.lower()
        if "count-only" in cmd:
            return "1"
        if "print" in cmd:
            return "some mikrotik output"
        return ""


@pytest.fixture()
def fake_exec():
    return FakeExecutor()


def make_dummy_value(param: inspect.Parameter) -> Any:
    ann = param.annotation
    name = param.name.lower()

    if name in {"ctx", "context"}:
        raise AssertionError("ctx should be injected explicitly")

    if name in {"content_base64", "file_content_base64"}:
        return base64.b64encode(b"hello").decode("utf-8")

    if ann is inspect._empty:
        return "test"

    origin = get_origin(ann)
    args = get_args(ann)
    if origin is typing.Union and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        ann = non_none[0] if non_none else str
        origin = get_origin(ann)
        args = get_args(ann)

    if origin is typing.Literal:
        return args[0]

    if origin is list:
        inner = get_args(ann)[0] if get_args(ann) else str
        if inner is str:
            if "server" in name:
                return ["1.1.1.1"]
            return ["test"]
        return []

    if origin is dict:
        return {}

    if origin is Callable:
        return lambda *args, **kwargs: None

    if origin is Any:
        return "test"

    if ann is str:
        if "address" in name:
            return "192.0.2.1"
        if "dst" in name:
            return "203.0.113.0/24"
        if "gateway" in name:
            return "192.0.2.254"
        if "interface" in name:
            return "ether1"
        if "name" == name:
            return "test-name"
        if "filename" in name:
            return "test.rsc"
        return "test"

    if ann is int:
        return 1

    if ann is float:
        return 1.0

    if ann is bool:
        return False

    try:
        if str(ann).startswith("typing.Literal"):
            return get_args(ann)[0]
    except Exception:
        pass

    return "test"
