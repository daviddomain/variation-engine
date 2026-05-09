from pathlib import Path

import soundfile as sf

from variation_engine.analysis.models import AnalysisResult, FileMetadata


class AudioMetadataError(ValueError):
    """Raised when an audio file cannot be read for analysis."""


def analyze_audio_file(path: str | Path) -> AnalysisResult:
    input_path = Path(path)

    if not input_path.exists():
        raise AudioMetadataError(f"Audio file does not exist: {input_path}")

    if not input_path.is_file():
        raise AudioMetadataError(f"Audio path is not a file: {input_path}")

    try:
        info = sf.info(input_path)
    except (RuntimeError, OSError) as exc:
        raise AudioMetadataError(f"Unsupported or unreadable audio file: {input_path}") from exc

    metadata = FileMetadata(
        path=str(path),
        sample_rate=info.samplerate,
        channels=info.channels,
        duration_seconds=round(info.duration, 3),
        sample_count=info.frames,
    )
    return AnalysisResult(file=metadata)
