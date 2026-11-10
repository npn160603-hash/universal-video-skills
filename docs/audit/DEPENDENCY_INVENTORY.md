# Dependency inventory (Phase 0 audit)

Measured in the sandbox on 2026-11-11. Hardware: 2 vCPU, 8 GB RAM.

## Runtime

| Dependency | Version tested | Used by | Required? | Notes |
|---|---|---|---|---|
| Python | 3.13.18 | all modules | yes | Code uses `X \| None` annotations, so 3.10+ is needed. 3.10–3.12 not tested. |
| Standard library | — | all modules | yes | argparse, json, subprocess, wave, array, hashlib, fractions, unicodedata, tempfile, dataclasses |
| Pillow | 12.3.0 | `captions` (text measurement), `charts`, `media_index` (dHash, image metrics) | yes | `requirements.txt` says `>=10.1`. Only 12.3.0 was tested. |
| ffmpeg | 6.1.1-3ubuntu5 | timeline, grade, render, audio, QA, pipeline | yes | Not pinned. Filters and encoders listed below. |
| ffprobe | ships with ffmpeg 6.1.1 | QA, media index | yes | — |
| fontconfig (`fc-match`) | system package | `captions.resolve_font_file` | yes on Linux | Font lookup falls back when missing (see TECHNICAL_DEBT D-07). |
| Inter font | Inter-Regular.otf, Inter-Bold.otf | captions, charts | yes for demo output | Resolved via fc-match. |

### ffmpeg features confirmed present
- Encoders: `libx264`, `libx265` (not used by any code path), `aac`, `libopus` (not used).
- Filters used by the code: `xfade`, `ass`, `blackdetect`, `freezedetect`, `silencedetect`, `volumedetect`, `ebur128`, `sidechaincompress`, `loudnorm`, `alimiter`, `lut3d`, `gradients`, `eq`, `colorbalance`, `vignette`, `noise`, `adelay`, `amix`, `signalstats`.
- Filters present but unused: `afftdn`.

## Test-only

| Dependency | Version tested | Used by | Notes |
|---|---|---|---|
| jsonschema | 4.26.0 | `tests/unit/test_schemas.py` | `requirements.txt` says `>=4.18`. |
| unittest | stdlib | all tests | Run with `python3 -m unittest discover -s tests -t .` |

## Installed but unused

| Package | Version | Status |
|---|---|---|
| numpy | 2.5.3 | Not imported by `uvs/` or `tests/`. Not in requirements. Can be ignored. |
| pytest | 9.1.1 | Not used. Tests use unittest. |

## Other tools present

| Tool | Version | Notes |
|---|---|---|
| Node.js | 22.23.4 | Not used by this project. |
| git | 2.43.0 | Used. Push works through the sandbox's git proxy. |
| gh | 2.89.0 | **Not authenticated.** `gh auth status` reports that the GH_TOKEN token failed to log in. Do not rely on `gh` for pushes. |

## Gaps in `requirements.txt`
- ffmpeg/ffprobe are not listed (they are an external binary).
- No upper bounds. No lock file.
- Neither the Python version nor the ffmpeg version is pinned.
