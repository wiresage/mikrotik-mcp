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
