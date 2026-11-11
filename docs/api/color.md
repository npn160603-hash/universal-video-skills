# Colour, compositing and VFX (Phase 9) — public interface

Status: PARTIAL. Primitives, shot matching, 20 looks, compositing builders, colour QA.

## Primitives (`uvs.color`)
- `ColorAdjust(exposure, contrast, saturation, gamma, temperature, tint, lift, gamma_rgb, gain).to_filter()`.
- `curves_filter(points, channel)`.
- Looks: `uvs.grade.look_filter(name, intensity)`; `uvs.grade.LOOKS` has 20 (10 original + 10 spec-named). `uvs.grade.lut_filter(path)` for a .cube LUT (none bundled).

## Analysis and shot matching
- `analyze_frame(path, t) -> ColorStats(mean_rgb, luma, contrast, saturation, warmth, shadow_crush, highlight_clip)`; `analyze_array(img)`; `decode_frame(path, t)`.
- `match_shots(reference, target, strength) -> MatchResult`; `.apply_to_array(img)`, `.to_filter()`. `match_distance(a, b)`.

## Colour QA
- `color_qa(stats, max_saturation, max_crush, max_clip) -> ColorQA(stats, issues)`.

## Compositing builders
- `chroma_key`, `gaussian_blur`, `glow` (filter_complex fragment → [glow]), `vignette`, `film_grain`, `unsharp`, `light_leak`, `alpha_over`. `BLEND_MODES` lists supported modes.

## Limits
- Shot matching corrects mean colour, not full histogram/contrast.
- No keyframed mask compositor or motion-trail helper; no bundled LUT.
