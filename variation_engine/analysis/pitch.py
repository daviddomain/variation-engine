import librosa
import numpy as np

from variation_engine.analysis.models import PitchMetrics


MIN_PITCH_CONFIDENCE = 0.45
MIN_PITCH_STABILITY = 0.35
MIN_VOICED_RATIO = 0.25


def calculate_pitch_metrics(audio: np.ndarray, sample_rate: int) -> PitchMetrics:
    """Estimate fundamental pitch and confidence for tonal samples."""
    mono_audio = _to_mono(audio)
    if mono_audio.size == 0 or sample_rate <= 0 or not np.any(mono_audio):
        return _empty_metrics()

    fmin = float(librosa.note_to_hz("C1"))
    fmax = min(float(librosa.note_to_hz("C7")), sample_rate * 0.45)
    if fmax <= fmin:
        return _empty_metrics()

    try:
        f0_values, voiced_flags, voiced_probabilities = librosa.pyin(
            mono_audio,
            fmin=fmin,
            fmax=fmax,
            sr=sample_rate,
        )
    except (librosa.util.exceptions.ParameterError, ValueError):
        return _empty_metrics()

    voiced_f0 = f0_values[voiced_flags & np.isfinite(f0_values)]
    if voiced_f0.size == 0:
        return _empty_metrics()

    voiced_ratio = float(np.mean(voiced_flags))
    voiced_probabilities = voiced_probabilities[voiced_flags]
    mean_voiced_probability = (
        float(np.mean(voiced_probabilities)) if voiced_probabilities.size else 0.0
    )
    stability = _pitch_stability(voiced_f0)
    confidence = _clamp01(
        (mean_voiced_probability * 0.55) + (voiced_ratio * 0.25) + (stability * 0.2)
    )

    is_probably_pitched = (
        confidence >= MIN_PITCH_CONFIDENCE
        and stability >= MIN_PITCH_STABILITY
        and voiced_ratio >= MIN_VOICED_RATIO
    )

    if not is_probably_pitched:
        return PitchMetrics(
            estimated_f0_hz=None,
            estimated_midi_note=None,
            estimated_note_name=None,
            pitch_confidence=round(confidence, 6),
            is_probably_pitched=False,
            pitch_stability=round(stability, 6),
        )

    estimated_f0 = float(np.median(voiced_f0))
    midi_note = int(round(float(librosa.hz_to_midi(estimated_f0))))
    return PitchMetrics(
        estimated_f0_hz=round(estimated_f0, 3),
        estimated_midi_note=midi_note,
        estimated_note_name=_midi_note_name(midi_note),
        pitch_confidence=round(confidence, 6),
        is_probably_pitched=True,
        pitch_stability=round(stability, 6),
    )


def _to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float64)

    if audio.ndim == 2:
        return np.mean(audio.astype(np.float64), axis=1)

    return np.array([], dtype=np.float64)


def _pitch_stability(f0_values: np.ndarray) -> float:
    if f0_values.size == 0:
        return 0.0

    median_f0 = float(np.median(f0_values))
    if median_f0 <= 0:
        return 0.0

    cents_from_median = 1200.0 * np.log2(f0_values / median_f0)
    cents_std = float(np.std(cents_from_median))
    return _clamp01(1.0 / (1.0 + cents_std / 50.0))


def _midi_note_name(midi_note: int) -> str:
    note_names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    octave = (midi_note // 12) - 1
    return f"{note_names[midi_note % 12]}{octave}"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _empty_metrics() -> PitchMetrics:
    return PitchMetrics(
        estimated_f0_hz=None,
        estimated_midi_note=None,
        estimated_note_name=None,
        pitch_confidence=0.0,
        is_probably_pitched=False,
        pitch_stability=0.0,
    )
