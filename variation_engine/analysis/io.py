from pathlib import Path

import numpy as np
import soundfile as sf

from variation_engine.analysis.models import AnalysisResult, AmplitudeMetrics, FileMetadata
from variation_engine.analysis.pitch import calculate_pitch_metrics
from variation_engine.analysis.profile import suggest_profile
from variation_engine.analysis.timbre import calculate_timbre_metrics
from variation_engine.analysis.transient import calculate_transient_metrics


class AudioMetadataError(ValueError):
    """Raised when an audio file cannot be read for analysis."""


SILENCE_THRESHOLD = 1e-4


def calculate_amplitude_metrics(
    audio: np.ndarray,
    sample_rate: int,
    silence_threshold: float = SILENCE_THRESHOLD,
) -> AmplitudeMetrics:
    """Calculate whole-file amplitude metrics.

    Peak and RMS use all sample/channel values. Silence detection uses a
    channel-merged reference where a frame is audible if any channel exceeds
    the deterministic threshold.
    """
    peak_amplitude = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    crest_factor = peak_amplitude / rms if rms > 0 else 0.0

    if audio.ndim == 1:
        silence_reference = np.abs(audio)
    else:
        silence_reference = np.max(np.abs(audio), axis=1)

    audible_indices = np.flatnonzero(silence_reference > silence_threshold)
    if audible_indices.size == 0:
        leading_silence_samples = audio.shape[0]
        trailing_silence_samples = audio.shape[0]
    else:
        leading_silence_samples = int(audible_indices[0])
        trailing_silence_samples = int(audio.shape[0] - audible_indices[-1] - 1)

    milliseconds_per_sample = 1000.0 / sample_rate
    return AmplitudeMetrics(
        peak_amplitude=round(peak_amplitude, 6),
        rms=round(rms, 6),
        crest_factor=round(crest_factor, 6),
        leading_silence_ms=round(leading_silence_samples * milliseconds_per_sample, 3),
        trailing_silence_ms=round(trailing_silence_samples * milliseconds_per_sample, 3),
    )


def analyze_audio_file(path: str | Path) -> AnalysisResult:
    input_path = Path(path)

    if not input_path.exists():
        raise AudioMetadataError(f"Audio file does not exist: {input_path}")

    if not input_path.is_file():
        raise AudioMetadataError(f"Audio path is not a file: {input_path}")

    try:
        info = sf.info(input_path)
        audio, sample_rate = sf.read(input_path, always_2d=True)
    except (RuntimeError, OSError) as exc:
        raise AudioMetadataError(f"Unsupported or unreadable audio file: {input_path}") from exc

    metadata = FileMetadata(
        path=str(path),
        sample_rate=info.samplerate,
        channels=info.channels,
        duration_seconds=round(info.duration, 3),
        sample_count=info.frames,
    )
    amplitude = calculate_amplitude_metrics(audio, sample_rate)
    transient = calculate_transient_metrics(audio, sample_rate)
    pitch = calculate_pitch_metrics(audio, sample_rate)
    timbre = calculate_timbre_metrics(audio, sample_rate)
    profile = suggest_profile(metadata, amplitude, transient, pitch, timbre)
    return AnalysisResult(
        file=metadata,
        amplitude=amplitude,
        transient=transient,
        pitch=pitch,
        timbre=timbre,
        profile=profile,
    )
