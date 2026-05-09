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
class TransientMetrics:
    onset_time_ms: float
    attack_duration_ms: float
    transient_strength: float
    transient_confidence: float


@dataclass(frozen=True)
class AnalysisResult:
    file: FileMetadata
    amplitude: AmplitudeMetrics
    transient: TransientMetrics

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
