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
  app.py                   MCP server instance, READ/WRITE/... annotation presets, one import per area package
  server.py                entry point (CLI parsing, transport selection)
  config.py                pydantic-settings: MIKROTIK_* env vars, CLI flags, inventory parsing
  connector.py             execute_mikrotik_command(): one fresh SSH connection per command
  inventory.py             multi-device inventory
  mikrotik_ssh_client.py   low-level SSH client (paramiko)
  configured_mcp_server.py --read-only filtering, sensitive-hiding wrapper, IP allowlist
  scope/                   the tools, one package per feature area (below)
    _shared/               helpers used by several areas: quoting.py, selectors.py
    <area>/                __init__.py (a charter and `from . import ...`) and one module per RouterOS menu family
tests/unit/                fast tests, no device needed
tests/unit/scope/<area>/   tests of one area; tests/unit/scope/ holds the tests that span areas
tests/integration/         need Docker (testcontainers), marked `integration`
docs/reference/<area>/     reference pages of one area: README.md plus one page per module
```

### Where code goes

The areas are `devices`, `dhcp`, `dns`, `firewall`, `interfaces`, `ip`, `monitoring`, `queue`, `routing`, `system`, `users` and `vpn`; the table in [CONTRIBUTING.md](CONTRIBUTING.md#project-structure) says what belongs in each. The rules are checked by `tests/unit/scope/test_layout.py`:

- A module lives in the package of its area, named after the RouterOS menu it manages without repeating the area (`firewall/raw.py`). An area with a single module names it after the area (`dns/dns.py`).
- A new module is added to the `from . import ...` line in its area's `__init__.py`; a module that is not imported registers no tools. A new area is a new package, added once to the import list in `app.py`.
- A helper used by one area is a `_name.py` module inside that area; a helper used by several areas goes in `scope/_shared/`. Areas never import each other.
- Tool modules import `mcp`, the annotation presets and `annotate` from `...app`, `execute_mikrotik_command` from `...connector`, and shared helpers from `.._shared`.

## Writing tools

- Name the function `mikrotik_<verb>_<resource>` and register it with `@mcp.tool(name="<verb>_<resource>", annotations=annotate(READ, "Title"))`. Import `Context` from `mcp.server.mcpserver`.
- `ctx: Context` is the first parameter, `device: Optional[str] = None` the last, and it is passed on: `execute_mikrotik_command(cmd, ctx, device=device)`. Start with `await ctx.info(...)`. Return strings.
- Keep the docstring to one sentence. Docstrings are sent to the model on every `tools/list`, so their length is a recurring token cost. Add a `Notes:` block only for something non-obvious, such as which filters are substring matches and which are exact. Do not repeat the `device` explanation; the server sends it once at initialize.
- Use `Literal` for fixed value sets and `Annotated[int, Field(ge=..., le=...)]` for ranges.
- A new tool module also needs: its name in its area's `__init__.py` (a new area also needs one name in the import list in `app.py`), tests in `tests/unit/scope/<area>/test_<module>.py` (the smoke test finds the module itself, there is no list to update), and a reference page `docs/reference/<area>/<module>.md` linked from the area's overview and from `docs/reference/README.md` (in a single-module area the page is the area's `README.md`).

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

### Declare the tool in the API coverage manifest

`docs/api-coverage.yml` is the source of truth; `docs/api-coverage.md` is generated — never edit it by hand. A new or changed tool is not finished until the manifest is updated.

- Set `status` (`implemented`, `partial`, `planned`, `legacy` or `not_applicable`) and list the registered MCP tool name(s) in `tools` for `implemented`, `partial` and `legacy`. `not_applicable` may also list the tool that explains it; `planned` commands must not list tools.
- `params` uses manual argument names (`vlan-id`, not `vlan_id`; `configuration.ssid` for nested arguments). `accepted_gaps` is for intentional omissions of manual arguments; read-only fields and flags are excluded from the unmapped-argument check automatically, so do not add them just to silence warnings.
- Add `notes` for `partial`, `legacy` or `not_applicable`, or for a non-obvious caveat. Menu-level `notes` explain the scope. Do not repeat the tool docstring.
- Use `manual_paths` for menus documented as separate command pages, and include the parent page when it has arguments. Use `allow_missing_manual` only for commands with no standalone manual page.
- Tools that do not map to one menu command go in `server_tools` (`kind` + note); out-of-scope menus go in the top-level `excluded` list with a reason.
- A new module also needs the registration, tests and reference page described under "Writing tools".

Then run:

```bash
uv run python scripts/api_coverage.py --write
uv run python scripts/api_coverage.py --check
uv run pytest -m "not integration"
```

CI fails if the generated checklist is stale, a registered tool is missing from the manifest, a manifest tool does not exist, or the manifest is structurally invalid. `docs/manual.lock.yml` is updated only after reviewing a drift report (from the manual-only **Check API coverage** workflow or a local `--manual` run); the manual corpus is never committed.

## RouterOS behaviour that has caused bugs here

Check these before trusting a new command, and verify on a real device (a 7.21 container is enough).

- **A successful `add`, `set` or `remove` prints nothing.** A refusal prints text on stdout with a zero exit status, and the text does not always contain "failure" or "error" (`not enough permissions (9)`, `expected end of command`, `no such item`). Treat any output from a write as a refusal, then confirm the change landed with `print count-only where ...`. Do not report success because no error word appeared.
- **A `set` or `remove` through `[find ...]` that matches nothing succeeds silently.** Count first and say "not found".
- **`print detail` prints the Flags legend even when nothing matches.** Decide "no results" by looking for real data (for example `"name=" in result`), not by checking for an empty string.
- **Quote enum values in `where` clauses:** `protocol="udp"`. An unquoted value can match nothing, with no error (issue #135).
- **Do not pass print positions as ids.** Numbers come from a per-device map that any `print` rebuilds, and every command here uses its own SSH connection. Use `*hex` ids, or resolve a position with `:pick [<menu> find] N` as `scope/_shared/selectors.py` does. `:put [<menu> add ...]` echoes the new `*id`.
- **No interactive or streaming commands** (`follow`, `monitor` without `once`, anything that waits). They hang the non-interactive session.
- **Target RouterOS 7.** Some names changed from v6 (`routing-mark` is now `routing-table`), so do not copy v6 syntax from old forum posts.
- **`proplist=` works on `print detail`** and is the way to leave a field out of a result.

## Testing instructions

- Run `uv run pytest -m "not integration"` before every commit. CI runs it on Python 3.10, 3.11 and 3.12.
- Scope tests replace `execute_mikrotik_command` with `FakeExecutor` from `tests/conftest.py` (`monkeypatch.setattr(module, "execute_mikrotik_command", fake)`) and assert the exact command string. Cover the refusal path and the "nothing matched" path too, not only success.
- Put new unit tests in `tests/unit/scope/<area>/test_<module>.py`; a test that spans several areas goes in `tests/unit/scope/`. Every test folder is a package, so a new area folder needs an `__init__.py`. Integration tests go in `tests/integration/`, use the `integration` marker and skip themselves without Docker.
- `tests/unit/scope/test_smoke.py` runs every tool function with dummy arguments and finds the modules itself, so there is no list to update. `tests/unit/scope/test_layout.py` checks the layout rules under "Where code goes" and says what to move or import when one is broken.
- A bug fix needs a test that fails without the fix.

## Security considerations

- Everything interpolated into a RouterOS command is model-controlled input. Validate ids, durations, names and similar values with a regular expression before building the command (see `_DURATION_RE` in `scope/dhcp/dhcp.py` and `scope/_shared/selectors.py`) instead of passing them through.
- The connector logs every command, to the server log and to the client as a notification. Do not put a password, key or token in your own `ctx.info` text, and do not write secrets to test fixtures or docs.
- `--sensitive-hiding` (`MIKROTIK_SENSITIVE_HIDING`) redacts recognised credentials in results through `sensitive.py`. A new tool that can return secrets must work with it, and a tool whose output cannot be redacted safely should be left out of that mode (see `SENSITIVE_TOOLS` in `configured_mcp_server.py`).
- Inventory files and `.env` files hold credentials. Never commit one; `inventory.example.yml` is the template.
- `SECURITY.md` has the reporting process for vulnerabilities.

## Commit and pull request instructions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `revert`, with an optional scope, for example `fix(firewall): quote protocol_filter`.
- Branches are named `<type>/issue-<number>-<short-description>`, with a literal `#` in place of the number when there is no issue (`fix/issue-#-typo-in-docs`). Quote such names in the shell.
- Open pull requests against `master`. Keep each PR to one concern. Reference the issue with `Closes #N`.
- Assign the pull request to the contributor it is for, not to yourself (`gh pr create --assignee <login>`, or
  `gh pr edit --add-assignee <login>`). If you do not know their login, leave it unassigned and say so in the description.
- Do not merge, and do not push to `master`. A merge can publish a release (below), so leave it to a maintainer.

## What a merge to master does

The version is computed by GitVersion from the commit messages: `feat:` raises the minor version, `fix:`, `chore:`, `refactor:`, `perf:`, `style:`, `test:`, `ci:`, `build:` and `revert:` raise the patch, `docs:` does not bump. Do not edit the version in `pyproject.toml` or `server.json`; CI writes it.

A push to `master` runs the release workflows only when it changes a shipped file: `src/**`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `docker-entrypoint.sh` or `server.json`. Then it publishes to PyPI, the MCP registry and GHCR and creates a GitHub release. Changes to docs, tests, workflows or other markdown do not release. `server.json` and the README `mcp-name` marker must name the same registry entry.

Releases are queued, one at a time. When several merges land within a few minutes, a release that is still waiting is cancelled in favour of the newest one, which publishes everything merged so far under one version; seeing cancelled runs in Actions is expected. Wait for the last run to finish before checking PyPI or GHCR.

## Documentation

`docs/` is the source of the documentation; the website at mikrotik-mcp.com is built from the separate `wiresage/mikrotik-mcp-website` repository. When a tool's parameters change, update its page under `docs/reference/`. A change to the scope layout or to the contributor workflow also needs a matching change in that repository, whose contributing page describes both.
