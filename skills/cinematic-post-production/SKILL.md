# cinematic-post-production

Status: **partial**. Named looks, intensity scaling, and a LUT path are implemented and measured on decoded pixels.
Audio mix, sidechain ducking, and two-pass loudness are implemented and measured. Skin-tone protection,
shot matching, and noise repair beyond `afftdn` are not.

## Colour (`uvs/grade.py`)
- Looks (10): `clean_documentary`, `natural_daylight`, `warm_lifestyle`, `moody_cinematic`, `dark_investigative`,
  `desaturated_emotional`, `bright_educational`, `modern_commercial`, `retro_film`, `soft_romantic`.
- Each look sets eq (brightness, contrast, saturation, gamma), colorbalance for lift (shadows), gamma (midtones),
  and gain (highlights), and optional vignette and grain.
- Intensity: `subtle` (0.5), `standard` (1.0), `cinematic` (1.3), `dynamic` (1.55). Deviations are multiplied and clamped.
- LUT: `lut_filter("grade.cube")` (3D LUT, tetrahedral interpolation). Paths with `:`, quotes, or commas are refused.

```python
from uvs import grade as G
G.grade("in.mp4", "out.mp4", G.look_filter("warm_lifestyle", "cinematic"))
```

## Audio (`uvs/audio.py`)
- Categories and default gains: VOICE 0 dB, MUSIC -14 dB, SFX -6 dB, AMBIENCE -22 dB.
- VOICE: high-pass 80 Hz, optional `afftdn` noise reduction (opt-in), compression.
- MUSIC ducks under VOICE with `sidechaincompress` (threshold 0.02, ratio 6, attack 15 ms, release 350 ms). Per clip, can be disabled.
- Output: two-pass `loudnorm` to the target (default -14 LUFS, true peak -1.5 dBTP), then `alimiter` (about -1 dBTP).
- Output is AAC, 48 kHz stereo.

```python
from uvs import audio as A
A.mix_to_file([A.AudioClip("VOICE", "voice.wav"), A.AudioClip("MUSIC", "music.wav")],
              "out/mix.m4a", target_lufs=-14, true_peak=-1.5, duration=30)
```

## Constraints
- Looks are original parameter sets. They are not calibrated against any commercial grade.
- `afftdn` is a generic spectral denoiser. It is not a speech-enhancement model.
- Loudness is measured over the whole mix. Per-scene loudness targets are not implemented.
- Per-scene colour automation is not implemented. The pipeline applies one look to the whole timeline.

## Tests
`tests/render/test_grade.py` (9 tests, measured patches and a LUT channel swap), `tests/render/test_audio.py`
(9 tests: ducking drops music by more than 4 dB under voice, mix hits -14 LUFS within 1 LU, true peak under -1 dBTP,
SFX timing, graph structure).
