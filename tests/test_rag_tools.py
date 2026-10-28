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


@pytest.mark.parametrize("path,expected", [
    ("current/ARCHIVE_FORMAT.md", "present"),
    ("archive/guide.md", "historique"),
    ("ARCHIVES/guide.md", "historique"),
    ("shared/CLAIMS_SNAPSHOT_PRE_RECONCILIATION.md", "historique"),
    ("current/snapshot_api.md", "present"),
])
def test_temporalite_path_segments(path, expected):
    from jps_mcp_scotch.modules.mcp_scotch.tools import _temporalite
    assert _temporalite(path) == expected


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
def tmp_md_file(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Small .md file under an EPHEMERAL ingest root (machine-indépendant, vitrine 260703).
    L'ancienne fixture écrivait un vrai fichier sous ~/Documents/GitHub/ (path machine-specific
    ET symlinké post-migration → le guard realpath refusait tout). JPS_INGEST_ROOT pointe le
    tmp_path du test : zéro dépendance à la machine, zéro écriture hors sandbox pytest."""
    monkeypatch.setenv("JPS_INGEST_ROOT", str(tmp_path))
    md = tmp_path / "fixture_ingest_test.md"
    md.write_text("# Test heading\n\nContent for ephemeral RAG ingest test.\n")
    yield md


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


def test_rag_query_source_from_source_key(ephemeral_rag):
    """Regression (260613): chunk['source'] must carry the seeded metadata 'source'
    value, not an empty string. The happy-path test only checked the key existed."""
    result = rag_query({"query": "SCOTCH canonical memory"})
    assert "error" not in result
    assert result["results"][0]["source"] == _SEED_SOURCE


def test_rag_query_source_falls_back_to_path_key(tmp_path, monkeypatch):
    """Regression (260613): the 14 live collections store provenance under the
    'path' metadata key (forge.rag / scotch_v6 ingest), NOT 'source'. rag_query
    must surface it. Before the fix m.get('source','') always returned '' for
    every real chunk."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    client = chromadb.PersistentClient(path=str(rag_dir))
    col = client.get_or_create_collection("scotch")
    col.add(
        documents=["chunk built like the real store"],
        metadatas=[{"path": "/Users/jp/Documents/GitHub/jps-scotch/scotch/FONDATIONS.md", "lines": 10}],
        ids=["path-chunk-0"],
    )
    result = rag_query({"query": "real store"})
    assert "error" not in result
    assert result["results"][0]["source"].endswith("FONDATIONS.md")


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


def test_rag_query_vault_collections_accepted(ephemeral_rag):
    """vault_* + patrimoine + vault accepted (dette MCP soldée 260628)."""
    for col in [
        "vault_pro", "vault_prive", "vault_admin", "vault_maison",
        "vault_notices", "vault_cuisine", "vault_outdoor", "patrimoine", "vault",
    ]:
        result = rag_query({"query": "test", "collection": col})
        if "error" in result:
            assert "invalid collection" not in result["error"].lower(), (
                f"Collection '{col}' incorrectly rejected: {result['error']}"
            )


def test_rag_collection_enums_derived_from_valid_set():
    """Enums inputSchema dérivés du set canonique (DRY anti-drift 260628)."""
    from jps_mcp_scotch.modules.mcp_scotch.tools import (
        VALID_COLLECTIONS,
        INGEST_BLOCKED_COLLECTIONS,
        _QUERY_COLLECTION_ENUM,
        _INGEST_COLLECTION_ENUM,
    )
    assert set(_QUERY_COLLECTION_ENUM) == VALID_COLLECTIONS
    assert set(_INGEST_COLLECTION_ENUM) == VALID_COLLECTIONS - INGEST_BLOCKED_COLLECTIONS
    assert "vault_pro" in _QUERY_COLLECTION_ENUM
    assert "vault_pro" in _INGEST_COLLECTION_ENUM
    assert "mvp0_legacy" not in _INGEST_COLLECTION_ENUM


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


def test_rag_query_present_avant_historique(tmp_path, monkeypatch):
    """Présent prioritaire : un checkpoint/archive ne passe jamais devant un doc courant
    et reste étiqueté historique (audit 260927)."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    col = chromadb.PersistentClient(path=str(rag_dir)).get_or_create_collection("scotch")
    hist = "/Users/jp/GitHub/jps-scotch/scotch/beta_prime/checkpoints/CP_260609_1.md"
    col.add(
        documents=["serveur MCP port 8765 architecture mvp0"] * 3 + ["serveur MCP architecture actuelle jps-mcp"],
        metadatas=[{"path": hist.replace("_1", f"_{i}")} for i in range(3)]
        + [{"path": "/Users/jp/GitHub/jps-scotch/vault/shared/ecosystem/guides/jps-mcp_GUIDE.md"}],
        ids=["h0", "h1", "h2", "p0"],
    )
    res = rag_query({"query": "serveur MCP port 8765 architecture mvp0", "k": 3})["results"]
    assert res[0]["temporalite"] == "present" and res[0]["source"].endswith("jps-mcp_GUIDE.md")
    assert [r["temporalite"] for r in res[1:]] == ["historique", "historique"]


# ── Tests complément lexical (H2 — 28/10/2026) ────────────────────────────────

def test_lexical_terms_extraction_and_stopwords():
    """_lexical_terms extrait les termes >= 5 lettres, exclut les stopwords, max 12 termes."""
    from jps_mcp_scotch.modules.mcp_scotch.tools import _lexical_terms

    # Mots courts (< 5 lettres) et stopwords exclus
    terms = _lexical_terms("Quelles sont les guides techniques pour le RAG et MCP dans ce dépôt ?")
    assert "guides" in terms
    assert "techniques" in terms
    assert "dépôt" in terms or "depot" in terms or any("d" in t for t in terms)
    # Stopwords exclus
    assert "quelles" not in terms
    assert "sont" not in terms
    assert "pour" not in terms
    assert "dans" not in terms
    # Mots < 5 lettres exclus
    assert "rag" not in terms
    assert "mcp" not in terms


def test_lexical_historic_regex():
    """_LEX_HISTORIC_Q_RE détecte les questions tournées vers l'historique ou datées."""
    from jps_mcp_scotch.modules.mcp_scotch.tools import _LEX_HISTORIC_Q_RE

    assert _LEX_HISTORIC_Q_RE.search("rapport le 15 octobre 2026")
    assert _LEX_HISTORIC_Q_RE.search("checkpoint hier soir")
    assert _LEX_HISTORIC_Q_RE.search("etat historique du repo")
    assert _LEX_HISTORIC_Q_RE.search("faits marquants ce mois")
    assert _LEX_HISTORIC_Q_RE.search("notes de janvier")
    # Questions neutres / présentes
    assert not _LEX_HISTORIC_Q_RE.search("guides techniques pour deploiement mcp")
    assert not _LEX_HISTORIC_Q_RE.search("architecture actuelle et configuration")


def test_rag_query_lexical_pas_de_complement_si_assez_de_presents(tmp_path, monkeypatch):
    """Pas de complément lexical déclenché si le pool contient déjà au moins k documents courants."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    col = chromadb.PersistentClient(path=str(rag_dir)).get_or_create_collection("scotch")

    col.add(
        documents=[
            "serveur MCP guide architecture document un",
            "serveur MCP guide architecture document deux",
            "serveur MCP guide architecture document trois",
            "serveur MCP archive historique checkpoint zero",
        ],
        metadatas=[
            {"path": "/Users/jp/GitHub/jps-scotch/vault/guide1.md"},
            {"path": "/Users/jp/GitHub/jps-scotch/vault/guide2.md"},
            {"path": "/Users/jp/GitHub/jps-scotch/vault/guide3.md"},
            {"path": "/Users/jp/GitHub/jps-scotch/scotch/checkpoints/CP_old.md"},
        ],
        ids=["p1", "p2", "p3", "h0"],
    )

    # k=2, le pool contient 3 documents courants >= 2
    res = rag_query({"query": "serveur MCP guide architecture", "k": 2})["results"]
    assert len(res) == 2
    assert all(r["temporalite"] == "present" for r in res)
    assert all("lexical" not in r for r in res)


class FakeCol:
    """Collection factice déterministe pour tester le complément lexical sans embeddings réels."""

    def count(self) -> int:
        return 4

    def query(
        self,
        query_texts: list[str] | None = None,
        n_results: int | None = None,
        where_document: dict | None = None,
        include: list[str] | None = None,
        **kwargs,
    ) -> dict:
        if where_document:
            # Requête lexicale : 1 document courant au terme rare
            return {
                "documents": [["guide specialisation technique courant"]],
                "metadatas": [[{"source": "/Users/jp/GitHub/jps-scotch/vault/specialisation_GUIDE.md"}]],
                "distances": [[0.15]],
                "ids": [["p_spec"]],
            }
        # Pool sémantique : 4 checkpoints historiques (k=1 donc n_results=4)
        return {
            "documents": [[f"checkpoint note detaillee numero {i}" for i in range(4)]],
            "metadatas": [[{"source": f"/Users/jp/GitHub/jps-scotch/scotch/beta_prime/checkpoints/CP_{i}.md"} for i in range(4)]],
            "distances": [[0.10 * (i + 1) for i in range(4)]],
            "ids": [[f"h_{i}" for i in range(4)]],
        }

    def get(
        self,
        where_document: dict | None = None,
        limit: int | None = None,
        include: list[str] | None = None,
        **kwargs,
    ) -> dict:
        if where_document and where_document.get("$contains") == "specialisation":
            return {"ids": ["p_spec"]}
        return {"ids": []}


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_collection(self, name: str, **kwargs):
        return FakeCol()


def test_rag_query_lexical_ajout_quand_pool_sature_historique(monkeypatch):
    """Ajout de documents courants via complément lexical quand le pool sémantique est saturé d'historique.
    Déterministe via FakeCol : le pool sémantique renvoie 4 checkpoints historiques (k=1 donc n_results=4)
    et le lexical renvoie 1 document courant au terme rare."""
    monkeypatch.setattr(chromadb, "PersistentClient", FakeClient)

    # k=1 : n_results=4 (pool historique saturé), l'ajout lexical est en première position
    res = rag_query({"query": "infrastructure kubernetes cluster specialisation", "k": 1})
    assert res.get("ok") is True
    chunks = res["results"]
    assert len(chunks) == 1
    assert chunks[0]["temporalite"] == "present"
    assert chunks[0]["source"].endswith("specialisation_GUIDE.md")
    assert chunks[0].get("lexical") is True
    assert all("lexical" not in c for c in chunks[1:])

    # k=2 : ajout marqué lexical=True en 1ère position (présent d'abord), les autres chunks sans 'lexical'
    res2 = rag_query({"query": "infrastructure kubernetes cluster specialisation", "k": 2})
    assert res2.get("ok") is True
    chunks2 = res2["results"]
    assert len(chunks2) == 2
    assert chunks2[0]["temporalite"] == "present"
    assert chunks2[0]["source"].endswith("specialisation_GUIDE.md")
    assert chunks2[0].get("lexical") is True
    assert chunks2[1]["temporalite"] == "historique"
    assert "lexical" not in chunks2[1]
    assert all("lexical" not in c for c in chunks2[1:])


def test_rag_query_lexical_terme_df_sup_20_ignore(tmp_path, monkeypatch):
    """Un terme présent dans plus de 20 documents (df > _LEX_MAX_DF) est ignoré par le complément lexical."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    col = chromadb.PersistentClient(path=str(rag_dir)).get_or_create_collection("scotch")

    # 22 checkpoints contenant le mot "diagnostic" (df = 22 > 20)
    hist_docs = [f"rapport checkpoint historique anomalie diagnostic test {i}" for i in range(22)]
    hist_metas = [{"path": f"/Users/jp/GitHub/jps-scotch/scotch/checkpoints/CP_{i}.md"} for i in range(22)]
    hist_ids = [f"h_{i}" for i in range(22)]

    # 1 document courant avec "diagnostic"
    present_doc = ["guide technique resolution anomalie diagnostic"]
    present_meta = [{"path": "/Users/jp/GitHub/jps-scotch/vault/diagnostic_guide.md"}]
    present_id = ["p_diag"]

    col.add(
        documents=hist_docs + present_doc,
        metadatas=hist_metas + present_meta,
        ids=hist_ids + present_id,
    )

    # Question contenant le terme fréquent "diagnostic"
    res = rag_query({"query": "anomalie diagnostic", "k": 3})["results"]
    # "diagnostic" a df=23 > 20 -> ignoré pour le complément lexical
    assert all("lexical" not in r for r in res)


def test_rag_query_lexical_question_datee_sans_complement(tmp_path, monkeypatch):
    """Une question datée (« le 15 octobre », « 2024 »...) ne déclenche aucun complément lexical."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    col = chromadb.PersistentClient(path=str(rag_dir)).get_or_create_collection("scotch")

    hist_docs = [f"rapport checkpoint de maintenance {i}" for i in range(5)]
    hist_metas = [{"path": f"/Users/jp/GitHub/jps-scotch/scotch/checkpoints/CP_{i}.md"} for i in range(5)]
    hist_ids = [f"h_{i}" for i in range(5)]

    present_doc = ["guide maintenance infrastructure installation"]
    present_meta = [{"path": "/Users/jp/GitHub/jps-scotch/vault/maintenance.md"}]
    present_id = ["p_maint"]

    col.add(
        documents=hist_docs + present_doc,
        metadatas=hist_metas + present_meta,
        ids=hist_ids + present_id,
    )

    res = rag_query({"query": "rapport maintenance le 15 octobre", "k": 3})["results"]
    assert all("lexical" not in r for r in res)


def test_rag_query_lexical_garde_de_distance(tmp_path, monkeypatch):
    """Un document courant contenant le terme rare est rejeté si sa distance dépasse ceiling = max(dists) + 0.10."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    col = chromadb.PersistentClient(path=str(rag_dir)).get_or_create_collection("scotch")

    # Checkpoints très proches de la requête sémantique sur la cryptographie
    hist_docs = [
        f"cryptographie asymetrique signature numerique hash sha256 algorithme cle publique prive checkpoint {i}"
        for i in range(5)
    ]
    hist_metas = [{"path": f"/Users/jp/GitHub/jps-scotch/scotch/checkpoints/CP_{i}.md"} for i in range(5)]
    hist_ids = [f"h_{i}" for i in range(5)]

    # Document présent avec le terme lexical "botanique", mais sémantiquement totalement hors sujet
    unrelated_present_doc = ["recette de gateau chocolat farine sucre vanille cuisson botanique"]
    unrelated_present_meta = [{"path": "/Users/jp/GitHub/jps-scotch/vault/recettes/gateau.md"}]
    unrelated_present_id = ["p_botanique"]

    col.add(
        documents=hist_docs + unrelated_present_doc,
        metadatas=hist_metas + unrelated_present_meta,
        ids=hist_ids + unrelated_present_id,
    )

    # Requête très ciblée sur la cryptographie, avec terme rare "botanique"
    res = rag_query({"query": "cryptographie asymetrique signature numerique botanique", "k": 3})["results"]
    # Le document botanique a une distance sémantique très élevée (> ceiling), il doit être filtré
    assert all("lexical" not in r for r in res)


def test_rag_query_lexical_exception_interne_degrade_proprement(tmp_path, monkeypatch):
    """Une exception interne lors du complément lexical dégrade proprement sans impacter rag_query."""
    from jps_mcp_scotch.modules.mcp_scotch import tools as t

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    monkeypatch.setenv("JPS_RAG_DIR", str(rag_dir))
    col = chromadb.PersistentClient(path=str(rag_dir)).get_or_create_collection("scotch")

    col.add(
        documents=["serveur MCP checkpoint note historique"] * 4,
        metadatas=[{"path": f"/Users/jp/GitHub/jps-scotch/scotch/checkpoints/CP_{i}.md"} for i in range(4)],
        ids=[f"h_{i}" for i in range(4)],
    )

    def _broken_lexical_terms(*_args, **_kwargs):
        raise RuntimeError("Crash interne simulé")

    monkeypatch.setattr(t, "_lexical_terms", _broken_lexical_terms)

    res = t.rag_query({"query": "serveur MCP architecture", "k": 3})
    assert res.get("ok") is True
    assert len(res.get("results", [])) == 3
    assert all("lexical" not in r for r in res["results"])


def test_rag_query_lexical_cle_presente_seulement_sur_ajouts(monkeypatch):
    """La clé 'lexical: True' n'est présente QUE sur les ajouts lexicaux, jamais sur le pool initial.
    Déterministe via FakeCol : le pool sémantique renvoie 4 checkpoints historiques et le lexical
    renvoie 1 document courant au terme rare."""
    monkeypatch.setattr(chromadb, "PersistentClient", FakeClient)

    # k=2 : 1 ajout lexical en première position (présent d'abord), l'autre chunk sans la clé 'lexical'
    res = rag_query({"query": "serveur base donnees cluster specialisation", "k": 2})
    assert res.get("ok") is True
    chunks = res["results"]
    assert len(chunks) == 2

    # Ajout marqué lexical=True en première position (présent d'abord)
    assert chunks[0]["temporalite"] == "present"
    assert chunks[0]["source"].endswith("specialisation_GUIDE.md")
    assert chunks[0].get("lexical") is True

    # Les autres chunks sans la clé 'lexical'
    assert chunks[1]["temporalite"] == "historique"
    assert "lexical" not in chunks[1]
    assert all("lexical" not in c for c in chunks[1:])



class _StubCol:
    """Collection minimale pour _lexical_complement : un terme rare, un seul résultat lexical."""

    def __init__(self, meta, dist_list):
        self._meta, self._dist = meta, dist_list

    def get(self, **kwargs):
        return {"ids": ["x"]}

    def query(self, **kwargs):
        return {"ids": [["lex"]], "documents": [["doc"]], "metadatas": [[self._meta]],
                "distances": [self._dist]}


def _pool_sature():
    meta = {"path": "/x/checkpoints/CP_1.md"}
    return [("d", meta, 0.4, "h1")]


def test_lexical_complement_distance_absente_ignoree():
    from jps_mcp_scotch.modules.mcp_scotch import tools as t
    col = _StubCol({"path": "/x/vault/guide.md"}, [])
    assert t._lexical_complement(col, "guides rares", _pool_sature(), 5) == []


def test_lexical_complement_source_vide_ignoree():
    from jps_mcp_scotch.modules.mcp_scotch import tools as t
    col = _StubCol(None, [0.45])
    assert t._lexical_complement(col, "guides rares", _pool_sature(), 5) == []


def test_lexical_complement_nominal_et_garde_de_distance():
    from jps_mcp_scotch.modules.mcp_scotch import tools as t
    ok = t._lexical_complement(_StubCol({"path": "/x/vault/guide.md"}, [0.45]), "guides rares", _pool_sature(), 5)
    far = t._lexical_complement(_StubCol({"path": "/x/vault/guide.md"}, [0.9]), "guides rares", _pool_sature(), 5)
    assert [r[0] for r in ok] == ["doc"] and far == []
