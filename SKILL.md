# universal-video-skills (index)

Skills implemented so far. Each skill has its own `SKILL.md` under `skills/`.

| Skill | Status | Entry point |
|---|---|---|
| `professional-caption-design` | Implemented, tested | `skills/professional-caption-design/SKILL.md` |
| `video-quality-assurance` | Implemented, tested | `skills/video-quality-assurance/SKILL.md` |

Other skills from the master prompt (timeline editing, motion design, color/audio, maps, charts,
media selection, style system, decision engine) are **not implemented**. Their status is in
`architecture/capability-matrix.md`. They have no SKILL.md on purpose, because a description
without working code does not count as a skill here.

Render pipeline: `uvs/render.py` (`python3 -m uvs.render --out out/demo`).
