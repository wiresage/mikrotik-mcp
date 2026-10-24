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
├── connector.py    # SSH connection handling
├── server.py       # Entry point — imports scopes, starts the server
└── mikrotik_ssh_client.py  # Low-level SSH client

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
- Import `mcp` and the appropriate `ToolAnnotations` constant from `..app`
- Import `execute_mikrotik_command` from `..connector`
- Register tools using `@mcp.tool()` decorators with annotations
- Follow the existing naming convention: `mikrotik_<action>_<resource>`
- Use type hints for all parameters (including `Literal` for fixed-value params)
- Handle errors gracefully and return meaningful messages

**Example structure** (based on `dhcp.py`):
```python
from typing import Optional
from mcp.server.fastmcp import Context
from ..connector import execute_mikrotik_command
from ..app import mcp, READ, WRITE

@mcp.tool(name="create_my_resource", annotations=WRITE)
async def mikrotik_create_my_resource(
    ctx: Context,
    name: str,
    required_param: str,
    optional_param: Optional[str] = None,
    comment: Optional[str] = None
) -> str:
    """Creates a new resource on MikroTik device."""
    await ctx.info(f"Creating resource: name={name}")

    cmd = f"/my/feature add name={name} param={required_param}"

    if optional_param:
        cmd += f" optional-param={optional_param}"
    if comment:
        cmd += f' comment="{comment}"'

    result = await execute_mikrotik_command(cmd, ctx)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create resource: {result}"

    return f"Resource created successfully:\n\n{result}"
```

### 2. Choose the Right Tool Annotation

Import the appropriate annotation constant from `app.py` and pass it via `@mcp.tool(annotations=...)`:

| Constant | Use for |
|---|---|
| `READ` | Read-only queries (print, list, get, export) |
| `WRITE` | Non-idempotent writes (add, create) |
| `WRITE_IDEMPOTENT` | Idempotent writes (set, update, enable, disable) |
| `DESTRUCTIVE` | Idempotent destructive operations (remove, flush) |
| `DANGEROUS` | Non-idempotent destructive operations (reset, bulk create) |

### 3. Register Your Scope

Update `src/mcp_mikrotik/app.py` to import your new scope module:

```python
from mcp_mikrotik.scope import (  # noqa: F401
    backup, dhcp, dns, firewall_filter, firewall_nat,
    ip_address, ip_pool, logs, my_feature, routes, users, vlan, wireless,
)
```

The import triggers the `@mcp.tool()` decorators, which automatically register your tools with the MCP server. No manual registry is needed.

### 4. Write Tests

Create tests in `tests/` for unit tests or `tests/integration/` for integration tests.

Integration tests should:
- Use testcontainers to spin up a real MikroTik RouterOS container
- Follow the existing test structure and naming conventions
- Test complete workflows (create, read, update, delete operations)
- Include proper cleanup to ensure tests are isolated
- Use the `@pytest.mark.integration` decorator

**Example structure** (based on `test_mikrotik_user_integration.py`):
```python
"""Integration tests for MikroTik my feature using testcontainers."""

import pytest
from mcp_mikrotik.scope.my_feature import (
    mikrotik_create_my_resource,
    mikrotik_list_my_resources
)

@pytest.mark.integration
class TestMikroTikMyFeatureIntegration:
    def test_01_create_resource(self, mikrotik_container):
        result = mikrotik_create_my_resource(
            name="test_resource",
            required_param="test_value"
        )
        assert "failed" not in result.lower()
        assert "test_resource" in result

    def test_02_list_resources(self, mikrotik_container):
        result = mikrotik_list_my_resources()
        assert "test_resource" in result
```

### 5. Test Your Implementation

Before submitting, ensure your implementation works:

1. **Run integration tests**: `uv run pytest tests/integration/test_my_feature_integration.py -v`
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

## Commit Message Format and Versioning

This project uses [GitVersion](https://gitversion.net/) for automatic semantic versioning based on commit messages. We follow [Conventional Commits](https://www.conventionalcommits.org/) specification.

All pull requests merge directly to `master`. There are no `develop` or `release` branches. Every merge that contains a non-`docs` commit will publish a new package version automatically.

### Version Format

Published versions use a **4-part** format: `MAJOR.MINOR.PATCH.BUILD`

| Position | Label | Incremented by |
|---|---|---|
| 1 (MAJOR) | `x.0.0.0` | **Never** — frozen at `0` |
| 2 (MINOR) | `0.x.0.0` | `feat:` commits |
| 3 (PATCH) | `0.0.x.0` | `fix:`, `chore:`, and other change commits |
| 4 (BUILD) | `0.0.0.x` | Auto — commit count since last version tag |
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

1. PR is merged to `master`
2. GitVersion calculates the new version from commit history
3. GitHub Actions builds the package with the calculated version
4. Unit tests run across Python 3.10 / 3.11 / 3.12
5. Package is published to PyPI (`skip-existing: true` — duplicate versions are silently skipped, never fail the pipeline)
6. Git tag and GitHub Release are created automatically

You never need to manually bump version numbers or create tags.

### Best Practices

1. **Be intentional with commit types** — `feat:` and `fix:` trigger **minor** version bumps automatically
2. **Default is minor bump** — Any commit to master without `+semver:` tags will bump the minor version
3. **Use `+semver: none` or `+semver: skip`** — To prevent version bumps for CI/CD, tests, or internal changes
4. **Use `+semver: patch`** — For documentation, formatting, or minor non-functional changes that should only bump patch version
5. **Use `+semver: breaking` or `+semver: major`** — For breaking changes that require major version bump
6. **Write clear commit messages** — They become part of the release history and changelog
7. **One logical change per commit** — Makes version history clearer and easier to track
8. **Test before committing** — Failed builds don't get published

## Submitting a Pull Request

1. **Fork the repository** and create your feature branch from `master`
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