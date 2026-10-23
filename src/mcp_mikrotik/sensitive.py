import re
from typing import Any, Iterable


REDACTED = "***"

_SENSITIVE_KEY = (
    r"(?:password|passphrase|private[-_. ]?key|pre[-_. ]?shared[-_. ]?key|"
    r"preshared[-_. ]?key|shared[-_. ]?secret|auth(?:entication)?[-_. ]?key|"
    r"enc(?:ryption)?[-_. ]?key|token|secret|community)"
)
_QUOTED_VALUE = re.compile(
    rf"(?i)(?P<prefix>(?<!\w)['\"]?{_SENSITIVE_KEY}['\"]?\s*(?:=|:)\s*)"
    r"(?P<escape>\\?)(?P<quote>['\"])(?:\\.|(?!(?P=quote))[^\\\n])*?"
    r"(?P=escape)(?P=quote)"
)
_BARE_VALUE = re.compile(
    rf"(?i)(?P<prefix>(?<!\w)['\"]?{_SENSITIVE_KEY}['\"]?\s*(?:=|:)\s*)"
    r"(?P<value>(?!\\['\"])[^'\"\s,;\]}]+)"
)
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?"
    r"-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.DOTALL,
)

SENSITIVE_PARAMETER_NAMES = frozenset({
    "password",
    "passphrase",
    "private_key",
    "preshared_key",
    "client_private_key",
    "content_base64",
})


def redact_sensitive_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Redact recognizable credentials while preserving surrounding output."""
    redacted = _PRIVATE_KEY_BLOCK.sub(REDACTED, text)
    redacted = _QUOTED_VALUE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('escape')}{match.group('quote')}"
            f"{REDACTED}{match.group('escape')}{match.group('quote')}"
        ),
        redacted,
    )
    redacted = _BARE_VALUE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", redacted)
    for secret in sorted({value for value in secrets if value}, key=len, reverse=True):
        if len(secret) >= 4:
            redacted = redacted.replace(secret, REDACTED)
        else:
            redacted = re.sub(rf"(?<!\w){re.escape(secret)}(?!\w)", REDACTED, redacted)
    return redacted


def redact_sensitive_data(value: Any, secrets: Iterable[str] = ()) -> Any:
    """Recursively redact strings used in MCP notifications and tool results."""
    if isinstance(value, str):
        return redact_sensitive_text(value, secrets)
    if isinstance(value, list):
        return [redact_sensitive_data(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item, secrets) for item in value)
    if isinstance(value, dict):
        return {
            key: REDACTED if redact_sensitive_text(f"{key}=value") != f"{key}=value"
            else redact_sensitive_data(item, secrets)
            for key, item in value.items()
        }
    return value


def redact_if_enabled(value: Any, secrets: Iterable[str] = ()) -> Any:
    from .config import mikrotik_config

    if not getattr(mikrotik_config, "sensitive_hiding", False):
        return value
    return redact_sensitive_data(value, secrets)


class SensitiveContext:
    """Proxy MCP notifications through the sensitive-data redactor."""

    def __init__(self, context: Any, secrets: Iterable[str] = ()):
        self._context = context
        self._secrets = tuple(secrets)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)

    async def debug(self, data: Any, **kwargs) -> None:
        await self._context.debug(redact_sensitive_data(data, self._secrets), **kwargs)

    async def info(self, data: Any, **kwargs) -> None:
        await self._context.info(redact_sensitive_data(data, self._secrets), **kwargs)

    async def warning(self, data: Any, **kwargs) -> None:
        await self._context.warning(redact_sensitive_data(data, self._secrets), **kwargs)

    async def error(self, data: Any, **kwargs) -> None:
        await self._context.error(redact_sensitive_data(data, self._secrets), **kwargs)

    async def log(self, level: Any, data: Any, **kwargs) -> None:
        await self._context.log(level, redact_sensitive_data(data, self._secrets), **kwargs)

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        await self._context.report_progress(
            progress, total, redact_sensitive_data(message, self._secrets)
        )
