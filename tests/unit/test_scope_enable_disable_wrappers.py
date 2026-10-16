"""The enable_*/disable_* tools (and expand_ip_pool) delegate to the matching update_* tool.

Every tool takes ``ctx`` as its FIRST parameter. These wrappers used to call
``update_x(identifier, disabled=..., ctx=ctx)``: the identifier then bound to ``ctx`` positionally and
``ctx=ctx`` bound it a second time, so every call raised ``TypeError: ... got multiple values for
argument 'ctx'`` and the client only saw "Error executing tool". Only the filter rule wrappers had
been fixed.
"""

import ast
import asyncio
import importlib
import pathlib

import pytest

SCOPE_DIR = pathlib.Path(__file__).resolve().parents[2] / "src" / "mcp_mikrotik" / "scope"

#            module          tool function                    kwargs                                  expected command fragment
WRAPPERS = [
    ("dns", "mikrotik_enable_dns_static", {"entry_id": "*1"}, "/ip dns static set *1 disabled=no"),
    ("dns", "mikrotik_disable_dns_static", {"entry_id": "*1"}, "/ip dns static set *1 disabled=yes"),
    ("firewall_nat", "mikrotik_enable_nat_rule", {"rule_id": "*1"}, "/ip firewall nat set *1 disabled=no"),
    ("firewall_nat", "mikrotik_disable_nat_rule", {"rule_id": "*1"}, "/ip firewall nat set *1 disabled=yes"),
    ("routes", "mikrotik_enable_route", {"route_id": "*1"}, "/ip route set *1 disabled=no"),
    ("routes", "mikrotik_disable_route", {"route_id": "*1"}, "/ip route set *1 disabled=yes"),
    ("users", "mikrotik_enable_user", {"name": "bob"}, '/user set [find name="bob"] disabled=no'),
    ("users", "mikrotik_disable_user", {"name": "bob"}, '/user set [find name="bob"] disabled=yes'),
    (
        "ip_pool",
        "mikrotik_expand_ip_pool",
        {"name": "p", "additional_ranges": "10.0.0.50-10.0.0.60"},
        '/ip pool set [find name="p"] ranges=10.0.0.10-10.0.0.20,10.0.0.50-10.0.0.60',
    ),
    # the ones that were already correct stay correct
    ("firewall_filter", "mikrotik_enable_filter_rule", {"rule_id": "*1"}, "/ip firewall filter set *1 disabled=no"),
    ("firewall_filter", "mikrotik_disable_filter_rule", {"rule_id": "*1"}, "/ip firewall filter set *1 disabled=yes"),
]


@pytest.mark.parametrize("module_name,function_name,kwargs,expected", WRAPPERS)
def test_wrapper_runs_the_update_command(module_name, function_name, kwargs, expected, ctx, monkeypatch):
    module = importlib.import_module(f"mcp_mikrotik.scope.{module_name}")
    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        if "count-only" in command:
            return "1"
        if command.startswith(":put"):
            return "*1"
        if command.startswith("/ip pool print"):
            return "name=p ranges=10.0.0.10-10.0.0.20"
        if "print" in command:
            return "chain=forward"
        return ""

    monkeypatch.setattr(module, "execute_mikrotik_command", execute)
    result = asyncio.run(getattr(module, function_name)(ctx, **kwargs))

    assert any(expected in command for command in commands), commands
    assert not result.startswith("Error"), result
    assert "multiple values" not in result


def _first_param_is_ctx(node):
    args = node.args.posonlyargs + node.args.args
    return bool(args) and args[0].arg == "ctx"


def _scope_modules():
    return sorted(p for p in SCOPE_DIR.glob("*.py") if not p.name.startswith("__"))


@pytest.mark.parametrize("path", _scope_modules(), ids=lambda p: p.name)
def test_no_call_passes_ctx_twice(path):
    """A function whose first parameter is ``ctx`` must get ``ctx`` first, not as a keyword after other arguments.

    This is the exact shape of the bug: ``f(identifier, ctx=ctx)`` with ``def f(ctx, identifier, ...)``.
    It scans every scope module, so a future wrapper written the same way fails here instead of in production.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    takes_ctx_first = {
        node.name for node in ast.walk(tree) if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and _first_param_is_ctx(node)
    }
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id not in takes_ctx_first:
            continue
        passes_ctx_by_keyword = any(kw.arg == "ctx" for kw in node.keywords)
        if passes_ctx_by_keyword and node.args:
            offenders.append(f"{path.name}:{node.lineno} {node.func.id}(...)")
    assert not offenders, "ctx is bound twice (positional argument first, then ctx=): " + ", ".join(offenders)
