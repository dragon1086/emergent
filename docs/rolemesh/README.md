# RoleMesh

> AI Tool Discovery & Task-to-Tool Routing Engine

RoleMesh discovers installed AI CLI tools on your system, profiles their capabilities, and automatically routes user requests to the best-fit tool.

## What It Does

1. **Discovers** AI CLI tools on your PATH (Claude, Codex, Gemini, Aider, Copilot, Cursor)
2. **Classifies** user requests into 13 task categories using bilingual regex (Korean + English)
3. **Routes** each request to the best tool based on strength, user preference, and cost
4. **Executes** the chosen tool via subprocess with automatic fallback on failure

## Components

| Component | File | Role |
|-----------|------|------|
| **Builder** | `builder.py` | Tool discovery + config generation |
| **Router** | `router.py` | Task classification + routing |
| **Dashboard** | `dashboard.py` | System status + health checks |
| **Executor** | `executor.py` | Subprocess dispatch + fallback |

## Quick Example

```bash
# Discover tools and save config
python -m src.rolemesh.builder --save

# Route a request (no execution)
python -m src.rolemesh.router "이 함수 리팩토링해줘"
# -> Codex CLI (codex)
#    Task: refactoring (100%)

# Route + execute
python -m src.rolemesh.executor "UI 컴포넌트 디자인"

# Check system health
python -m src.rolemesh.dashboard
```

## Documentation

| Doc | Description |
|-----|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Setup in 5 minutes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and data flow |
| [BUILDER_GUIDE.md](BUILDER_GUIDE.md) | Tool discovery and config customization |
| [ROUTER_GUIDE.md](ROUTER_GUIDE.md) | Task classification and routing logic |
| [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) | Health checks and coverage matrix |
| [EXECUTOR_GUIDE.md](EXECUTOR_GUIDE.md) | Subprocess dispatch and fallback |
| [API_REFERENCE.md](API_REFERENCE.md) | Full public interface |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Extension and contribution guidelines |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Test infrastructure and patterns |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Supported Tools

| Tool | Vendor | Strengths | Cost |
|------|--------|-----------|------|
| Claude Code | Anthropic | coding, analysis, reasoning, architecture | high |
| Codex CLI | OpenAI | coding, refactoring, quick-edit | medium |
| Gemini CLI | Google | multimodal, search, ui-design, frontend | medium |
| Aider | Community | coding, git-integration, pair-programming | low |
| GitHub Copilot | GitHub | completion, quick-edit, explain | low |
| Cursor | Cursor | coding, ui, inline-edit | medium |

## Design Principles

- **Instant routing**: Regex-based classification (~1ms), no LLM calls for routing
- **Config-driven**: Wizard runs once, router reads config every time
- **Cost-aware**: Cheaper tools rank higher among equally-capable options
- **Bilingual**: All patterns support Korean and English keywords
- **Graceful degradation**: No config → default to Claude; no match → assume coding
