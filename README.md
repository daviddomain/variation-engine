# variation-engine

Experimental audio sample variation engine.

The long-term goal is to turn one input sample into subtle musical variations, such as round-robin alternates and velocity layers. The intended pipeline is:

```txt
Sample -> Analysis -> Instrument Type -> Variation Rules -> DSP Chain -> Optional AI Enhancement -> Export
```

## Current Phase 1 Status

Phase 1 is an audio analysis lab. It focuses on analyzing one input sample and returning a structured JSON result that future variation rules can use.

The project does not currently generate samples, execute variation rules, provide a UI, or integrate with plugins, VSTs, or DAWs. The current CLI only analyzes audio and prints analysis data.

The analyzer currently returns these top-level JSON sections:

```txt
file
amplitude
transient
pitch
timbre
profile
```

The analysis is intentionally practical rather than academically perfect. Its job is to collect enough information for later musical decisions, such as how much pitch, attack, timbre, or space variation may be safe for a sample.

## Setup

Use Python with `uv`.

```bash
uv sync
```

## Analyze a Sample

Run the analyzer with:

```bash
uv run python main.py analyze path/to/sample.wav
```

Supported input depends on the audio formats available through `soundfile`, such as WAV, AIFF, and FLAC.

The command prints formatted JSON to stdout. On unreadable or missing files, it prints an error to stderr and exits with a non-zero status.

## Example JSON Output

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

## Analysis Sections

`file` contains basic audio file metadata: path, sample rate, channel count, duration, and sample count.

`amplitude` contains whole-file level metrics. Peak amplitude and RMS provide simple loudness proxies, crest factor describes the relationship between peak and RMS level, and leading/trailing silence estimate silent regions at the start and end of the file.

`transient` describes onset and attack behavior. It includes the estimated onset time, attack duration, transient strength, and a confidence value for the transient estimate.

`pitch` contains an estimated fundamental frequency, MIDI note, note name, confidence, pitch stability, and a boolean indicating whether the sample is probably pitched. Pitch fields can be `null` when the analyzer does not have enough confidence.

`timbre` contains spectral descriptors used for later tone and texture decisions, including centroid, bandwidth, rolloff, flatness, and mean spectral contrast.

`profile` is a conservative, rule-based internal profile suggestion derived from the existing analysis metrics. It is not full instrument recognition. It currently helps identify broad behavior such as percussive, tonal-percussive, sustained tonal, sound-effect texture, or unknown.

## Instrument Category Schema

The current instrument category schema lives in:

```txt
variation_engine/analysis/categories.py
```

These categories are intended for future user-facing selection and later mapping to variation rules:

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

The labels are:

| ID | Label |
| --- | --- |
| `piano_keys` | Piano / Keys |
| `plucked_string` | Plucked String |
| `bowed_string` | Bowed String |
| `guitar_bass` | Guitar / Bass |
| `drum_percussion` | Drum / Percussion |
| `synth_lead` | Synth Lead |
| `synth_pad` | Synth Pad |
| `vocal_voice` | Vocal / Voice |
| `fx_foley_texture` | FX / Foley / Texture |
| `unknown_auto` | Unknown / Auto |

Hornbostel-Sachs is used only as an optional internal hint for future rule-system design. It is not the main user-facing category system.

`FX / Foley / Texture` is a first-class category because sound-design material does not fit cleanly into traditional instrument taxonomies.

`Unknown / Auto` is a valid category for cases where the user does not choose a specific source or where the analyzer should remain conservative.

This schema does not yet execute variation logic. It only defines stable IDs, labels, default internal profiles, optional internal hints, and future variation-permission flags.

## Validation

Useful local checks:

```bash
uv run python --version
uv run python -c "import librosa, soundfile, pedalboard, audiomentations, numpy, scipy; print('ok')"
uv run python -m unittest discover -s tests -p "test_*.py"
```
