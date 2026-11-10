# ai-director

Status: **implemented (rule-based), tested**. No language model is used.

## Purpose
Turn timed words into scenes and a director plan: pacing, transition, music level, sound-effect
placement, caption style, colour look, and an edit decision record that explains each non-default choice.

## Inputs
- Word timings (`{"text", "start", "end"}` list, or a JSON file of that list).
- `genre`: one of 12 supported genres (see `GENRES` in `uvs/director.py`).
- Optional title.

## Outputs
- A plan dict: `title`, `genre`, `duration`, `scenes` (one dict per scene with `id`, `start`, `end`, `text`,
  `emotion`, `intensity`, `pacing`, `transition`, `transition_duration`, `turning_point`, `music_level`,
  `sfx`, `caption_style`, `color_look`, `decisions`), and `summary`.
- `write_plan(plan, path)` writes it as JSON. Schema: `schemas/scene.schema.json`.

## Execution
```python
from uvs import director as D
from uvs.captions import load_words
plan = D.plan(load_words("examples/demo_caption/words.json"), "real_life_storytelling", "demo")
```
The pipeline calls this as stage one (`uvs/pipeline.py`).

## Rules
- Scenes split at sentence ends, merge if shorter than 1.2 s, and split at a clause break if longer than 6 s.
- Pacing: FAST for fast genres or informational speech above 3.2 words/s. SLOW for emotional genres, or grief or
  warmth words, or speech below 1.8 words/s. MEDIUM otherwise.
- Transitions, in priority order: dip to black (turning point in a tension scene), dissolve (emotional or SLOW),
  dissolve (documentary), cut (everything else).
- Music level: 0.55 FAST, 0.40 MEDIUM, 0.22 SLOW or emotional.
- One soft impact per turning point. None elsewhere.
- Nothing is random. The same input gives the same plan, and this is tested.

## Parameters
`DirectorConfig`: `min_scene`, `max_scene`, `fast_wps`, `slow_wps`. The lexicons `EMOTION_LEXICON` and
`TURN_WORDS` are small editable lists (English and Vietnamese examples).

## Constraints
- Emotion and turn detection use word lists. They do not understand meaning or tone.
- No automatic B-roll selection, no shot planning beyond scene timing, no per-scene colour automation.
- Only the pipeline applies one look to the whole timeline (style lock). Per-scene exceptions are recorded in the plan but not applied.
- The optional language-model reasoning layer is not implemented.

## Errors
Unknown genre: `KeyError`. No words: `ValueError`.

## Tests
`tests/unit/test_director.py` (13 tests). `tests/unit/test_schemas.py` checks plan scenes against the scene schema.
