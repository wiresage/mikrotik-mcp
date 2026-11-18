# Running Tests

This project uses **pytest**. Install the locked environment first:

```bash
uv sync --frozen
```

## Unit tests

The unit tests need neither Docker nor a router and are what CI runs on every pull
request (Python 3.10, 3.11 and 3.12):

```bash
uv run pytest -m "not integration"
```

## Integration tests

Integration tests are marked `integration` and need **Docker** running. They start a
temporary MikroTik RouterOS container, create, list and delete a user, then remove
the container:

```bash
uv run pytest -m integration -v
```

Run `uv run pytest` for both suites.

## Where the tests live

```
tests/unit/                 what is not about the tool modules: connector, config, ssh, app, docs links, ...
tests/unit/scope/           tests that span feature areas, the layout checks and the smoke test
tests/unit/scope/<area>/    the tests of one feature area (firewall, interfaces, ip, ...)
tests/integration/          needs Docker
```

The folders mirror `src/mcp_mikrotik/scope/`, so one area can be tested on its own:

```bash
uv run pytest tests/unit/scope/firewall
```

Two checks keep the code and the documentation in step: `tests/unit/scope/test_layout.py` (every tool module is
registered by its area, every area has reference pages) and `tests/unit/test_docs_links.py` (every relative link in the
markdown files resolves).
