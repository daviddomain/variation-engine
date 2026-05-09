# AGENTS.md

## Project

This project is an experimental audio sample variation engine.

Goal:
Create subtle musical variations of one input sample, including round-robin variations and velocity layers.

Pipeline:
Sample → Analysis → Instrument Type → Variation Rules → DSP Chain → Optional AI Enhancement → Export

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

## Validation

After changes, run:

```bash
uv run python --version
uv run python -c "import librosa, soundfile, pedalboard, audiomentations, numpy, scipy; print('ok')"
```

## Current MVP Direction

First milestone:
Create a CLI script that analyzes one WAV sample and prints basic properties:

- sample rate
- duration
- channels
- peak level
- RMS
- estimated brightness / spectral centroid
- onset count
