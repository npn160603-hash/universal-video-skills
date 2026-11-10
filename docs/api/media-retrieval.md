# Media index and retrieval (Phase 3) — public interface

Status: PARTIAL. Lexical, explainable, deterministic. No embeddings.

## Index (`uvs.media_index`)
- `scan(folder, cache_dir=None) -> list[Asset]`: indexes images, videos and audio. Re-scanning with the same `cache_dir` reuses metrics for unchanged files (keyed by SHA-256 and `INDEX_VERSION`).
- `index_file(path, cache_dir=None) -> Asset | None`
- `Asset` fields added in Phase 3: `tags`, `description` (from the sidecar), `motion_per_second` (video scene cuts per second; `None` for images and audio).
- Sidecar `<asset>.json`: `{"source": "...", "license": "...", "tags": ["city", "night"], "description": "..."}`. Tags are lowercased, de-duplicated, capped at 50 and 60 characters each. The description is capped at 500 characters. Missing provenance means `unknown`.
- `rank(assets, ..., require_known_licence=False)`: with `True`, unknown-licence assets are dropped.

## Retrieval (`uvs.retrieval`)
- `search(assets, query, *, count=5, kind=None, require_known_licence=False, min_score=0.3, exclude=frozenset()) -> list[Hit]`
  - Fields: tags weight 3, description 2, file name 1. Terms are weighted by inverse document frequency.
  - An exact term match gets full weight. A synonym match (from `SYNONYM_GROUPS`) gets 60 % weight and is labelled `(synonym of …)`.
  - Score is 0–1. 1 means every query term matched a tag exactly.
  - `Hit.missing` lists query terms with no match.
  - Near-duplicates (same SHA-256, or dHash within 5 bits) are skipped inside the result.
- `plan_broll(plan, assets, *, require_known_licence=False, min_score=0.3) -> dict`
  - Works on a `uvs.narrative` plan. Scenes with visuals `chart`, `graphics`, `map`, `text_emphasis` or `negative_space` are `generated`.
  - Each footage scene gets `matched` (with path, score, matched and missing terms) or `unfilled` (with a reason: no content words, already used in scene X, or no asset reaches `min_score`).
  - Each asset is used at most once across the plan.
- CLI:
  - `python3 -m uvs.retrieval <folder> --query "city at night" [--count 5] [--kind video] [--cache DIR] [--require-licence] [--out hits.json]`
  - `python3 -m uvs.retrieval <folder> --plan plan.json [--cache DIR] [--require-licence] [--out assign.json]`

## Limits
- Matching is word-based. A word with no entry in `SYNONYM_GROUPS` does not match a related word.
- The synonym list is small and English-only. Vietnamese has no synonym groups.
- Footage is not analysed visually. Only sidecar text, file names and the metrics above are used.
- Assignment is per scene, not per shot.
