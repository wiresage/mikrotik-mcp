# Contributing to MikroTik MCP

Thank you for your interest in contributing to the MikroTik MCP server! This guide will help you understand the project structure and contribution process.

## Overview

This MCP (Model Context Protocol) server provides tools for managing MikroTik RouterOS devices. Contributors can extend functionality by adding new scopes (feature areas) and their corresponding tools.

## Project Structure

```
src/mcp_mikrotik/
├── scope/          # Feature modules — each file registers MCP tools via decorators
├── app.py          # MCPServer instance and ToolAnnotation constants
├── config.py       # Configuration (pydantic-settings, CLI args, env vars)
├── configured_mcp_server.py  # Read-only filtering, sensitive hiding, IP allowlist
├── connector.py    # Runs one command over a fresh SSH connection
├── http_security.py  # IP allowlist for the HTTP transports
├── inventory.py    # Multi-device inventory
├── mikrotik_ssh_client.py  # Low-level SSH client
├── safe_mode.py    # RouterOS safe mode sessions
├── sensitive.py    # Credential redaction
└── server.py       # Entry point: CLI parsing and transport selection

tests/
├── integration/    # Integration tests using testcontainers
└── unit/          # Unit tests
```

## Development Setup

The project uses [uv](https://docs.astral.sh/uv/) as its single Python toolchain;
[install uv](https://docs.astral.sh/uv/getting-started/installation/) first. After
that, provisioning a working environment is **two commands**:

```bash
git clone https://github.com/wiresage/mikrotik-mcp.git
cd mikrotik-mcp
uv sync --frozen
```

`uv sync --frozen` installs the exact versions pinned in `uv.lock` (including the
`dev` dependency group) without re-resolving, so a clean checkout gets the same
environment CI uses. `uv` creates and manages the `.venv` for you.

### Running the tests

```bash
uv run pytest                        # full suite
uv run pytest -m "not integration"   # unit tests only (no Docker needed)
uv run pytest -m integration         # integration tests (needs Docker)
```

No manual dependency install is needed — `uv run` executes against the locked
environment.

### Changing dependencies (regenerating the lockfile)

When you add, remove, or change a dependency in `pyproject.toml`, regenerate and
commit the lockfile **in the same PR**:

```bash
uv lock    # update uv.lock to match pyproject.toml
uv sync    # apply it to your environment
```

CI runs a **lockfile-drift gate** (`uv lock --check`): a PR that changed
`pyproject.toml` without a matching `uv.lock` fails with a plain-language message
saying the lockfile is out of date. Commit the updated `uv.lock` and the gate passes.

Keep these in mind when you touch dependencies:

- `pyproject.toml` declares the version **ranges** users get (`pip`, `uvx`); `uv.lock`
  pins the exact versions used by CI, the release build's tests and the Docker image.
  Never edit `uv.lock` by hand.
- Test tooling (`pytest`, `testcontainers`) lives in the `dev` dependency group, not in
  `dependencies`, so it is not shipped in the wheel or the Docker image.
- `uv.lock` counts as a shipped file: a merged change to it releases a new version,
  because the Docker image installs from it.
- Do not edit the `version` line in `pyproject.toml`; the release workflow writes it.

## Contributing New Features

To add a new MikroTik feature/scope to the project, follow these steps:

### 1. Create the Scope Implementation

Navigate to `src/mcp_mikrotik/scope/` and create a new Python file for your feature (e.g., `my_feature.py`).

Your scope file should:
- Import `mcp`, the appropriate `ToolAnnotations` constant, **and `annotate`** from `..app`
- Import `execute_mikrotik_command` from `..connector`
- Register tools using `@mcp.tool()` decorators — **always use `annotate(BASE, "Title")`** (never a bare constant)
- Follow the existing naming convention: `mikrotik_<action>_<resource>`
- Use type hints for all parameters (including `Literal` for fixed-value params)
- Keep docstrings **concise** — a single sentence is ideal; avoid re-documenting every parameter
- Handle errors gracefully and return meaningful messages

**Example structure**:
```python
from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, WRITE, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted


@mcp.tool(name="create_my_resource", annotations=annotate(WRITE, "Create My Resource"))
async def mikrotik_create_my_resource(
    ctx: Context,
    name: str,
    comment: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Creates a resource on the MikroTik device."""
    await ctx.info(f"Creating resource: name={name}")

    quoted_name = ros_quoted(name)
    cmd = f'/my/feature add name="{quoted_name}"'
    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    # A successful add prints nothing, so any output is a refusal.
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Failed to create resource: {result}"

    count = await execute_mikrotik_command(
        f'/my/feature print count-only where name="{quoted_name}"', ctx, device=device
    )
    if count.strip() == "0":
        return f"Failed to create resource: '{name}' was not found afterwards."

    return f"Resource '{name}' created."
```

### 2. Choose the Right Tool Annotation

Import the appropriate annotation constant from `app.py` and pass it via `@mcp.tool(annotations=...)`:

| Constant | Use for |
|---|---|
| `READ` | Reads that change nothing on the device. `/export file=...` and `/system backup save` write files, so they are not reads |
| `WRITE` | Non-idempotent writes (add, create) |
| `WRITE_IDEMPOTENT` | Idempotent writes (set, update, enable, disable, move) |
| `DESTRUCTIVE` | Removals (remove, flush, disconnect) |
| `DANGEROUS` | Restore, import, reset, and anything that can lock you out |

`--read-only` exposes only `READ` tools, so this choice is a safety control.

### 3. Register Your Scope

Add your module to the `from mcp_mikrotik.scope import (...)` list in `src/mcp_mikrotik/app.py`. The import triggers the `@mcp.tool()` decorators, which register your tools with the MCP server.

Then add:

- the module name to `SCOPE_MODULES` in `tests/unit/test_scopes_smoke.py`
- a reference page at `docs/reference/<area>/README.md`, linked from `docs/reference/README.md`
- the tools to `docs/api-coverage.yml` (see [API Coverage](#api-coverage))

### 4. Write Tests

Put unit tests in `tests/unit/test_scope_<area>.py`. Replace the connector with `FakeExecutor`, assert the exact command, and cover the refusal and "nothing matched" paths as well as success:

```python
import asyncio

from mcp_mikrotik.scope import my_feature
from tests.conftest import FakeExecutor


def test_create_sends_expected_command(ctx, monkeypatch):
    fake = FakeExecutor()
    monkeypatch.setattr(my_feature, "execute_mikrotik_command", fake)

    result = asyncio.run(my_feature.mikrotik_create_my_resource(ctx, name="r1"))

    assert fake.commands[0] == '/my/feature add name="r1"'
    assert "created" in result
```

Integration tests go in `tests/integration/`, use the `@pytest.mark.integration` marker, and run against a RouterOS container started with testcontainers. See `tests/integration/test_mikrotik_user_integration.py`.

### 5. Test Your Implementation

Before submitting, ensure your implementation works:

1. **Run the unit tests**: `uv run pytest -m "not integration"`
2. **Use MCP Inspector**: Test your tools interactively using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
   ```bash
   # Test your MCP server (stdio transport)
   npx @modelcontextprotocol/inspector uv run mcp-server-mikrotik
   ```
3. **Manual testing**: Test with a real MikroTik device to ensure commands work correctly

## Transport Modes

The server supports three transport modes:

- **stdio** (default) — standard input/output, used by most MCP clients
- **sse** — Server-Sent Events over HTTP (exposes `/health` endpoint)
- **streamable-http** — HTTP with streaming support (exposes `/health` endpoint)

Configure via CLI (`--mcp.transport`) or environment variable (`MIKROTIK_MCP__TRANSPORT`).

## Development Guidelines

### Code Style
- Follow existing code patterns and naming conventions
- Use type hints for all function parameters and return values
- Use `Literal` types for parameters with a fixed set of valid values
- Use `Annotated[..., Field(...)]` for numeric constraints (e.g., VLAN IDs)
- Handle errors gracefully with meaningful error messages
- Log important operations using `ctx.info()` / `ctx.error()` for client-visible logging

### MikroTik Command Guidelines
- Always validate command syntax against MikroTik documentation
- Use proper escaping for string parameters (wrap in quotes when needed)
- Implement both creation and listing/querying functionality
- Consider implementing filtering options where appropriate
- Test commands on actual RouterOS before implementation

### Testing Requirements
- Write tests that cover the main functionality
- Ensure tests are isolated and clean up after themselves
- Use descriptive test names that explain what is being tested
- Include edge cases and error conditions in your tests

### API Coverage

`docs/api-coverage.yml` is the source of truth for the RouterOS menus and commands the MCP intends to cover. `docs/api-coverage.md` is generated from it; never edit it by hand. The generated checklist is the checked/unchecked progress view for developers and users.

When adding or changing a tool:

1. Update `docs/api-coverage.yml`:
   - `status`: `implemented`, `partial`, `planned`, `legacy` or `not_applicable`.
   - `tools`: registered MCP tool names for `implemented`, `partial` and `legacy`. `not_applicable` may also list the tool that explains it; `planned` commands must not list tools.
   - `params`: manual argument names (`vlan-id`, not `vlan_id`; `configuration.ssid` for nested arguments).
   - `accepted_gaps`: intentional omissions of manual arguments. Read-only fields and flags are excluded from the unmapped-argument check automatically, so do not add them just to silence warnings.
   - `notes`: explain `partial`, `legacy`, `not_applicable`, or a non-obvious caveat. Menu-level `notes` explain the scope; do not repeat the tool docstring.
   - `manual_paths`: menus documented as separate command pages. Include the parent page when it has arguments.
   - `allow_missing_manual`: only for commands with no standalone manual page.
   - `server_tools`: tools that do not map to one menu command (`kind` + note).
   - top-level `excluded`: out-of-scope menus, with a reason.
2. Run `uv run python scripts/api_coverage.py --write`.
3. Run `uv run python scripts/api_coverage.py --check`; CI runs the same check.
4. Run `uv run pytest -m "not integration"`.
5. Commit `docs/api-coverage.yml`, the regenerated `docs/api-coverage.md`, and the tool code/tests/docs.

If the tool's parameters change, update its page under `docs/reference/<area>/`.

The **Check API coverage** workflow does not update the lockfile (`docs/manual.lock.yml`) or manifest (`docs/api-coverage.yml`): review the `api-coverage-report` artifact, then update `docs/manual.lock.yml` and the manifest deliberately, run `--write`, and commit. Use `--strict` (or the workflow's `strict` input) when warnings should fail the run. The corpus is not committed; only the lockfile metadata is.

### PR demo GIF

Every pull request that targets `master` gets one comment from the **PR demo** workflow: a short GIF that illustrates the change, a title, a one-line description and a `#demonstration_<pr-title>` tag (spaces become `-`). The comment is updated on every push. The GIF is drawn by AI from the diff, so it is an illustration, not a recording; check it against the code. The workflow runs from `master` and never executes code from the pull request: the model gets no tools, `scripts/pr_demo.py` validates its storyboard and draws the GIF, and GIFs are stored on the orphan `pr-demos` branch. Re-run it for a pull request from the Actions tab (**PR demo**, *Run workflow*, with the number).

## Commit Message Format and Versioning

This project uses [GitVersion](https://gitversion.net/) for automatic semantic versioning based on commit messages. We follow [Conventional Commits](https://www.conventionalcommits.org/) specification.

All pull requests merge directly to `master`. There are no `develop` or `release` branches. A merge publishes a new version only when it changes a shipped file: `src/**`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `docker-entrypoint.sh` or `server.json`.

### Version Format

Published versions use a **4-part** format: `MAJOR.MINOR.PATCH.BUILD`

| Position | Label | Incremented by |
|---|---|---|
| 1 (MAJOR) | `x.0.0.0` | **Never** — frozen at `0` |
| 2 (MINOR) | `0.x.0.0` | `feat:` commits |
| 3 (PATCH) | `0.0.x.0` | `fix:`, `chore:`, and other change commits |
| 4 (BUILD) | `0.0.0.x` | Always `0` |
| — | no change | `docs:` commits |

### Quick Reference Table

| Commit prefix | Example | Version change |
|---|---|---|
| `feat:` | `feat: add queue management tools` | Minor bump: `0.5.0 → 0.6.0` |
| `fix:` | `fix: handle empty SSH response` | Patch bump: `0.5.0 → 0.5.1` |
| `chore:` | `chore: update dependencies` | Patch bump: `0.5.0 → 0.5.1` |
| `refactor:` | `refactor: simplify connector` | Patch bump: `0.5.0 → 0.5.1` |
| `perf:` | `perf: cache SSH connection` | Patch bump: `0.5.0 → 0.5.1` |
| `ci:` | `ci: add Python 3.13 to matrix` | Patch bump: `0.5.0 → 0.5.1` |
| `test:` | `test: add queue smoke tests` | Patch bump: `0.5.0 → 0.5.1` |
| `docs:` | `docs: update safe mode guide` | **No bump** |
| `doc:` | `doc: fix typo` | **No bump** |
| (untyped) | `update something` | Patch bump (fallback) |
| `+semver: breaking` | footer tag | Major bump (emergency only) |

> **Major version is intentionally frozen at `0`.** Never use `+semver: breaking` or `+semver: major` without explicit approval.

### Commit Message Structure

```
<type>[optional scope]: <description>

[optional body]
```

#### Types

| Type | Description | Version effect |
|---|---|---|
| `feat` | New feature or tool | Minor bump |
| `fix` | Bug fix | Patch bump |
| `chore` | Dependency updates, tooling | Patch bump |
| `refactor` | Code restructuring | Patch bump |
| `perf` | Performance improvement | Patch bump |
| `ci` | CI/CD pipeline changes | Patch bump |
| `test` | Test additions or updates | Patch bump |
| `style` | Code formatting | Patch bump |
| `build` | Build system changes | Patch bump |
| `revert` | Reverting a previous commit | Patch bump |
| `docs` / `doc` | Documentation only | **No bump** |

#### Scopes (optional)

Scopes help indicate which area of the codebase is affected:
- Feature areas: `dhcp`, `dns`, `firewall`, `wireless`, `users`, `backup`, `queue`, `safe-mode`, `wireguard`, etc.
- Infrastructure: `api`, `cli`, `config`, `ssh`, `connector`

### Examples

#### Example 1: New Feature → Minor Bump

```bash
git commit -m "feat(queue): add simple queue and queue tree management

Implements create, list, get, update, remove, enable, and disable
operations for queue types, queue trees, and simple queues."
```
**Result:** `0.5.0.0 → 0.6.0.0`

#### Example 2: Bug Fix → Patch Bump

```bash
git commit -m "fix(safe-mode): handle ANSI escape sequences in <SAFE> prompt detection"
```
**Result:** `0.5.0.0 → 0.5.1.0`

#### Example 3: Chore / Maintenance → Patch Bump

```bash
git commit -m "chore: bump paramiko to 3.5.1 for CVE-2024-xxxx"
```
**Result:** `0.5.0.0 → 0.5.1.0`

#### Example 4: Documentation → No Bump

```bash
git commit -m "docs: add queue and safe-mode reference pages"
```
**Result:** version unchanged — pipeline skips PyPI publish

#### Example 5: Mixed PR (feat + docs commits)

When a PR contains both `feat:` and `docs:` commits, GitVersion picks the **highest** increment across all commits. The result is a Minor bump.

### Version Release Process

1. PR that changes a shipped file is merged to `master`
2. GitVersion calculates the new version from commit history
3. GitHub Actions builds the package with the calculated version
4. Unit tests run across Python 3.10 / 3.11 / 3.12
5. Package is published to PyPI (`skip-existing: true` — duplicate versions are silently skipped, never fail the pipeline)
6. Git tag and GitHub Release are created automatically

You never need to manually bump version numbers or create tags.

### Best Practices

1. **Be intentional with commit types**: `feat:` bumps the minor version, and other change types bump the patch version
2. **Use `docs:` for documentation-only commits**: they do not bump the version
3. **Do not use `+semver: breaking` or `+semver: major`** without explicit approval; the major version is frozen at `0`
4. **Write clear commit messages**: they become part of the release history and changelog
5. **Keep one logical change per commit**: it makes version history easier to follow
6. **Test before committing**: failed builds don't get published

## Branching Strategy

Branches for new pull requests carry the issue number they address:

```
<type>/issue-<number>-<short-description>
```

- `<type>` is one of the conventional commit types above (`feat`, `fix`, `docs`, …)
- `<number>` is the GitHub issue number the branch addresses
- when the change has **no issue**, put `#` in place of the number
- `<short-description>` is a few kebab-case words describing the change

### Examples

```
feat/issue-123-branch-one
fix/issue-#-branch-two
```

This makes every branch self-documenting: the type tells reviewers what kind
of change to expect, and the issue number links the work back to its context
(or `#` states explicitly that no issue exists, rather than leaving reviewers
to search for one).

## Submitting a Pull Request

1. **Fork the repository** and create your feature branch from `master`,
   named according to the [branching strategy](#branching-strategy) above
2. **Implement your changes** following the guidelines above
3. **Run all tests** to ensure nothing is broken
4. **Test with MCP Inspector** to verify tools work correctly
5. **Write descriptive commit messages** following the format above
6. **Submit a pull request** with:
   - Clear description of what you've added
   - Reference to any related issues
   - Screenshots or examples if applicable
   - Confirmation that tests pass
   - Indication of version bump impact (minor, major, patch, or none)
7. **Assign the pull request to yourself.** Use *Assignees* in the sidebar, or open it with
   `gh pr create --assignee @me`. GitHub only lets people with write access set assignees; if you
   cannot, a maintainer assigns the pull request to you, so every contribution is listed under the
   contributor's name.

## Getting Help

- Check existing scope implementations for reference
- Review the MikroTik RouterOS documentation for command syntax
- Look at existing tests for testing patterns
- Open an issue if you need clarification on implementation details

## Code Review Process

All contributions go through code review to ensure:
- Code follows project conventions and patterns
- MikroTik commands are correct and safe
- Tests provide adequate coverage
- Documentation is clear and complete
- Integration with existing codebase is smooth
- Commit messages follow versioning guidelines

Thank you for contributing to MikroTik MCP! Your additions help make RouterOS management more accessible through the Model Context Protocol.