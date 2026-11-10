"""AI director (deterministic rules, Phase 3).

Turns timed words into scenes and a director plan: pacing, transitions, music level,
sound-effect placement, caption style, colour look, and an edit decision record that
explains each non-default choice.

Everything is rule-based. Nothing is random, so the same input gives the same plan.
The lexicons below are small, editable heuristics. They are not language understanding.
An optional language-model reasoning layer is not implemented.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from uvs.captions import SENTENCE_END, CLAUSE_END, Word, load_words

GENRES = {
    "real_life_storytelling": {"kind": "emotional", "caption": "emotional_storytelling", "look": "desaturated_emotional"},
    "personal_experience_life_lessons": {"kind": "emotional", "caption": "emotional_storytelling", "look": "warm_lifestyle"},
    "psychology_emotional": {"kind": "emotional", "caption": "emotional_storytelling", "look": "desaturated_emotional"},
    "educational_explainer": {"kind": "informational", "caption": "bold_shorts", "look": "bright_educational"},
    "historical_documentary": {"kind": "documentary", "caption": "documentary_minimal", "look": "clean_documentary"},
    "geography_travel": {"kind": "documentary", "caption": "cinematic", "look": "natural_daylight"},
    "mystery_investigative": {"kind": "documentary", "caption": "cinematic", "look": "dark_investigative"},
    "self_improvement_motivational": {"kind": "fast", "caption": "bold_shorts", "look": "modern_commercial"},
    "cinematic_essay": {"kind": "documentary", "caption": "cinematic", "look": "moody_cinematic"},
    "short_lifestyle": {"kind": "emotional", "caption": "cinematic", "look": "warm_lifestyle"},
    "news_explainer": {"kind": "informational", "caption": "documentary_minimal", "look": "clean_documentary"},
    "business_technology": {"kind": "informational", "caption": "bold_shorts", "look": "modern_commercial"},
}

# Editable heuristics, lowercase, letters only. English and Vietnamese examples.
EMOTION_LEXICON = {
    "grief": {"lost", "gone", "miss", "missed", "alone", "tears", "funeral", "goodbye",
              "mất", "nhớ", "nước", "mắt", "cô", "đơn", "qua", "đời"},
    "warmth": {"home", "love", "family", "mom", "grandma", "kitchen", "together",
               "nhà", "mẹ", "bà", "yêu", "bếp", "cùng"},
    "tension": {"secret", "never", "suddenly", "danger", "hidden", "truth", "fear",
                "bí", "mật", "sợ"},
}
TURN_WORDS = {"but", "however", "until", "suddenly", "then", "finally", "nhưng", "rồi", "cuối", "cùng"}

PACING = ("FAST", "MEDIUM", "SLOW", "DYNAMIC")
TRANSITION_DURATION = {"cut": 0.0, "dissolve": 0.5, "dip_black": 0.6}
MUSIC_LEVEL = {"FAST": 0.55, "MEDIUM": 0.40, "SLOW": 0.22}
SFX_ALLOWED_AT_TURNS = True


@dataclass
class Scene:
    id: str
    start: float
    end: float
    text: str
    emotion: str
    intensity: float
    pacing: str
    transition: str
    transition_duration: float
    turning_point: bool
    music_level: float
    sfx: list[str] = field(default_factory=list)
    caption_style: str = "documentary_minimal"
    color_look: str = "clean_documentary"
    decisions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DirectorConfig:
    min_scene: float = 1.2       # shorter scenes merge into the previous one
    max_scene: float = 6.0       # longer scenes split at a clause break when one exists
    fast_wps: float = 3.2        # words per second above which an informational scene is FAST
    slow_wps: float = 1.8        # words per second below which a scene is SLOW


def _norm(word: Word) -> str:
    return word.key


def segment_scenes(words: Sequence[Word], cfg: DirectorConfig = DirectorConfig()) -> list[list[Word]]:
    """Split at sentence ends, merge short scenes into the previous one, split long scenes at clauses."""
    scenes: list[list[Word]] = []
    current: list[Word] = []
    for w in words:
        current.append(w)
        if w.text.endswith(SENTENCE_END):
            scenes.append(current)
            current = []
    if current:
        scenes.append(current)

    merged: list[list[Word]] = []
    for s in scenes:
        if merged and (s[-1].end - s[0].start) < cfg.min_scene:
            merged[-1] = merged[-1] + s
        else:
            merged.append(s)

    result: list[list[Word]] = []
    for s in merged:
        if (s[-1].end - s[0].start) <= cfg.max_scene:
            result.append(s)
            continue
        # Split at the last clause break that leaves each part above min_scene.
        cut = None
        for i, w in enumerate(s[:-1]):
            if w.text.endswith(CLAUSE_END):
                left = w.end - s[0].start
                right = s[-1].end - s[i + 1].start
                if left >= cfg.min_scene and right >= cfg.min_scene:
                    cut = i + 1
        if cut is None:
            result.append(s)
        else:
            result.append(s[:cut])
            result.append(s[cut:])
    return result


def _emotion(words: Sequence[Word]) -> str:
    counts = {name: 0 for name in EMOTION_LEXICON}
    for w in words:
        for name, lex in EMOTION_LEXICON.items():
            if _norm(w) in lex:
                counts[name] += 1
    best = max(counts.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "neutral"


def analyze_scene(idx: int, words: Sequence[Word], genre: str, cfg: DirectorConfig) -> Scene:
    info = GENRES[genre]
    kind = info["kind"]
    duration = max(1e-6, words[-1].end - words[0].start)
    wps = len(words) / duration
    emotion = _emotion(words)
    turn = any(_norm(w) in TURN_WORDS for w in words)
    exclaim = sum(1 for w in words if w.text.endswith("!"))
    intensity = min(1.0, 0.25 + 0.15 * exclaim + (0.25 if turn else 0) + (0.2 if emotion == "tension" else 0))

    decisions: list[str] = []
    # Pacing: a deterministic rule set based on genre kind, speech rate, and emotion.
    if kind == "fast" or (kind == "informational" and wps >= cfg.fast_wps):
        pacing = "FAST"
        decisions.append(f"fast pacing: {genre} at {wps:.1f} words/s")
    elif kind == "emotional" or emotion in ("grief", "warmth") or wps <= cfg.slow_wps:
        pacing = "SLOW"
        decisions.append(f"slow pacing: {genre}, emotion '{emotion}', {wps:.1f} words/s")
    else:
        pacing = "MEDIUM"

    # Transition rules: never random, always explained.
    turning = turn and intensity >= 0.45
    if turning and emotion == "tension":
        transition = "dip_black"
        decisions.append("dip to black: marks a turning point in a tension scene")
    elif emotion in ("grief", "warmth") or pacing == "SLOW":
        transition = "dissolve"
        decisions.append("dissolve: restrained transition for an emotional scene; avoided whip/zoom")
    elif kind == "documentary":
        transition = "dissolve"
        decisions.append("dissolve: continuity-preserving transition for documentary material")
    else:
        transition = "cut"
        decisions.append("hard cut: precise cut for an informational or fast scene")

    music = MUSIC_LEVEL.get(pacing, 0.35)
    if emotion in ("grief", "warmth"):
        music = min(music, 0.22)
        decisions.append("music reduced to 0.22: keeps voiceover intelligible in an emotional scene")

    sfx: list[str] = []
    if SFX_ALLOWED_AT_TURNS and turning:
        sfx.append("soft_impact")
        decisions.append("one soft impact at the turning point; no SFX elsewhere")

    return Scene(
        id=f"S{idx:02d}",
        start=round(words[0].start, 3),
        end=round(words[-1].end, 3),
        text=" ".join(w.text for w in words),
        emotion=emotion,
        intensity=round(intensity, 2),
        pacing=pacing,
        transition=transition,
        transition_duration=TRANSITION_DURATION[transition],
        turning_point=turning,
        music_level=round(music, 2),
        sfx=sfx,
        caption_style=info["caption"],
        color_look=info["look"],
        decisions=decisions,
    )


def plan(words: Sequence[Word] | str | Path, genre: str, title: str = "untitled",
         cfg: DirectorConfig = DirectorConfig()) -> dict:
    if genre not in GENRES:
        raise KeyError(f"unsupported genre {genre!r}; choose from {sorted(GENRES)}")
    loaded = load_words(words) if isinstance(words, (str, Path)) else list(words)
    if not loaded:
        raise ValueError("no words to plan")
    scenes = [analyze_scene(i + 1, s, genre, cfg) for i, s in enumerate(segment_scenes(loaded, cfg))]
    return {
        "title": title,
        "genre": genre,
        "duration": round(loaded[-1].end, 3),
        "scenes": [asdict(s) for s in scenes],
        "summary": {
            "scenes": len(scenes),
            "turning_points": sum(1 for s in scenes if s.turning_point),
            "transitions": {t: sum(1 for s in scenes if s.transition == t) for t in TRANSITION_DURATION},
        },
    }


def write_plan(p: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
