import asyncio


def test_expand_ip_pool_appends_the_new_ranges(ctx, monkeypatch):
    """
    expand_ip_pool delegates to update_ip_pool. It used to pass `name` positionally and `ctx=` by
    keyword, although `ctx` is update_ip_pool's first parameter, which raised
    "TypeError: got multiple values for argument 'ctx'" on every call. (This test used to assert
    that TypeError.)
    """
    from mcp_mikrotik.scope import ip_pool as mod

    commands = []

    async def fake_exec(command: str, _ctx, device=None):
        commands.append(command)
        if "print detail" in command:
            return 'name="pool1" ranges=10.0.0.1-10.0.0.10'
        return ""

    monkeypatch.setattr(mod, "execute_mikrotik_command", fake_exec, raising=True)

    result = asyncio.run(mod.mikrotik_expand_ip_pool(ctx=ctx, name="pool1", additional_ranges="10.0.0.11-10.0.0.12"))

    assert not result.startswith("Error")
    assert any(
        'set [find name="pool1"] ranges=10.0.0.1-10.0.0.10,10.0.0.11-10.0.0.12' in command for command in commands
    ), commands
