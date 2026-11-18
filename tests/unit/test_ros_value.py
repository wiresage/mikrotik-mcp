"""`ros_value` decides whether a value needs quotes. That decision is the boundary."""

import pytest

from mcp_mikrotik.scope._quoting import ros_quoted, ros_value


@pytest.mark.parametrize("value", [
    "ether1", "10.0.0.1", "10.86.0.0/24", "2001:db8::1/64", "1d", "*3", "0",
    "10.0.0.1-10.0.0.9", "syn,!ack", "!hop", "10,5:packet", "128:0", "mine.backup",
    "ether9-ap,ether10-ap", "flash/backup.rsc",
])
def test_a_value_made_of_safe_characters_keeps_its_exact_shape(value):
    """RouterOS fixed quoting of multi-argument properties only in 7.24beta2, so a list
    that needs no quotes must not get them: on an earlier release it would stop parsing."""
    assert ros_value(value) == value


@pytest.mark.parametrize("value", [
    'zz" ; :log info BREAKOUT ; "zz',   # the payload the checklist drives
    'a b',                              # a space starts another argument
    'x;y',                              # `;` starts another command
    "[/system reboot]",                 # brackets substitute a command
    "$var",                             # `$` reads a variable
    "back\slash",
    "",                                 # an empty value still needs its quotes
    "name=value",                       # `=` would add an argument
])
def test_anything_else_is_escaped_and_wrapped(value):
    out = ros_value(value)
    assert out.startswith('"') and out.endswith('"')
    assert out == '"' + ros_quoted(value) + '"'
    # Whatever is between the quotes carries no unescaped quote of its own, so the value
    # cannot end where RouterOS would start reading a command.
    assert '\\"' in out or '"' not in out[1:-1]
