# AGENTS.md

## Project

This project is an experimental audio sample variation engine.

Goal:
Create subtle musical variations of one input sample, including round-robin variations and velocity layers.

Pipeline:
Sample → Analysis → Instrument Type → Variation Rules → DSP Chain → Optional AI Enhancement → Export

## Project Context

Before working on Phase 1 analysis tasks, read the project context documents in:

```txt
docs/phase-1/audio-labor.md
docs/phase-1/sample-variation-processes.md
```

These documents describe the intended direction of the project, especially:

- why Phase 1 focuses on an audio analysis lab before any VST/plugin work
- why the variation engine is the core value of the project
- how one input sample should later become multiple round-robin and velocity-layer variations
- which variation processes are relevant later, such as micropitch, attack, timbre, velocity, modulation and space
- why instrument-aware processing matters for future variation rules

Do not ignore these documents when implementing analysis-related tasks.

## Environment

Use Python with uv.

Setup:

```bash
uv sync
```

Run scripts with:

```bash
uv run python <script>
```

Do not commit `.venv/`.

## Dependencies

Main libraries:

- librosa: audio analysis
- soundfile: audio file IO
- numpy/scipy: signal processing
- pedalboard: musical DSP effects
- audiomentations: audio transformations

## Code Style

- Keep changes small and focused.
- Prefer simple readable Python over clever abstractions.
- Do not introduce AI/ML models unless explicitly requested.
- Start with deterministic DSP-based processing.
- Keep generated audio files out of git.
- Prefer explicit, testable analysis functions over hidden side effects.
- Keep CLI output deterministic and machine-readable where possible.

## Validation

After changes, run:

```bash
uv run python --version
uv run python -c "import librosa, soundfile, pedalboard, audiomentations, numpy, scipy; print('ok')"
```

If tests are added later, also run the relevant test command before finishing a task.

## Current MVP Direction

First milestone:
Create a Phase 1 audio analysis CLI that analyzes one input sample and prints a structured JSON result.

The analysis should start simple and grow incrementally.

Initial analysis areas:

- file metadata
- sample rate
- duration
- channels
- sample count
- peak level
- RMS
- crest factor
- leading silence
- trailing silence
- onset / transient information
- attack characteristics
- estimated brightness / spectral centroid
- basic spectral/timbre descriptors
- pitch estimate where applicable
- pitch confidence
- rough instrument/profile hints

The goal of the analysis is not perfect academic classification.

The goal is to collect enough useful information so that future variation rules can make musical decisions, for example:

- how much pitch variation is safe
- how much attack variation is safe
- whether the sample is probably tonal or noisy
- whether it behaves more like percussion, a sustained tone, a plucked tone, a texture or an unknown sound

## Instrument Classification Direction

Use Hornbostel-Sachs only as an internal classification and rule-system inspiration.

Do not expose Hornbostel-Sachs directly as the main user-facing category system.

Future user-facing categories should stay musically understandable, for example:

- Piano / Keys
- Plucked String
- Bowed String
- Guitar / Bass
- Drum / Percussion
- Synth Lead
- Synth Pad
- Vocal / Voice
- FX / Foley / Texture
- Unknown / Auto

The internal system may later map these categories to analysis profiles and variation rules.

Important:
FX / Foley / Texture must be treated as a first-class category even though it does not fit cleanly into Hornbostel-Sachs.

## Scope Control

When implementing GitHub issues:

- Work on one issue at a time.
- Do not jump ahead into sample generation unless the issue explicitly asks for it.
- Do not add plugin, VST, GUI or DAW integration code during Phase 1.
- Do not introduce machine learning classification unless explicitly requested.
- Keep analysis code reusable for later variation generation.
- Prefer small pull requests with clear acceptance criteria.
