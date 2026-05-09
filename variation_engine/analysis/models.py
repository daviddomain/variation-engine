from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FileMetadata:
    path: str
    sample_rate: int
    channels: int
    duration_seconds: float
    sample_count: int


@dataclass(frozen=True)
class AnalysisResult:
    file: FileMetadata

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
