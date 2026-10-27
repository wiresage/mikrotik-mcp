# AGENTS.md

Instructions for AI coding agents working in this repository. Humans should read [CONTRIBUTING.md](CONTRIBUTING.md); this file adds the things an agent needs to know up front and the RouterOS behaviour that has caused bugs here before.

## Project overview

MikroTik MCP is a Python [MCP](https://modelcontextprotocol.io) server that lets an AI assistant manage MikroTik RouterOS devices over SSH. It is written and tested against RouterOS 7. It ships as the PyPI package `mcp-server-mikrotik`, a Docker image (`ghcr.io/wiresage/mikrotik-mcp`) and an MCP registry entry (`io.github.wiresage/mikrotik-mcp`). The repository is `wiresage/mikrotik-mcp`.

- Python 3.10 or newer, `mcp>=2,<3`, `paramiko`, `pydantic-settings`.
- [uv](https://docs.astral.sh/uv/) is the toolchain. `pyproject.toml` declares dependency ranges (what `pip` and `uvx` users get), `uv.lock` pins the exact versions CI and the Docker image use, and test tooling sits in the `dev` dependency group. Commit `uv.lock` together with any `pyproject.toml` dependency change (`uv lock`); CI fails a PR whose lock is stale. Never edit `uv.lock` by hand.
- One server can manage several devices. Every tool takes an optional `device` (the inventory title), see `inventory.example.yml`.

## Setup commands

```bash
uv sync --frozen                                    # creates .venv from uv.lock, dev tooling included
uv run pytest -m "not integration"                  # what CI runs
uv run mcp-server-mikrotik --help                   # CLI options mirror the MIKROTIK_* env vars
```

Live testing needs a RouterOS device. The repo ships two throwaway RouterOS containers (SSH on host ports 2222 and 2223, default `admin` with an empty password, about two minutes to boot):

```bash
docker compose -f routeros-docker/docker-compose.yml up -d
uv run python tests/smoke_multi_device.py           # drives the server over stdio against both
```

## Project structure

```
src/mcp_mikrotik/
  app.py                   MCP server instance, READ/WRITE/... annotation presets, scope imports
  server.py                entry point (CLI parsing, transport selection)
  config.py                pydantic-settings: MIKROTIK_* env vars, CLI flags, inventory parsing
  connector.py             execute_mikrotik_command(): one fresh SSH connection per command
  inventory.py             multi-device inventory
  mikrotik_ssh_client.py   low-level SSH client (paramiko)
  configured_mcp_server.py --read-only filtering, sensitive-hiding wrapper, IP allowlist
  scope/                   one module per feature area, each registers tools with @mcp.tool
tests/unit/                fast tests, no device needed
tests/integration/         need Docker (testcontainers), marked `integration`
docs/reference/<area>/     one reference page per scope
```

## Writing tools

- Name the function `mikrotik_<verb>_<resource>` and register it with `@mcp.tool(name="<verb>_<resource>", annotations=annotate(READ, "Title"))`. Import `Context` from `mcp.server.mcpserver` (the snippets in CONTRIBUTING.md still show the old `mcp.server.fastmcp`).
- `ctx: Context` is the first parameter, `device: Optional[str] = None` the last, and it is passed on: `execute_mikrotik_command(cmd, ctx, device=device)`. Start with `await ctx.info(...)`. Return strings.
- Keep the docstring to one sentence. Docstrings are sent to the model on every `tools/list`, so their length is a recurring token cost. Add a `Notes:` block only for something non-obvious, such as which filters are substring matches and which are exact. Do not repeat the `device` explanation; the server sends it once at initialize.
- Use `Literal` for fixed value sets and `Annotated[int, Field(ge=..., le=...)]` for ranges.
- A new scope module also needs: an entry in the import list in `app.py`, an entry in `SCOPE_MODULES` in `tests/unit/test_scopes_smoke.py` (so the smoke test exercises its tools), a page at `docs/reference/<area>/README.md` and a link to it in `docs/reference/README.md`.

### Pick the annotation honestly

`--read-only` exposes only tools annotated `READ`, so the annotation is a safety control, not a label.

| Preset | Use for |
|---|---|
| `READ` | Reads that change nothing on the device. |
| `WRITE` | Non-idempotent writes (add, create). |
| `WRITE_IDEMPOTENT` | set, update, enable, disable, move. |
| `DESTRUCTIVE` | remove, flush, disconnect. |
| `DANGEROUS` | restore, import, reset, anything that can lock you out. |

Never mark a tool `READ` if it writes anything, including a file: `/export file=...` and `/system backup save` create files on the router and are not reads.

## RouterOS behaviour that has caused bugs here

Check these before trusting a new command, and verify on a real device (a 7.21 container is enough).

- **A successful `add`, `set` or `remove` prints nothing.** A refusal prints text on stdout with a zero exit status, and the text does not always contain "failure" or "error" (`not enough permissions (9)`, `expected end of command`, `no such item`). Treat any output from a write as a refusal, then confirm the change landed with `print count-only where ...`. Do not report success because no error word appeared.
- **A `set` or `remove` through `[find ...]` that matches nothing succeeds silently.** Count first and say "not found".
- **`print detail` prints the Flags legend even when nothing matches.** Decide "no results" by looking for real data (for example `"name=" in result`), not by checking for an empty string.
- **Quote enum values in `where` clauses:** `protocol="udp"`. An unquoted value can match nothing, with no error (issue #135).
- **Free text goes through `ros_quoted`.** Inside double quotes RouterOS reads `"`, `\` and `$` as syntax and turns non-ASCII bytes into blanks, so a comment like `say "hi"` fails with "expected end of command", `cost $5` loses the `$5` and `café` is stored as `caf `. Wrap every comment, log prefix, TXT text, SSID and password in `ros_quoted()` (`scope/_quoting.py`) before it goes into a command, and put both the raw and the escaped form of a secret in `redact=`.
- **Do not pass print positions as ids.** Numbers come from a per-device map that any `print` rebuilds, and every command here uses its own SSH connection. Use `*hex` ids, or resolve a position with `:pick [<menu> find] N` as `scope/_selectors.py` does. `:put [<menu> add ...]` echoes the new `*id`.
- **No interactive or streaming commands** (`follow`, `monitor` without `once`, anything that waits). They hang the non-interactive session.
- **Target RouterOS 7.** Some names changed from v6 (`routing-mark` is now `routing-table`), so do not copy v6 syntax from old forum posts.
- **`proplist=` works on `print detail`** and is the way to leave a field out of a result.

## Testing instructions

- Run `uv run pytest -m "not integration"` before every commit. CI runs it on Python 3.10, 3.11 and 3.12.
- Scope tests replace `execute_mikrotik_command` with `FakeExecutor` from `tests/conftest.py` (`monkeypatch.setattr(module, "execute_mikrotik_command", fake)`) and assert the exact command string. Cover the refusal path and the "nothing matched" path too, not only success.
- Put new unit tests in `tests/unit/test_scope_<area>.py`. Integration tests go in `tests/integration/`, use the `integration` marker and skip themselves without Docker.
- `tests/unit/test_scopes_smoke.py` lists wrappers that are known to raise (`BROKEN_WRAPPER_FUNCS`). If you fix one, remove it from that list.
- A bug fix needs a test that fails without the fix.

## Security considerations

- Everything interpolated into a RouterOS command is model-controlled input. Validate ids, durations, names and similar values with a regular expression before building the command (see `_DURATION_RE` in `scope/dhcp.py` and `scope/_selectors.py`) instead of passing them through.
- The connector logs every command, to the server log and to the client as a notification. Do not put a password, key or token in your own `ctx.info` text, and do not write secrets to test fixtures or docs.
- `--sensitive-hiding` (`MIKROTIK_SENSITIVE_HIDING`) redacts recognised credentials in results through `sensitive.py`. A new tool that can return secrets must work with it, and a tool whose output cannot be redacted safely should be left out of that mode (see `SENSITIVE_TOOLS` in `configured_mcp_server.py`).
- Inventory files and `.env` files hold credentials. Never commit one; `inventory.example.yml` is the template.
- `SECURITY.md` has the reporting process for vulnerabilities.

## Commit and pull request instructions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `revert`, with an optional scope, for example `fix(firewall): quote protocol_filter`.
- Branches are named `<type>/issue-<number>-<short-description>`, with a literal `#` in place of the number when there is no issue (`fix/issue-#-typo-in-docs`). Quote such names in the shell.
- Open pull requests against `master`. Keep each PR to one concern. Reference the issue with `Closes #N`.
- Do not merge, and do not push to `master`. A merge can publish a release (below), so leave it to a maintainer.

## What a merge to master does

The version is computed by GitVersion from the commit messages: `feat:` raises the minor version, `fix:`, `chore:`, `refactor:`, `perf:`, `style:`, `test:`, `ci:`, `build:` and `revert:` raise the patch, `docs:` does not bump. Do not edit the version in `pyproject.toml` or `server.json`; CI writes it.

A push to `master` runs the release workflows only when it changes a shipped file: `src/**`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `docker-entrypoint.sh` or `server.json`. Then it publishes to PyPI, the MCP registry and GHCR and creates a GitHub release. Changes to docs, tests, workflows or other markdown do not release. `server.json` and the README `mcp-name` marker must name the same registry entry.

Releases are queued, one at a time. When several merges land within a few minutes, a release that is still waiting is cancelled in favour of the newest one, which publishes everything merged so far under one version; seeing cancelled runs in Actions is expected. Wait for the last run to finish before checking PyPI or GHCR.

## Documentation

`docs/` is the source of the documentation; the website at mikrotik-mcp.com is built from the separate `wiresage/mikrotik-mcp-website` repository. When a tool's parameters change, update its page under `docs/reference/`.
