# variation-engine

Experimental audio sample variation engine.

The long-term goal is to turn one input sample into subtle musical variations, such as round-robin alternates and velocity layers. The intended pipeline is:

```txt
Sample -> Analysis -> Instrument Type -> Variation Rules -> DSP Chain -> Optional AI Enhancement -> Export
```

The project is still in Phase 1. It is an audio analysis and rendering lab, not a complete sampler, VST, DAW integration, or playable instrument builder.

## Current Pipeline Status

The current CLI supports three steps:

```txt
Analyze sample -> Create dry-run variation plan -> Render source-only round-robins
```

Implemented now:

- structured JSON analysis for one input sample
- dry-run variation planning as JSON
- first source-only round-robin WAV renderer
- deterministic rendering with `--seed`

Not implemented yet:

- velocity layer rendering
- pitch-mapped target-note rendering
- major-third tonal expansion rendering
- complete playable instrument export
- VST, plugin, UI, DAW, AI processing, or export metadata

## Setup

Use Python with `uv`.

```bash
uv sync
```

Useful local checks:

```bash
uv run python --version
uv run python -c "import librosa, soundfile, pedalboard, audiomentations, numpy, scipy; print('ok')"
```

## CLI Commands

The project currently exposes:

```bash
uv run python main.py analyze <path-to-sample>
uv run python main.py plan <path-to-sample>
uv run python main.py render <path-to-sample> --output generated
```

Supported input depends on the audio formats available through `soundfile`, such as WAV, AIFF, and FLAC.

## Analyze a Sample

Run:

```bash
uv run python main.py analyze path/to/sample.wav
```

The command prints formatted JSON to stdout. On unreadable or missing files, it prints an error to stderr and exits with a non-zero status.

The analyzer currently returns these top-level JSON sections:

```txt
file
amplitude
transient
pitch
timbre
profile
```

The analysis is practical rather than academically perfect. Its job is to collect enough information for later musical decisions, such as how much pitch, attack, timbre, or space variation may be safe for a sample.

## Dry-run Variation Planning

Run:

```bash
uv run python main.py plan path/to/sample.wav
```

`plan` is dry-run only. It analyzes the sample, selects a variation rule preset, calculates target notes, estimates the number of planned samples, and prints JSON to stdout.

It does not write WAV files and does not process audio.

Optional category override:

```bash
uv run python main.py plan path/to/sample.wav --category piano_keys
```

Optional source note override:

```bash
uv run python main.py plan path/to/sample.wav --category piano_keys --source-note C3
```

If no category is provided, the planner uses the analyzer's suggested internal profile. If `--category` is provided, the category's default profile is used to select the variation rule preset. If `--source-note` is provided, it overrides the detected pitch.

## Source-only Round-robin Rendering

Run:

```bash
uv run python main.py render path/to/sample.wav --output generated
```

`render` now creates WAV files, but only for source-only round-robin variants. It writes exactly eight files:

```txt
generated/
  rr_01.wav
  rr_02.wav
  rr_03.wav
  rr_04.wav
  rr_05.wav
  rr_06.wav
  rr_07.wav
  rr_08.wav
```

The first renderer is intentionally limited:

- source-only rendering
- 8 round-robin variants
- gain and timing micro-variations only
- no velocity layers
- no pitch-mapped target notes
- no major-third expansion rendering

Rendering is deterministic with `--seed`:

```bash
uv run python main.py render path/to/sample.wav --output generated --seed 11
```

The command prints a JSON render summary to stdout. For presets that plan velocity layers or pitch-mapped notes, the renderer reports warnings because those planned dimensions are skipped by the current source-only renderer.

The render summary includes `selected_render_recipe_id`, which identifies the round-robin render recipe used for deterministic variation instructions.

Optional category and source note overrides are available here too:

```bash
uv run python main.py render path/to/sample.wav --output generated --category piano_keys --source-note C3
```

These options affect preset selection and warnings, but they do not make the current renderer create velocity layers or pitch-mapped notes.

## Local Audio Lab

The Local Audio Lab is a local-only Phase 1 developer interface for audio experimentation and tuning category-specific render recipe ranges. It is not a product UI.

Start the lab with:

```bash
uv run python main.py lab
```

By default, it is available at:

```txt
http://127.0.0.1:8765
```

You can also set the host and port explicitly:

```bash
uv run python main.py lab --host 127.0.0.1 --port 8765
```

The lab scans sample folders with this layout:

```txt
samples/<category_id>/*.wav
```

Example:

```txt
samples/plucked_string/Harp.wav
```

Only `.wav` files are scanned currently.

Every render run is saved automatically under `lab_output/`, which is ignored by git:

```txt
lab_output/<category_id>/<sample-stem>_seed-<seed>_<YYYYMMDD-HHMMSS>/
  rr_01.wav
  rr_02.wav
  rr_03.wav
  rr_04.wav
  rr_05.wav
  rr_06.wav
  rr_07.wav
  rr_08.wav
  render.json
```

`render.json` contains the analysis data, parameter ranges, parameter limits, render result, and audio URLs for the run.

## Category-aware Render Recipes

The render command selects a category-aware round-robin render recipe. Render recipes define deterministic instruction ranges for source-only round-robin variation, including gain, timing, micropitch, attack, brightness, decay, saturation, and stereo balance values.

Recipe selection follows this priority:

1. Use a category-specific recipe when `--category` is provided and known.
2. Fall back to a profile-specific recipe.
3. Fall back to the conservative unknown recipe.

This allows categories such as `plucked_string`, `piano_keys`, and `drum_percussion` to define different musical variation ranges even when they share a broader analysis profile.

Currently, the renderer applies only the supported safe gain and timing transforms. Additional recipe values such as micropitch, attack, brightness, decay, saturation, and stereo balance are generated deterministically as instruction data and reserved for future DSP rendering work.

## Variation Planning Model

The variation rule preset schema lives in:

```txt
variation_engine/variation/presets.py
```

Current preset IDs:

```txt
percussive
tonal_percussive
sustained_tonal
sfx_texture
unknown
```

Each preset defines:

- round-robin count
- velocity layer count
- pitch mapping strategy
- transform ranges for micropitch, timing, attack, timbre, saturation, gain, and space

The planner can describe more than the renderer currently writes. For example, `source_only` plans one target note with 8 round-robin variants and 4 velocity layers, for 32 planned samples. The current renderer only writes the 8 source-note round-robin WAV files.

`major_thirds_around_source` is planned for future tonal expansion. With +/-2 octaves it can describe anchor notes in major-third steps around the source note, but those pitch-mapped target notes are not rendered yet.

Example for source note C3:

```txt
C1, E1, G#1,
C2, E2, G#2,
C3, E3, G#3,
C4, E4, G#4,
C5
```

## Instrument Category Schema

The current instrument category schema lives in:

```txt
variation_engine/analysis/categories.py
```

These categories are intended for user-facing selection and later mapping to variation rules:

```txt
piano_keys
plucked_string
bowed_string
guitar_bass
drum_percussion
synth_lead
synth_pad
vocal_voice
fx_foley_texture
unknown_auto
```

Hornbostel-Sachs is used only as an optional internal hint for future rule-system design. It is not the main user-facing category system.

`FX / Foley / Texture` is a first-class category because sound-design material does not fit cleanly into traditional instrument taxonomies.

## Example Analysis JSON

This is a representative output shape. The values are examples only and are not guaranteed for every sample.

```json
{
  "file": {
    "path": "samples/kick.wav",
    "sample_rate": 44100,
    "channels": 1,
    "duration_seconds": 0.842,
    "sample_count": 37132
  },
  "amplitude": {
    "peak_amplitude": 0.98,
    "rms": 0.182,
    "crest_factor": 5.38,
    "leading_silence_ms": 2.4,
    "trailing_silence_ms": 17.8
  },
  "transient": {
    "onset_time_ms": 3.1,
    "attack_duration_ms": 12.6,
    "transient_strength": 0.82,
    "transient_confidence": 0.76
  },
  "pitch": {
    "estimated_f0_hz": 110.0,
    "estimated_midi_note": 45,
    "estimated_note_name": "A2",
    "pitch_confidence": 0.81,
    "is_probably_pitched": true,
    "pitch_stability": 0.73
  },
  "timbre": {
    "spectral_centroid": 2840.5,
    "spectral_bandwidth": 1650.2,
    "spectral_rolloff": 6120.0,
    "spectral_flatness": 0.18,
    "spectral_contrast_mean": 21.4
  },
  "profile": {
    "suggested_profile": "percussive",
    "confidence": 0.74,
    "reasons": [
      "strong transient",
      "short duration",
      "low pitch confidence"
    ]
  }
}
```

## Next Planned Milestones

Likely next steps:

- broaden source-only rendering with more deterministic DSP variation types
- render velocity layers after the planner and renderer agree on the output structure
- render pitch-mapped major-third target notes for tonal presets
- add export metadata once the rendered output model is stable
- keep VST, UI, DAW integration, and AI processing out of scope until the variation engine itself is useful

## Validation

Run:

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```
