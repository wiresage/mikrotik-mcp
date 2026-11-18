import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


# A scheduler that alerts through a bot URL and a mail login: the token and the
# user:password@host URL are not labelled, so redaction alone would not hide them.
LEAKY = (
    'name="nightly" interval=1d on-event="/tool fetch '
    'url=https://api.telegram.org/bot123456789:AAHSecretTokenValue/sendMessage; '
    '/tool fetch url=ftp://u:UrlPassword@h.example/f password=LabelledPassword" run-count=3\n'
)


class Leaky(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        return LEAKY


class LegendOnly(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        return "Flags: X - disabled\n"


def test_schedulers_default_withholds_on_event(ctx, monkeypatch):
    """`on-event` carries commands, so by default the proplist must keep it off the wire."""
    from mcp_mikrotik.scope.system import scheduler

    fake = Leaky()
    monkeypatch.setattr(scheduler, "execute_mikrotik_command", fake, raising=True)

    out = _run(scheduler.mikrotik_list_schedulers(ctx, device="edge"))
    assert fake.devices == ["edge"]
    assert fake.commands == [
        f"/system scheduler print detail proplist={scheduler._SCHEDULER_METADATA}"
    ]
    assert "on-event" not in scheduler._SCHEDULER_METADATA.split(",")
    assert out.startswith("SCHEDULERS (metadata only):")


def test_schedulers_keep_the_fields_that_say_whether_a_job_runs():
    from mcp_mikrotik.scope.system import scheduler

    fields = scheduler._SCHEDULER_METADATA.split(",")
    assert len(fields) == len(set(fields))
    for prop in ("name", "interval", "next-run", "run-count", "owner", "policy", "disabled"):
        assert prop in fields, prop


def test_schedulers_with_source_ask_for_everything_and_redact(ctx, monkeypatch):
    from mcp_mikrotik.scope.system import scheduler

    fake = Leaky()
    monkeypatch.setattr(scheduler, "execute_mikrotik_command", fake, raising=True)

    out = _run(scheduler.mikrotik_list_schedulers(ctx, name_filter="night", include_source=True))
    assert fake.commands == ['/system scheduler print detail where name~"night"']
    assert out.startswith("SCHEDULERS (with on-event):")
    assert "on-event" in out
    assert "LabelledPassword" not in out


def test_schedulers_no_match_is_not_the_legend(ctx, monkeypatch):
    from mcp_mikrotik.scope.system import scheduler

    monkeypatch.setattr(scheduler, "execute_mikrotik_command", LegendOnly(), raising=True)
    assert _run(scheduler.mikrotik_list_schedulers(ctx, name_filter="x")) == (
        "No schedulers found matching the criteria."
    )
