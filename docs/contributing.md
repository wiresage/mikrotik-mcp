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
from mcp.server.fastmcp import Context
from ..connector import execute_mikrotik_command
from ..app import mcp, READ, WRITE, annotate

@mcp.tool(name="create_my_resource", annotations=annotate(WRITE, "Create My Resource"))
async def mikrotik_create_my_resource(
    ctx: Context,
    name: str,
    required_param: str,
    optional_param: Optional[str] = None,
    comment: Optional[str] = None
) -> str:
    """Creates a new resource on the MikroTik device."""
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

## Commit Message Format

This project follows [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Format
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools

### Examples
```
feat(dhcp): add DHCP server creation and management tools

Add comprehensive DHCP server management including:
- Create DHCP servers with configurable options
- List and filter DHCP servers
- Create DHCP networks and pools
- Remove DHCP servers

Includes integration tests with RouterOS container
```

```
fix(firewall): handle special characters in rule comments

Escape special characters when creating firewall rules with comments
to prevent command parsing errors on RouterOS devices
```

```
test(users): expand integration test coverage

Add tests for user group management and permission validation
```

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
5. **Write descriptive commit messages** following conventional commits
6. **Submit a pull request** with:
   - Clear description of what you've added
   - Reference to any related issues
   - Screenshots or examples if applicable
   - Confirmation that tests pass

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

Thank you for contributing to MikroTik MCP! Your additions help make RouterOS management more accessible through the Model Context Protocol.
