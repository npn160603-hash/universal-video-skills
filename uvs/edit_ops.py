"""Non-destructive timeline editing operations with undo records (Phase 1.3).

Every operation takes a timeline and returns a NEW timeline plus a record. The input is never
modified. If the result would be invalid (per `uvs.timeline.validate`), the operation raises
EditError and nothing changes.

A record looks like:

    {"op": "set_duration", "args": {...}, "undo": [{"op": ..., "args": ...}, ...]}

`undo` is a list of operations that, applied in order to the result, restore the earlier state.
Replaying a list of records on the original timeline reproduces the edited timeline.

Video tracks form a chain: each clip's start is derived from its predecessor, so video edits
reflow the following clips. Audio and overlay clips are placed freely by their start frame.
"""
from __future__ import annotations

import copy
from dataclasses import asdict

from uvs import timeline as T


class EditError(ValueError):
    """An operation is invalid or would produce an invalid timeline."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _track(tl: T.Timeline, name: str) -> T.Track:
    for t in tl.tracks:
        if t.name == name:
            return t
    raise EditError(f"no track named {name!r}; tracks are {[t.name for t in tl.tracks]}")


def _clip(track: T.Track, clip_id: str) -> tuple[int, T.Clip]:
    for i, c in enumerate(track.clips):
        if c.id == clip_id:
            return i, c
    raise EditError(f"no clip {clip_id!r} on track {track.name!r}")


def _video_track_of(tl: T.Timeline, clip_id: str) -> T.Track:
    for t in tl.tracks:
        if t.kind == "video" and any(c.id == clip_id for c in t.clips):
            return t
    raise EditError(f"no video clip {clip_id!r}")


def _reflow(track: T.Track) -> None:
    """Recompute video clip starts from durations and transitions. The first clip starts at frame 0."""
    if track.clips:
        track.clips[0].start = 0
    for i in range(1, len(track.clips)):
        prev, c = track.clips[i - 1], track.clips[i]
        c.start = prev.start + prev.duration - c.transition_frames


def _commit(tl: T.Timeline, touched_video: bool) -> None:
    """Validate after an edit. Raises EditError with every error listed."""
    for t in tl.tracks:
        if t.kind == "video" and touched_video:
            _reflow(t)
    errors = [i for i in T.validate(tl, check_files=False) if i.level == "error"]
    if errors:
        raise EditError("; ".join(f"[{i.code}] {i.message}" for i in errors))


def _clip_from_dict(d: dict) -> T.Clip:
    try:
        return T.Clip(**d)
    except TypeError as exc:
        raise EditError(f"bad clip definition: {exc}") from exc


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _op_move_clip(tl: T.Timeline, args: dict) -> tuple[T.Timeline, list[dict]]:
    track = _track(tl, args["track"])
    if track.kind == "video":
        raise EditError("video clips are placed by the transition chain; use set_duration or set_transition")
    _, clip = _clip(track, args["clip_id"])
    old = clip.start
    clip.start = int(args["start"])
    _commit(tl, touched_video=False)
    return tl, [{"op": "move_clip", "args": {"track": track.name, "clip_id": clip.id, "start": old}}]


def _op_set_duration(tl: T.Timeline, args: dict) -> tuple[T.Timeline, list[dict]]:
    track = _track(tl, args["track"])
    _, clip = _clip(track, args["clip_id"])
    old = clip.duration
    clip.duration = int(args["frames"])
    _commit(tl, touched_video=track.kind == "video")
    return tl, [{"op": "set_duration", "args": {"track": track.name, "clip_id": clip.id, "frames": old}}]


def _op_set_transition(tl: T.Timeline, args: dict) -> tuple[T.Timeline, list[dict]]:
    track = _video_track_of(tl, args["clip_id"])
    idx, clip = _clip(track, args["clip_id"])
    if idx == 0:
        raise EditError("the first clip has no incoming transition")
    old = {"kind": clip.transition, "frames": clip.transition_frames}
    clip.transition = args["kind"]
    clip.transition_frames = int(args["frames"])
    _commit(tl, touched_video=True)
    return tl, [{"op": "set_transition", "args": {"clip_id": clip.id, "kind": old["kind"], "frames": old["frames"]}}]


def _op_add_clip(tl: T.Timeline, args: dict) -> tuple[T.Timeline, list[dict]]:
    track = _track(tl, args["track"])
    clip = _clip_from_dict(dict(args["clip"]))
    if any(c.id == clip.id for t in tl.tracks for c in t.clips):
        raise EditError(f"clip id {clip.id!r} already exists")
    index = args.get("index")
    if track.kind == "video":
        if index is None:
            index = len(track.clips)
        if not 0 <= index <= len(track.clips):
            raise EditError(f"index {index} is out of range")
        track.clips.insert(index, clip)
    else:
        track.clips.append(clip)
        track.clips.sort(key=lambda c: c.start)
        index = track.clips.index(clip)
    _commit(tl, touched_video=track.kind == "video")
    return tl, [{"op": "remove_clip", "args": {"track": track.name, "clip_id": clip.id}}]


def _op_remove_clip(tl: T.Timeline, args: dict) -> tuple[T.Timeline, list[dict]]:
    track = _track(tl, args["track"])
    idx, clip = _clip(track, args["clip_id"])
    removed = asdict(clip)
    undo: list[dict] = []
    if track.kind == "video" and idx == 0 and len(track.clips) > 1:
        # The new first clip cannot keep an incoming transition, so it becomes a plain cut.
        # Middle removals keep the neighbours' transitions: reflow recomputes their positions.
        succ = track.clips[1]
        undo.append({"op": "set_transition", "args": {
            "clip_id": succ.id, "kind": succ.transition, "frames": succ.transition_frames}})
        succ.transition, succ.transition_frames = "cut", 0
    track.clips.pop(idx)
    _commit(tl, touched_video=track.kind == "video")
    undo.insert(0, {"op": "add_clip", "args": {"track": track.name, "clip": removed, "index": idx}})
    return tl, undo


_OPS = {
    "move_clip": _op_move_clip,
    "set_duration": _op_set_duration,
    "set_transition": _op_set_transition,
    "add_clip": _op_add_clip,
    "remove_clip": _op_remove_clip,
}


def apply_op(tl: T.Timeline, op: str, args: dict) -> tuple[T.Timeline, dict]:
    """Apply one operation to a copy of tl. Returns (new_timeline, record)."""
    if op not in _OPS:
        raise EditError(f"unknown operation {op!r}; expected one of {', '.join(_OPS)}")
    work = copy.deepcopy(tl)
    new_tl, undo = _OPS[op](work, dict(args))
    return new_tl, {"op": op, "args": dict(args), "undo": undo}


def undo(tl: T.Timeline, record: dict) -> T.Timeline:
    """Reverse a record. The timeline passed in should be the result of that record."""
    current = tl
    for step in record["undo"]:
        current, _ = apply_op(current, step["op"], step["args"])
    return current


def replay(tl: T.Timeline, records: list[dict]) -> T.Timeline:
    """Re-apply a sequence of records to a timeline (for example, reloading an edit log)."""
    current = tl
    for rec in records:
        current, _ = apply_op(current, rec["op"], rec["args"])
    return current


# ---------------------------------------------------------------------------
# Scene boundaries
# ---------------------------------------------------------------------------

def validate_scene_boundaries(tl: T.Timeline, scene_starts: list[int]) -> list[str]:
    """Each scene must begin exactly where a video clip begins (a cut or a transition point)."""
    track = next((t for t in tl.tracks if t.kind == "video"), None)
    if track is None:
        raise EditError("timeline has no video track")
    starts = {c.start for c in track.clips}
    problems = []
    for frame in scene_starts:
        if frame not in starts:
            problems.append(f"scene starts at frame {frame}, which is not the start of any video clip")
    if scene_starts != sorted(scene_starts):
        problems.append("scene starts are not in ascending order")
    return problems
