# Narrative planner (Phase 2) — public interface

Status: PARTIAL. Rule-based and deterministic. Tested on 8 genres.

## Entry points
- `uvs.narrative.build(words, genre, title="untitled", fps=30.0, audience=None) -> dict`
  - `words`: list of `uvs.captions.Word` or a path to word-timing JSON.
  - Raises `ValueError` for empty or out-of-order timings, and `KeyError` for an unknown genre.
- CLI: `python3 -m uvs.narrative <words.json> --genre <genre> [--title T] [--audience A] [--out plan.json]`
- Examples: `examples/narrative_demo/` (two word files and their plans).

## Plan contents
- `analysis`: topic keywords, tone, objective, hook, conflict, emotional development, key events (numeric tokens), turning points, resolution, call to action (only when a CTA phrase is present). `audience` is reported only when supplied; it is not inferred.
- `structure`: one of 4 templates (Hook/Context/Conflict/Revelation/Payoff; Question/Explanation/Evidence/Conclusion; Problem/Struggle/Discovery/Change; Setup/Tension/Twist/Resolution), chosen from cues in the script.
- `acts`: Act 1 (first 25 %), Act 2 (to 75 %), Act 3.
- `scenes[]`: the director's scene fields plus `act`, `beat`, `narrative_emotion`, `target_shot_seconds`, `visual`, `motion`, `shots[]` (acts > scenes > shots > spoken phrases), `attention`, and `decision`.
- `cinematic.applied`: J-cuts, L-cuts, reaction cuts, motivated cuts, continuity, rhythmic montage, with reasons. `cinematic.not_applied`: match cut, parallel montage, cross-cutting, each with the reason it is not built.
- `summary`: counts, visual usage, over-budget scenes, mean target shot length.

## Visual choice
Shot types: establishing, wide, medium, close_up, detail (insert at a turning point), b_roll, chart (2+ numeric tokens), map (location name in a documentary), graphics (numberless informational sentence), text_emphasis (urgency or ≤4 words), negative_space (reflective slow scene). Each choice lists the other matching rules as `rejected_alternatives` with reasons.

## Attention budget
Load = caption density + movement + background + 0.5 × overlays + information density. Budget 2.0. Over-budget scenes get concrete actions.

## Decision records
Each scene: `selected`, `emotional_justification`, `rejected_alternatives`, `confidence` (0.45 for neutral scenes; otherwise 0.5 + 0.1 × cue count, capped at 0.95), `uncertainty`.

## Limits
- Heuristic lexicons, English-focused. Vietnamese coverage comes from the existing director lexicon only.
- No language model. No speaker information. No footage analysis, so shot choices are text-based.
- Match cut, parallel montage, and cross-cutting are not implemented.
