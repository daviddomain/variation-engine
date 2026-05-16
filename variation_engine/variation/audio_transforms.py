import numpy as np

from variation_engine.analysis.models import AnalysisResult
from variation_engine.variation.render_recipes import RoundRobinRenderInstruction


PLUCKED_STRING_RECIPE_ID = "plucked_string"


def apply_micropitch(
    audio: np.ndarray,
    *,
    cents: float,
) -> np.ndarray:
    """Apply a subtle deterministic pitch shift while preserving buffer shape."""
    if audio.shape[0] == 0 or cents == 0.0:
        return audio.copy()

    pitch_factor = 2 ** (cents / 1200.0)
    source_positions = np.arange(audio.shape[0], dtype=np.float64) * pitch_factor
    sample_positions = np.arange(audio.shape[0], dtype=np.float64)
    shifted = np.empty_like(audio, dtype=np.float64)

    for channel_index in range(audio.shape[1]):
        shifted[:, channel_index] = np.interp(
            source_positions,
            sample_positions,
            audio[:, channel_index],
            left=0.0,
            right=0.0,
        )

    return shifted.astype(audio.dtype, copy=False)


def apply_attack_envelope(
    audio: np.ndarray,
    *,
    sample_rate: int,
    amount: float,
) -> np.ndarray:
    """Subtly soften or emphasize the first few milliseconds."""
    if audio.shape[0] == 0 or amount == 0.0:
        return audio.copy()

    window_length = min(audio.shape[0], max(1, int(round(sample_rate * 0.006))))
    envelope = np.ones(audio.shape[0], dtype=np.float64)
    envelope[:window_length] = np.linspace(1.0 + amount, 1.0, window_length)
    return (audio * envelope[:, np.newaxis]).astype(audio.dtype, copy=False)


def apply_brightness(
    audio: np.ndarray,
    *,
    sample_rate: int,
    amount: float,
    estimated_f0_hz: float | None = None,
    spectral_centroid: float | None = None,
    spectral_bandwidth: float | None = None,
    spectral_rolloff: float | None = None,
) -> np.ndarray:
    """Shape plucked-string brightness around the analyzed presence region."""
    if audio.shape[0] == 0 or amount == 0.0:
        return audio.copy()

    shaping = _brightness_shaping_parameters(
        sample_rate=sample_rate,
        estimated_f0_hz=estimated_f0_hz,
        spectral_centroid=spectral_centroid,
        spectral_bandwidth=spectral_bandwidth,
        spectral_rolloff=spectral_rolloff,
    )
    frequencies = np.fft.rfftfreq(audio.shape[0], d=1.0 / sample_rate)
    presence_offset = (frequencies - shaping["presence_center"]) / shaping["presence_width"]
    presence = np.exp(-0.5 * presence_offset**2)
    detail = _smooth_high_shelf(
        frequencies,
        anchor=shaping["detail_anchor"],
        width=shaping["detail_width"],
    )

    clamped_amount = max(-1.0, min(1.0, amount))
    if clamped_amount < 0.0:
        gain_db = clamped_amount * (7.0 * presence + 3.0 * detail)
    else:
        gain_db = clamped_amount * (8.0 * presence + 2.5 * detail)

    gain = (10.0 ** (gain_db / 20.0)).reshape(-1, 1)
    spectrum = np.fft.rfft(audio.astype(np.float64, copy=False), axis=0)
    transformed = np.fft.irfft(spectrum * gain, n=audio.shape[0], axis=0)

    return transformed.astype(audio.dtype, copy=False)


def apply_decay_envelope(
    audio: np.ndarray,
    *,
    sample_rate: int,
    amount: float,
) -> np.ndarray:
    """Subtly change the body and tail without cutting the sample."""
    if audio.shape[0] == 0 or amount == 0.0:
        return audio.copy()

    start = min(audio.shape[0], max(1, int(round(sample_rate * 0.012))))
    envelope = np.ones(audio.shape[0], dtype=np.float64)
    if start < audio.shape[0]:
        envelope[start:] = np.linspace(1.0, 1.0 + amount, audio.shape[0] - start)

    return (audio * envelope[:, np.newaxis]).astype(audio.dtype, copy=False)


def apply_stereo_balance(
    audio: np.ndarray,
    *,
    amount: float,
) -> np.ndarray:
    """Apply a very small left/right balance variation for stereo-like inputs."""
    if audio.shape[0] == 0 or audio.shape[1] < 2 or amount == 0.0:
        return audio.copy()

    balanced = audio.copy()
    left_gain = 1.0 + amount
    right_gain = 1.0 - amount
    balanced[:, 0] *= left_gain
    balanced[:, 1] *= right_gain
    return balanced


def apply_plucked_string_transforms(
    audio: np.ndarray,
    *,
    sample_rate: int,
    instruction: RoundRobinRenderInstruction,
    analysis: AnalysisResult | None = None,
) -> np.ndarray:
    """Apply the first musical DSP chain for plucked-string round robins."""
    transformed = apply_micropitch(audio, cents=instruction.micropitch_cents)
    transformed = apply_attack_envelope(
        transformed,
        sample_rate=sample_rate,
        amount=instruction.attack_amount,
    )
    transformed = apply_brightness(
        transformed,
        sample_rate=sample_rate,
        amount=instruction.brightness_amount,
        estimated_f0_hz=analysis.pitch.estimated_f0_hz if analysis is not None else None,
        spectral_centroid=analysis.timbre.spectral_centroid if analysis is not None else None,
        spectral_bandwidth=analysis.timbre.spectral_bandwidth if analysis is not None else None,
        spectral_rolloff=analysis.timbre.spectral_rolloff if analysis is not None else None,
    )
    transformed = apply_decay_envelope(
        transformed,
        sample_rate=sample_rate,
        amount=instruction.decay_amount,
    )
    return apply_stereo_balance(
        transformed,
        amount=instruction.stereo_balance_amount,
    )


def limit_peak(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        return audio / peak

    return audio


def _brightness_shaping_parameters(
    *,
    sample_rate: int,
    estimated_f0_hz: float | None,
    spectral_centroid: float | None,
    spectral_bandwidth: float | None,
    spectral_rolloff: float | None,
) -> dict[str, float]:
    nyquist = max(float(sample_rate) / 2.0, 1.0)
    fallback_centroid = min(1200.0, nyquist * 0.45)
    centroid = _valid_frequency(
        spectral_centroid,
        fallback=fallback_centroid,
        nyquist=nyquist,
    )
    bandwidth = _valid_frequency(
        spectral_bandwidth,
        fallback=max(centroid * 0.75, 200.0),
        nyquist=nyquist,
    )
    rolloff = _valid_frequency(
        spectral_rolloff,
        fallback=centroid + bandwidth * 0.65,
        nyquist=nyquist,
    )
    f0 = _valid_optional_frequency(estimated_f0_hz, nyquist=nyquist)

    lower_anchor = f0 * 3.0 if f0 > 0.0 else centroid * 0.45
    safe_low = min(max(lower_anchor, 80.0), nyquist * 0.45)
    presence_center = _clamp(centroid * 1.6, safe_low, nyquist * 0.82)
    presence_width = _clamp(
        bandwidth * 0.75,
        max(presence_center * 0.25, 120.0),
        max(presence_center * 1.1, 180.0),
    )
    detail_anchor = _clamp(
        max(rolloff, presence_center + presence_width * 0.35),
        presence_center,
        nyquist * 0.92,
    )
    detail_width = max(presence_width * 0.5, 120.0)

    return {
        "presence_center": presence_center,
        "presence_width": presence_width,
        "detail_anchor": detail_anchor,
        "detail_width": detail_width,
    }


def _valid_frequency(value: float | None, *, fallback: float, nyquist: float) -> float:
    if value is None or not np.isfinite(value) or value <= 0.0:
        return _clamp(fallback, 1.0, nyquist)

    return _clamp(float(value), 1.0, nyquist)


def _valid_optional_frequency(value: float | None, *, nyquist: float) -> float:
    if value is None or not np.isfinite(value) or value <= 0.0:
        return 0.0

    return _clamp(float(value), 1.0, nyquist)


def _smooth_high_shelf(
    frequencies: np.ndarray,
    *,
    anchor: float,
    width: float,
) -> np.ndarray:
    exponent = np.clip(-(frequencies - anchor) / max(width, 1.0), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(exponent))


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))
