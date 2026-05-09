from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FileMetadata:
    path: str
    sample_rate: int
    channels: int
    duration_seconds: float
    sample_count: int


@dataclass(frozen=True)
class AmplitudeMetrics:
    peak_amplitude: float
    rms: float
    crest_factor: float
    leading_silence_ms: float
    trailing_silence_ms: float


@dataclass(frozen=True)
class AnalysisResult:
    file: FileMetadata
    amplitude: AmplitudeMetrics

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
