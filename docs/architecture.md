# Architecture Overview

## System Design

Flipper Zero MCP follows a modular plugin architecture: the core handles MCP protocol and device connectivity, while modules provide tools.

## Components

### 1. Core Layer

The core provides infrastructure services:

```
core/
├── server.py          # MCP protocol handler
├── registry.py        # Module discovery and management
├── flipper_client.py  # RPC client abstraction
├── rpc.py             # RPC wrapper (protobuf-first)
├── protobuf_rpc.py    # Protobuf RPC implementation (nanopb-delimited framing)
├── transport/         # Connection layer
│   ├── base.py       # Abstract transport interface
│   ├── usb.py        # USB serial implementation
│   ├── wifi.py       # WiFi (ESP32) implementation
│   └── bluetooth.py  # BLE implementation
└── utils.py          # Shared utilities
```

**Responsibilities:**
- MCP protocol communication (stdio)
- Module lifecycle management
- Transport abstraction
- Tool routing
- Error handling

**Key Principle:** The core never knows about specific module implementations.

### 2. Module Layer

Modules are self-contained plugins:

```
modules/
├── base_module.py    # Abstract module interface
├── badusb/          # BadUSB module
│   ├── module.py    # Module implementation
│   ├── generator.py # DuckyScript generator
│   ├── validator.py # Safety validator
│   └── templates/   # Script templates
├── music/           # Music Player module
│   ├── module.py
│   └── formatter.py
└── systeminfo/       # System info module
    └── module.py
```

**Module Interface:**
```python
class FlipperModule(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    def get_tools(self) -> List[Tool]: ...
    
    @abstractmethod
    async def handle_tool_call(self, tool_name: str, arguments: Any): ...
```

### 3. Transport Layer

Abstracts communication with Flipper Zero:

```python
class FlipperTransport(ABC):
    async def connect(self) -> bool: ...
    async def send(self, data: bytes) -> None: ...
    async def receive(self) -> bytes: ...
```

**Implementations:**
- **USB**: Serial port communication
- **WiFi**: TCP/IP over ESP32 Dev Board
- **Bluetooth**: present as a stub transport (not implemented)

## Data Flow

### Tool Execution Flow

```
1. MCP client (e.g., Claude Desktop)
   │
   └──> MCP Protocol (stdio)
        │
        └──> Core Server
             │
             ├──> Tool Routing (registry)
             │    │
             │    └──> Module.handle_tool_call()
             │         │
             │         └──> Flipper Client
             │              │
             │              └──> Transport Layer
             │                   │
             │                   └──> Flipper Zero Hardware
             │
             └──> Response
                  │
                  └──> MCP Protocol
                       │
                       └──> MCP client
```

### Module Discovery Flow

```
1. Server Startup
   │
   └──> Module Registry
        │
        ├──> Scan modules/ package
        │
        ├──> For each package:
        │    ├──> Import <package>.module
        │    ├──> Find concrete FlipperModule subclasses
        │    └──> Instantiate module
        │
        ├──> Validate environment
        │
        ├──> Check dependencies
        │
        └──> Register module
             │
             └──> Call module.on_load()
```

## Module Lifecycle

```
┌─────────────────┐
│   Discovery     │  Registry scans for modules
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Registration   │  Instantiate and validate
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Loading      │  Call on_load()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Active      │  Handle tool calls
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Unloading     │  Call on_unload()
└─────────────────┘
```

## Module Communication

Modules access the injected `FlipperClient` via `self.flipper` to perform operations (RPC queries, storage operations, launching apps).

## Security Model

### Safety Layers

1. **Input Validation**
   - Schema validation (MCP)
   - Type checking
   - Range validation

2. **Module Validation**
   - Environment checks
   - Dependency verification
   - Safety validators (e.g., BadUSB script validation)

3. **Confirmation Flags**
   - Dangerous operations require `confirm=true`
   - Double-check before execution

### Example: BadUSB Safety

```python
# 1. Generate script
script = generator.generate(description, target_os)

# 2. Validate for safety
is_valid, error = validator.validate(script)
if not is_valid:
    return error

# 3. Require confirmation for execution
if not arguments.get("confirm", False):
    return "Execution blocked - confirm required"

# 4. Execute
await flipper.app.launch("BadUsb", script_path)
```

## Extension Points

### Adding New Transports

```python
from flipper_mcp.core.transport.base import FlipperTransport

class MyTransport(FlipperTransport):
    async def connect(self) -> bool: ...
    async def send(self, data: bytes) -> None: ...
    async def receive(self) -> bytes: ...

# Register in transport/__init__.py
TRANSPORTS["mytransport"] = MyTransport
```

### Adding New Modules

1. Create module directory
2. Implement `FlipperModule` interface
3. Export from `__init__.py`
4. Restart server → Auto-discovered!

### Custom Validators

```python
class MyValidator:
    def validate(self, data: Any) -> tuple[bool, str]:
        # Your validation logic
        return is_valid, error_message
```

## Configuration

The default server entry point builds a Python `config` dict in `flipper_mcp.core.server.main()` and supports environment variable overrides:

- `FLIPPER_TRANSPORT`
- `FLIPPER_PORT`

## Testing Strategy

### Unit Tests

Test individual components in isolation:

```python
@pytest.mark.asyncio
async def test_module_tool():
    mock_flipper = Mock()
    module = MyModule(mock_flipper)
    result = await module.handle_tool_call("tool", {})
    assert result is not None
```

### Integration Tests

Test with real Flipper hardware:

```python
@pytest.mark.integration
@pytest.mark.skipif(not has_flipper(), reason="No Flipper")
async def test_with_hardware():
    # Test with actual device
    pass
```

## References

- [MCP Protocol](https://github.com/modelcontextprotocol)
- [Flipper Zero](https://flipperzero.one/)
- [Python Async](https://docs.python.org/3/library/asyncio.html)
