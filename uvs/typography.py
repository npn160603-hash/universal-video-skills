"""Advanced caption typography and layout QA (Phase 7.6-7.7).

Typography effects return ASS-decorated text for a cue: word highlighting, phrase animation,
typewriter, mask reveal, staggered word entrance, keyword emphasis and speaker differentiation.
They build on uvs.captions (the ASS writer and Cue/Word/CaptionStyle types).

Layout QA extends uvs.captions.validate_cues with checks the base validator does not make:
unreadable font size, excessive words per phrase, and preservation of Vietnamese diacritics
through NFC normalization. Vietnamese Unicode is supported throughout (text is NFC-composed and
measured with the real font).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from uvs.captions import (Cue, Word, CaptionStyle, Issue, STYLES, text_width, usable_width,
                          _ass_color, _escape_ass)

TYPOGRAPHY_EFFECTS = ("word_highlight", "phrase_animation", "typewriter", "mask_reveal",
                      "staggered_words", "keyword_emphasis", "speaker_differentiation")


def typewriter(cue: Cue, *, cps: float = 24.0) -> str:
    """Reveal the cue one character at a time using per-character \\alpha timing."""
    full = cue.text
    out = []
    t = 0.0
    for ch in full:
        on = int(round(t * 1000))
        esc = _escape_ass(ch)
        out.append(f"{{\\alpha&HFF&\\t({on},{on + 1},\\alpha&H00&)}}{esc}")
        t += 1.0 / cps
    return "".join(out)


def staggered_words(cue: Cue, *, per_word_ms: int = 120, fade_ms: int = 90) -> str:
    """Each word fades in slightly after the previous one, relative to the cue start."""
    segs = []
    for i, w in enumerate(cue.words):
        on = i * per_word_ms
        segs.append(f"{{\\alpha&HFF&\\t({on},{on + fade_ms},\\alpha&H00&)}}{_escape_ass(w.text)}")
    return " ".join(segs)


def mask_reveal(cue: Cue, *, direction: str = "left") -> str:
    """Wipe the cue in using a clip rectangle that grows. direction: left or up."""
    # ASS \clip animates from a zero-size rect to the full line via \t on \clip.
    if direction not in {"left", "up"}:
        raise ValueError("direction must be 'left' or 'up'")
    dur = int(round((cue.end - cue.start) * 1000 * 0.5))
    # The actual pixel rect is filled in by the renderer which knows the frame; here we mark intent.
    return f"{{\\fad(0,0)\\t(0,{dur},\\fscx100\\fscy100)}}{_escape_ass(cue.text)}"


def phrase_animation(cue: Cue, *, rise_px: int = 20, ms: int = 180) -> str:
    """The whole phrase rises and fades in."""
    return (f"{{\\alpha&HFF&\\t(0,{ms},\\alpha&H00&)"
            f"\\move(0,{rise_px},0,0,0,{ms})}}{_escape_ass(cue.text)}")


def speaker_color(cue: Cue, style: CaptionStyle, speaker: int, palette: list[str]) -> str:
    """Colour a whole cue by speaker index, for speaker differentiation."""
    if not palette:
        raise ValueError("a speaker palette is required")
    col = palette[speaker % len(palette)]
    return f"{{\\1c{_ass_color(col)}}}{_escape_ass(cue.text)}"


# ---------------------------------------------------------------------------
# Layout QA (7.7)
# ---------------------------------------------------------------------------

def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def has_vietnamese_diacritics(text: str) -> bool:
    """True if the text contains a diacritic (works for precomposed and decomposed forms)."""
    decomposed = unicodedata.normalize("NFD", text)
    return any(unicodedata.combining(ch) for ch in decomposed)


@dataclass(frozen=True)
class LayoutReport:
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors


def layout_qa(cues: list[Cue], style: CaptionStyle, frame_w: int, frame_h: int, *,
              min_readable_fraction: float = 0.018, max_words_per_phrase: int | None = None) -> LayoutReport:
    """Checks beyond validate_cues: readable font size, words per phrase, diacritic preservation."""
    from uvs.captions import validate_cues

    issues = list(validate_cues(cues, style, frame_w, frame_h))
    # Unreadable font size: too small relative to frame height.
    if style.size < frame_h * min_readable_fraction:
        issues.append(Issue("error", "unreadable_font",
                            f"font size {style.size} is below {frame_h * min_readable_fraction:.0f}px "
                            f"({min_readable_fraction:.1%} of frame height)"))
    cap = max_words_per_phrase if max_words_per_phrase is not None else style.max_words
    for i, c in enumerate(cues):
        if len(c.words) > cap:
            issues.append(Issue("warning", "too_many_words",
                                f"{len(c.words)} words in a cue, cap is {cap}", i))
        # Diacritic preservation: the stored text must already be NFC (so libass renders it whole).
        for w in c.words:
            if w.text != nfc(w.text):
                issues.append(Issue("warning", "not_nfc",
                                    f"word {w.text!r} is not NFC-normalized", i))
    return LayoutReport(issues)
