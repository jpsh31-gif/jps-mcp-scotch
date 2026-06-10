"""Tests mcp_scotch — 5 subprocess wrappers scotch_v6.py CLI."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jps_mcp_scotch.modules.mcp_scotch import MODULE
from jps_mcp_scotch.modules.mcp_scotch.tools import handle


def test_module_exposes_9_tools_exact_set():
    assert MODULE.name == "mcp_scotch"
    names = {t["name"] for t in MODULE.tools}
    assert names == {
        "boot_jiminy", "boot_beta_prime", "boot_dispatch",
        "checkpoint", "scotch_lint",
        # V1 migration mvp0→jps-mcp gap-list (260610): 3 nouveaux
        "scotch_query", "scotch_append", "scotch_rag_refresh",
        # V2 re-audit gap (260610): scotch_read générique
        "scotch_read",
    }


def test_module_tools_have_input_schema():
    for t in MODULE.tools:
        assert t["inputSchema"]["type"] == "object"


def test_handle_unknown_tool():
    res = handle("nope", {})
    assert "Unknown" in res["error"]


def test_handle_exception_caught(monkeypatch):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t

    def boom(_args):
        raise RuntimeError("boom_scotch")

    monkeypatch.setitem(t._HANDLERS, "boot_jiminy", boom)
    res = handle("boot_jiminy", {})
    assert "boom_scotch" in res["error"]


# ──────────────────── boot_* ────────────────────


def _make_fake_run_ok(stdout: str = "boot context OK\n"):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
    return fake_run


def test_boot_jiminy_happy_path(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("#!/usr/bin/env python3.13\n", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    monkeypatch.setattr(t.subprocess, "run", _make_fake_run_ok("FONDATIONS+STATE OK\n"))

    res = handle("boot_jiminy", {})
    assert res["ok"] is True
    assert res["agent"] == "jiminy"
    assert res["budget"] == "normal"
    assert "FONDATIONS" in res["context"]


def test_boot_beta_prime_with_minimal_budget(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)
    handle("boot_beta_prime", {"budget": "minimal"})
    assert "boot" in captured["cmd"]
    assert "beta_prime" in captured["cmd"]
    assert "minimal" in captured["cmd"]


def test_boot_dispatch_default_budget(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    monkeypatch.setattr(t.subprocess, "run", _make_fake_run_ok())

    res = handle("boot_dispatch", {})
    assert res["budget"] == "normal"


def test_boot_invalid_budget_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))

    res = handle("boot_jiminy", {"budget": "huge"})
    assert "error" in res
    assert "budget" in res["error"]


def test_boot_cli_missing_returns_error(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    # No tools/scotch_v6.py created → path missing
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    res = handle("boot_jiminy", {})
    assert "error" in res
    assert "scotch_v6.py not found" in res["error"]


def test_boot_returncode_nonzero(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, stdout="", stderr="STATE.md missing"),
    )
    res = handle("boot_jiminy", {})
    assert "error" in res
    assert "returncode=2" in res["error"]
    assert "STATE.md missing" in res["stderr"]


def test_boot_subprocess_timeout(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))

    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 60)
    monkeypatch.setattr(t.subprocess, "run", boom)
    res = handle("boot_jiminy", {})
    assert "error" in res
    assert "timed out" in res["error"]


def test_boot_subprocess_oserror(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))

    def boom(cmd, **kw):
        raise OSError("io")
    monkeypatch.setattr(t.subprocess, "run", boom)
    res = handle("boot_jiminy", {})
    assert "error" in res
    assert "subprocess failed" in res["error"]


# ──────────────────── checkpoint ────────────────────


def test_checkpoint_happy_path(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="OK: checkpoint ecrit pour jim\n", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)

    res = handle("checkpoint", {"agent": "jim", "summary": "260517 test"})
    assert res["ok"] is True
    assert res["agent"] == "jiminy"  # alias jim resolved to canonical
    assert "OK" in res["stdout"]
    assert "checkpoint" in captured["cmd"]
    assert "jiminy" in captured["cmd"]
    assert "260517 test" in captured["cmd"]


def test_checkpoint_missing_agent():
    assert "error" in handle("checkpoint", {"summary": "x"})


def test_checkpoint_missing_summary():
    assert "error" in handle("checkpoint", {"agent": "jim"})


def test_checkpoint_non_string_agent():
    assert "error" in handle("checkpoint", {"agent": 42, "summary": "x"})


def test_checkpoint_summary_too_long(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    long_summary = "x" * (t.MAX_SUMMARY_LEN + 1)
    res = handle("checkpoint", {"agent": "jim", "summary": long_summary})
    assert "error" in res
    assert "max length" in res["error"]


def test_checkpoint_invalid_agent_rejected(monkeypatch, tmp_path):
    """ÉLEVÉ-1 regression: agent path-traversal blocked by VALID_AGENTS allowlist."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    for evil in ("../../etc/passwd", "jim; rm -rf /", "evil", "../../scotch"):
        res = handle("checkpoint", {"agent": evil, "summary": "x"})
        assert "error" in res, f"agent={evil!r} should be rejected"
        assert "Invalid agent" in res["error"]


def test_checkpoint_alias_jim_resolved_to_jiminy(monkeypatch, tmp_path):
    """Aliases jim/bp resolved before allowlist check (frugalité tokens doctrine 270426)."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="OK\n", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)
    res = handle("checkpoint", {"agent": "jim", "summary": "x"})
    assert res["ok"] is True
    assert res["agent"] == "jiminy"
    assert "jim->jiminy" in res["agent_alias_resolved"]
    assert "jiminy" in captured["cmd"]
    # MINEUR-2 fix Phase 2B.5 cycle 2: positional assertion (in-on-list checks
    # element equality, not substring — old check missed "jim_raw"-style leaks).
    # CLI form: [python, scotch_v6.py, "checkpoint", "<agent>", "<summary>"]
    assert captured["cmd"][-2] == "jiminy"
    assert captured["cmd"][-1] == "x"


def test_checkpoint_summary_rejects_null_byte(monkeypatch, tmp_path):
    """ÉLEVÉ-1 hardening: null bytes in summary blocked."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    res = handle("checkpoint", {"agent": "jim", "summary": "ok\x00evil"})
    assert "error" in res
    assert "null bytes" in res["error"]


def test_checkpoint_cli_error_propagation(monkeypatch, tmp_path):
    """MINEUR-1: error envelope from _run_cli propagated to handler caller."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="vault missing"),
    )
    res = handle("checkpoint", {"agent": "jim", "summary": "x"})
    assert "error" in res
    assert "returncode=1" in res["error"]
    assert "vault missing" in res["stderr"]


# ──────────────────── scotch_lint ────────────────────


def test_scotch_lint_happy_path(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="LINT OK 0 issues\n", stderr=""),
    )
    res = handle("scotch_lint", {})
    assert res["ok"] is True
    assert "LINT OK" in res["report"]


def test_scotch_lint_returncode_nonzero(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="stale STATE"),
    )
    res = handle("scotch_lint", {})
    assert "error" in res
    assert "returncode=1" in res["error"]


# ──────────────────── _resolve_jps_scotch_dir ────────────────────


def test_resolve_jps_scotch_env_override(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    assert t._resolve_jps_scotch_dir() == tmp_path


def test_resolve_jps_scotch_legacy_fallback(monkeypatch):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    monkeypatch.delenv("JPS_SCOTCH_DIR", raising=False)
    resolved = t._resolve_jps_scotch_dir()
    # Either sibling found OR legacy fallback (depending on test cwd)
    assert isinstance(resolved, Path)
    assert "jps-scotch" in str(resolved)


def test_resolve_jps_scotch_env_invalid_path_falls_back(monkeypatch):
    """MOYEN-1: JPS_SCOTCH_DIR pointing to non-existent path falls through to walk/legacy."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    monkeypatch.setenv("JPS_SCOTCH_DIR", "/no/such/path/__never_exists__")
    resolved = t._resolve_jps_scotch_dir()
    # Must NOT return the invalid env path
    assert str(resolved) != "/no/such/path/__never_exists__"


# ──────────────────── _parse_timeout ────────────────────


def test_parse_timeout_valid():
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    assert t._parse_timeout("30") == 30


def test_parse_timeout_invalid_falls_back_to_default():
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    assert t._parse_timeout("not-a-number") == 60
    assert t._parse_timeout(None) == 60


def test_parse_timeout_non_positive_falls_back():
    """MOYEN-2: timeout=0 or negative falls back to default."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    assert t._parse_timeout("0") == 60
    assert t._parse_timeout("-5") == 60
    assert t._parse_timeout("0", default=10) == 10


# ──────────────────── scotch_query (V1 260610) ────────────────────


def _setup_fake_cli(monkeypatch, tmp_path):
    cli = tmp_path / "tools" / "scotch_v6.py"
    cli.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("", encoding="utf-8")
    monkeypatch.setenv("JPS_SCOTCH_DIR", str(tmp_path))
    return cli


def test_scotch_query_happy_path(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="RAG chunk 1\nRAG chunk 2\n", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)

    res = handle("scotch_query", {"question": "where is doctrine 280428", "top_k": 3})
    assert res["ok"] is True
    assert "RAG chunk 1" in res["results"]
    assert "query" in captured["cmd"]
    assert "where is doctrine 280428" in captured["cmd"]
    assert "--top-k" in captured["cmd"]
    assert "3" in captured["cmd"]


def test_scotch_query_default_top_k(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)
    handle("scotch_query", {"question": "q"})
    assert "5" in captured["cmd"]  # default top_k


def test_scotch_query_missing_question():
    res = handle("scotch_query", {})
    assert "error" in res
    assert "question" in res["error"]


def test_scotch_query_invalid_top_k(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    for bad in (0, -1, "five", 1.5):
        res = handle("scotch_query", {"question": "q", "top_k": bad})
        assert "error" in res, f"top_k={bad!r} should be rejected"
        assert "top_k" in res["error"]


def test_scotch_query_null_byte_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_query", {"question": "ok\x00evil"})
    assert "error" in res
    assert "null" in res["error"].lower()


def test_scotch_query_returncode_nonzero(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, stdout="", stderr="RAG down"),
    )
    res = handle("scotch_query", {"question": "q"})
    assert "error" in res
    assert "returncode=2" in res["error"]


# ──────────────────── scotch_append (V1 260610) ────────────────────


def test_scotch_append_happy_path(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="OK: append STATE.md pour jiminy\n", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)

    res = handle("scotch_append", {"agent": "jim", "content": "note rapide"})
    assert res["ok"] is True
    assert res["agent"] == "jiminy"  # alias resolved
    assert "state-append" in captured["cmd"]
    # CLI form: [python, scotch_v6.py, "state-append", "<agent>", "<content>"]
    assert captured["cmd"][-2] == "jiminy"
    assert "note rapide" in captured["cmd"][-1]
    assert "MCP-APPEND" in captured["cmd"][-1]  # decorated timestamp header


def test_scotch_append_missing_agent():
    res = handle("scotch_append", {"content": "x"})
    assert "error" in res
    assert "agent" in res["error"]


def test_scotch_append_missing_content():
    res = handle("scotch_append", {"agent": "jim"})
    assert "error" in res
    assert "content" in res["error"]


def test_scotch_append_invalid_agent_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    for evil in ("../../etc/passwd", "evil", "jim; rm -rf /"):
        res = handle("scotch_append", {"agent": evil, "content": "x"})
        assert "error" in res, f"agent={evil!r} should be rejected"
        assert "Invalid agent" in res["error"]


def test_scotch_append_null_byte_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_append", {"agent": "jim", "content": "ok\x00evil"})
    assert "error" in res
    assert "null" in res["error"].lower()


def test_scotch_append_returncode_nonzero(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="agent dir missing"),
    )
    res = handle("scotch_append", {"agent": "jim", "content": "x"})
    assert "error" in res
    assert "returncode=1" in res["error"]


# ──────────────────── scotch_rag_refresh (V1 260610) ────────────────────


def test_scotch_rag_refresh_default(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": 1}', stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)

    res = handle("scotch_rag_refresh", {})
    assert res["ok"] is True
    assert "rag-refresh" in captured["cmd"]
    assert "--dry-run" not in captured["cmd"]
    assert res["dry_run"] is False


def test_scotch_rag_refresh_dry_run(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout='{"dry": 1}', stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)

    res = handle("scotch_rag_refresh", {"dry_run": True})
    assert res["ok"] is True
    assert "--dry-run" in captured["cmd"]
    assert res["dry_run"] is True


def test_scotch_rag_refresh_returncode_nonzero(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(
        t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, stdout="", stderr="ingest fail"),
    )
    res = handle("scotch_rag_refresh", {})
    assert "error" in res
    assert "returncode=2" in res["error"]


# ──────────────────── guards bornes argv (V1 260610) ────────────────────


def test_scotch_query_too_long_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_query", {"question": "x" * (t.MAX_QUESTION_LEN + 1)})
    assert "error" in res
    assert "max length" in res["error"]


def test_scotch_query_top_k_bool_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_query", {"question": "q", "top_k": True})
    assert "error" in res
    assert "top_k" in res["error"]


def test_scotch_append_content_too_long_rejected(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_append", {"agent": "jim", "content": "x" * (t.MAX_CONTENT_LEN + 1)})
    assert "error" in res
    assert "max length" in res["error"]


# ──────────────────── Inspecteur MINEUR/NITS fixes (260610) ────────────────────


def test_scotch_query_top_k_too_large_rejected(monkeypatch, tmp_path):
    """MINEUR-2 Inspecteur: top_k borné supérieurement (anti memory-exhaustion RAG)."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_query", {"question": "q", "top_k": t.MAX_TOP_K + 1})
    assert "error" in res
    assert "top_k" in res["error"]


def test_scotch_append_blank_content_rejected(monkeypatch, tmp_path):
    """NITS-1 Inspecteur: content whitespace-only rejeté (anti pollution STATE.md)."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    for blank in ("   ", "\n", "\t  \n"):
        res = handle("scotch_append", {"agent": "jim", "content": blank})
        assert "error" in res, f"content={blank!r} should be rejected"
        assert "content" in res["error"]


# ──────────────────── budget riche alignment (Inspecteur MINEUR-3 260610) ────────────────────


def test_boot_budget_riche_valid(monkeypatch, tmp_path):
    """budget=riche (canonical scotch_v6) accepté + passé au CLI."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ctx", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)
    res = handle("boot_jiminy", {"budget": "riche"})
    assert res["ok"] is True
    assert res["budget"] == "riche"
    assert "riche" in captured["cmd"]


def test_boot_budget_full_rejected_cleanly(monkeypatch, tmp_path):
    """budget=full (n'existe pas côté scotch_v6) rejeté proprement côté MCP (pas subprocess silencieux)."""
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(t.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    res = handle("boot_jiminy", {"budget": "full"})
    assert "error" in res
    assert "budget" in res["error"]
    assert calls == []  # rejected before subprocess


# ──────────────────── scotch_read générique (V2 re-audit gap, 260610) ────────────────────
# Distinct des boot_jiminy/beta_prime/dispatch (agent fixe) : 1 outil, param agent.
# Parité mvp0 scotch_read(agent). Frugalité tool-list (1 vs 3).
# NB: count exact + présence scotch_read couverts par test_module_exposes_9_tools_exact_set.


def test_scotch_read_happy_alias(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="CTX jiminy", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)

    res = handle("scotch_read", {"agent": "jim", "budget": "normal"})
    assert res["ok"] is True
    assert res["agent"] == "jiminy"
    assert res["budget"] == "normal"
    assert "CTX jiminy" in res["context"]
    assert "boot" in captured["cmd"]
    assert captured["cmd"][-3] == "jiminy"  # [..., boot, jiminy, --budget, normal]
    assert "normal" in captured["cmd"]


def test_scotch_read_riche_budget(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="x", stderr="")
    monkeypatch.setattr(t.subprocess, "run", fake_run)
    res = handle("scotch_read", {"agent": "beta_prime", "budget": "riche"})
    assert res["ok"] is True
    assert "riche" in captured["cmd"]


def test_scotch_read_missing_agent():
    res = handle("scotch_read", {})
    assert "error" in res
    assert "agent" in res["error"]


def test_scotch_read_invalid_agent(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    for evil in ("rogue", "../../etc", "jim; rm -rf /"):
        res = handle("scotch_read", {"agent": evil})
        assert "error" in res
        assert "Invalid agent" in res["error"]


def test_scotch_read_invalid_budget(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    res = handle("scotch_read", {"agent": "jim", "budget": "huge"})
    assert "error" in res
    assert "budget" in res["error"]


def test_scotch_read_default_budget(monkeypatch, tmp_path):
    import jps_mcp_scotch.modules.mcp_scotch.tools as t
    _setup_fake_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(t.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="x", stderr=""))
    res = handle("scotch_read", {"agent": "dispatch"})
    assert res["budget"] == "normal"
