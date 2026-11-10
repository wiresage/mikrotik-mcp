# Context Length Optimization

MikroTik MCP ships **162 tools**. At full verbosity the tool schema can occupy
≈ 54 000 tokens — more than the entire context window of many local LLMs
(LM Studio, Ollama, etc.).

Starting with this release every tool carries a short **`title` annotation**
(MCP spec 2025-03-26) and a trimmed description, reducing the description
token budget by **~75 %**.

---

## What changed

### 1. `title` in `ToolAnnotations`

Every `@mcp.tool()` call now passes `annotations=annotate(READ|WRITE|…, "Short Title")`.

```python
# before
@mcp.tool(name="create_queue_type", annotations=WRITE)

# after
@mcp.tool(name="create_queue_type", annotations=annotate(WRITE, "Create Queue Type"))
```

The `title` field is part of the [MCP Tool Annotations spec][spec].  
MCP clients that support it can display a compact tool list using only the
title — without rendering the full description text — significantly shrinking
the prompt context they pass to the LLM.

### 2. Trimmed descriptions

Verbose multi-paragraph docstrings with redundant `Args:` / `Returns:`
sections have been replaced by concise one-liners.  The function signature
already carries full type information; the description only needs to convey
*what* the tool does.

| Tool | Before | After |
|------|--------|-------|
| `create_queue_type` | 1 580 chars | 145 chars |
| `generate_wireguard_client_config` | 1 519 chars | 91 chars |
| `create_filter_rule` | 1 080 chars | ≤ 120 chars |
| _all 162 tools (avg)_ | **209 chars** | **51 chars** |

Estimated description-token savings: **≈ 6 400 tokens** (≈ 75 % reduction).

---

## How to benefit

### MCP clients that use `title`

Any client following the MCP spec can read `tool.annotations.title` and show
that short string in its tool list rather than the full description.  If you
are building an integration, prefer displaying the title in compact views.

### Local LLMs with small context windows

Even without client-side filtering, the trimmed descriptions directly reduce
the tokens consumed at MCP initialisation.  For a 64 k-token LLM this brings
the tool schema from **≈ 54 k tokens → ≈ 48 k tokens**, leaving meaningful
room for the conversation.

> **Further reduction:** If you only need a subset of tools (e.g. only DNS
> and WireGuard), you can comment out the unused area imports in
> `src/mcp_mikrotik/app.py` to drop a whole feature area, or the unused
> modules in an area's `__init__.py` to drop single modules (WireGuard lives
> in `src/mcp_mikrotik/scope/interfaces/__init__.py`, next to VLAN, bridge and
> wireless).

---

## Developer notes

The `annotate()` helper lives in `src/mcp_mikrotik/app.py`:

```python
def annotate(base: ToolAnnotations, title: str) -> ToolAnnotations:
    """Return a copy of *base* with a human-readable *title* attached."""
    return ToolAnnotations(
        title=title,
        readOnlyHint=base.readOnlyHint,
        destructiveHint=base.destructiveHint,
        idempotentHint=base.idempotentHint,
        openWorldHint=base.openWorldHint,
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
