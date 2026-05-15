from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from variation_engine.analysis.categories import INSTRUMENT_CATEGORIES, get_instrument_category
from variation_engine.analysis.io import AudioMetadataError, analyze_audio_file
from variation_engine.variation.render_recipes import (
    NumericRange,
    RENDER_RECIPE_PARAMETER_LIMITS,
    RoundRobinRenderRecipe,
    select_round_robin_render_recipe,
)


DEFAULT_LAB_HOST = "127.0.0.1"
DEFAULT_LAB_PORT = 8765
STATIC_DIR = Path(__file__).resolve().parent / "static"
RECIPE_PARAMETER_LIMITS: dict[str, NumericRange] = RENDER_RECIPE_PARAMETER_LIMITS


def ensure_sample_category_folders(samples_root: str | Path = "samples") -> list[Path]:
    """Create the expected sample category folders and return their paths."""
    root = Path(samples_root)
    created_paths = []

    for category in INSTRUMENT_CATEGORIES:
        path = root / category.id
        path.mkdir(parents=True, exist_ok=True)
        created_paths.append(path)

    return created_paths


def build_lab_handler(samples_root: str | Path = "samples") -> Callable[..., SimpleHTTPRequestHandler]:
    root = Path(samples_root)

    class AudioLabRequestHandler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed_url = urlparse(self.path)
            if not parsed_url.path.startswith("/api/"):
                super().do_GET()
                return

            query = parse_qs(parsed_url.query)
            response = handle_api_request(parsed_url.path, query, root)
            self._send_json(response.body, status=response.status)

        def _send_json(self, body: object, *, status: int) -> None:
            payload = json.dumps(body, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return partial(AudioLabRequestHandler, directory=str(STATIC_DIR))


@dataclass(frozen=True)
class ApiResponse:
    body: object
    status: int = 200


def handle_api_request(
    path: str,
    query: dict[str, list[str]],
    samples_root: Path,
) -> ApiResponse:
    try:
        if path == "/api/categories":
            return ApiResponse(list_categories())

        if path == "/api/samples":
            category_id = _required_query_value(query, "category")
            return ApiResponse(list_category_samples(samples_root, category_id))

        if path == "/api/render-recipe":
            category_id = _required_query_value(query, "category")
            return ApiResponse(get_render_recipe_payload(category_id))

        if path == "/api/analyze":
            sample_path = _required_query_value(query, "sample_path")
            return ApiResponse(analyze_sample_payload(samples_root, sample_path))
    except ValueError as exc:
        return ApiResponse({"error": str(exc)}, status=400)
    except AudioMetadataError as exc:
        return ApiResponse({"error": str(exc)}, status=400)

    return ApiResponse({"error": "Unknown API endpoint"}, status=404)


def list_categories() -> list[dict[str, str]]:
    return [
        {
            "id": category.id,
            "label": category.label,
            "default_profile": category.default_profile,
        }
        for category in INSTRUMENT_CATEGORIES
    ]


def list_category_samples(samples_root: Path, category_id: str) -> list[dict[str, str]]:
    get_instrument_category(category_id)
    category_path = samples_root / category_id
    if not category_path.is_dir():
        return []

    return [
        {
            "label": path.name,
            "path": _relative_sample_api_path(category_id, path.name),
        }
        for path in sorted(category_path.glob("*.wav"), key=lambda item: item.name.lower())
        if path.is_file()
    ]


def get_render_recipe_payload(category_id: str) -> dict[str, object]:
    category = get_instrument_category(category_id)
    recipe = select_round_robin_render_recipe(
        category_id=category.id,
        profile_id=category.default_profile,
    )
    return {
        "recipe_id": recipe.id,
        "ranges": _recipe_ranges(recipe),
        "parameter_limits": {
            name: _range_to_list(value_range)
            for name, value_range in RECIPE_PARAMETER_LIMITS.items()
        },
    }


def analyze_sample_payload(samples_root: Path, sample_path: str) -> dict[str, object]:
    allowed_path = resolve_allowed_sample_path(samples_root, sample_path)
    analysis = analyze_audio_file(allowed_path)
    analysis_dict = analysis.to_dict()
    return {
        "analysis": analysis_dict,
        "summary": {
            "estimated_note_name": analysis.pitch.estimated_note_name,
            "pitch_confidence": analysis.pitch.pitch_confidence,
            "suggested_profile": analysis.profile.suggested_profile,
            "duration_seconds": analysis.file.duration_seconds,
            "sample_rate": analysis.file.sample_rate,
            "channels": analysis.file.channels,
        },
    }


def resolve_allowed_sample_path(samples_root: Path, sample_path: str) -> Path:
    decoded_path = unquote(sample_path).replace("\\", "/")
    candidate = Path(decoded_path)

    if candidate.is_absolute():
        raise ValueError("Invalid sample path")

    parts = decoded_path.split("/")
    if (
        len(parts) != 3
        or parts[0] != "samples"
        or any(part in {"", ".", ".."} for part in parts)
        or not parts[2].lower().endswith(".wav")
    ):
        raise ValueError("Invalid sample path")

    category_id = parts[1]
    get_instrument_category(category_id)
    resolved_root = samples_root.resolve()
    resolved_path = (samples_root / category_id / parts[2]).resolve()

    try:
        resolved_path.relative_to(resolved_root / category_id)
    except ValueError as exc:
        raise ValueError("Invalid sample path") from exc

    if not resolved_path.is_file():
        raise ValueError("Invalid sample path")

    return resolved_path


def run_lab_server(
    host: str = DEFAULT_LAB_HOST,
    port: int = DEFAULT_LAB_PORT,
    samples_root: str | Path = "samples",
) -> None:
    ensure_sample_category_folders(samples_root)

    handler_class = build_lab_handler(samples_root)
    server = ThreadingHTTPServer((host, port), handler_class)

    print(f"Audio Lab running at http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _required_query_value(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name)
    if not values or values[0] == "":
        raise ValueError(f"Missing required query parameter: {name}")
    return values[0]


def _recipe_ranges(recipe: RoundRobinRenderRecipe) -> dict[str, list[float]]:
    return {
        "micropitch_cents": _range_to_list(recipe.micropitch_cents),
        "timing_shift_ms": _range_to_list(recipe.timing_shift_ms),
        "gain_db": _range_to_list(recipe.gain_db),
        "attack_amount": _range_to_list(recipe.attack_amount),
        "brightness_amount": _range_to_list(recipe.brightness_amount),
        "decay_amount": _range_to_list(recipe.decay_amount),
        "saturation_amount": _range_to_list(recipe.saturation_amount),
        "stereo_balance_amount": _range_to_list(recipe.stereo_balance_amount),
    }


def _range_to_list(value_range: NumericRange) -> list[float]:
    return [value_range.min_value, value_range.max_value]


def _relative_sample_api_path(category_id: str, filename: str) -> str:
    return f"samples/{category_id}/{filename}"
