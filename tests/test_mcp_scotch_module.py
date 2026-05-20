"""Tests mcp_scotch — 5 subprocess wrappers scotch_v6.py CLI."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jps_mcp_scotch.modules.mcp_scotch import MODULE
from jps_mcp_scotch.modules.mcp_scotch.tools import handle


def test_module_exposes_5_tools():
    assert MODULE.name == "mcp_scotch"
    names = {t["name"] for t in MODULE.tools}
    assert names == {
        "boot_jiminy", "boot_beta_prime", "boot_dispatch",
        "checkpoint", "scotch_lint",
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
