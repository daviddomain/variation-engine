import librosa
import numpy as np

from variation_engine.analysis.models import TimbreMetrics


def calculate_timbre_metrics(audio: np.ndarray, sample_rate: int) -> TimbreMetrics:
    """Calculate deterministic spectral summaries for timbre decisions."""
    mono_audio = _to_mono(audio)
    if mono_audio.size < 2 or sample_rate <= 0 or not np.any(mono_audio):
        return _empty_metrics()

    n_fft = _feature_fft_size(mono_audio)
    try:
        centroid = librosa.feature.spectral_centroid(y=mono_audio, sr=sample_rate, n_fft=n_fft)
        bandwidth = librosa.feature.spectral_bandwidth(y=mono_audio, sr=sample_rate, n_fft=n_fft)
        rolloff = librosa.feature.spectral_rolloff(y=mono_audio, sr=sample_rate, n_fft=n_fft)
        flatness = librosa.feature.spectral_flatness(y=mono_audio, n_fft=n_fft)
        contrast = _spectral_contrast(mono_audio, sample_rate, n_fft)
    except (librosa.util.exceptions.ParameterError, ValueError):
        return _empty_metrics()

    return TimbreMetrics(
        spectral_centroid=_rounded_mean(centroid, decimals=3),
        spectral_bandwidth=_rounded_mean(bandwidth, decimals=3),
        spectral_rolloff=_rounded_mean(rolloff, decimals=3),
        spectral_flatness=_rounded_mean(flatness, decimals=6),
        spectral_contrast_mean=_rounded_mean(contrast, decimals=3),
    )


def _to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float64)

    if audio.ndim == 2:
        return np.mean(audio.astype(np.float64), axis=1)

    return np.array([], dtype=np.float64)


def _feature_fft_size(audio: np.ndarray) -> int:
    return max(2, min(2048, int(audio.size)))


def _spectral_contrast(audio: np.ndarray, sample_rate: int, n_fft: int) -> np.ndarray:
    if audio.size < 32:
        return np.array([[0.0]], dtype=np.float64)

    fmin = 50.0
    nyquist = sample_rate / 2.0
    n_bands = 1
    while fmin * (2 ** (n_bands + 1)) < nyquist and n_bands < 6:
        n_bands += 1

    try:
        return librosa.feature.spectral_contrast(
            y=audio,
            sr=sample_rate,
            fmin=fmin,
            n_bands=n_bands,
            n_fft=n_fft,
        )
    except (librosa.util.exceptions.ParameterError, ValueError, IndexError):
        return np.array([[0.0]], dtype=np.float64)


def _rounded_mean(values: np.ndarray, decimals: int) -> float:
    finite_values = values[np.isfinite(values)]
    if finite_values.size == 0:
        return 0.0

    return round(float(np.mean(finite_values)), decimals)


def _empty_metrics() -> TimbreMetrics:
    return TimbreMetrics(
        spectral_centroid=0.0,
        spectral_bandwidth=0.0,
        spectral_rolloff=0.0,
        spectral_flatness=0.0,
        spectral_contrast_mean=0.0,
    )
