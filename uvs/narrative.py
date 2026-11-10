"""Narrative analysis and storytelling plan (Phase 2).

Builds on uvs.director (scene segmentation, pacing, transitions, music, SFX). Adds:

2.1 Script analysis: topic, genre, tone, objective, hook, conflict, emotional development,
    key events, turning points, resolution, call to action.
2.2 Story segmentation: acts > scenes > beats > shots > spoken phrases, with a structure
    template chosen from cues in the script.
2.3 Emotional pacing: target shot lengths from emotional intent. Fast editing is not forced.
2.4 Shot planning: wide, medium, close-up, detail, establishing, B-roll, graphics, map, chart,
    text emphasis, negative space. Each choice records the alternatives that were rejected.
2.5 Cinematic grammar: J-cuts, L-cuts, reaction cuts, motivated cuts, insert shots, continuity,
    rhythmic montage. Match cuts, parallel montage, and cross-cutting are NOT applied (they need
    visual or multi-storyline analysis that this build does not have).
2.6 Visual attention budget: a cognitive-load score per scene with concrete reduction actions.
2.7 Explainable decisions: one record per scene with selected options, justification,
    rejected alternatives, confidence, and uncertainty.

All of it is rule-based and deterministic. The lexicons are short and English-focused; they are
heuristics, not language understanding. Vietnamese coverage is limited to the existing director
lexicon.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from uvs import director as D
from uvs.captions import CLAUSE_END, SENTENCE_END, Word, load_words

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_words(words: Sequence[Word]) -> list[str]:
    problems: list[str] = []
    if not words:
        return ["no words: provide at least one timed word"]
    prev_start = -1.0
    for i, w in enumerate(words):
        if not w.text.strip():
            problems.append(f"word {i} has empty text")
        if w.start < 0:
            problems.append(f"word {i} ({w.text!r}) starts before 0 s")
        if w.end <= w.start:
            problems.append(f"word {i} ({w.text!r}) ends at or before it starts")
        if w.start < prev_start:
            problems.append(f"word {i} ({w.text!r}) starts before the previous word; timings must be ordered")
        prev_start = w.start
    return problems


# ---------------------------------------------------------------------------
# Lexicons (2.1, 2.3, 2.4)
# ---------------------------------------------------------------------------

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "is", "are", "was",
    "were", "be", "been", "it", "this", "that", "i", "you", "he", "she", "they", "we", "my", "your",
    "our", "their", "as", "by", "from", "but", "not", "so", "if", "then", "than", "there", "here",
    "what", "when", "where", "why", "how", "do", "does", "did", "have", "has", "had", "will", "would",
    "can", "could", "should", "about", "into", "over", "just", "like", "me", "him", "her", "them",
    "us", "its", "all", "up", "out", "one", "no", "yes", "both", "same", "every", "even", "some",
    "much", "many", "more", "most", "very", "also", "only", "each", "still", "such", "built", "made",
    "went", "got", "get", "make", "take", "took", "came", "come", "said", "says", "say",
    # Vietnamese function words
    "là", "và", "của", "có", "không", "một", "những", "các", "cho", "với", "này", "đã", "để", "khi",
    "trong", "được", "người", "thì", "mà", "ở", "ra", "lại", "về",
}

EMOTION_CUES = {
    "tension": {"secret", "never", "danger", "hidden", "truth", "fear", "afraid", "threat", "trap"},
    "grief": {"lost", "gone", "miss", "missed", "alone", "tears", "funeral", "goodbye", "sad", "cry", "hurt", "sorrow"},
    "warmth": {"home", "love", "family", "mom", "grandma", "kitchen", "together", "hug"},
    "curiosity": {"why", "how", "wonder", "question", "mystery", "unknown", "guess", "puzzle"},
    "hope": {"hope", "tomorrow", "better", "future", "dream", "believe", "healing", "chance", "possible"},
    "joy": {"happy", "laugh", "smile", "joy", "delight", "fun", "celebrate", "wonderful", "great"},
    "surprise": {"suddenly", "unexpected", "shock", "surprised", "realized", "wow", "turned"},
    "reflection": {"remember", "looked", "thought", "think", "memory", "reflect", "years", "once", "maybe"},
    "urgency": {"now", "today", "hurry", "immediately", "deadline", "quick", "urgent", "must"},
}
# Maps the narrative emotion to the director's coarser emotion label where they overlap.
DIRECTOR_EMOTION = {"tension": "tension", "grief": "grief", "warmth": "warmth"}

TARGET_SHOT_SECONDS = {
    "tension": 1.6, "curiosity": 2.0, "sadness": 3.6, "hope": 3.0, "joy": 1.8,
    "surprise": 1.4, "reflection": 4.0, "urgency": 1.5, "neutral": 2.6,
    "grief": 3.6, "warmth": 3.2,
}
PACING_MULTIPLIER = {"FAST": 0.75, "MEDIUM": 1.0, "SLOW": 1.25}

STRUCTURES = {
    "hook_context_conflict_revelation_payoff": ["Hook", "Context", "Conflict", "Revelation", "Payoff"],
    "question_explanation_evidence_conclusion": ["Question", "Explanation", "Evidence", "Conclusion"],
    "problem_struggle_discovery_change": ["Problem", "Struggle", "Discovery", "Change"],
    "setup_tension_twist_resolution": ["Setup", "Tension", "Twist", "Resolution"],
}
PROBLEM_CUES = {"problem", "struggle", "stuck", "failed", "hard", "difficult", "trouble", "broke"}
DISCOVERY_CUES = {"learned", "discovered", "found", "realized", "changed", "understood"}
LOCATION_CUES = {"hanoi", "tokyo", "japan", "vietnam", "china", "korea", "seoul", "paris", "london",
                 "bangkok", "singapore", "america", "york", "delhi", "beijing", "sydney"}
CTA_PATTERN = re.compile(r"\b(subscribe|follow|comment|share|click|link in bio)\b|đăng ký|theo dõi|bình luận|chia sẻ",
                         re.IGNORECASE)

SHOT_TYPES = ("establishing", "wide", "medium", "close_up", "detail", "b_roll", "chart", "map", "graphics",
              "text_emphasis", "negative_space")
MOTION_FOR_PACING = {"FAST": "push_in_fast", "MEDIUM": "slow_drift", "SLOW": "static_hold"}
MOTION_ENERGY = {"push_in_fast": 0.8, "slow_drift": 0.4, "static_hold": 0.1}
BACKGROUND_LOAD = {"b_roll": 0.7, "map": 0.6, "chart": 0.6, "establishing": 0.5, "wide": 0.4,
                   "medium": 0.4, "detail": 0.3, "close_up": 0.3, "negative_space": 0.1, "text_emphasis": 0.1}
ATTENTION_BUDGET = 2.0


def _key(w: Word) -> str:
    return w.key


def _has_digit(w: Word) -> bool:
    return any(ch.isdigit() for ch in w.text)


# ---------------------------------------------------------------------------
# 2.1 Script analysis
# ---------------------------------------------------------------------------

def _topic(words: Sequence[Word], top: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for w in words:
        k = _key(w)
        if len(k) < 3 or k in STOPWORDS or not k.isalpha():
            continue
        counts[k] = counts.get(k, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:top]]


def _tone(words: Sequence[Word]) -> str:
    text_lower = [_key(w) for w in words]
    exclaim = sum(1 for w in words if w.text.endswith("!"))
    question = sum(1 for w in words if w.text.endswith("?"))
    urgent = sum(1 for k in text_lower if k in EMOTION_CUES["urgency"])
    reflect = sum(1 for k in text_lower if k in EMOTION_CUES["reflection"] | EMOTION_CUES["grief"])
    warm = sum(1 for k in text_lower if k in EMOTION_CUES["warmth"] | EMOTION_CUES["joy"] | EMOTION_CUES["hope"])
    if urgent >= 2 or exclaim >= 3:
        return "urgent"
    if reflect > max(warm, 1):
        return "reflective"
    if warm >= 2:
        return "warm"
    if question >= 2:
        return "inquisitive"
    return "neutral"


def _objective(genre_kind: str) -> str:
    return {
        "emotional": "move the viewer through a personal story",
        "informational": "explain a concept clearly",
        "documentary": "inform with a sequence of verifiable events",
        "fast": "motivate and hold attention quickly",
    }.get(genre_kind, "tell a story")


def analyze_script(words: Sequence[Word], genre: str, scenes: list[dict], audience: str | None = None) -> dict:
    """Script-level facts. Audience is not inferred from text; it is only reported when supplied."""
    kind = D.GENRES[genre]["kind"]
    turning = [s["id"] for s in scenes if s["turning_point"]]
    emotions = [s["narrative_emotion"] for s in scenes]
    hook = scenes[0]
    conflict = next((s for s in scenes if s["turning_point"] or s["narrative_emotion"] in ("tension", "urgency", "grief")),
                    None)
    numbers = [w.text for w in words if _has_digit(w)]
    text_all = " ".join(w.text for w in words)
    cta = CTA_PATTERN.search(text_all)
    return {
        "topic_keywords": _topic(words),
        "genre": genre,
        "audience": audience if audience else "not supplied",
        "tone": _tone(words),
        "objective": _objective(kind),
        "hook": {"scene": hook["id"], "text": hook["text"]},
        "conflict": {"scene": conflict["id"], "text": conflict["text"]} if conflict else None,
        "emotional_development": emotions,
        "key_events": {"numeric_tokens": numbers,
                       "scenes_with_numbers": [s["id"] for s in scenes if re.search(r"\d", s["text"])]},
        "turning_points": turning,
        "resolution": {"scene": scenes[-1]["id"], "text": scenes[-1]["text"]},
        "call_to_action": cta.group(0) if cta else None,
    }


# ---------------------------------------------------------------------------
# 2.2 Structure and acts
# ---------------------------------------------------------------------------

def choose_structure(words: Sequence[Word]) -> str:
    keys = [_key(w) for w in words]
    questions = sum(1 for w in words if w.text.endswith("?"))
    turns = sum(1 for k in keys if k in D.TURN_WORDS)
    tension = any(k in EMOTION_CUES["tension"] for k in keys)
    if questions >= 2:
        return "question_explanation_evidence_conclusion"
    if turns >= 2 and tension:
        return "setup_tension_twist_resolution"
    if any(k in PROBLEM_CUES for k in keys) and any(k in DISCOVERY_CUES for k in keys):
        return "problem_struggle_discovery_change"
    return "hook_context_conflict_revelation_payoff"


def assign_beats(n_scenes: int, labels: list[str]) -> list[str]:
    k = len(labels)
    return [labels[min(k - 1, (i * k) // n_scenes)] for i in range(n_scenes)]


def assign_acts(n_scenes: int) -> list[str]:
    out = []
    for i in range(n_scenes):
        f = i / n_scenes
        out.append("Act 1: setup" if f < 0.25 else "Act 2: confrontation" if f < 0.75 else "Act 3: resolution")
    return out


# ---------------------------------------------------------------------------
# 2.3 / 2.4 Scene-level planning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Phrase:
    text: str
    start: float
    end: float


def _phrases(words: Sequence[Word]) -> list[_Phrase]:
    out, buf = [], []
    for w in words:
        buf.append(w)
        if w.text.endswith(SENTENCE_END) or w.text.endswith(CLAUSE_END):
            out.append(_Phrase(" ".join(x.text for x in buf), buf[0].start, buf[-1].end))
            buf = []
    if buf:
        out.append(_Phrase(" ".join(x.text for x in buf), buf[0].start, buf[-1].end))
    return out


def _split_shots(words: Sequence[Word], n: int) -> list[tuple[float, float, str]]:
    """Group spoken phrases into n shots of roughly equal duration. Returns (start, end, text)."""
    phrases = _phrases(words)
    t0, t1 = words[0].start, words[-1].end
    if n <= 1 or len(phrases) <= 1:
        return [(t0, t1, " ".join(w.text for w in words))]
    width = (t1 - t0) / n
    shots: list[list[_Phrase]] = [[] for _ in range(n)]
    for p in phrases:
        idx = min(n - 1, int((p.start - t0) / width))
        shots[idx].append(p)
    result = []
    for i, group in enumerate(shots):
        if not group:
            continue
        start = group[0].start
        end = group[-1].end
        result.append((start, end, " ".join(p.text for p in group)))
    if result:
        result[0] = (t0, result[0][1], result[0][2])
        result[-1] = (result[-1][0], t1, result[-1][2])
    return result


def _narrative_emotion(words: Sequence[Word]) -> tuple[str, int]:
    counts = {name: 0 for name in EMOTION_CUES}
    for w in words:
        k = _key(w)
        for name, lex in EMOTION_CUES.items():
            if k in lex:
                counts[name] += 1
    best = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    hits = best[1]
    return (best[0], hits) if hits else ("neutral", 0)


def _choose_visual(idx: int, kind: str, emotion: str, pacing: str, intensity: float,
                   words: Sequence[Word]) -> tuple[str, list[dict]]:
    """Pick one shot type. Returns (choice, rejected alternatives with reasons)."""
    keys = {_key(w) for w in words}
    digits = sum(1 for w in words if _has_digit(w))
    location = bool(keys & LOCATION_CUES)
    candidates: list[tuple[str, str]] = []  # (shot type, condition description) in priority order
    if location and kind == "documentary":
        candidates.append(("map", "location named in a documentary scene"))
    if digits >= 2 and kind in ("informational", "documentary", "fast"):
        candidates.append(("chart", f"{digits} numeric tokens"))
    if idx == 1 and kind == "documentary":
        candidates.append(("establishing", "first scene of a documentary"))
    if emotion in ("grief", "sadness", "warmth") or intensity >= 0.6:
        candidates.append(("close_up", f"emotion '{emotion}' or intensity {intensity:.2f}"))
    if digits == 0 and kind == "informational" and len(words) >= 8 and emotion in ("neutral", "curiosity"):
        candidates.append(("graphics", "explainer sentence without numbers suits a diagram or process graphic"))
    if emotion in ("reflection", "sadness") and pacing == "SLOW":
        candidates.append(("negative_space", "reflective slow scene leaves room for silence"))
    if kind == "documentary" and not location and idx > 1 and emotion in ("reflection", "hope"):
        candidates.append(("wide", "open framing for a reflective documentary beat"))
    if emotion == "urgency" or len(words) <= 4:
        candidates.append(("text_emphasis", "urgent or very short line"))
    if kind in ("documentary", "emotional"):
        candidates.append(("b_roll", f"{kind} material"))
    default = "medium"
    if not candidates:
        return default, []
    chosen, _ = candidates[0]
    rejected = [{"option": opt, "reason": f"lost to '{chosen}' by priority; condition: {cond}"}
                for opt, cond in candidates[1:]]
    if chosen != default:
        rejected.append({"option": default, "reason": "default shot; a condition matched above it"})
    return chosen, rejected


def _visual_load(visual: str, words_per_second: float, motion: str, n_overlays: int, info_density: float) -> dict:
    components = {
        "caption_density": round(min(1.0, words_per_second / 3.5), 2),
        "movement": MOTION_ENERGY[motion],
        "background": BACKGROUND_LOAD.get(visual, 0.4),
        "overlays": round(0.5 * n_overlays, 2),
        "information": round(min(1.0, info_density), 2),
    }
    return components


def _attention(components: dict, visual: str, motion: str, n_overlays: int) -> dict:
    load = round(sum(components.values()), 2)
    actions = []
    if components["movement"] > 0.6:
        actions.append("change push_in_fast to slow_drift to reduce movement")
    if components["caption_density"] > 0.8:
        actions.append("split captions into shorter cues")
    if components["background"] > 0.6:
        actions.append(f"replace the busy {visual} background with medium or negative_space")
    if n_overlays >= 2:
        actions.append("remove one graphic overlay")
    over = load > ATTENTION_BUDGET
    if over and components["information"] > 0.8:
        actions.append("split the numbers across two scenes or shots")
    if over and not actions:
        biggest = max(components, key=lambda k: components[k])
        actions.append(f"reduce the largest load component '{biggest}' ({components[biggest]:.2f})")
    return {
        "load": load,
        "budget": ATTENTION_BUDGET,
        "over_budget": over,
        "components": components,
        "actions": actions if over else [],
    }


# ---------------------------------------------------------------------------
# 2.5 Cinematic grammar (applied at scene boundaries)
# ---------------------------------------------------------------------------

def _grammar(scenes: list[dict], fps: float) -> tuple[list[dict], dict]:
    annotations: list[dict] = []
    for a, b in zip(scenes, scenes[1:]):
        boundary = {"at_scene": b["id"], "at_seconds": b["start"]}
        if a["transition"] == "dissolve" and a["narrative_emotion"] in ("grief", "sadness", "warmth", "reflection", "hope"):
            annotations.append({**boundary, "type": "j_cut", "audio_leads_frames": round(0.4 * fps),
                                "reason": "emotional dissolve: narration arrives before the picture changes"})
        if a["turning_point"]:
            annotations.append({**boundary, "type": "l_cut", "audio_tail_seconds": 0.4,
                                "reason": "turning point: previous audio carries over the new picture"})
        if a["text"].endswith("?") and len(b["text"].split()) <= 4:
            annotations.append({**boundary, "type": "reaction_cut",
                                "reason": "question followed by a short reply"})
        if a["transition"] == "cut" and a["text"].endswith(SENTENCE_END):
            annotations.append({**boundary, "type": "motivated_cut",
                                "reason": "cut on a sentence end"})
        if a["color_look"] == b["color_look"]:
            annotations.append({**boundary, "type": "continuity",
                                "reason": f"same colour look '{a['color_look']}' across the cut"})

    # Rhythmic montage: runs of three or more short shots in a FAST scene.
    rhythmic = []
    for s in scenes:
        if s["pacing"] != "FAST":
            continue
        run = [sh for sh in s["shots"] if sh["duration_s"] < 1.5]
        if len(run) >= 3:
            rhythmic.append({"scene": s["id"], "type": "rhythmic_montage", "shots": len(run),
                             "reason": "three or more short shots in a fast scene"})
    annotations.extend(rhythmic)

    not_applied = {
        "match_cut": "needs visual similarity between shots; not available in this build",
        "parallel_montage": "needs two or more storylines; the script analyser handles one",
        "cross_cutting": "needs two or more storylines; not available in this build",
    }
    return annotations, not_applied


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build(words: Sequence[Word] | str, genre: str, title: str = "untitled", fps: float = 30.0,
          audience: str | None = None, cfg: D.DirectorConfig = D.DirectorConfig()) -> dict:
    """Produce a narrative plan: analysis, structure, acts, scene plans, grammar, and decision records."""
    if isinstance(words, str):
        words = load_words(words)
    words = list(words)
    problems = validate_words(words)
    if problems:
        raise ValueError("invalid words: " + "; ".join(problems))
    if genre not in D.GENRES:
        raise KeyError(f"unsupported genre {genre!r}; choose from {sorted(D.GENRES)}")

    base = D.plan(words, genre, title, cfg)
    groups = D.segment_scenes(words, cfg)
    if len(groups) != len(base["scenes"]):
        raise RuntimeError("scene segmentation mismatch between director and narrative planner")

    kind = D.GENRES[genre]["kind"]
    labels_key = choose_structure(words)
    labels = STRUCTURES[labels_key]
    beats = assign_beats(len(groups), labels)
    acts = assign_acts(len(groups))

    scenes: list[dict] = []
    for i, (base_scene, group) in enumerate(zip(base["scenes"], groups)):
        emo, hits = _narrative_emotion(group)
        pacing = base_scene["pacing"]
        duration = group[-1].end - group[0].start
        target = TARGET_SHOT_SECONDS[emo] * PACING_MULTIPLIER[pacing]
        n_shots = max(1, round(duration / target))
        visual, rejected_visual = _choose_visual(i + 1, kind, emo, pacing, base_scene["intensity"], group)
        motion = MOTION_FOR_PACING[pacing]
        motion_rejected = [{"option": m, "reason": f"pacing {pacing} calls for {MOTION_FOR_PACING[pacing]}"}
                           for p, m in MOTION_FOR_PACING.items() if p != pacing]

        raw_shots = _split_shots(group, n_shots)
        shots = []
        for j, (s0, s1, text) in enumerate(raw_shots):
            shot_visual = visual
            if j == len(raw_shots) - 1 and base_scene["turning_point"] and len(raw_shots) >= 2:
                shot_visual = "detail"  # insert shot at the turning point
            elif visual == "b_roll" and j % 2 == 1:
                shot_visual = "medium"
            shots.append({"index": j + 1, "start": round(s0, 3), "end": round(s1, 3),
                          "duration_s": round(s1 - s0, 3), "visual": shot_visual, "text": text})

        n_overlays = sum(1 for sh in shots if sh["visual"] in ("chart", "map", "text_emphasis"))
        words_per_second = len(group) / max(duration, 1e-6)
        info_density = min(1.0, (sum(1 for w in group if _has_digit(w)) + 0.5 * sum(
            1 for w in group if _key(w) in LOCATION_CUES)) / max(len(group) / 8.0, 1.0))
        comps = _visual_load(visual, words_per_second, motion, n_overlays, info_density)
        attention = _attention(comps, visual, motion, n_overlays)

        evidence = hits + (1 if base_scene["turning_point"] else 0)
        confidence = round(0.45 if emo == "neutral" else min(0.95, 0.5 + 0.1 * evidence), 2)
        uncertainty = []
        if emo == "neutral":
            uncertainty.append("no emotional cue found; default pacing and visuals used")
        if visual == "medium" and not rejected_visual:
            uncertainty.append("no visual rule matched; medium shot is the fallback")

        justification = (f"{emo} ({hits} cue{'s' if hits != 1 else ''}), pacing {pacing} from genre '{genre}' "
                         f"and {words_per_second:.1f} words/s; target shot {target:.1f} s, {n_shots} shot(s).")
        scene = dict(base_scene)
        scene.update({
            "act": acts[i],
            "beat": beats[i],
            "narrative_emotion": emo,
            "target_shot_seconds": round(target, 2),
            "visual": visual,
            "motion": motion,
            "shots": shots,
            "attention": attention,
            "decision": {
                "scene_id": base_scene["id"],
                "selected": {"visual": visual, "shot_count": len(shots),
                             "shot_duration_s": round(duration / len(shots), 3), "motion": motion,
                             "transition": base_scene["transition"], "music_level": base_scene["music_level"]},
                "emotional_justification": justification,
                "rejected_alternatives": rejected_visual + motion_rejected,
                "confidence": confidence,
                "uncertainty": uncertainty,
            },
        })
        scenes.append(scene)

    grammar, not_applied = _grammar(scenes, fps)
    acts_summary: dict[str, list[str]] = {}
    for s in scenes:
        acts_summary.setdefault(s["act"], []).append(s["id"])

    return {
        "title": title,
        "genre": genre,
        "duration": base["duration"],
        "analysis": analyze_script(words, genre, scenes, audience),
        "structure": {"name": labels_key, "beats": labels},
        "acts": [{"label": k, "scenes": v} for k, v in acts_summary.items()],
        "scenes": scenes,
        "cinematic": {"applied": grammar, "not_applied": not_applied},
        "summary": {
            "scenes": len(scenes),
            "shots": sum(len(s["shots"]) for s in scenes),
            "over_budget_scenes": [s["id"] for s in scenes if s["attention"]["over_budget"]],
            "visuals": {v: sum(1 for s in scenes if s["visual"] == v) for v in SHOT_TYPES
                        if any(s["visual"] == v for s in scenes)},
            "mean_target_shot_seconds": round(sum(s["target_shot_seconds"] for s in scenes) / len(scenes), 2),
        },
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys
    p = argparse.ArgumentParser(description="Build a narrative plan from a timed-word JSON file.")
    p.add_argument("words", help="word timing JSON (see uvs.captions.load_words)")
    p.add_argument("--genre", required=True, choices=sorted(D.GENRES))
    p.add_argument("--title", default="untitled")
    p.add_argument("--audience", default=None, help="optional; not inferred from the text")
    p.add_argument("--out", default=None, help="write the plan here instead of printing it")
    args = p.parse_args(argv)
    plan = build(args.words, args.genre, args.title, audience=args.audience)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if args.out:
        from pathlib import Path
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {plan['summary']['scenes']} scenes, {plan['summary']['shots']} shots", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
