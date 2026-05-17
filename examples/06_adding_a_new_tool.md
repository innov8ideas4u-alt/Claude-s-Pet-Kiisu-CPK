# 06 — Extending the MCP server: a guided tour

> **What this shows:** how to add a new MCP tool to CPK end-to-end, walking through the same shapes the project's own `app_lifecycle` module uses.
>
> **Why it matters:** every capability Claude has is one of these modules. If you can read this doc and follow `app_lifecycle/module.py` along with it, you can give Claude a new superpower in roughly an hour.
>
> **Companion doc:** `docs/module_development.md` is the dry reference. This file is the *worked tour* — it explains *why* each piece exists, not just what to type.

---

## The 30-second mental model

CPK's MCP server is a thin router. It loads "modules" (subpackages under `flipper_mcp/modules/`), asks each one *"what tools do you expose?"*, and registers them with Claude. When Claude calls a tool, the server looks up which module owns it and forwards the call.

Adding a new tool = adding (or extending) a module. There are three moving pieces:

1. **Your module class** — a `FlipperModule` subclass that names itself, lists its tools, and handles their calls.
2. **The dispatcher** — `handle_tool_call` in your class. Switch on `tool_name`, call your implementation, return a `TextContent`.
3. **The RPC primitive (optional)** — if your tool needs a firmware capability that isn't already wrapped in `core/protobuf_rpc.py`, you add a method there too.

Module auto-discovery means: drop the package in the right place, and the server finds it on next startup. There is no manifest to edit. No registry to update.

---

## Step 1 — Where the file goes

```
flipper_mcp/
  modules/
    your_module/         <-- new package
      __init__.py        <-- can be empty
      module.py          <-- your FlipperModule subclass lives here
```

That's it. The registry scans `flipper_mcp.modules`, finds your subpackage, looks for `module.py`, imports it, instantiates the first concrete `FlipperModule` subclass it finds.

**Convention:** the package name is the module's logical name (e.g. `app_lifecycle`, `storage`, `music`). Tools the module exposes typically start with that name as a prefix (e.g. `flipper_app_start`, `storage_read`), but it's not enforced.

## Step 2 — The `FlipperModule` subclass shape

Open `flipper_mcp/modules/app_lifecycle/module.py` and follow along. It's our reference because it's medium-sized (~600 lines), exposes 9 tools, and shows every shape you'll need.

The required surface:

```python
from ..base_module import FlipperModule
from mcp.types import Tool, TextContent

class AppLifecycleModule(FlipperModule):
    @property
    def name(self) -> str: return "app_lifecycle"

    @property
    def version(self) -> str: return "0.5.0"

    @property
    def description(self) -> str: return "..."

    def get_tools(self) -> List[Tool]: ...

    async def handle_tool_call(self, tool_name, arguments): ...
```

Five abstract members — `name`, `version`, `description`, `get_tools()`, `handle_tool_call()`. The base class (`flipper_mcp/modules/base_module.py`) also gives you optional hooks: `on_load`, `on_unload`, `get_dependencies`, `validate_environment`, `requires_sd_card`. Leave them defaulted unless you need them.

### Returning a `Tool` from `get_tools()`

```python
Tool(
    name="flipper_app_start",
    description="Start a Flipper app by name via protobuf RPC...",
    inputSchema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "App identifier..."},
            "args": {"type": "string", "default": ""},
        },
        "required": ["name"],
    },
)
```

Three rules of thumb that pay off for AI consumers:

1. **`description` is a contract with Claude, not a developer comment.** Claude reads it to decide whether to call this tool. Include: what it does, common arg values, what failure modes look like, follow-up tools that diagnose the failure. The `flipper_app_start` description in `app_lifecycle/module.py` is a good model.
2. **Default optional args** in `inputSchema.properties[x].default` AND in your Python handler. Don't trust Claude to remember the default.
3. **Use `required`** even for single-required-arg tools. It documents the contract.

### Implementing `handle_tool_call`

Pure dispatch — switch on `tool_name`, peel out args, call your private method, return its result.

```python
async def handle_tool_call(self, tool_name, arguments) -> Sequence[TextContent]:
    args = arguments or {}

    if tool_name == "flipper_app_start":
        return await self._app_start(
            name=args.get("name", ""),
            args=args.get("args", "") or "",
        )
    # ... more branches ...

    return [TextContent(type="text", text=f"Unknown tool '{tool_name}'")]
```

Don't put logic here. Put it in the private method. This is the file most likely to be read by a human debugging which tool got called — keep it readable as a table.

### Returning results

Every handler returns `Sequence[TextContent]`. In practice, almost always a single-element list:

```python
return [TextContent(type="text", text=f"✅ app_start({name!r}) → OK")]
```

`app_lifecycle/module.py` uses leading emoji to denote success / warning / error at a glance (✅ ⚠️ ❌). That's a project convention, not a requirement, but it helps a human reader scan tool output fast.

## Step 3 — The dispatcher routes you automatically

There is no dispatcher code you write outside `handle_tool_call`. The registry's job is:

1. On server start, call `discover_modules()`.
2. For each discovered module, call `get_tools()` and remember which tool name maps to which module instance.
3. On a tool call, look up the module by name, call `await module.handle_tool_call(name, args)`.

If two modules try to register tools with the same name, the registry will warn — fix it by renaming one. Don't expect any particular load order.

## Step 4 — Adding a new RPC primitive (only if you need to)

Often your new tool wraps an existing RPC method — `client.rpc.app_start()`, `client.storage.read()`, etc. In that case, skip this step.

But if you're exposing a *new firmware capability* that the protobuf RPC layer doesn't wrap yet, you'll add a method to `flipper_mcp/core/protobuf_rpc.py`. The pattern there:

1. Find the relevant request/response message names in `proto/*.proto` (e.g. `gpio.proto` for GPIO ops).
2. Add a public coroutine on `ProtobufRPC` — `async def gpio_read(self, pin)` — decorated with `@_with_wire_lock` (the wire is single-tasked; the decorator serializes calls so two coroutines don't interleave bytes).
3. Inside, build the proto request via the generated code in `core/protobuf_gen/`, send it with `_send_rpc_message`, parse the response.

That's a deeper rabbit hole than this doc is for. See `docs/protobuf_rpc.md` for the protocol details and `_send_rpc_message`'s docstring for the wire-level mechanics.

## Step 5 — Module auto-discovery: nothing to register

Once your package exists at `flipper_mcp/modules/<your_module>/module.py` with a concrete `FlipperModule` subclass, the registry finds it on next server startup. No `__init__.py` exports needed. No manifest. No CLI command.

You'll see something like this in the MCP server logs on startup:

```
[registry] discovered module: your_module v0.1.0 (3 tools)
```

If your module *isn't* showing up, the most common culprits are:

- File path off — must be `flipper_mcp/modules/<name>/module.py`, not `module/module.py` or `your_module.py`.
- Class isn't concrete — left an `@abstractmethod` defined but not overridden, so the registry skips it.
- Import error inside `module.py` — the registry catches `ImportError`/`AttributeError` and logs a warning. Check the server stderr.

## Step 6 — Smoke-testing locally before any device interaction

You can verify your module loads without ever touching the Flipper:

```bash
# from the repo root
python -c "from flipper_mcp.core.registry import ModuleRegistry; \
           r = ModuleRegistry(flipper_client=None); \
           r.discover_modules(); \
           print(list(r.modules.keys()))"
```

That should print a list that includes your module's `name`. If it doesn't, the registry logged a warning to stderr explaining why.

For testing the actual tool logic without hardware, you can mock `self.flipper.rpc` and `self.flipper.storage`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock
from flipper_mcp.modules.your_module.module import YourModule

client = MagicMock()
client.rpc = AsyncMock()
client.rpc.app_start.return_value = MagicMock(ok=True, status_name="OK", status_code=0)

m = YourModule(client)
result = asyncio.run(m.handle_tool_call("your_tool", {"arg": "value"}))
print(result[0].text)
```

That's enough to catch ~80% of dispatch / argument-handling bugs before you risk a USB-CDC dropout from a buggy real-hardware call.

---

## A complete checklist

- [ ] Created `flipper_mcp/modules/<your_module>/__init__.py` (empty is fine).
- [ ] Created `flipper_mcp/modules/<your_module>/module.py` with a `FlipperModule` subclass.
- [ ] Implemented `name`, `version`, `description` properties.
- [ ] Implemented `get_tools()` returning at least one `Tool` with `inputSchema`.
- [ ] Implemented `handle_tool_call()` as a clean switch on `tool_name`.
- [ ] (Optional) Added a new RPC primitive to `core/protobuf_rpc.py` if the firmware capability wasn't wrapped.
- [ ] Smoke-tested with the registry one-liner above.
- [ ] Reviewed `app_lifecycle/module.py` once more for description style and emoji conventions.
- [ ] Restarted the MCP server (Claude Desktop / `claude` CLI) so it re-discovers modules.

When you can ask Claude *"list your Flipper tools"* and see yours appear, you're done.

**Next:** `07_structured_logs.js` — the log format CPK missions use and why.
