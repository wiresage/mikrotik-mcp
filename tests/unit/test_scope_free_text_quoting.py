"""Free text in a write tool must reach RouterOS as data (issue: quotes, backslashes, $ and non-ASCII in comments).

A comment such as `say "hi"` closed the string early ("expected end of command") and the tool failed, `a\\b` was
stored with a backspace in it, `cost $5` lost the `$5` to variable expansion, and every non-ASCII character was
stored as a blank. Passwords were affected the same way, so a password with a `$` or a quote was set to
something else than what was asked for.

The test drives every tool that takes one of these values and looks at the command it sends.
"""

import asyncio
import inspect

import pytest

from mcp_mikrotik.scope._quoting import ros_quoted
from tests.conftest import FakeExecutor, make_dummy_value

BS = chr(92)  # one backslash, written this way so the tests do not depend on how a backslash is escaped here
NASTY = f'say "hi" {BS}b cost $5 [x]; café 日本\tend'

# scope module -> the parameters whose value is free text, and the RouterOS argument each one becomes
MODULES = [
    "dhcp",
    "dns",
    "firewall_address_list",
    "firewall_filter",
    "firewall_nat",
    "ip_address",
    "ip_pool",
    "ipv6_address",
    "ipv6_firewall_filter",
    "queue",
    "routes",
    "users",
    "vlan",
    "wireguard",
    "wireless",
]
FREE_TEXT = {"comment": "comment", "log_prefix": "log-prefix", "text": "text", "ssid": "ssid", "password": "password"}


class Recorder(FakeExecutor):
    def __init__(self):
        super().__init__()
        self.redacted: list = []

    async def __call__(self, command, _ctx, device=None, redact=None):
        self.redacted.append(list(redact or []))
        return await super().__call__(command, _ctx, device, redact)


def free_text_tools():
    for module_name in MODULES:
        module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])
        for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if not name.startswith("mikrotik_"):
                continue
            params = [p for p in inspect.signature(fn).parameters if p in FREE_TEXT]
            if params:
                yield pytest.param(module, name, fn, params, id=f"{module_name}.{name}")


def call(fn, ctx, nasty_params):
    kwargs = {}
    for param in inspect.signature(fn).parameters.values():
        if param.name == "ctx":
            kwargs["ctx"] = ctx
        elif param.name in nasty_params:
            kwargs[param.name] = NASTY
        elif param.name == "log":
            kwargs["log"] = True  # a log prefix is only sent together with log=yes
        elif param.name.endswith("_id") and param.default is inspect._empty:
            kwargs[param.name] = "*1"  # an internal id, so the update tools get past their lookup
        elif param.name == "action" and param.default is inspect._empty:
            kwargs["action"] = "accept"  # the NAT tool refuses an action it does not know
        elif param.default is inspect._empty:
            kwargs[param.name] = make_dummy_value(param)
    return asyncio.run(fn(**kwargs))


@pytest.mark.parametrize("module,name,fn,params", list(free_text_tools()))
def test_every_free_text_value_is_escaped(module, name, fn, params, ctx, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(module, "execute_mikrotik_command", recorder, raising=True)

    call(fn, ctx, params)

    sent = "\n".join(recorder.commands)
    for param in params:
        key = FREE_TEXT[param]
        assert f'{key}="{ros_quoted(NASTY)}"' in sent, f"{name}: {param} did not reach RouterOS escaped:\n{sent}"
    assert 'say "hi"' not in sent, f"{name} sent a bare double quote from a free text value:\n{sent}"
    for command in recorder.commands:
        # a newline or a tab would split the command line, and raw UTF-8 bytes are stored as blanks
        assert "\n" not in command and "\t" not in command, f"{name} sent a control character: {command!r}"
        assert command.isascii(), f"{name} sent non-ASCII text as it is: {command!r}"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("plain text, 1-2: (a) [b] {c} ; ' ? * ~ !", "plain text, 1-2: (a) [b] {c} ; ' ? * ~ !"),  # nothing to escape
        ('say "hi"', f'say {BS}"hi{BS}"'),
        (f"a{BS}b", f"a{BS}{BS}b"),  # `\b` would otherwise be stored as a backspace
        ("cost $5", f"cost {BS}$5"),  # `$5` would otherwise be expanded as a variable and vanish
        ("café", f"caf{BS}C3{BS}A9"),  # the UTF-8 bytes, as RouterOS stores and prints them
        ("日本", f"{BS}E6{BS}97{BS}A5{BS}E6{BS}9C{BS}AC"),
        ("\U0001f600", f"{BS}F0{BS}9F{BS}98{BS}80"),
        ("a\nb\tc\r", f"a{BS}0Ab{BS}09c{BS}0D"),  # a line break would end the command
        ("\x7f", f"{BS}7F"),
        ("\ud800", f"{BS}3F"),  # a lone surrogate cannot be encoded: it becomes "?" instead of an exception
        (f"{BS}C3", f"{BS}{BS}C3"),  # a literal backslash followed by hex digits stays literal
        ("", ""),
    ],
)
def test_ros_quoted_escapes_everything_routeros_reads_as_syntax(value, expected):
    assert ros_quoted(value) == expected


def test_the_tools_that_take_free_text_are_all_covered():
    covered = {p.id for p in free_text_tools()}
    # a new write tool with a comment must show up here, or it ships without the escaping test
    for expected in (
        "ip_address.mikrotik_add_ip_address",
        "users.mikrotik_add_user",
        "users.mikrotik_update_user",
        "firewall_filter.mikrotik_create_filter_rule",
        "firewall_nat.mikrotik_create_nat_rule",
        "wireguard.mikrotik_add_wireguard_peer",
        "dns.mikrotik_add_dns_static",
    ):
        assert expected in covered
    assert len(covered) >= 35


# ----------------------------------------------------------------------------------------- passwords in the logs
@pytest.mark.parametrize("tool", ["mikrotik_add_user", "mikrotik_update_user"])
def test_a_password_is_declared_in_both_forms_for_the_logs(tool, ctx, monkeypatch):
    from mcp_mikrotik.scope import users

    password = f'p"w{BS}d$1'
    recorder = Recorder()
    monkeypatch.setattr(users, "execute_mikrotik_command", recorder, raising=True)
    fn = getattr(users, tool)
    kwargs = {"ctx": ctx, "name": "u1", "password": password}
    if tool == "mikrotik_add_user":
        kwargs["group"] = "read"
    asyncio.run(fn(**kwargs))

    write = next(i for i, c in enumerate(recorder.commands) if "password=" in c)
    assert f'password="{ros_quoted(password)}"' in recorder.commands[write]
    # the command line carries the escaped form: the logs only stay clean if both forms are blanked
    assert password in recorder.redacted[write]
    assert ros_quoted(password) in recorder.redacted[write]
