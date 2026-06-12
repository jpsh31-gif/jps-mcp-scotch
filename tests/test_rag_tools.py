"""RED tests for RAG tools (rag_query, rag_stats, rag_ingest).

TDD discipline:
- NO access to real /Users/jp/Documents/GitHub/jps-scotch/scotch/rag/ — ephemeral tmp_path only.
- monkeypatch JPS_RAG_DIR env var so _resolve_rag_dir() uses tmp chroma.
- chromadb.PersistentClient created in fixture to seed ephemeral collections.
- Run with: /opt/homebrew/bin/python3.11 -m pytest tests/test_rag_tools.py -v
"""
from __future__ import annotations

import os
import pathlib

import pytest

# chromadb must be importable from python3.11 (homebrew)
import chromadb

# Import the module under test — these will FAIL (RED) until tools.py implements the symbols.
from jps_mcp_scotch.modules.mcp_scotch.tools import (
    MODULE,
    rag_ingest,
    rag_query,
    rag_stats,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

_SEED_TEXT = "SCOTCH canonical memory test chunk for ephemeral RAG."
_SEED_SOURCE = "tests/fixture_seed.md"


@pytest.fixture()
def ephemeral_rag(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Create ephemeral chroma at tmp_path/rag, seed 'scotch' collection, patch env."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))

    # Seed collection "scotch" with 1 document
    client = chromadb.PersistentClient(path=str(rag_dir))
    col = client.get_or_create_collection("scotch")
    col.add(
        documents=[_SEED_TEXT],
        metadatas=[{"source": _SEED_SOURCE}],
        ids=["test-chunk-0"],
    )
    yield rag_dir


@pytest.fixture()
def tmp_md_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """Small .md file under /Users/jp/Documents/GitHub/ (simulated via real subpath)."""
    # Must be absolute + under /Users/jp/Documents/GitHub/
    # We create a real temp dir under that path prefix using a symlink trick — but
    # the brief says "path absolu sous /Users/jp/Documents/GitHub/ uniquement".
    # To keep tests self-contained, we create the file at a real path the guard accepts.
    safe_dir = pathlib.Path("/Users/jp/Documents/GitHub") / "jps-mcp-scotch" / "tests" / "_tmp_ingest_fixture"
    safe_dir.mkdir(parents=True, exist_ok=True)
    md = safe_dir / "fixture_ingest_test.md"
    md.write_text("# Test heading\n\nContent for ephemeral RAG ingest test.\n")
    yield md
    # cleanup
    if md.exists():
        md.unlink()


# ── MODULE tool list ───────────────────────────────────────────────────────────


def test_module_exposes_12_tools_exact_set():
    """After adding 3 RAG tools, module must expose exactly 12 tools."""
    names = {t["name"] for t in MODULE.tools}
    assert names == {
        "boot_jiminy", "boot_beta_prime", "boot_dispatch",
        "checkpoint", "scotch_lint",
        "scotch_query", "scotch_append", "scotch_rag_refresh",
        "scotch_read",
        # NEW v7
        "rag_query", "rag_stats", "rag_ingest",
    }


def test_rag_query_in_profile_default():
    """rag_query must be exposed in default profile (read-only, safe)."""
    assert "rag_query" in MODULE.profile_default


def test_rag_stats_in_profile_default():
    """rag_stats must be exposed in default profile (read-only)."""
    assert "rag_stats" in MODULE.profile_default


def test_rag_ingest_not_in_profile_default():
    """rag_ingest must NOT be in default profile — write op, trusted profiles only."""
    assert "rag_ingest" not in MODULE.profile_default


# ── rag_query tests ────────────────────────────────────────────────────────────


def test_rag_query_happy_path(ephemeral_rag):
    """Happy path: valid query returns list with {text, source, score}."""
    result = rag_query({"query": "SCOTCH canonical memory"})
    assert "error" not in result
    assert result.get("ok") is True
    chunks = result.get("results", [])
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    first = chunks[0]
    assert "text" in first
    assert "source" in first
    assert "score" in first
    assert isinstance(first["score"], float)


def test_rag_query_default_collection_is_scotch(ephemeral_rag):
    """Default collection 'scotch' used when collection param omitted."""
    result = rag_query({"query": "canonical"})
    assert "error" not in result
    assert result.get("collection") == "scotch"


def test_rag_query_k_default_5(ephemeral_rag):
    """k defaults to 5 when not provided."""
    result = rag_query({"query": "canonical"})
    assert "error" not in result
    assert result.get("k") == 5


def test_rag_query_k_explicit(ephemeral_rag):
    """Explicit k honored."""
    result = rag_query({"query": "canonical", "k": 1})
    assert "error" not in result
    assert result.get("k") == 1
    # Only 1 chunk seeded, k=1 → at most 1 result
    assert len(result["results"]) <= 1


def test_rag_query_k_exceeds_max(ephemeral_rag):
    """k > 100 → error."""
    result = rag_query({"query": "canonical", "k": 101})
    assert "error" in result


def test_rag_query_k_zero(ephemeral_rag):
    """k=0 → error (must be positive)."""
    result = rag_query({"query": "canonical", "k": 0})
    assert "error" in result


def test_rag_query_k_bool_rejected(ephemeral_rag):
    """bool is not accepted as k (bool is subclass of int)."""
    result = rag_query({"query": "canonical", "k": True})
    assert "error" in result


def test_rag_query_missing_query(ephemeral_rag):
    """Missing 'query' param → error."""
    result = rag_query({})
    assert "error" in result


def test_rag_query_empty_query(ephemeral_rag):
    """Empty string 'query' → error."""
    result = rag_query({"query": ""})
    assert "error" in result


def test_rag_query_invalid_collection(ephemeral_rag):
    """Unknown collection → clean error."""
    result = rag_query({"query": "test", "collection": "nonexistent_collection"})
    assert "error" in result


def test_rag_query_valid_collections_accepted(ephemeral_rag):
    """All 5 valid collections accepted (may return empty results for unseeded ones)."""
    for col in ["scotch", "history", "doctrine", "skills", "mvp0_legacy"]:
        result = rag_query({"query": "test", "collection": col})
        # Should not error on collection validation — may error on chroma "not found"
        # but not on "invalid collection". Either ok or chroma error is acceptable.
        # Key: must NOT have "Invalid collection" error message.
        if "error" in result:
            assert "invalid collection" not in result["error"].lower(), (
                f"Collection '{col}' incorrectly rejected: {result['error']}"
            )


# ── rag_stats tests ────────────────────────────────────────────────────────────


def test_rag_stats_returns_dict(ephemeral_rag):
    """rag_stats returns dict with ok=True."""
    result = rag_stats({})
    assert "error" not in result
    assert result.get("ok") is True


def test_rag_stats_has_collections_key(ephemeral_rag):
    """rag_stats result contains 'collections' key with per-collection counts."""
    result = rag_stats({})
    assert "collections" in result
    assert isinstance(result["collections"], dict)


def test_rag_stats_has_total(ephemeral_rag):
    """rag_stats result contains 'total' (sum of all chunks)."""
    result = rag_stats({})
    assert "total" in result
    assert isinstance(result["total"], int)


def test_rag_stats_seeded_scotch_count(ephemeral_rag):
    """Seeded 'scotch' collection has count >= 1."""
    result = rag_stats({})
    # scotch was seeded with 1 doc; count should be >= 1
    collections = result.get("collections", {})
    assert "scotch" in collections
    assert collections["scotch"].get("count", 0) >= 1


def test_rag_stats_total_is_sum(ephemeral_rag):
    """total = sum of all per-collection counts."""
    result = rag_stats({})
    collections = result.get("collections", {})
    expected_total = sum(v.get("count", 0) for v in collections.values())
    assert result["total"] == expected_total


def test_rag_stats_no_params_required(ephemeral_rag):
    """rag_stats accepts empty args."""
    result = rag_stats({})
    assert "error" not in result


# ── rag_ingest tests ───────────────────────────────────────────────────────────


def test_rag_ingest_happy_path(ephemeral_rag, tmp_md_file: pathlib.Path):
    """Happy path: ingest a valid .md file → {ok, chunks_added, collection}."""
    result = rag_ingest({"path": str(tmp_md_file)})
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result.get("ok") is True
    assert "chunks_added" in result
    assert isinstance(result["chunks_added"], int)
    assert result["chunks_added"] >= 1
    assert "collection" in result


def test_rag_ingest_default_collection_is_scotch(ephemeral_rag, tmp_md_file: pathlib.Path):
    """Default ingest collection is 'scotch'."""
    result = rag_ingest({"path": str(tmp_md_file)})
    assert "error" not in result
    assert result.get("collection") == "scotch"


def test_rag_ingest_explicit_collection(ephemeral_rag, tmp_md_file: pathlib.Path):
    """Explicit collection 'history' honored."""
    result = rag_ingest({"path": str(tmp_md_file), "collection": "history"})
    assert "error" not in result
    assert result.get("collection") == "history"


def test_rag_ingest_path_not_absolute(ephemeral_rag):
    """Relative path → error (anti-traversal)."""
    result = rag_ingest({"path": "relative/path/file.md"})
    assert "error" in result


def test_rag_ingest_path_outside_root(ephemeral_rag, tmp_path: pathlib.Path):
    """Path outside /Users/jp/Documents/GitHub/ → error (anti-traversal)."""
    # tmp_path is typically /private/tmp/... which is outside the allowed root
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("outside content")
    result = rag_ingest({"path": str(outside_file)})
    assert "error" in result


def test_rag_ingest_file_not_found(ephemeral_rag):
    """Non-existent file → error."""
    result = rag_ingest({"path": "/Users/jp/Documents/GitHub/jps-mcp-scotch/nonexistent_260611.md"})
    assert "error" in result


def test_rag_ingest_file_too_large(ephemeral_rag, tmp_md_file: pathlib.Path):
    """File > 5MB → error."""
    # Write >5MB content
    big_file = tmp_md_file.parent / "big_fixture.md"
    big_file.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    result = rag_ingest({"path": str(big_file)})
    assert "error" in result
    big_file.unlink(missing_ok=True)


def test_rag_ingest_mvp0_legacy_blocked(ephemeral_rag, tmp_md_file: pathlib.Path):
    """Ingest into mvp0_legacy collection → error (write forbidden per brief)."""
    result = rag_ingest({"path": str(tmp_md_file), "collection": "mvp0_legacy"})
    assert "error" in result


def test_rag_ingest_invalid_collection(ephemeral_rag, tmp_md_file: pathlib.Path):
    """Unknown collection → error."""
    result = rag_ingest({"path": str(tmp_md_file), "collection": "nonexistent_col"})
    assert "error" in result


def test_rag_ingest_missing_path(ephemeral_rag):
    """Missing 'path' param → error."""
    result = rag_ingest({})
    assert "error" in result


def test_rag_ingest_wrong_extension(ephemeral_rag):
    """File with unsupported extension → error (only .md and .txt accepted)."""
    # Create a .py file under allowed root
    bad = pathlib.Path("/Users/jp/Documents/GitHub/jps-mcp-scotch/tests/_tmp_ingest_fixture/bad.py")
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("not a markdown file")
    result = rag_ingest({"path": str(bad)})
    assert "error" in result
    bad.unlink(missing_ok=True)


def test_rag_ingest_traversal_startswith_bypass_blocked(ephemeral_rag, tmp_path: pathlib.Path):
    """CWE-22: a path that string-prefix-matches the allowed root but resolves OUTSIDE
    it (via ..) MUST be rejected. Regression for the raw-startswith bypass (Inspecteur
    MOYEN V7 260612 — fixed via resolve()+is_relative_to)."""
    # Real .md target outside the root, reached by traversing out of the allowed prefix.
    outside = tmp_path / "secret.md"
    outside.write_text("sensitive content that must not be ingested")
    # Build a path that *starts with* the allowed root but escapes it after resolution.
    up = "/".join([".."] * 12)
    evil = f"/Users/jp/Documents/GitHub/{up}{outside}"
    assert evil.startswith("/Users/jp/Documents/GitHub/")  # the bypass precondition
    result = rag_ingest({"path": evil})
    assert "error" in result
    assert "under" in result["error"].lower()  # rejected by the root guard, not extension


# ── Robustesse import chromadb (fix 260612: except Exception, pas seulement ImportError) ──

def test_rag_tools_degrade_cleanly_when_chromadb_unavailable(monkeypatch):
    """chromadb cassé à l'import (ex pydantic ConfigError py3.14) → tools répondent
    une erreur propre, AUCUNE exception ne remonte (le module reste sain)."""
    from jps_mcp_scotch.modules.mcp_scotch import tools as t
    monkeypatch.setattr(t, "chromadb", None)
    for fn, args in ((t.rag_query, {"query": "x"}), (t.rag_stats, {}), (t.rag_ingest, {"path": "/tmp/whatever.md"})):
        out = fn(args)
        assert isinstance(out, dict) and "error" in out and "chromadb" in out["error"]
