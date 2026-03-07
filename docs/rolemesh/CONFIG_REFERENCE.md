# Config Reference

> Schema, validation rules, and file locations for RoleMesh configuration

## File Locations

| File | Default Path | Override |
|------|-------------|----------|
| Config | `~/.rolemesh/config.json` | `--config` flag, `ROLEMESH_CONFIG` env, or `SetupWizard(config_path=...)` |
| History | `~/.rolemesh/history.jsonl` | `RoleMeshExecutor(history_path=...)` |

Both files are created automatically. The config directory (`~/.rolemesh/`) is created by `save_config()` if it doesn't exist.

## config.json Schema

```json
{
  "version": "1.0.0",
  "tools": {
    "<tool_key>": {
      "key": "string",
      "name": "string",
      "vendor": "string",
      "strengths": ["string"],
      "cost_tier": "low | medium | high",
      "available": true,
      "version": "string | null",
      "user_preference": 0
    }
  },
  "routing": {
    "<task_type>": {
      "primary": "<tool_key>",
      "fallback": "<tool_key>"
    }
  }
}
```

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `string` | Yes | Schema version. Currently `"1.0.0"` |
| `tools` | `object` | Yes | Map of tool key to tool profile |
| `routing` | `object` | No | Map of task type to routing rule |

### Tool Profile Fields

| Field | Type | Description |
|-------|------|-------------|
| `key` | `string` | Unique identifier (matches the object key) |
| `name` | `string` | Display name shown in CLI output and dashboard |
| `vendor` | `string` | Tool vendor or author |
| `strengths` | `string[]` | Task types the tool excels at |
| `cost_tier` | `string` | `"low"`, `"medium"`, or `"high"` |
| `available` | `boolean` | Whether the CLI binary was found on PATH at discovery time |
| `version` | `string \| null` | Detected version string, or `null` if unavailable |
| `user_preference` | `integer` | `1` = prefer, `-1` = avoid, `0` = neutral |

### Routing Rule Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `primary` | `string` | Yes | Tool key for the primary handler |
| `fallback` | `string` | No | Tool key for the fallback handler |

Both `primary` and `fallback` must reference a key that exists in the `tools` object.

### Task Types

The 13 built-in task types used as routing keys:

| Task Type | Korean Patterns | English Patterns |
|-----------|----------------|-----------------|
| `coding` | 코드, 구현, 함수, 클래스, 작성, 만들어, 생성, 추가 | code, implement, function, class, write, build, create, add |
| `refactoring` | 리팩토링, 정리, 개선, 분리, 추출, 단순화 | refactor, cleanup, improve, split, extract, simplify |
| `quick-edit` | 오타, 수정, 바꿔, 이름, 삭제, 제거 | typo, fix, change, rename, delete, remove |
| `analysis` | 분석, 조사, 원인, 왜, 디버그, 에러, 버그 | analyze, investigate, cause, why, debug, error, bug |
| `architecture` | 아키텍처, 설계, 구조, 마이그레이션, 전략, 시스템 | architect, design, structure, migrate, strategy, system |
| `reasoning` | 추론, 논리, 판단, 평가, 비교, 선택, 결정 | reason, logic, judge, evaluate, compare, choose, decide |
| `frontend` | UI, UX, 화면, 레이아웃, 스타일, 컴포넌트, 디자인, 반응형 | screen, layout, style, css, component, design, responsive |
| `multimodal` | 이미지, 사진, 스크린샷, 그래프, 차트, 시각 | image, photo, screenshot, graph, chart, visual |
| `search` | 검색, 찾아, 조회, 문서, 최신, 뉴스, 정보 | search, find, lookup, doc, latest, news, info |
| `explain` | 설명, 이해, 알려, 의미, 뭐야, 어떻게 | explain, understand, tell, mean, what is, how |
| `git-integration` | 커밋, 브랜치, merge, PR, 깃, 리베이스, 체리픽 | commit, branch, merge, pull request, git, rebase, cherry |
| `completion` | 자동완성, 채워, 이어서, 다음, 마저 | complete, fill, continue, next, rest |
| `pair-programming` | 같이, 페어, 도와, 봐줘, 코드리뷰, 검토 | together, pair, help, review, code review, check |

## Validation

### Using the Validator

```python
from src.rolemesh.builder import SetupWizard

config = {"version": "1.0.0", "tools": {}, "routing": {}}
errors = SetupWizard.validate_config(config)
# [] (empty = valid)
```

### Validation Rules

The validator checks for:

| Check | Error Message |
|-------|--------------|
| Config is a dict | `"Config must be a dict"` |
| `version` field exists | `"Missing 'version' field"` |
| `version` is a string | `"'version' must be a string"` |
| `tools` field exists | `"Missing 'tools' field"` |
| `tools` is a dict | `"'tools' must be a dict"` |
| Each tool value is a dict | `"tools['<key>'] must be a dict"` |
| Routing refs exist in tools | `"routing['<type>'].<role> references unknown tool '<key>'"` |

### Dead Reference Detection

The validator catches routing rules that point to tools not present in the `tools` object:

```json
{
  "tools": { "claude": { "..." : "..." } },
  "routing": {
    "coding": { "primary": "claude", "fallback": "codex" }
  }
}
```

This would produce: `"routing['coding'].fallback references unknown tool 'codex'"` because `codex` is not in `tools`.

## history.jsonl Schema

Each line in the history file is a JSON object:

```json
{
  "timestamp": "2026-03-07T10:30:00.000Z",
  "request": "리팩토링해줘 (first 200 chars)",
  "tool": "claude",
  "task_type": "refactoring",
  "confidence": 1.0,
  "success": true,
  "exit_code": 0,
  "duration_ms": 4520,
  "fallback_used": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `string` | ISO 8601 timestamp |
| `request` | `string` | First 200 characters of the request |
| `tool` | `string` | Tool key that was executed |
| `task_type` | `string` | Classified task type |
| `confidence` | `float` | Classification confidence (0.0-1.0) |
| `success` | `boolean` | Whether exit code was 0 |
| `exit_code` | `integer` | Process exit code |
| `duration_ms` | `integer` | Execution time in milliseconds |
| `fallback_used` | `boolean` | Whether the fallback tool was used |

History is append-only. The dashboard reads the last 50 entries by default.

## Manual Config Editing

You can edit `config.json` manually to:

- Override routing rules (force a specific tool for a task type)
- Adjust `user_preference` scores
- Remove tools you don't want routed to

After manual edits, validate:

```bash
python -c "
import json
from src.rolemesh.builder import SetupWizard
config = json.load(open('~/.rolemesh/config.json'.replace('~', __import__('os').path.expanduser('~'))))
errors = SetupWizard.validate_config(config)
print('Valid' if not errors else errors)
"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ROLEMESH_CONFIG` | `~/.rolemesh/config.json` | Override config file path |
| `NO_COLOR` | unset | Disable ANSI colors in dashboard output |

## See Also

- [Builder Guide](BUILDER_GUIDE.md) - Discovery and setup walkthrough
- [Custom Tools](CUSTOM_TOOLS.md) - Register your own AI tools
- [Architecture](ARCHITECTURE.md) - System design overview
