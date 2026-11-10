# universal-video-skills (index)

Skills implemented so far. Each has a SKILL.md under `skills/`. Partial skills list what is missing.

| Skill | Status | Entry point |
|---|---|---|
| `ai-director` | Partial (rule-based) | `skills/ai-director/SKILL.md` |
| `professional-caption-design` | Done (tested) | `skills/professional-caption-design/SKILL.md` |
| `professional-timeline-editing` | Partial | `skills/professional-timeline-editing/SKILL.md` |
| `advanced-motion-design` | Partial (easing, keyframes) | `skills/advanced-motion-design/SKILL.md` |
| `cinematic-post-production` | Partial (colour, audio) | `skills/cinematic-post-production/SKILL.md` |
| `data-visual-storytelling` | Partial (bar chart) | `skills/data-visual-storytelling/SKILL.md` |
| `semantic-media-selection` | Partial (index, duplicates, ranking) | `skills/semantic-media-selection/SKILL.md` |
| `video-quality-assurance` | Partial (technical and audio QA) | `skills/video-quality-assurance/SKILL.md` |

Not implemented, so there is no SKILL.md: maps and animated routes (`cinematic-map-animation`), emotional sound design
beyond music levels and SFX placement, the video style system beyond looks, and a separate decision engine
(the decision record lives in the director).

Pipeline: `python3 -m uvs.pipeline examples/demo_pipeline/spec.json out/pipeline_demo`.
Status of every feature: `architecture/capability-matrix.md`.
