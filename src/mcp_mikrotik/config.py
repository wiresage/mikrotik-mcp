import json
from typing import Annotated, List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .http_security import parse_allowed_ips


class McpServerSettings(BaseModel):
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    host: str = "0.0.0.0"
    port: int = 8000

    # DNS-rebinding protection for the HTTP transports (sse / streamable-http).
    # Comma-separated allowlists for the Host and Origin request headers. Needed
    # when serving behind a reverse proxy or on a non-localhost host — otherwise
    # requests with an external Host header are rejected with HTTP 421
    # "Invalid Host header". Set allowed_hosts to your domain (e.g.
    # "mcp.example.com"); a value of "*" disables the host check entirely.
    allowed_hosts: str = ""
    allowed_origins: str = ""
    # Comma-separated client IP addresses and CIDR networks. Unlike the Host
    # header allowlist above, this restricts which remote clients may connect.
    allowed_ips: str = ""

    @field_validator("allowed_ips")
    @classmethod
    def _valid_allowed_ips(cls, value: str) -> str:
        try:
            parse_allowed_ips(value)
        except ValueError as exc:
            raise ValueError(f"invalid IP address or network: {exc}") from exc
        return value


class DeviceConfig(BaseModel):
    """A single MikroTik device in the inventory.

    ``title`` is the identifier the LLM uses to target this device; it must be
    unique across the inventory.
    """

    # The inventory carries credentials, so validation errors must never echo
    # the offending input back — they end up in tool results and logs.
    model_config = ConfigDict(hide_input_in_errors=True)

    title: str
    host: str
    port: int = 22
    username: str = "admin"
    password: str = ""
    key_filename: Optional[str] = None
    tags: List[str] = []
    region: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("device 'title' must be a non-empty string")
        return v.strip()


class MikrotikConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MIKROTIK_",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        cli_prog_name="mcp-server-mikrotik",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        # The inventory value carries credentials; validation errors must not
        # echo the offending input into logs or tool results.
        hide_input_in_errors=True,
    )

    # ── Single-device settings (unchanged; still the default) ───────────────
    host: str = "127.0.0.1"
    username: str = "admin"
    password: str = ""
    port: int = 22
    key_filename: Optional[str] = None
    read_only: bool = False
    sensitive_hiding: bool = False
    # Seconds a command may wait for the device before the call fails. Idle time on the SSH
    # channel, not a total: output that keeps arriving resets it. See mikrotik_ssh_client.
    command_timeout: float = 180.0
    mcp: McpServerSettings = McpServerSettings()

    @field_validator("command_timeout")
    @classmethod
    def _positive_command_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be greater than 0 seconds")
        return v

    # ── Multi-device inventory ─────────────────────────────────────────────
    # A list of devices, written in YAML. JSON is a subset of YAML, so a JSON
    # array works everywhere YAML does. Two sources, inline winning over file:
    #
    #   MIKROTIK_INVENTORY='[{title: TitleA, host: 10.0.0.1, region: NL}]'
    #   MIKROTIK_INVENTORY_FILE=/config/inventory.yaml
    #
    # YAML flow syntax keeps the inline form free of escaped quotes inside an
    # MCP client's JSON config. These belong in the server's "env" block — that
    # is the channel a client actually forwards to the spawned process.
    #
    # When left empty, a single-device inventory is synthesised from the flat
    # settings above, so existing single-device setups keep working unchanged.
    #
    # NoDecode stops pydantic-settings from JSON-decoding the env value itself,
    # so the raw string reaches the validator and YAML can be accepted.
    inventory: Annotated[List[DeviceConfig], NoDecode] = []
    inventory_file: Optional[str] = None

    @field_validator("inventory", mode="before")
    @classmethod
    def _parse_inventory(cls, v):
        """Accept a YAML/JSON string (env var) as well as a real list."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # JSON first: PyYAML's scanner rejects tab whitespace, which is
            # legal in JSON, so yaml.safe_load alone would break previously
            # working tab-indented JSON inventories.
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                try:
                    v = yaml.safe_load(v)
                except yaml.YAMLError as exc:
                    # Report the position only — the value holds credentials
                    # and must not be echoed into logs or tool results.
                    mark = getattr(exc, "problem_mark", None)
                    where = (
                        f" (line {mark.line + 1}, column {mark.column + 1})"
                        if mark else ""
                    )
                    raise ValueError(
                        f"MIKROTIK_INVENTORY is not valid YAML/JSON{where}"
                    ) from exc
        if isinstance(v, dict):
            v = [v]
        return v


mikrotik_config = MikrotikConfig()
