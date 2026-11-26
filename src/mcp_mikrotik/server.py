import logging
import os
import sys

from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError

from mcp_mikrotik.sensitive import redact_if_enabled


def _config_error_message(exc: ValidationError) -> str:
    """One readable line per problem, without echoing any input values."""
    problems = "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or 'config'}: {err['msg']}"
        for err in exc.errors()
    )
    return f"Invalid MikroTik configuration: {problems}"


# An inline MIKROTIK_INVENTORY is parsed the moment MikrotikConfig is built,
# which happens at import — so a broken one must be caught here to die with
# one clear message rather than a raw traceback.
try:
    from mcp_mikrotik import config
    from mcp_mikrotik.config import McpServerSettings, MikrotikConfig
except ValidationError as _exc:
    print(_config_error_message(_exc), file=sys.stderr)
    sys.exit(1)

_LOCALHOST_HOSTS = ("127.0.0.1", "localhost", "::1")
mcp = None


def _warn_if_plaintext_password_in_container(cfg: MikrotikConfig, logger: logging.Logger) -> None:
    """Warn when running inside a container with a plaintext password in the env.

    Environment variables are visible via ``docker inspect``, so a password
    passed this way is exposed to anyone with host access. This is purely a
    nudge — it does not block startup. Credential management is ultimately an
    infrastructure concern (Docker secrets, a vault, restricted host access).
    """
    in_container = os.path.exists("/.dockerenv") or os.environ.get("container") == "docker"
    if in_container and cfg.password:
        logger.warning(
            "Security notice: MikroTik MCP is running inside a container with a "
            "plaintext password set as an environment variable. Environment "
            "variables are visible via 'docker inspect', so anyone with access "
            "to the host can read the credential. In shared or production "
            "environments, manage the secret through your infrastructure "
            "(e.g. Docker secrets or a secrets manager) and restrict host "
            "access. See SECURITY.md."
        )


def _build_transport_security(
    mcp_cfg: McpServerSettings, logger: logging.Logger
) -> TransportSecuritySettings:
    """Build DNS-rebinding protection settings for the HTTP transports.

    Why this is needed (issue #86): the MCP SDK defaults its DNS-rebinding
    protection to a localhost-only Host allowlist. When the server is bound to a
    non-localhost host (e.g. ``0.0.0.0`` in a container) and fronted by a reverse
    proxy, that localhost allowlist rejects every real request to ``/mcp`` with
    HTTP 421 "Invalid Host header". Here we reconcile the protection settings
    with the actual runtime host and any user-provided allowlist.

    Resolution order:
      1. ``allowed_hosts`` contains "*"        -> protection disabled (explicit opt-out)
      2. ``allowed_hosts`` / ``allowed_origins`` set -> protection on, with that allowlist
      3. host is localhost                     -> secure localhost allowlist (default)
      4. host is non-localhost, no allowlist    -> protection disabled + a warning
    """
    hosts = [h.strip() for h in mcp_cfg.allowed_hosts.split(",") if h.strip()]
    origins = [o.strip() for o in mcp_cfg.allowed_origins.split(",") if o.strip()]

    if "*" in hosts:
        logger.warning(
            "DNS-rebinding protection is DISABLED (MIKROTIK_MCP__ALLOWED_HOSTS=*). "
            "Ensure the server is only reachable by trusted clients."
        )
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    if hosts or origins:
        logger.info(f"DNS-rebinding protection enabled for hosts={hosts or '[]'} origins={origins or '[]'}")
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        )

    if mcp_cfg.host in _LOCALHOST_HOSTS:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        )

    logger.warning(
        "Serving the HTTP transport on a non-localhost host (%s) without "
        "MIKROTIK_MCP__ALLOWED_HOSTS set, so DNS-rebinding protection is "
        "disabled. Behind a reverse proxy, set MIKROTIK_MCP__ALLOWED_HOSTS to "
        "your domain (e.g. 'mcp.example.com') to re-enable it.",
        mcp_cfg.host,
    )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def main():
    """
    Entry point for the MCP MikroTik server when run as a command-line program.
    """
    global mcp

    logger = logging.getLogger(__name__)

    try:
        config.mikrotik_config = MikrotikConfig(_cli_parse_args=True)
    except ValidationError as e:
        logger.error(_config_error_message(e))
        sys.exit(1)

    # Tool registration depends on catalogue policies, including CLI flags.
    # Import the application only after the final config is ready.
    if mcp is None:
        from mcp_mikrotik.app import mcp as configured_mcp

        mcp = configured_mcp

    logger.info("Starting MCP MikroTik server")

    # Build the inventory now rather than at the first tool call, so a broken
    # inventory (unreadable file, bad YAML, invalid entry) stops the server at
    # startup with one clear message instead of failing every tool call later.
    # No connections are opened here — those stay lazy, per command.
    from mcp_mikrotik.inventory import get_inventory, reset_inventory

    reset_inventory()
    try:
        inventory = get_inventory()
    except ValueError as e:
        logger.error(f"Invalid MikroTik inventory: {e}")
        sys.exit(1)
    if inventory:
        logger.info(
            f"Managing {len(inventory)} device(s): {', '.join(inventory.titles)}"
        )
    else:
        logger.info(
            "No MikroTik devices are configured yet; use add_device to enroll one."
        )

    _warn_if_plaintext_password_in_container(config.mikrotik_config, logger)

    try:
        transport = config.mikrotik_config.mcp.transport
        # stdio takes no transport options.
        run_kwargs = {}
        if transport in ("sse", "streamable-http"):
            run_kwargs = {
                "host": config.mikrotik_config.mcp.host,
                "port": config.mikrotik_config.mcp.port,
                # Reconcile DNS-rebinding protection with the actual runtime host
                # so the HTTP transports work behind a reverse proxy / on
                # non-localhost (#86).
                "transport_security": _build_transport_security(
                    config.mikrotik_config.mcp, logger
                ),
            }
        mcp.run(transport=transport, **run_kwargs)
    except KeyboardInterrupt:
        logger.info("MCP MikroTik server stopped by user")
    except Exception as e:
        logger.error("Error running MCP MikroTik server: %s", redact_if_enabled(str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
