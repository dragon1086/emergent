# S4 Redesigned: Real-World Self-Improvement Benchmark

## Task: stock_analyzer.py built in 3 phases

| Metric | System A (OpenClaw) | System B (Claude) | System C (GPT) |
|--------|--------------------|--------------------|----------------|
| Memory Persistence | ✅ | ❌ | ❌ |
| Files Created | 2 files | 0 files | 0 files |
| Subprocess Run | ✅ | ❌ | ❌ |
| Test Passed | ❌ | ❌ | ❌ |
| Git Committed | ✅ | ❌ | ❌ |
| Phase 1 Score | 4.8 | 3.8 | 6.4 |
| Phase 2 Score | 3.8 | 2.0 | 6.8 |
| Phase 3 Score | 3.0 | 2.5 | 2.5 |
| Improvement (P3-P1) | -1.8 | -1.3 | -3.9 |
| Total Time (s) | 75.8 | 145.9 | 52.7 |

## Key Differentiator

System A (OpenClaw) uniquely demonstrates:
- **Persistent memory**: `memory.json` loaded between phases — no context re-passing
- **Real file I/O**: Code written to `/tmp/s4_work/` and actually exists on disk
- **Subprocess execution**: Code actually run with `python stock_analyzer_v2.py MSFT`
- **Git integration**: Working `git init` + `add` + `commit` cycle

Systems B and C must re-paste the entire previous code into each prompt,
cannot verify their own output, and cannot commit to a real repository.

*Generated: 2026-03-09 10:49:17*