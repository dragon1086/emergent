# RoleMesh Changelog

All notable changes to the RoleMesh module are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-03-07

### Added

- **Builder** (`builder.py`)
  - `TOOL_REGISTRY` with 6 built-in AI CLI tools: Claude, Codex, Gemini, Aider, Copilot, Cursor
  - `ToolProfile` dataclass for discovered tool metadata
  - `SetupWizard` with full discovery pipeline: `discover()` -> `rank_tools()` -> `build_config()` -> `save_config()`
  - `discover_tools()` standalone function for quick system probing
  - `register_tool()` / `unregister_tool()` for custom tool management
  - `validate_config()` static method for config schema validation
  - Interactive setup wizard (`--interactive` flag) with user preference prompts
  - Config file at `~/.rolemesh/config.json` with `ROLEMESH_CONFIG` env override
  - `--json` output mode for scripting

- **Router** (`router.py`)
  - `TASK_PATTERNS` with 13 bilingual (Korean/English) task type classifiers
  - `RouteResult` dataclass with tool, task_type, confidence, fallback, and reason
  - `RoleMeshRouter.classify_task()` - regex-based confidence scoring
  - `RoleMeshRouter.route()` - single best-match routing with fallback
  - `RoleMeshRouter.route_multi()` - multi-match routing for complex requests
  - Default tool fallback to Claude when no config exists

- **Executor** (`executor.py`)
  - `TOOL_COMMANDS` mapping tool keys to CLI invocation patterns
  - `ExecutionResult` dataclass with exit_code, stdout, stderr, duration_ms
  - `RoleMeshExecutor.run()` - full pipeline: route -> check -> dispatch -> fallback -> log
  - `RoleMeshExecutor.dispatch()` - direct tool dispatch bypassing router
  - `build_command()` for CLI command construction
  - `check_tool()` for runtime availability verification
  - Automatic fallback on primary tool failure
  - `--dry-run` mode for safe testing
  - Configurable timeout (default: 120s)
  - Execution history logging to `~/.rolemesh/history.jsonl`
  - `get_history()` for reading recent execution records
  - Exit code semantics: 0 (success), 1-125 (tool error), 126 (OS error), 127 (not found), -1 (timeout)

- **Dashboard** (`dashboard.py`)
  - `RoleMeshDashboard.collect()` aggregates tools, config, health, and history
  - 5 health checks: config_file, tools_available, routing_coverage, config_version, no_dead_refs
  - 5 render views: tools, routing, coverage matrix, health, history
  - `render_full()` combined dashboard view
  - `Color` ANSI helper respecting `NO_COLOR` env var and TTY detection
  - `--history` subcommand for execution history display

- **CLI** (`__main__.py`)
  - Unified entry point: `python -m src.rolemesh <command>`
  - Subcommands: `dashboard` (d), `setup` (s), `route` (r), `exec` (x), `status` (st)
  - Global `--config` flag for custom config paths
  - `--json` output on all subcommands

- **Documentation**
  - README.md - Project overview and quick start
  - BUILDER_GUIDE.md - Discovery pipeline walkthrough
  - CUSTOM_TOOLS.md - Custom tool registration guide
  - CONFIG_REFERENCE.md - Config schema and validation rules
  - API_REFERENCE.md - Full Python API documentation
  - ARCHITECTURE.md - System design and data flow
  - BEST_PRACTICES.md - Patterns and anti-patterns
  - MONITORING_GUIDE.md - Metrics, alerting, and log rotation
  - DEPLOYMENT_GUIDE.md - Docker, CI/CD, and team setup
  - TROUBLESHOOTING.md - Common issues and solutions
  - CONTRIBUTING.md - Contribution guidelines
  - CHANGELOG.md - This file

- **Testing**
  - Unit tests for builder, router, executor, and dashboard modules
  - Isolated config paths via `tempfile` for test safety
