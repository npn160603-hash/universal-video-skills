# semantic-media-selection

Status: **partial**. Local indexing, duplicate detection, sidecar provenance, and rule-based ranking are implemented.
Semantic search (embeddings), motion scoring, subject tracking, and scene detection are not.

## Purpose
Index a folder of media, find duplicates, and rank assets for a shot. Never invent a file, and never fill time
with footage that does not match.

## Execution
```python
from uvs import media_index as M
assets = M.scan("footage/")
groups = M.find_duplicates(assets)            # byte-identical (sha256) or near-identical (dHash distance <= 5)
ranked = M.rank(assets, orientation="portrait", min_width=1080, kind="video")
shots = M.pick_diverse(ranked, count=4)       # skips visual near-duplicates already chosen
M.save_index(assets, "out/index.json")
```

## Metadata
- Images: width, height, orientation, sharpness (edge-response variance), mean brightness, four dominant colours
  (median-cut quantization), 64-bit dHash.
- Video and audio: duration, fps, has-audio, dimensions (via ffprobe).
- Provenance: `<asset>.json` sidecar with `source` and `license`. Missing values are reported as `unknown`, not guessed.

## Ranking
Scores: +2 for the requested orientation (-2 otherwise), +1 for meeting the minimum width (-1.5 below),
up to +2 from sharpness, +1 for enough duration (-2 below), -0.5 for unknown licence.
Reasons are returned with each score.

## Constraints
- No embeddings and no text-to-media matching. "Semantic" selection is not implemented.
- Motion intensity for video is not measured.
- Folder scans read every file. Indexes are not cached incrementally yet.

## Tests
`tests/render/test_charts_media.py` (media index part): scan reads dimensions, orientation, and video facts; sidecar
provenance is read and missing provenance is marked unknown; near-duplicate images are grouped; ranking prefers
the requested orientation; diverse picking skips duplicates.
