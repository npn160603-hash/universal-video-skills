"""Caption engine for professional-caption-design.

Pipeline: word timings -> phrase cues -> measured two-line layout -> ASS / SRT / WebVTT
-> validation report.

Word timings are supplied by the caller. No speech-to-text model is bundled, so this
module never invents timings. Line widths are measured with the real font file
(through fontconfig + Pillow), so the fit checks match the glyphs libass draws.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from PIL import ImageFont

SENTENCE_END = (".", "?", "!", "…")
CLAUSE_END = (",", ";", ":")
PUNCT_SPACE_RE = re.compile(r"\s[,.!?;:]")
PUNCT_NOSPACE_RE = re.compile(r"[,;:!?][^\s\"'\)\]\}]")
DOUBLE_SPACE_RE = re.compile(r"\S {2,}\S")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("word text is empty")
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid timing for {self.text!r}: {self.start}-{self.end}")

    @property
    def key(self) -> str:
        """Normalized token used for keyword matching (letters/digits only, lowercase)."""
        return re.sub(r"[\W_]+", "", self.text, flags=re.UNICODE).lower()


@dataclass(frozen=True)
class CaptionStyle:
    name: str
    font: str
    size: int
    bold: bool
    primary: str            # RRGGBB text colour
    highlight: str | None   # RRGGBB colour for highlighted keywords, None = no highlight
    outline: int
    shadow: int
    margin_v: int           # bottom safe zone in px (keeps captions above platform UI)
    margin_h: int = 90      # left/right safe margin in px
    max_lines: int = 2
    animation: str = "fade"  # "fade" (whole cue), "pop" (highlighted words scale), "none"
    fade_ms: int = 150
    pop_scale: int = 115
    outline_color: str = "000000"
    shadow_color: str = "000000"
    background: str = "outline"   # "outline" (stroked text) or "box" (opaque caption box)
    box_color: str = "000000"     # RRGGBB fill when background == "box"
    box_alpha: int = 160          # 0 = opaque, 255 = invisible (ASS alpha), used for the box
    line_spacing: int = 0         # extra px between lines (ASS Spacing is horizontal; used by QA)
    max_words: int = 7            # max words per phrase/cue, used by segmentation QA


STYLES: dict[str, CaptionStyle] = {
    "documentary_minimal": CaptionStyle(
        name="documentary_minimal", font="Inter", size=52, bold=False,
        primary="F4F1EA", highlight=None, outline=2, shadow=0,
        margin_v=300, animation="fade", fade_ms=250,
    ),
    "bold_shorts": CaptionStyle(
        name="bold_shorts", font="Inter", size=84, bold=True,
        primary="FFFFFF", highlight="FFD700", outline=6, shadow=0,
        margin_v=430, animation="pop", fade_ms=80,
    ),
    "cinematic": CaptionStyle(
        name="cinematic", font="Inter", size=60, bold=False,
        primary="EDE6DA", highlight="D9B26F", outline=2, shadow=2,
        margin_v=320, animation="fade", fade_ms=500,
    ),
    "emotional_storytelling": CaptionStyle(
        name="emotional_storytelling", font="Inter", size=56, bold=False,
        primary="EFE8DC", highlight=None, outline=2, shadow=1,
        margin_v=340, animation="fade", fade_ms=700,
    ),
    "clean_modern": CaptionStyle(
        name="clean_modern", font="Inter", size=64, bold=True,
        primary="FFFFFF", highlight="4FA3FF", outline=0, shadow=0,
        margin_v=360, animation="fade", fade_ms=120, max_lines=2,
        background="box", box_color="101418", box_alpha=120, max_words=6,
    ),
    "podcast_highlight": CaptionStyle(
        name="podcast_highlight", font="Inter", size=76, bold=True,
        primary="FFFFFF", highlight="FFE14D", outline=4, shadow=0,
        margin_v=450, animation="pop", fade_ms=90, pop_scale=122, max_lines=2,
    ),
    "educational": CaptionStyle(
        name="educational", font="Inter", size=58, bold=True,
        primary="FFFFFF", highlight="57C48C", outline=3, shadow=1,
        margin_v=300, animation="fade", fade_ms=160, max_lines=2,
    ),
}


@dataclass(frozen=True)
class SegmentConfig:
    max_gap: float = 0.45          # silence (s) between words that forces a cue break
    max_duration: float = 2.8      # target longest cue on screen (s)
    hard_max_duration: float = 3.4  # a sentence end may finish a cue up to this length
    min_duration: float = 0.7      # shortest cue on screen (s); enforced when exporting
    clause_break_min_words: int = 3
    clause_break_min_seconds: float = 1.0


@dataclass
class Cue:
    start: float
    end: float
    words: list[Word]
    lines: list[list[Word]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def line_texts(self) -> list[str]:
        return [" ".join(w.text for w in line) for line in self.lines]


@dataclass(frozen=True)
class Issue:
    level: str        # "error" | "warning"
    code: str
    message: str
    cue: int | None = None


# ---------------------------------------------------------------------------
# Font measurement
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def resolve_font_file(family: str, bold: bool) -> str | None:
    """Ask fontconfig for the font file behind a family and weight."""
    if not shutil.which("fc-match"):
        return None
    style = "Bold" if bold else "Regular"
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", f"{family}:style={style}"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    return out or None


@lru_cache(maxsize=64)
def _font(family: str, bold: bool, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = resolve_font_file(family, bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def text_width(text: str, style: CaptionStyle) -> float:
    """Rendered width in pixels of a single line of text in this style."""
    return float(_font(style.font, style.bold, style.size).getlength(text))


def usable_width(style: CaptionStyle, frame_w: int) -> float:
    """Pixels available for one line, after side safe margins and the outline."""
    return frame_w - 2 * style.margin_h - 2 * style.outline


# ---------------------------------------------------------------------------
# Loading and normalization
# ---------------------------------------------------------------------------

def load_words(source: str | Path | Sequence[dict]) -> list[Word]:
    """Load word timings from a JSON file path or a list of dicts.

    Accepts a list of {"text", "start", "end"} or {"words": [...]}. Text is
    normalized to Unicode NFC so Vietnamese diacritics compare and render reliably.
    """
    if isinstance(source, (str, Path)):
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        data = list(source)
    if isinstance(data, dict):
        data = data["words"]
    words = []
    for item in data:
        text = unicodedata.normalize("NFC", str(item["text"]))
        words.append(Word(text=text, start=float(item["start"]), end=float(item["end"])))
    for prev, nxt in zip(words, words[1:]):
        if nxt.start < prev.start:
            raise ValueError(f"words are not in time order: {prev.text!r} then {nxt.text!r}")
    return words


# ---------------------------------------------------------------------------
# Layout and segmentation
# ---------------------------------------------------------------------------

def _joined(words: Iterable[Word]) -> str:
    return " ".join(w.text for w in words)


def layout_lines(words: Sequence[Word], style: CaptionStyle, max_width: float) -> list[list[Word]] | None:
    """Split words into at most style.max_lines lines that each fit max_width.

    Returns None when the words cannot fit. A two-line split is balanced by measured
    width. A split after punctuation gets a small bonus.
    """
    if not words:
        return []
    if text_width(_joined(words), style) <= max_width:
        return [list(words)]
    if style.max_lines < 2 or len(words) < 2:
        return None

    best: tuple[float, list[list[Word]]] | None = None
    for k in range(1, len(words)):
        a, b = list(words[:k]), list(words[k:])
        wa = text_width(_joined(a), style)
        wb = text_width(_joined(b), style)
        if wa > max_width or wb > max_width:
            continue
        score = abs(wa - wb)
        if a[-1].text.endswith(CLAUSE_END + SENTENCE_END):
            score -= 0.15 * max_width
        if best is None or score < best[0]:
            best = (score, [a, b])
    return best[1] if best else None


def _ends_phrase(word: Word, current: Sequence[Word], cfg: SegmentConfig) -> bool:
    if word.text.endswith(SENTENCE_END):
        return True
    if word.text.endswith(CLAUSE_END):
        duration = current[-1].end - current[0].start
        return len(current) >= cfg.clause_break_min_words and duration >= cfg.clause_break_min_seconds
    return False


def segment_words(words: Sequence[Word], style: CaptionStyle, frame_w: int,
                  cfg: SegmentConfig = SegmentConfig()) -> list[Cue]:
    """Group words into on-screen cues that respect layout, timing and phrase boundaries.

    A cue breaks on a sentence end, on a long silence, when it would exceed the max
    duration, or when the next word would not fit the style's line budget.
    A single word that is wider than a line is kept so the validator can flag it.
    """
    max_w = usable_width(style, frame_w)
    cues: list[Cue] = []
    current: list[Word] = []

    def close() -> None:
        nonlocal current
        if not current:
            return
        lines = layout_lines(current, style, max_w)
        if lines is None:
            lines = [list(current)]  # overflow: validator reports it
        cues.append(Cue(start=current[0].start, end=current[-1].end,
                        words=list(current), lines=lines))
        current = []

    for word in words:
        if current:
            gap = word.start - current[-1].end
            span = word.end - current[0].start
            ends_sentence = word.text.endswith(SENTENCE_END)
            # Soft limit: finish a sentence instead of leaving an orphan word behind it.
            too_long = span > cfg.max_duration and not (ends_sentence and span <= cfg.hard_max_duration)
            no_fit = layout_lines(current + [word], style, max_w) is None
            if gap > cfg.max_gap or too_long or no_fit:
                close()
        current.append(word)
        if _ends_phrase(word, current, cfg):
            close()
    close()
    return cues


def finalize_timings(cues: list[Cue], cfg: SegmentConfig = SegmentConfig()) -> list[Cue]:
    """Extend very short cues up to min_duration without overlapping the next cue."""
    for i, cue in enumerate(cues):
        target = max(cue.end, cue.start + cfg.min_duration)
        if i + 1 < len(cues):
            target = min(target, max(cue.end, cues[i + 1].start - 0.02))
        cue.end = target
    return cues


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _escape_ass(text: str) -> str:
    # Braces start override blocks in ASS. Backslashes start tags. Swap both for
    # look-alike characters so user text can never inject styling.
    return text.replace("{", "(").replace("}", ")").replace("\\", "/")


def _ass_color(hex_rgb: str) -> str:
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H00{b}{g}{r}".upper() + "&"


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_time(t: float) -> str:
    return _srt_time(t).replace(",", ".")


def is_highlighted(word: Word, keys: frozenset[str], auto_numbers: bool) -> bool:
    if word.key and word.key in keys:
        return True
    return auto_numbers and any(ch.isdigit() for ch in word.text)


def _ass_cue_text(cue: Cue, style: CaptionStyle, keys: frozenset[str], auto_numbers: bool) -> str:
    prim = _ass_color(style.primary)
    prefix = ""
    if style.animation in ("fade", "pop"):
        prefix = f"{{\\fad({style.fade_ms},{style.fade_ms})}}"
    rendered_lines = []
    for line in cue.lines:
        segs = []
        for w in line:
            text = _escape_ass(w.text)
            if style.highlight and style.animation != "none" and is_highlighted(w, keys, auto_numbers):
                hl = _ass_color(style.highlight)
                if style.animation == "pop":
                    off = int(round((w.start - cue.start) * 1000))
                    s = style.pop_scale
                    segs.append(
                        f"{{\\1c{hl}\\t({off},{off + 120},\\fscx{s}\\fscy{s})}}{text}"
                        f"{{\\1c{prim}\\fscx100\\fscy100}}"
                    )
                else:
                    segs.append(f"{{\\1c{hl}}}{text}{{\\1c{prim}}}")
            else:
                segs.append(text)
        rendered_lines.append(" ".join(segs))
    return prefix + "\\N".join(rendered_lines)


def to_ass(cues: list[Cue], style: CaptionStyle, frame_w: int, frame_h: int,
           keys: frozenset[str] = frozenset(), auto_numbers: bool = False) -> str:
    bold = -1 if style.bold else 0
    border_style = 3 if style.background == "box" else 1
    # For a box, BackColour carries the box fill and alpha; outline becomes the box padding.
    if style.background == "box":
        a = max(0, min(255, style.box_alpha))
        back = f"&H{a:02X}{style.box_color[4:6]}{style.box_color[2:4]}{style.box_color[0:2]}"
        outline_px = max(style.outline, 6)
    else:
        back = _ass_color(style.shadow_color)
        outline_px = style.outline
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {frame_w}",
        f"PlayResY: {frame_h}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (f"Style: Default,{style.font},{style.size},{_ass_color(style.primary)},"
         f"{_ass_color(style.primary)},{_ass_color(style.outline_color)},"
         f"{back},{bold},0,0,0,100,100,{style.line_spacing},0,{border_style},"
         f"{outline_px},{style.shadow},2,{style.margin_h},{style.margin_h},{style.margin_v},1"),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [
        f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,0,0,0,,"
        f"{_ass_cue_text(c, style, keys, auto_numbers)}"
        for c in cues
    ]
    return "\n".join(header + events) + "\n"


def to_srt(cues: list[Cue]) -> str:
    blocks = []
    for i, c in enumerate(cues, 1):
        blocks.append(f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n" + "\n".join(c.line_texts))
    return "\n\n".join(blocks) + "\n"


def to_vtt(cues: list[Cue]) -> str:
    blocks = ["WEBVTT"]
    for c in cues:
        blocks.append(f"{_vtt_time(c.start)} --> {_vtt_time(c.end)}\n" + "\n".join(c.line_texts))
    return "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_cues(cues: list[Cue], style: CaptionStyle, frame_w: int, frame_h: int,
                  cfg: SegmentConfig = SegmentConfig(), max_cps: float = 22.0) -> list[Issue]:
    issues: list[Issue] = []
    max_w = usable_width(style, frame_w)

    if style.margin_v + style.size * 1.25 > frame_h:
        issues.append(Issue("error", "outside_frame",
                            "bottom margin plus line height exceeds the frame height"))
    if style.margin_h + style.outline >= frame_w / 2:
        issues.append(Issue("error", "safe_margin", "side safe margin leaves no room for text"))

    for i, c in enumerate(cues):
        if not c.text.strip():
            issues.append(Issue("error", "empty_cue", "cue has no text", i))
            continue
        if c.end <= c.start:
            issues.append(Issue("error", "non_positive_duration", "cue end is not after start", i))
        if i + 1 < len(cues) and c.end > cues[i + 1].start + 1e-6:
            issues.append(Issue("error", "overlap", "cue overlaps the next cue", i))
        if len(c.lines) > style.max_lines:
            issues.append(Issue("error", "too_many_lines",
                                f"{len(c.lines)} lines, style allows {style.max_lines}", i))
        for text in c.line_texts:
            width = text_width(text, style)
            if width > max_w:
                issues.append(Issue("error", "line_overflow",
                                    f"line is {width:.0f}px, usable width is {max_w:.0f}px", i))
        duration = c.end - c.start
        if duration < cfg.min_duration - 1e-6:
            issues.append(Issue("warning", "short_cue", f"cue lasts {duration:.2f}s", i))
        if duration > cfg.hard_max_duration + 1e-6:
            issues.append(Issue("warning", "long_cue", f"cue lasts {duration:.2f}s", i))
        if len(c.words) == 1 and len(cues) > 1:
            issues.append(Issue("warning", "orphan_word",
                                f"single word {c.words[0].text!r} forms its own cue", i))
        chars = len(re.sub(r"\s", "", c.text))
        if duration > 0 and chars / duration > max_cps:
            issues.append(Issue("warning", "too_fast",
                                f"{chars / duration:.1f} characters per second (limit {max_cps:g})", i))
        if PUNCT_SPACE_RE.search(c.text):
            issues.append(Issue("warning", "space_before_punctuation", "space before punctuation", i))
        if PUNCT_NOSPACE_RE.search(c.text):
            issues.append(Issue("warning", "missing_space_after_punctuation",
                                "no space after punctuation", i))
        if DOUBLE_SPACE_RE.search(c.text):
            issues.append(Issue("warning", "double_space", "double space inside cue", i))
        if c.text != unicodedata.normalize("NFC", c.text):
            issues.append(Issue("warning", "not_nfc", "text is not NFC-normalized", i))
    return issues


# ---------------------------------------------------------------------------
# One-call build
# ---------------------------------------------------------------------------

@dataclass
class CaptionBuild:
    cues: list[Cue]
    issues: list[Issue]
    style: CaptionStyle
    frame_w: int
    frame_h: int
    keys: frozenset[str] = frozenset()
    auto_numbers: bool = False

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]


def build_captions(words: Sequence[Word] | str | Path, style_name: str, frame_w: int = 1080,
                   frame_h: int = 1920, keywords: Iterable[str] = (), auto_numbers: bool = False,
                   cfg: SegmentConfig = SegmentConfig()) -> CaptionBuild:
    if style_name not in STYLES:
        raise KeyError(f"unknown caption style {style_name!r}; choose from {sorted(STYLES)}")
    style = STYLES[style_name]
    if isinstance(words, (str, Path)):
        loaded = load_words(words)
    else:
        items = list(words)
        loaded = items if all(isinstance(w, Word) for w in items) else load_words(items)
    keys = frozenset(re.sub(r"[\W_]+", "", k, flags=re.UNICODE).lower() for k in keywords)
    cues = finalize_timings(segment_words(loaded, style, frame_w, cfg), cfg)
    issues = validate_cues(cues, style, frame_w, frame_h, cfg)
    return CaptionBuild(cues=cues, issues=issues, style=style, frame_w=frame_w, frame_h=frame_h,
                        keys=keys, auto_numbers=auto_numbers)


def write_outputs(build: CaptionBuild, out_dir: str | Path, stem: str = "captions") -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "ass": out / f"{stem}.ass",
        "srt": out / f"{stem}.srt",
        "vtt": out / f"{stem}.vtt",
    }
    paths["ass"].write_text(to_ass(build.cues, build.style, build.frame_w, build.frame_h,
                                   build.keys, build.auto_numbers), encoding="utf-8")
    paths["srt"].write_text(to_srt(build.cues), encoding="utf-8")
    paths["vtt"].write_text(to_vtt(build.cues), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build styled captions (ASS/SRT/VTT) from word timings.")
    p.add_argument("words", help="JSON file with word timings")
    p.add_argument("--style", default="bold_shorts", choices=sorted(STYLES))
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--height", type=int, default=1920)
    p.add_argument("--out-dir", default="out")
    p.add_argument("--keywords", default="", help="comma-separated keywords to highlight")
    p.add_argument("--auto-numbers", action="store_true", help="also highlight tokens containing digits")
    args = p.parse_args(argv)

    kws = [k.strip() for k in args.keywords.split(",") if k.strip()]
    build = build_captions(args.words, args.style, args.width, args.height, kws, args.auto_numbers)
    paths = write_outputs(build, args.out_dir)
    report = {
        "style": args.style,
        "cues": len(build.cues),
        "errors": len(build.errors),
        "warnings": len([i for i in build.issues if i.level == "warning"]),
        "issues": [i.__dict__ for i in build.issues],
        "files": paths,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if build.errors else 0


if __name__ == "__main__":
    sys.exit(main())
