# jps-mcp-scotch

JPS MCP Scotch — `scotch_v6.py` subprocess wrappers (Phase 2B.5 sibling).

## Modules

- `mcp_scotch` — 5 tools wrapping `tools/scotch_v6.py` CLI (boot ×3 + checkpoint + lint).

## Tools

| Tool | Auth | Wraps |
|------|------|-------|
| `boot_jiminy` | read | `scotch_v6.py boot jiminy --budget normal` |
| `boot_beta_prime` | read | `scotch_v6.py boot beta_prime --budget normal` |
| `boot_dispatch` | read | `scotch_v6.py boot dispatch --budget normal` |
| `checkpoint` | write (trusted local) | `scotch_v6.py checkpoint <agent> "<summary>"` |
| `scotch_lint` | read | `scotch_v6.py lint` |

## Doctrine

- `jps-scotch/` is the canonical memory vault (INTOUCHABLE — no direct writes).
- All wrappers shell out to `scotch_v6.py` (python3.13 shebang, chromadb 1.4.1).
- Profile gating: `checkpoint` restricted to `_TRUSTED_LOCAL` (jim/dispatch/dispatch_agent).
  Read tools (`boot_*`, `scotch_lint`) available to readonly profiles.

## Config

- `JPS_SCOTCH_DIR` (default: `~/Documents/GitHub/jps-scotch` via sibling-walk fallback)
- `JPS_SCOTCH_TIMEOUT_S` (default: `60`; positive integer)

## Install

```bash
# 1. Install sibling jps-mcp first (local, not on PyPI):
pip install -e ../jps-mcp
# 2. Install this package:
pip install -e .
```

## Tests

Tests use a root `conftest.py` that locates the sibling `jps-mcp/src/` via a
bounded parent-walk and adds it to `sys.path` — so the test-suite is
reproducible from a virgin venv without needing a prior `pip install -e
../jps-mcp` (ÉLEVÉ-1 fix Phase 2B.5 cycle 2):

```bash
pip install -e '.[dev]'
pytest
```

## Coordinated dependency

This sibling repo's tools are gated by `jps-mcp/src/jps_mcp/profile_filter.py`.
Phase 2B.5 requires the matching `_SCOTCH_FULL` / `_SCOTCH_READ` allowlists in
the parent repo. Without them, the dispatcher HTTP filter rejects all 5 tools
for every profile (module dead in production). Merge `jps-mcp` Phase 2B.5
branch first (or simultaneously) before merging this repo to main.
