# Running Integration Tests

This project uses **pytest** for integration testing against a temporary MikroTik RouterOS container.

1. Make sure you have **Docker** installed and running.
2. Install dependencies:

   ```bash
   uv sync
   ```
3. Run the tests:

   ```bash
   uv run pytest -v
   ```

   This will:

   * Spin up a MikroTik RouterOS container
   * Run integration tests (create, list, and delete user)
   * Tear down the container automatically

By default, tests are marked with `@pytest.mark.integration`.
You can run only integration tests with:

```bash
uv run pytest -m integration -v
```

The unit tests need neither Docker nor a router and are what CI runs on every pull
request (Python 3.10, 3.11 and 3.12):

```bash
uv run pytest -m "not integration"
```
