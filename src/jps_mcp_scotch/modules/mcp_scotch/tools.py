"""mcp_scotch tools — 5 wrappers subprocess scotch_v6.py CLI.

Source canonique: /Users/jp/Documents/GitHub/jps-scotch/tools/scotch_v6.py
(shebang python3.13, chromadb 1.4.1, RAG 45286 chunks 5 collections).

Doctrine:
  - jps-scotch/ INTOUCHABLE — wrappers subprocess only, zero direct fs writes
  - profile gating: checkpoint = trusted_local only (write authority)
  - boot_*/scotch_lint = read-only, available to readonly profiles

stdlib only.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from jps_mcp.modules import Module


_LEGACY_JPS_SCOTCH = "/Users/jp/Documents/GitHub/jps-scotch"
DEFAULT_BUDGET = "normal"
VALID_BUDGETS = {"minimal", "normal", "full"}
# Canonical agents (FS form). Aliases jim/bp resolved before validation.
VALID_AGENTS = {"jiminy", "beta_prime", "dispatch"}
AGENT_ALIASES = {"jim": "jiminy", "bp": "beta_prime"}
MAX_SIBLING_WALK_DEPTH = 10
MAX_SUMMARY_LEN = 4096


def _parse_timeout(raw: str | None, default: int = 60) -> int:
    """Parse timeout from env, reject non-positive or non-int values."""
    try:
        v = int(raw if raw is not None else default)
    except (TypeError, ValueError):
        return default
    return v if v > 0 else default


DEFAULT_TIMEOUT_S = _parse_timeout(os.environ.get("JPS_SCOTCH_TIMEOUT_S"))


def _resolve_agent(agent: str) -> str:
    """Resolve agent identifier to canonical FS form.

    Aliases (jim/bp) are matched case-insensitively → jiminy/beta_prime.
    Canonical agents (jiminy/beta_prime/dispatch) must already be lowercase —
    "JIMINY" is NOT normalized; pass it through unchanged so the downstream
    VALID_AGENTS allowlist rejects it explicitly.
    """
    if not isinstance(agent, str):
        return ""
    return AGENT_ALIASES.get(agent.lower(), agent)


def _resolve_jps_scotch_dir() -> Path:
    """Resolve canonical jps-scotch path.

    Priority: JPS_SCOTCH_DIR env (if .is_dir()) > sibling-walk (bounded depth)
    > legacy fallback. Mirror pattern jps_fondations (AAIF sibling-walk 2025).

    Defensive: validates env path is_dir, bounds walk to MAX_SIBLING_WALK_DEPTH,
    catches PermissionError on candidate.is_dir() (NFS/perm-restricted parents).
    """
    env = os.environ.get("JPS_SCOTCH_DIR")
    if env:
        p = Path(env)
        try:
            if p.is_dir():
                return p
        except OSError:
            pass
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:MAX_SIBLING_WALK_DEPTH]:
        candidate = parent / "jps-scotch"
        try:
            if candidate.is_dir():
                return candidate
        except (OSError, PermissionError):
            continue
    return Path(_LEGACY_JPS_SCOTCH)


def _scotch_cli_path() -> Path:
    return _resolve_jps_scotch_dir() / "tools" / "scotch_v6.py"


def _python_bin() -> str:
    """Use python3.13 (chromadb 1.4.1 compatible). Fallback to python3."""
    return shutil.which("python3.13") or shutil.which("python3") or "python3"


def _err(msg: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"error": msg}
    out.update(extra)
    return out


def _run_cli(args: List[str], timeout: int = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    cli = _scotch_cli_path()
    if not cli.exists():
        return _err(f"scotch_v6.py not found: {cli}", path=str(cli))
    cmd = [_python_bin(), str(cli), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _err(f"scotch_v6.py timed out after {timeout}s", cmd=cmd[1:])
    except (FileNotFoundError, OSError) as e:
        return _err(f"subprocess failed: {e}", cmd=cmd[1:])
    if proc.returncode != 0:
        return _err(
            f"scotch_v6.py returncode={proc.returncode}",
            stderr=(proc.stderr or "").strip()[:2000],
            stdout=(proc.stdout or "").strip()[:2000],
            cmd=cmd[1:],
        )
    return {
        "ok": True,
        "stdout": proc.stdout,
        "returncode": 0,
        "cmd": cmd[1:],
    }


# ──────────────────── Tool definitions ────────────────────


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "boot_jiminy",
        "description": (
            "Boot Jim (jiminy) SCOTCH context: FONDATIONS.md + STATE.md jiminy "
            "+ RAG top-5. Subprocess wrapper scotch_v6.py boot jiminy. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "budget": {
                    "type": "string",
                    "enum": sorted(VALID_BUDGETS),
                    "default": DEFAULT_BUDGET,
                },
            },
            "required": [],
        },
    },
    {
        "name": "boot_beta_prime",
        "description": (
            "Boot Beta-Prime SCOTCH context: FONDATIONS.md + STATE.md beta_prime "
            "+ RAG top-5. Subprocess wrapper scotch_v6.py boot beta_prime. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "budget": {
                    "type": "string",
                    "enum": sorted(VALID_BUDGETS),
                    "default": DEFAULT_BUDGET,
                },
            },
            "required": [],
        },
    },
    {
        "name": "boot_dispatch",
        "description": (
            "Boot Dispatch SCOTCH context: FONDATIONS.md + STATE.md dispatch "
            "+ RAG top-5. Subprocess wrapper scotch_v6.py boot dispatch. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "budget": {
                    "type": "string",
                    "enum": sorted(VALID_BUDGETS),
                    "default": DEFAULT_BUDGET,
                },
            },
            "required": [],
        },
    },
    {
        "name": "checkpoint",
        "description": (
            "Write SCOTCH checkpoint for agent. Subprocess wrapper "
            "scotch_v6.py checkpoint <agent> '<summary>'. Trusted-local profiles only. "
            "Summary max 4096 chars."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent identifier (jiminy/beta_prime/dispatch). Aliases jim, bp.",
                },
                "summary": {
                    "type": "string",
                    "description": "Checkpoint summary (FAIT/ÉTAT/NEXT/BLOCAGES format).",
                },
            },
            "required": ["agent", "summary"],
        },
    },
    {
        "name": "scotch_lint",
        "description": (
            "Audit SCOTCH vault for stale STATE.md / missing FONDATIONS / etc. "
            "Subprocess wrapper scotch_v6.py lint. Read-only (no fs writes)."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


# ──────────────────── Handlers ────────────────────


def _validate_budget(args: Dict[str, Any]) -> str | None:
    budget = args.get("budget", DEFAULT_BUDGET)
    if budget not in VALID_BUDGETS:
        return None
    return budget


def _boot_agent(agent: str, args: Dict[str, Any]) -> Dict[str, Any]:
    budget = _validate_budget(args)
    if budget is None:
        return _err(f"Invalid budget. Allowed: {sorted(VALID_BUDGETS)}")
    res = _run_cli(["boot", agent, "--budget", budget])
    if "error" in res:
        return res
    return {
        "ok": True,
        "agent": agent,
        "budget": budget,
        "context": res["stdout"],
    }


def boot_jiminy(args: Dict[str, Any]) -> Dict[str, Any]:
    return _boot_agent("jiminy", args)


def boot_beta_prime(args: Dict[str, Any]) -> Dict[str, Any]:
    return _boot_agent("beta_prime", args)


def boot_dispatch(args: Dict[str, Any]) -> Dict[str, Any]:
    return _boot_agent("dispatch", args)


def checkpoint(args: Dict[str, Any]) -> Dict[str, Any]:
    agent_raw = args.get("agent")
    summary = args.get("summary")
    if not isinstance(agent_raw, str) or not agent_raw:
        return _err("agent is required (non-empty string)")
    # Resolve alias (jim→jiminy, bp→beta_prime) then allowlist check.
    # Prevents path-traversal / argv injection on canonical FS form.
    agent = _resolve_agent(agent_raw)
    if agent not in VALID_AGENTS:
        return _err(
            f"Invalid agent {agent_raw!r} (resolved={agent!r}). "
            f"Allowed: {sorted(VALID_AGENTS)} (aliases: {sorted(AGENT_ALIASES)})"
        )
    if not isinstance(summary, str) or not summary:
        return _err("summary is required (non-empty string)")
    if "\x00" in summary:
        return _err("summary must not contain null bytes")
    if len(summary) > MAX_SUMMARY_LEN:
        return _err(f"summary exceeds max length {MAX_SUMMARY_LEN}")
    res = _run_cli(["checkpoint", agent, summary])
    if "error" in res:
        return res
    return {
        "ok": True,
        "agent": agent,
        "agent_alias_resolved": (
            agent_raw if agent_raw == agent else f"{agent_raw}->{agent}"
        ),
        "stdout": res["stdout"].strip(),
    }


def scotch_lint(args: Dict[str, Any]) -> Dict[str, Any]:
    res = _run_cli(["lint"])
    if "error" in res:
        return res
    return {
        "ok": True,
        "report": res["stdout"],
    }


_HANDLERS = {
    "boot_jiminy": boot_jiminy,
    "boot_beta_prime": boot_beta_prime,
    "boot_dispatch": boot_dispatch,
    "checkpoint": checkpoint,
    "scotch_lint": scotch_lint,
}


def handle(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    handler = _HANDLERS.get(name)
    if handler is None:
        return _err(f"Unknown mcp_scotch tool: {name}")
    try:
        return handler(arguments or {})
    except Exception as e:  # noqa: BLE001
        return _err(f"Handler failed: {e}")


MODULE = Module(
    name="mcp_scotch",
    tools=TOOLS,
    handle=handle,
    profile_default=["boot_jiminy", "scotch_lint"],
)
