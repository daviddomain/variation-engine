from variation_engine.analysis.models import (
    AmplitudeMetrics,
    FileMetadata,
    PitchMetrics,
    ProfileMetrics,
    TimbreMetrics,
    TransientMetrics,
)


STRONG_TRANSIENT = 0.68
SOFT_ATTACK_MS = 80.0
SHORT_DURATION_SECONDS = 0.8
LONG_DURATION_SECONDS = 1.2
LOW_PITCH_CONFIDENCE = 0.35
HIGH_PITCH_CONFIDENCE = 0.55
HIGH_SPECTRAL_FLATNESS = 0.08


def suggest_profile(
    file: FileMetadata,
    amplitude: AmplitudeMetrics,
    transient: TransientMetrics,
    pitch: PitchMetrics,
    timbre: TimbreMetrics,
) -> ProfileMetrics:
    """Suggest a conservative internal profile from existing analysis metrics."""
    if amplitude.peak_amplitude <= 0.0 or file.duration_seconds <= 0.0:
        return ProfileMetrics(
            suggested_profile="unknown",
            confidence=0.0,
            reasons=["no audible signal"],
        )

    strong_transient = transient.transient_strength >= STRONG_TRANSIENT
    short_duration = file.duration_seconds <= SHORT_DURATION_SECONDS
    longer_duration = file.duration_seconds >= LONG_DURATION_SECONDS
    high_pitch_confidence = (
        pitch.is_probably_pitched and pitch.pitch_confidence >= HIGH_PITCH_CONFIDENCE
    )
    low_pitch_confidence = (
        not pitch.is_probably_pitched or pitch.pitch_confidence <= LOW_PITCH_CONFIDENCE
    )
    soft_attack = transient.attack_duration_ms >= SOFT_ATTACK_MS
    noisy_texture = timbre.spectral_flatness >= HIGH_SPECTRAL_FLATNESS

    if strong_transient and short_duration and low_pitch_confidence:
        return _profile(
            "percussive",
            0.74,
            [
                "strong transient",
                "short duration",
                "low pitch confidence",
            ],
        )

    if strong_transient and high_pitch_confidence:
        reasons = [
            "strong transient",
            "stable pitch estimate",
        ]
        if short_duration:
            reasons.append("short duration")
        return _profile("tonal_percussive", 0.7, reasons)

    if soft_attack and high_pitch_confidence and longer_duration:
        return _profile(
            "sustained_tonal",
            0.72,
            [
                "soft attack",
                "stable pitch estimate",
                "longer duration",
            ],
        )

    if noisy_texture and low_pitch_confidence:
        reasons = [
            "high spectral flatness",
            "low pitch confidence",
        ]
        if not strong_transient:
            reasons.append("no dominant transient")
        return _profile("sfx_texture", 0.66, reasons)

    return _profile(
        "unknown",
        0.25,
        ["analysis did not match a conservative profile rule"],
    )


def _profile(suggested_profile: str, confidence: float, reasons: list[str]) -> ProfileMetrics:
    return ProfileMetrics(
        suggested_profile=suggested_profile,
        confidence=round(confidence, 6),
        reasons=reasons,
    )
