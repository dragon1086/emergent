# RoleMesh API Reference

> Public interface for tool discovery, config generation, and task routing

## Module: `src.rolemesh`

```python
from src.rolemesh import SetupWizard, ToolProfile, discover_tools, RoleMeshRouter
```

---

## Router (`src.rolemesh.router`)

### `RoleMeshRouter`

Routes user requests to the best available AI tool based on config.

```python
router = RoleMeshRouter(config_path=None)
```

**Parameters:**
- `config_path` (Path, optional): Path to routing config. Defaults to `~/.rolemesh/config.json`

---

### `RoleMeshRouter.classify_task(request: str) -> list[tuple[str, float]]`

Classifies a request into task types with confidence scores.

**Parameters:**
- `request` (str): Natural language task description (Korean or English)

**Returns:** Sorted list of `(task_type, confidence)` tuples, highest confidence first.

**Example:**
```python
router = RoleMeshRouter()
types = router.classify_task("이 함수 리팩토링해줘")
# [("refactoring", 1.0), ("coding", 0.5)]
```

If no patterns match, returns `[("coding", 0.3)]` as default.

---

### `RoleMeshRouter.route(request: str) -> RouteResult`

Routes a request to the best tool. Uses the highest-confidence classification and looks up the routing config.

**Parameters:**
- `request` (str): Task description

**Returns:** `RouteResult`

**Example:**
```python
result = router.route("UI 컴포넌트 디자인")
print(result.tool)       # "gemini"
print(result.tool_name)  # "Gemini CLI"
print(result.task_type)  # "frontend"
print(result.confidence) # 1.0
print(result.fallback)   # "claude"
print(result.reason)     # "Strong match for 'frontend'"
```

Without config, always returns `tool="claude"`.

---

### `RoleMeshRouter.route_multi(request: str) -> list[RouteResult]`

Returns routing suggestions for all matched task types. Useful for complex requests that span multiple categories.

**Parameters:**
- `request` (str): Task description

**Returns:** List of `RouteResult` objects, one per matched task type.

**Example:**
```python
results = router.route_multi("코드 리팩토링 개선해줘")
for r in results:
    print(f"  [{r.confidence:.0%}] {r.task_type} -> {r.tool_name}")
# [100%] refactoring -> Codex CLI
# [ 50%] coding -> Claude Code
```

---

### `RouteResult`

```python
@dataclass
class RouteResult:
    tool: str              # Tool key (e.g., "claude", "gemini")
    tool_name: str         # Display name (e.g., "Claude Code")
    task_type: str         # Classified task category
    confidence: float      # Match strength (0.0 - 1.0)
    fallback: Optional[str]  # Backup tool key, or None
    reason: str            # Human-readable routing explanation
```

**Methods:**
- `to_dict() -> dict`: Serializes to dictionary (confidence rounded to 2 decimals)

---

## Builder (`src.rolemesh.builder`)

### `discover_tools() -> list[ToolProfile]`

Probes the system for all known AI CLI tools. Checks PATH for each tool's binary and attempts to read its version.

**Returns:** List of `ToolProfile` objects for all registered tools (both available and unavailable).

**Example:**
```python
from src.rolemesh import discover_tools

profiles = discover_tools()
for p in profiles:
    status = "installed" if p.available else "not found"
    print(f"  {p.name}: {status}")
```

---

### `SetupWizard`

Orchestrates tool discovery, ranking, and config generation.

```python
wizard = SetupWizard(config_path=None)
```

**Parameters:**
- `config_path` (Path, optional): Where to save/load config. Defaults to `~/.rolemesh/config.json`

---

### `SetupWizard.discover() -> list[ToolProfile]`

Runs `discover_tools()` and stores results internally.

**Returns:** List of all `ToolProfile` objects.

---

### `SetupWizard.available_tools() -> list[ToolProfile]`

Filters to only tools with `available=True`.

---

### `SetupWizard.rank_tools(task_type: str) -> list[ToolProfile]`

Ranks available tools for a given task type by relevance.

**Parameters:**
- `task_type` (str): Task category to rank for (e.g., `"coding"`, `"frontend"`)

**Returns:** Available tools sorted by score (best first).

**Scoring:**
- Strength match: +10.0
- User preference: +5.0 (preferred), 0 (neutral), -5.0 (avoid)
- Cost tier: +2.0 (low), +1.0 (medium), +0.0 (high)

**Example:**
```python
wizard = SetupWizard()
wizard.discover()
ranked = wizard.rank_tools("coding")
print(ranked[0].name)  # Best tool for coding tasks
```

---

### `SetupWizard.build_config() -> dict`

Generates a complete routing configuration from discovered tools.

**Returns:** Config dict with structure:
```json
{
  "version": "1.0.0",
  "tools": {
    "claude": { "key": "claude", "name": "Claude Code", ... }
  },
  "routing": {
    "coding": { "primary": "claude", "fallback": "codex" }
  }
}
```

---

### `SetupWizard.save_config(path=None) -> Path`

Persists config to disk. Creates parent directories if needed.

**Returns:** Path where config was saved.

---

### `SetupWizard.load_config(path=None) -> dict`

Loads existing config from disk. Returns empty dict if file doesn't exist.

---

### `SetupWizard.summary() -> str`

Returns a human-readable summary of discovered tools.

**Example:**
```python
print(wizard.summary())
# Found 3 AI tool(s):
#   - Claude Code v1.0 (Anthropic) [coding, analysis, reasoning, architecture]
#   - Codex CLI v0.1 (OpenAI) [coding, refactoring, quick-edit]
#   - Gemini CLI v2.0 (Google) [multimodal, search, ui-design, frontend]
```

---

## Data Types

### `ToolProfile`

```python
@dataclass
class ToolProfile:
    key: str                    # Registry key (e.g., "claude")
    name: str                   # Display name (e.g., "Claude Code")
    vendor: str                 # Company (e.g., "Anthropic")
    strengths: list[str]        # Task types this tool excels at
    cost_tier: str              # "low", "medium", or "high"
    available: bool = False     # Whether binary found on PATH
    version: Optional[str] = None  # Detected version string
    user_preference: int = 0    # 1=preferred, 0=neutral, -1=avoid
```

**Methods:**
- `to_dict() -> dict`: Serializes all fields to dictionary

---

## CLI Usage

### Router CLI

```bash
# Route a single request
python -m src.rolemesh.router "이 함수 구현해줘"
# -> Claude Code (claude)
#    Task: coding (100%)
#    Strong match for 'coding'

# JSON output
python -m src.rolemesh.router "UI 디자인" --json

# Show all matching task types
python -m src.rolemesh.router "코드 리팩토링" --all
```

### Builder CLI

```bash
# Discover tools (display only)
python -m src.rolemesh.builder

# Save config
python -m src.rolemesh.builder --save

# Interactive setup with preferences
python -m src.rolemesh.builder --interactive

# JSON output
python -m src.rolemesh.builder --json
```

---

## Constants

### `TOOL_REGISTRY` (builder.py)

Dict of known AI CLI tools and their profiles. Keys: `claude`, `codex`, `gemini`, `aider`, `copilot`, `cursor`.

### `TASK_PATTERNS` (router.py)

List of `(task_type, [regex_patterns])` tuples defining the 13 task categories. Patterns support Korean and English.

### `RoleMeshRouter.DEFAULT_TOOL`

Fallback tool when no config exists. Value: `"claude"`.
