import numpy as np

from variation_engine.analysis.models import TransientMetrics


DEFAULT_NOISE_FLOOR_PERCENTILE = 10
ONSET_THRESHOLD_RATIO = 0.1
ATTACK_TARGET_RATIO = 0.9


def calculate_transient_metrics(audio: np.ndarray, sample_rate: int) -> TransientMetrics:
    """Estimate onset and attack characteristics from an audio buffer."""
    envelope = _amplitude_envelope(audio)
    if envelope.size == 0 or sample_rate <= 0:
        return _empty_metrics()

    peak = float(np.max(envelope))
    if peak <= 0:
        return _empty_metrics()

    noise_floor = float(np.percentile(envelope, DEFAULT_NOISE_FLOOR_PERCENTILE))
    dynamic_range = max(0.0, peak - noise_floor)
    if dynamic_range <= 0:
        return _empty_metrics()

    onset_threshold = noise_floor + dynamic_range * ONSET_THRESHOLD_RATIO
    attack_target = noise_floor + dynamic_range * ATTACK_TARGET_RATIO

    onset_sample = _first_index_at_or_above(envelope, onset_threshold, start=0)
    attack_sample = _first_index_at_or_above(envelope, attack_target, start=onset_sample)
    if attack_sample < onset_sample:
        attack_sample = onset_sample

    onset_time_ms = onset_sample * 1000.0 / sample_rate
    attack_duration_ms = (attack_sample - onset_sample) * 1000.0 / sample_rate

    attack_speed = 1.0 / (1.0 + attack_duration_ms / 30.0)
    crest_score = _crest_score(envelope)
    transient_strength = _clamp01((attack_speed * 0.65) + (crest_score * 0.35))

    contrast = dynamic_range / peak
    confidence = _clamp01((contrast * 0.5) + (attack_speed * 0.3) + (transient_strength * 0.2))

    return TransientMetrics(
        onset_time_ms=round(onset_time_ms, 3),
        attack_duration_ms=round(attack_duration_ms, 3),
        transient_strength=round(transient_strength, 6),
        transient_confidence=round(confidence, 6),
    )


def _amplitude_envelope(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.abs(audio.astype(np.float64))

    if audio.ndim == 2:
        return np.max(np.abs(audio.astype(np.float64)), axis=1)

    return np.array([], dtype=np.float64)


def _first_index_at_or_above(values: np.ndarray, threshold: float, start: int) -> int:
    indices = np.flatnonzero(values[start:] >= threshold)
    if indices.size == 0:
        return int(values.size - 1)

    return int(start + indices[0])


def _crest_score(envelope: np.ndarray) -> float:
    mean_level = float(np.mean(envelope))
    if mean_level <= 0:
        return 0.0

    crest = float(np.max(envelope)) / mean_level
    return _clamp01((crest - 1.0) / 9.0)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _empty_metrics() -> TransientMetrics:
    return TransientMetrics(
        onset_time_ms=0.0,
        attack_duration_ms=0.0,
        transient_strength=0.0,
        transient_confidence=0.0,
    )
