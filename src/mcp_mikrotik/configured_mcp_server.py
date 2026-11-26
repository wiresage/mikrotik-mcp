import datetime
import functools
import inspect
import json
import logging

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette

from . import config
from .http_security import IPAllowListMiddleware, parse_allowed_ips
from .sensitive import SENSITIVE_PARAMETER_NAMES, SensitiveContext, redact_sensitive_data


logger = logging.getLogger(__name__)

SENSITIVE_TOOLS = frozenset({"download_file", "generate_wireguard_client_config"})

# The tool functions take the target as a Python parameter named `device`, but
# the schema advertises it as `device_name`. Some MCP hosts reserve a top-level
# `device` argument for their own routing (e.g. a remote-device bridge that
# picks which computer a call goes to) and strip it before forwarding, so a
# parameter by that name never reaches the server. `device` is still accepted
# on input as a deprecated alias for older callers.
TARGET_ARG = "device_name"
DEVICE_PARAM = "device"
TARGET_DESCRIPTION = (
    "Title of the target MikroTik device (router, switch, access point), as "
    "listed by `list_devices` (case-insensitive). Required when several devices "
    "are configured, unless the server sets MIKROTIK_DEFAULT_DEVICE."
)


def _rename_device_property(schema: dict) -> None:
    """Rename the `device` property of a tool input schema to `device_name`, in place.

    Property order is kept so the argument shows up where it always did.
    """
    properties = schema.get("properties")
    if not isinstance(properties, dict) or DEVICE_PARAM not in properties:
        return
    renamed = {}
    for key, value in properties.items():
        if key == DEVICE_PARAM:
            value = dict(value)
            value["title"] = "Device Name"
            value["description"] = TARGET_DESCRIPTION
            key = TARGET_ARG
        renamed[key] = value
    schema["properties"] = renamed
    required = schema.get("required")
    if isinstance(required, list):
        schema["required"] = [TARGET_ARG if r == DEVICE_PARAM else r for r in required]


def normalize_device_argument(arguments: dict) -> dict:
    """Map the public `device_name` argument onto the tools' internal `device` parameter.

    Returns a new dict. Raises ToolError when both are given and disagree, so a
    call is never silently sent to a different device than the one asked for.
    """
    args = dict(arguments or {})
    target = args.pop(TARGET_ARG, None)
    device = args.get(DEVICE_PARAM)
    if target is not None and str(target).strip():
        if device is not None and str(device).strip() and (
            str(device).strip().casefold() != str(target).strip().casefold()
        ):
            raise ToolError(
                f"Conflicting targets: device_name={target!r} but device={device!r}. "
                "Pass only `device_name`."
            )
        args[DEVICE_PARAM] = target
    return args


def _log_arguments(name: str, arguments: dict) -> None:
    """Append one diagnostic line per call to MIKROTIK_ARG_LOG, if set.

    Only argument names are written, plus the device_name/device values (titles from
    the inventory, never secrets), so the log shows what a host forwarded.
    """
    path = getattr(config.mikrotik_config, "arg_log", None)
    if not path:
        return
    line = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "tool": name,
        "keys": sorted((arguments or {}).keys()),
        TARGET_ARG: (arguments or {}).get(TARGET_ARG),
        DEVICE_PARAM: (arguments or {}).get(DEVICE_PARAM),
    }
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
    except OSError as exc:  # diagnostics must never break a call
        logger.warning("Cannot write MIKROTIK_ARG_LOG %r: %s", path, exc)


class ConfiguredMCPServer(MCPServer):
    """Apply configured catalogue and response policies to MCP tools."""

    def add_tool(self, fn, name=None, *args, **kwargs):
        super().add_tool(fn, name, *args, **kwargs)
        tool = self._tool_manager.get_tool(name or fn.__name__)
        if tool is not None:
            _rename_device_property(tool.parameters)

    def tool(self, *args, **kwargs):
        annotations = kwargs.get("annotations")
        if config.mikrotik_config.read_only and not (
            annotations and annotations.read_only_hint
        ):
            return lambda fn: fn
        name = kwargs.get("name") or (args[0] if args else None)
        if config.mikrotik_config.sensitive_hiding and name in SENSITIVE_TOOLS:
            return lambda fn: fn

        decorator = super().tool(*args, **kwargs)
        if not config.mikrotik_config.sensitive_hiding:
            return decorator

        def sensitive_decorator(fn):
            signature = inspect.signature(fn)

            def prepare_call(call_args, call_kwargs):
                bound = signature.bind_partial(*call_args, **call_kwargs)
                secrets = [
                    str(value) for parameter, value in bound.arguments.items()
                    if parameter in SENSITIVE_PARAMETER_NAMES and value
                ]
                if "ctx" in bound.arguments:
                    bound.arguments["ctx"] = SensitiveContext(bound.arguments["ctx"], secrets)
                return bound, secrets

            if inspect.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def wrapped(*call_args, **call_kwargs):
                    bound, secrets = prepare_call(call_args, call_kwargs)
                    try:
                        result = await fn(*bound.args, **bound.kwargs)
                    except Exception as exc:
                        message = redact_sensitive_data(str(exc), secrets)
                        if message == str(exc):
                            raise
                        raise (ToolError if isinstance(exc, ToolError) else RuntimeError)(message) from None
                    return redact_sensitive_data(result, secrets)
            else:
                @functools.wraps(fn)
                def wrapped(*call_args, **call_kwargs):
                    bound, secrets = prepare_call(call_args, call_kwargs)
                    try:
                        result = fn(*bound.args, **bound.kwargs)
                    except Exception as exc:
                        message = redact_sensitive_data(str(exc), secrets)
                        if message == str(exc):
                            raise
                        raise (ToolError if isinstance(exc, ToolError) else RuntimeError)(message) from None
                    return redact_sensitive_data(result, secrets)

            return decorator(wrapped)

        return sensitive_decorator

    async def call_tool(self, name, arguments, context=None):
        _log_arguments(name, arguments)
        arguments = normalize_device_argument(arguments)
        if not config.mikrotik_config.sensitive_hiding:
            return await super().call_tool(name, arguments, context)

        secrets = [
            str(value) for parameter, value in arguments.items()
            if parameter in SENSITIVE_PARAMETER_NAMES and value
        ]
        try:
            return await super().call_tool(name, arguments, context)
        except Exception as exc:
            message = redact_sensitive_data(str(exc), secrets)
            if message == str(exc):
                raise
            raise ToolError(message) from None

    @staticmethod
    def _apply_ip_allowlist(app: Starlette) -> Starlette:
        allowed_ips = parse_allowed_ips(config.mikrotik_config.mcp.allowed_ips)
        if allowed_ips:
            app.add_middleware(IPAllowListMiddleware, allowed_ips=allowed_ips)
        return app

    def sse_app(self, *args, **kwargs) -> Starlette:
        return self._apply_ip_allowlist(super().sse_app(*args, **kwargs))

    def streamable_http_app(self, *args, **kwargs) -> Starlette:
        return self._apply_ip_allowlist(super().streamable_http_app(*args, **kwargs))
