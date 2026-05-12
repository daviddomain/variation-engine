import numpy as np

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
    amount: float,
) -> np.ndarray:
    """Blend a small lowpass or high-frequency emphasis into the signal."""
    if audio.shape[0] == 0 or amount == 0.0:
        return audio.copy()

    lowpassed = _one_pole_lowpass(audio, coefficient=0.18)
    if amount < 0.0:
        wet = min(abs(amount), 1.0) * 0.6
        transformed = (1.0 - wet) * audio + wet * lowpassed
    else:
        high_frequency_detail = audio - lowpassed
        transformed = audio + high_frequency_detail * min(amount, 1.0) * 0.7

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
) -> np.ndarray:
    """Apply the first musical DSP chain for plucked-string round robins."""
    transformed = apply_micropitch(audio, cents=instruction.micropitch_cents)
    transformed = apply_attack_envelope(
        transformed,
        sample_rate=sample_rate,
        amount=instruction.attack_amount,
    )
    transformed = apply_brightness(transformed, amount=instruction.brightness_amount)
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


def _one_pole_lowpass(audio: np.ndarray, *, coefficient: float) -> np.ndarray:
    lowpassed = np.empty_like(audio, dtype=np.float64)
    lowpassed[0] = audio[0]
    for index in range(1, audio.shape[0]):
        lowpassed[index] = (
            coefficient * audio[index] + (1.0 - coefficient) * lowpassed[index - 1]
        )

    return lowpassed
