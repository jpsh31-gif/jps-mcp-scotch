# CLAUDE.md — jps-mcp-scotch (harnais léger, entrypoint commun Claude/Codex via symlink AGENTS.md)

> Créé 260705. Sibling de jps-mcp (Phase 2B.5) : wrappers subprocess autour de `scotch_v6.py`
> (mémoire agents). **Repo VITRINE public** — tout contenu committé ici est publiable.

## IDENTITÉ

Rôle : exposer en MCP les opérations mémoire SCOTCH (boot, checkpoint, query, state) via
subprocess wrappers. Voir README.md pour les modules. Repo technique, public.

## BOOT

```bash
python3 /Users/jp/GitHub/jps-scotch/tools/scotch_v6.py boot <agent> --budget normal
git log --oneline -5 && git status -s && pytest -q 2>/dev/null | tail -3
```

## RÈGLES (public = exigences renforcées)

- **PUBLIABLE ONLY** : zéro donnée perso, zéro path/contenu privé au-delà du nécessaire, zéro
  fixture contenant du réel. Les exemples/tests = synthétiques.
- Qualité vitrine : README exact, pas de claim marketing non prouvé (zéro-mock vaut pour la doc).
- Modif = branche + tests + Inspecteur avant merge. Claim CLAIMS.md au pickup (chantier vitrine
  souvent en vol côté Jim).
- Piège worktree sibling-walk : worktree dans ~/GitHub/ ou PYTHONPATH=jps-mcp/src (cf jps-mcp/CLAUDE.md).

---
*Harnais léger v1.0 — 260705. NE PAS MODIFIER SANS ACCORD JP.*
