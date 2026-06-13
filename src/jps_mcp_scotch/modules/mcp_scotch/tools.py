"""mcp_scotch tools — 9 subprocess wrappers scotch_v6.py CLI + 3 direct chromadb RAG tools.

Source canonique: /Users/jp/Documents/GitHub/jps-scotch/tools/scotch_v6.py
(shebang python3.13, chromadb 1.5.0, RAG 45286 chunks 5 collections).

Doctrine:
  - jps-scotch/ INTOUCHABLE — wrappers subprocess only, zero direct fs writes
  - profile gating: checkpoint = trusted_local only (write authority)
  - boot_*/scotch_lint/rag_query/rag_stats = read-only, available to readonly profiles
  - rag_ingest = write-authority profiles only (not profile_default)
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    import chromadb  # type: ignore[import]
except Exception:  # pragma: no cover  # noqa: BLE001
    # ImportError ne suffit pas : chromadb casse sous python3.14 avec
    # pydantic.v1.errors.ConfigError pendant l'import (constaté 260612).
    chromadb = None  # type: ignore[assignment]

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

# RAG tool constants (V7 RAG 260612)
VALID_COLLECTIONS = {"scotch", "history", "doctrine", "skills", "mvp0_legacy"}
INGEST_BLOCKED_COLLECTIONS = {"mvp0_legacy"}
ALLOWED_INGEST_EXTENSIONS = {".md", ".txt"}
INGEST_ALLOWED_ROOT = "/Users/jp/Documents/GitHub/"
MAX_INGEST_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


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


def _resolve_rag_dir() -> Path:
    """Resolve RAG chromadb directory. JPS_RAG_DIR env var overrides (test isolation)."""
    env = os.environ.get("JPS_RAG_DIR")
    if env:
        return Path(env)
    return Path(_LEGACY_JPS_SCOTCH) / "scotch" / "rag"


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
        "name": "scotch_read",
        "description": (
            "Boot SCOTCH context for ANY agent (param). FONDATIONS.md + STATE.md "
            "+ RAG top-5. Subprocess wrapper scotch_v6.py boot <agent>. Read-only. "
            "Forme générique de boot_jiminy/beta_prime/dispatch. Aliases jim, bp."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent identifier (jiminy/beta_prime/dispatch). Aliases jim, bp.",
                },
                "budget": {
                    "type": "string",
                    "enum": sorted(VALID_BUDGETS),
                    "default": DEFAULT_BUDGET,
                },
            },
            "required": ["agent"],
        },
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
    {
        "name": "rag_query",
        "description": (
            "Semantic search in a ChromaDB RAG collection. "
            "Returns top-k chunks with text, source and similarity score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query.",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (1-100, default 5).",
                    "default": 5,
                },
                "collection": {
                    "type": "string",
                    "enum": ["scotch", "history", "doctrine", "skills", "mvp0_legacy"],
                    "description": "ChromaDB collection to query (default: scotch).",
                    "default": "scotch",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "rag_stats",
        "description": "Return chunk counts per collection and total in the RAG store.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "rag_ingest",
        "description": (
            "Ingest a .md or .txt file into a ChromaDB collection. "
            "File must be under /Users/jp/Documents/GitHub/. "
            "mvp0_legacy is read-only and cannot be ingested into."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to file to ingest (must be under /Users/jp/Documents/GitHub/).",
                },
                "collection": {
                    "type": "string",
                    "enum": ["scotch", "history", "doctrine", "skills"],
                    "description": "Target collection (default: scotch).",
                    "default": "scotch",
                },
            },
            "required": ["path"],
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


def scotch_read(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generic boot read for any agent (vs boot_jiminy/beta_prime/dispatch fixed).

    Parité mvp0 scotch_read(agent). Frugalité tool-list (1 outil param vs 3 fixes).
    """
    agent_raw = args.get("agent")
    if not isinstance(agent_raw, str) or not agent_raw:
        return _err("agent is required (non-empty string)")
    agent = _resolve_agent(agent_raw)
    if agent not in VALID_AGENTS:
        return _err(
            f"Invalid agent {agent_raw!r} (resolved={agent!r}). "
            f"Allowed: {sorted(VALID_AGENTS)} (aliases: {sorted(AGENT_ALIASES)})"
        )
    out = _boot_agent(agent, args)
    if "error" in out:
        return out
    out["agent_alias_resolved"] = (
        agent_raw if agent_raw == agent else f"{agent_raw}->{agent}"
    )
    return out


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


def rag_query(args: Dict[str, Any]) -> Dict[str, Any]:
    if chromadb is None:
        return _err("chromadb not installed")
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return _err("query must be a non-empty string")
    k = args.get("k", DEFAULT_TOP_K)
    if isinstance(k, bool):
        return _err("k must be an integer, not bool")
    if not isinstance(k, int) or k <= 0:
        return _err("k must be a positive integer")
    if k > MAX_TOP_K:
        return _err(f"k must be <= {MAX_TOP_K}")
    collection = args.get("collection", "scotch")
    if collection not in VALID_COLLECTIONS:
        return _err(f"Invalid collection '{collection}'. Valid: {sorted(VALID_COLLECTIONS)}")
    rag_dir = _resolve_rag_dir()
    try:
        client = chromadb.PersistentClient(path=str(rag_dir))
        col = client.get_collection(collection)
        results = col.query(query_texts=[query], n_results=k)
    except Exception as e:
        return _err(f"ChromaDB error: {e}")
    docs = results["documents"][0] if results.get("documents") else []
    metas = results["metadatas"][0] if results.get("metadatas") else []
    dists = results["distances"][0] if results.get("distances") else []
    # Provenance: the 14 live collections were built by forge.rag / scotch_v6
    # ingest which stores the file path under metadata key "path" (verified
    # 260613: scotch/doctrine/skills metas = {size_bytes, path, lines}). Only
    # rag_ingest (this module) writes "source". Read both, "source" first so
    # rag_ingest-written chunks keep their key, falling back to "path" for the
    # canonical store — otherwise every chunk returns an empty source (the bug
    # the brief's "source/score" output requirement exposed).
    chunks = [
        {
            "text": d,
            "source": (m or {}).get("source") or (m or {}).get("path", ""),
            "score": round(1.0 - dist, 6),
        }
        for d, m, dist in zip(docs, metas, dists)
    ]
    return {"ok": True, "results": chunks, "collection": collection, "k": k}


def rag_stats(args: Dict[str, Any]) -> Dict[str, Any]:  # noqa: ARG001
    if chromadb is None:
        return _err("chromadb not installed")
    rag_dir = _resolve_rag_dir()
    try:
        client = chromadb.PersistentClient(path=str(rag_dir))
        collections_info: Dict[str, Any] = {}
        for col_obj in client.list_collections():
            col = client.get_collection(col_obj.name)
            collections_info[col_obj.name] = {"count": col.count()}
    except Exception as e:
        return _err(f"ChromaDB error: {e}")
    total = sum(v["count"] for v in collections_info.values())
    return {"ok": True, "collections": collections_info, "total": total}


def rag_ingest(args: Dict[str, Any]) -> Dict[str, Any]:
    if chromadb is None:
        return _err("chromadb not installed")
    path_str = args.get("path")
    if not isinstance(path_str, str):
        return _err("path must be a string")
    p = Path(path_str)
    if not p.is_absolute():
        return _err("path must be absolute (anti-traversal)")
    # CWE-22: resolve symlinks/.. BEFORE the root check (raw startswith is bypassable
    # via /Users/jp/Documents/GitHub/../<elsewhere>.md). is_relative_to on the resolved
    # path is the correct anti-traversal guard (Inspecteur MOYEN V7 260612).
    try:
        resolved = p.resolve()
    except OSError as e:
        return _err(f"path resolution failed: {e}")
    if not resolved.is_relative_to(INGEST_ALLOWED_ROOT):
        return _err(f"path must be under {INGEST_ALLOWED_ROOT}")
    p = resolved
    if not p.exists():
        return _err(f"file not found: {path_str}")
    if p.suffix not in ALLOWED_INGEST_EXTENSIONS:
        return _err(f"unsupported extension '{p.suffix}'. Allowed: {sorted(ALLOWED_INGEST_EXTENSIONS)}")
    if p.stat().st_size > MAX_INGEST_FILE_BYTES:
        return _err(f"file too large (>{MAX_INGEST_FILE_BYTES} bytes)")
    collection = args.get("collection", "scotch")
    if collection not in VALID_COLLECTIONS:
        return _err(f"Invalid collection '{collection}'. Valid: {sorted(VALID_COLLECTIONS)}")
    if collection in INGEST_BLOCKED_COLLECTIONS:
        return _err(f"Collection '{collection}' is read-only (write forbidden)")
    text = p.read_text(encoding="utf-8", errors="replace")
    raw_chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
    if not raw_chunks:
        return _err("file produced no chunks after splitting")
    canonical = str(p)  # resolved path = stable identity (anti dup-id, accurate source)
    prefix = hashlib.md5(canonical.encode()).hexdigest()[:8]
    ids = [f"{prefix}-{i}" for i in range(len(raw_chunks))]
    metas = [{"source": canonical}] * len(raw_chunks)
    rag_dir = _resolve_rag_dir()
    try:
        client = chromadb.PersistentClient(path=str(rag_dir))
        col = client.get_or_create_collection(collection)
        col.upsert(documents=raw_chunks, metadatas=metas, ids=ids)
    except Exception as e:
        return _err(f"ChromaDB error: {e}")
    return {"ok": True, "chunks_added": len(raw_chunks), "collection": collection}


_HANDLERS = {
    "boot_jiminy": boot_jiminy,
    "boot_beta_prime": boot_beta_prime,
    "boot_dispatch": boot_dispatch,
    "checkpoint": checkpoint,
    "scotch_lint": scotch_lint,
    "scotch_read": scotch_read,
    "scotch_query": scotch_query,
    "scotch_append": scotch_append,
    "scotch_rag_refresh": scotch_rag_refresh,
    "rag_query": rag_query,
    "rag_stats": rag_stats,
    "rag_ingest": rag_ingest,
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
    profile_default=["boot_jiminy", "scotch_lint", "rag_query", "rag_stats"],
)
