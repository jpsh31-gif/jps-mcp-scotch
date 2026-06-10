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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jps_mcp.modules import Module


_LEGACY_JPS_SCOTCH = "/Users/jp/Documents/GitHub/jps-scotch"
DEFAULT_BUDGET = "normal"
# Aligné sur canonical scotch_v6.py VALID_BUDGETS = ("minimal","normal","riche").
# Inspecteur MINEUR-3 260610: "full" rejeté par scotch_v6 → divergence corrigée.
VALID_BUDGETS = {"minimal", "normal", "riche"}
# Canonical agents (FS form). Aliases jim/bp resolved before validation.
VALID_AGENTS = {"jiminy", "beta_prime", "dispatch"}
AGENT_ALIASES = {"jim": "jiminy", "bp": "beta_prime"}
MAX_SIBLING_WALK_DEPTH = 10
MAX_SUMMARY_LEN = 4096
# V1 migration 260610: bornes argv pour scotch_query/scotch_append (anti ARG_MAX / DoS).
MAX_QUESTION_LEN = 2048
MAX_CONTENT_LEN = 8192
DEFAULT_TOP_K = 5
MAX_TOP_K = 100  # borne sup top_k (anti memory-exhaustion RAG — Inspecteur MINEUR-2 260610)
# rag-refresh = ingest embeddings, lent → timeout généreux (override DEFAULT_TIMEOUT_S 60s).
RAG_REFRESH_TIMEOUT_S = 600


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

    Type pre-check (isinstance str) is enforced by the single caller
    (`checkpoint()`) before this helper runs — MINEUR-1 fix Phase 2B.5
    cycle 2 (dead `not isinstance` branch removed, was unreachable).
    """
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
    {
        "name": "scotch_query",
        "description": (
            "Query SCOTCH RAG (collection scotch, semantic search). Subprocess wrapper "
            "scotch_v6.py query. Read-only. USE BEFORE affirming system state "
            "(rule scotch-lecture-obligatoire)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language query against SCOTCH RAG.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to retrieve.",
                    "default": DEFAULT_TOP_K,
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "scotch_append",
        "description": (
            "Append raw timestamped note to agent STATE.md (no RAG, lightweight). "
            "Subprocess wrapper scotch_v6.py state-append. Distinct de checkpoint "
            "(STATE+RAG). Trusted-local only (write authority). Aliases jim, bp."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent identifier (jiminy/beta_prime/dispatch). Aliases jim, bp.",
                },
                "content": {
                    "type": "string",
                    "description": "Raw note content appended to STATE.md.",
                },
            },
            "required": ["agent", "content"],
        },
    },
    {
        "name": "scotch_rag_refresh",
        "description": (
            "Re-ingest FONDATIONS/T4/T5 into SCOTCH RAG. Subprocess wrapper "
            "scotch_v6.py rag-refresh. Slow op (embeddings). Trusted-local only "
            "(write authority). Use dry_run=true to preview."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview without writing to RAG.",
                    "default": False,
                },
            },
            "required": [],
        },
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


def scotch_query(args: Dict[str, Any]) -> Dict[str, Any]:
    question = args.get("question")
    if not isinstance(question, str) or not question:
        return _err("question is required (non-empty string)")
    if "\x00" in question:
        return _err("question must not contain null bytes")
    if len(question) > MAX_QUESTION_LEN:
        return _err(f"question exceeds max length {MAX_QUESTION_LEN}")
    top_k = args.get("top_k", DEFAULT_TOP_K)
    # bool is an int subclass — reject explicitly so True/False can't pass as top_k.
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        return _err(f"Invalid top_k {top_k!r}: must be a positive integer")
    if top_k > MAX_TOP_K:
        return _err(f"top_k {top_k} exceeds max {MAX_TOP_K}")
    res = _run_cli(["query", question, "--top-k", str(top_k)])
    if "error" in res:
        return res
    return {"ok": True, "question": question, "top_k": top_k, "results": res["stdout"]}


def scotch_append(args: Dict[str, Any]) -> Dict[str, Any]:
    agent_raw = args.get("agent")
    content = args.get("content")
    if not isinstance(agent_raw, str) or not agent_raw:
        return _err("agent is required (non-empty string)")
    # Resolve alias then allowlist check (path-traversal / argv-injection guard).
    agent = _resolve_agent(agent_raw)
    if agent not in VALID_AGENTS:
        return _err(
            f"Invalid agent {agent_raw!r} (resolved={agent!r}). "
            f"Allowed: {sorted(VALID_AGENTS)} (aliases: {sorted(AGENT_ALIASES)})"
        )
    if not isinstance(content, str) or not content.strip():
        return _err("content is required (non-empty, non-blank string)")
    if "\x00" in content:
        return _err("content must not contain null bytes")
    if len(content) > MAX_CONTENT_LEN:
        return _err(f"content exceeds max length {MAX_CONTENT_LEN}")
    # mvp0 scotch_append semantics: note brute timestampée (séparateur + header).
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    decorated = f"\n\n## [{ts}] MCP-APPEND\n{content}"
    res = _run_cli(["state-append", agent, decorated])
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


def scotch_rag_refresh(args: Dict[str, Any]) -> Dict[str, Any]:
    dry_run = bool(args.get("dry_run", False))
    cli_args = ["rag-refresh"]
    if dry_run:
        cli_args.append("--dry-run")
    res = _run_cli(cli_args, timeout=RAG_REFRESH_TIMEOUT_S)
    if "error" in res:
        return res
    return {"ok": True, "dry_run": dry_run, "stdout": res["stdout"]}


_HANDLERS = {
    "boot_jiminy": boot_jiminy,
    "boot_beta_prime": boot_beta_prime,
    "boot_dispatch": boot_dispatch,
    "checkpoint": checkpoint,
    "scotch_lint": scotch_lint,
    "scotch_query": scotch_query,
    "scotch_append": scotch_append,
    "scotch_rag_refresh": scotch_rag_refresh,
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
