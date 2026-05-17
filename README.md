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
- `JPS_SCOTCH_BUDGET` (default: `normal`; valid: `minimal` | `normal` | `full`)

## Install

```bash
pip install -e .
```
