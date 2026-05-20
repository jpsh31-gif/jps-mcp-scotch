"""Root conftest — sibling-walk import resolution for jps-mcp.

ÉLEVÉ-1 fix (Phase 2B.5 cycle 2 verdict BP 260517):
  pyproject.toml declares `jps-mcp >= 0.1.0` runtime dep but jps-mcp is local
  (not on PyPI). `pip install -e .` in a virgin venv silently fails to satisfy
  the dep. This conftest makes the test-suite reproducible without requiring
  prior `pip install -e ../jps-mcp` — it locates the sibling jps-mcp repo by
  walking parents (same pattern as jps_fondations, AAIF sibling-walk 2025) and
  injects its `src/` onto sys.path.

Doctrine:
  - Test-time only (pytest collection). Production runtime still requires the
    real jps-mcp installation via the entry_point dispatcher.
  - Bounded depth (MAX_DEPTH=10) to avoid escaping the user's GitHub workspace.
  - Idempotent (sys.path.insert guarded by membership check).
"""
from __future__ import annotations

import sys
from pathlib import Path


_MAX_DEPTH = 10


def _find_sibling_jps_mcp_src() -> Path | None:
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:_MAX_DEPTH]:
        candidate = parent / "jps-mcp" / "src"
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


def _inject_sibling_jps_mcp() -> None:
    src = _find_sibling_jps_mcp_src()
    if src is None:
        return
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_inject_sibling_jps_mcp()
