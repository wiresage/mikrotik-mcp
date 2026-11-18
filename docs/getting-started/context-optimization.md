# Context Length Optimization

MikroTik MCP ships **239 tools**. The `tools/list` answer a client receives is about
230 KB of JSON, which is roughly 57 000 tokens (an estimate at four characters per
token; tokenizers differ). That is more than the entire context window of many local
LLMs (LM Studio, Ollama, etc.).

Two things keep it smaller: every tool carries a short `title`, and descriptions stay
at a sentence or two. For anything beyond that, `--read-only` is the lever.

---

## What is in place

### 1. `title` in `ToolAnnotations`

Every `@mcp.tool()` call passes `annotations=annotate(READ|WRITE|…, "Short Title")`.

```python
# before
@mcp.tool(name="create_queue_type", annotations=WRITE)

# after
@mcp.tool(name="create_queue_type", annotations=annotate(WRITE, "Create Queue Type"))
```

The `title` field is part of the [MCP Tool Annotations spec][spec].
MCP clients that support it can display a compact tool list using only the
title, without rendering the full description text, which shrinks the prompt
context they pass to the LLM.

### 2. Short descriptions

Verbose multi-paragraph docstrings with redundant `Args:` / `Returns:`
sections are not used. The function signature already carries full type
information; the description only needs to convey *what* the tool does. A tool
keeps a `Notes:` block only when something is not obvious from its signature.

| Tool | Description today |
|------|-------------------|
| `generate_wireguard_client_config` | 120 chars |
| `create_queue_type` | 429 chars |
| `create_filter_rule` | 517 chars |
| _all 239 tools (avg)_ | **155 chars** |

The longest are the read tools that explain a legend or a redaction rule, for example
`get_ipsec_installed_sa` (about 1 750 chars) and `list_netwatch` (about 1 240 chars).

---

## How to benefit

### MCP clients that use `title`

Any client following the MCP spec can read `tool.annotations.title` and show
that short string in its tool list rather than the full description. If you
are building an integration, prefer displaying the title in compact views.

### Local LLMs with small context windows

Start the server with `--read-only` (or `MIKROTIK_READ_ONLY=true`). It exposes only the
107 tools that change nothing on the router, and their `tools/list` answer is about
91 KB, roughly 23 000 tokens, against about 57 000 for all 239 tools. See the
[CLI options](installation.md#cli-options).

> `--read-only` limits the MCP tool catalogue only. Use a restricted RouterOS
> account if the router itself must not be changed.

There is no per-area switch: a deployment that needs a different subset has to
use `--read-only` or filter the tool list in the client.

---

## Developer notes

The `annotate()` helper lives in `src/mcp_mikrotik/app.py`:

```python
def annotate(base: ToolAnnotations, title: str) -> ToolAnnotations:
    """Return a copy of *base* with a human-readable *title* attached."""
    return ToolAnnotations(
        title=title,
        read_only_hint=base.read_only_hint,
        destructive_hint=base.destructive_hint,
        idempotent_hint=base.idempotent_hint,
        open_world_hint=base.open_world_hint,
    )
```

When adding new tools, always use `annotate()` instead of a bare annotation
constant:

```python
# ✅ correct
@mcp.tool(name="my_new_tool", annotations=annotate(READ, "My New Tool"))

# ❌ avoid — omits the title
@mcp.tool(name="my_new_tool", annotations=READ)
```

[spec]: https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/
