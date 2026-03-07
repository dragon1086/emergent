# RoleMesh Changelog

> Version history and notable changes

## v1.0.0 (2026-03-07)

### Components

#### Builder (`builder.py`)
- Tool discovery via PATH probing for 6 AI CLIs: Claude Code, Codex CLI, Gemini CLI, Aider, GitHub Copilot, Cursor
- `SetupWizard`: orchestrates discovery, ranking, config generation
- `discover_tools()`: probes system for all registered tools
- `rank_tools()`: scores tools by strength match (+10), user preference (+5/-5), cost tier (+0/+1/+2)
- `build_config()`: generates routing rules mapping 13 task types to best tools
- `save_config()` / `load_config()`: persist to `~/.rolemesh/config.json`
- `register_tool()`: runtime tool registration without source edits
- `unregister_tool()`: runtime tool removal
- `validate_config()`: schema validation with cross-reference checks
- Interactive wizard with user preference prompts
- CLI: `python -m src.rolemesh.builder [--save] [--interactive] [--json]`

#### Router (`router.py`)
- 13 bilingual task categories (Korean + English regex patterns)
- `classify_task()`: regex-based classification with confidence scoring (~1ms)
- `route()`: maps classified task to primary tool + fallback via config
- `route_multi()`: returns routing suggestions for all matched categories
- Default fallback: `"claude"` when no config or no match (0.3 confidence)
- `RouteResult` dataclass with `to_dict()` serialization
- CLI: `python -m src.rolemesh.router "request" [--json] [--all]`

#### Dashboard (`dashboard.py`)
- `RoleMeshDashboard.collect()`: unified data gathering
- 5 health checks: config_file, tools_available, routing_coverage, config_version, no_dead_refs
- `render_tools()`: installed/missing tool display
- `render_routing()`: task-to-tool routing table
- `render_coverage()`: task/tool matrix with strength (X) and route (*) markers
- `render_health()`: pass/fail indicators with score
- `render_full()`: combined dashboard view
- `DashboardData.to_dict()` for JSON export
- CLI: `python -m src.rolemesh.dashboard [--json]`

#### Executor (`executor.py`)
- `RoleMeshExecutor.run()`: full pipeline — classify, route, check, execute
- `dispatch()`: direct tool dispatch (skip router)
- `build_command()`: CLI command construction with file context support
- `check_tool()`: binary availability check via `shutil.which()`
- Automatic fallback on primary tool failure
- Subprocess timeout (default 120s) with exit code -1 on timeout
- Dry-run mode: preview commands without execution
- Execution history: JSONL logging with `get_history(limit=N)`
- `ExecutionResult` dataclass with `success` property and `to_dict()`
- CLI: `python -m src.rolemesh.executor "request" [--dry-run] [--tool KEY]`

### Task Categories (13)

| Category | Example Keywords |
|----------|-----------------|
| coding | code, implement, function, class |
| refactoring | refactor, cleanup, improve, extract |
| quick-edit | typo, fix, change, rename |
| analysis | analyze, investigate, debug, error |
| architecture | architect, design, structure, migration |
| reasoning | reason, logic, judge, evaluate |
| frontend | ui, ux, screen, layout, component |
| multimodal | image, photo, screenshot, chart |
| search | search, find, lookup, docs |
| explain | explain, understand, tell, meaning |
| git-integration | commit, branch, merge, PR |
| completion | autocomplete, fill, continue |
| pair-programming | together, pair, help, review |

### Test Coverage

- 51 test cases across all components
- Zero external dependencies (stdlib only)
- Covers: registry validation, discovery, ranking, routing, config I/O, health checks, rendering, execution, tool registration, config validation, execution history

### Documentation

- README.md — project overview and quick example
- QUICKSTART.md — setup in 5 minutes
- ARCHITECTURE.md — system design and data flow
- BUILDER_GUIDE.md — tool discovery and config customization
- ROUTER_GUIDE.md — task classification and routing logic
- DASHBOARD_GUIDE.md — health checks and coverage matrix
- EXECUTOR_GUIDE.md — subprocess dispatch and fallback
- API_REFERENCE.md — full public interface
- CONTRIBUTING.md — extension and contribution guidelines
- TESTING_GUIDE.md — test infrastructure and patterns
- CHANGELOG.md — this file

### Design Decisions

- Regex over LLM classification for instant, cost-free routing
- Config-driven routing with one-time wizard setup
- Cost-aware ranking favoring cheaper tools among equals
- Bilingual patterns for Korean + English user bases
- Graceful degradation at every layer (no config, no tools, no match)
