from __future__ import annotations

import json
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
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
    validate_render_recipe_range_overrides,
)
from variation_engine.variation.planner import InvalidNoteNameError, parse_note_name
from variation_engine.variation.renderer import render_source_round_robins


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


def build_lab_handler(
    samples_root: str | Path = "samples",
    lab_output_root: str | Path = "lab_output",
) -> Callable[..., SimpleHTTPRequestHandler]:
    root = Path(samples_root)
    output_root = Path(lab_output_root)

    class AudioLabRequestHandler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed_url = urlparse(self.path)
            if parsed_url.path.startswith("/lab-output/"):
                self._send_lab_output_file(parsed_url.path)
                return

            if not parsed_url.path.startswith("/api/"):
                super().do_GET()
                return

            query = parse_qs(parsed_url.query)
            response = handle_api_request(parsed_url.path, query, root)
            self._send_json(response.body, status=response.status)

        def do_POST(self) -> None:
            parsed_url = urlparse(self.path)
            if parsed_url.path != "/api/render":
                self._send_json({"error": "Unknown API endpoint"}, status=404)
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                request_body = json.loads(raw_body.decode("utf-8"))
                response = render_sample_payload(root, output_root, request_body)
            except json.JSONDecodeError:
                response = ApiResponse({"error": "Invalid JSON request body"}, status=400)
            except ValueError as exc:
                response = ApiResponse({"error": str(exc)}, status=400)
            except AudioMetadataError as exc:
                response = ApiResponse({"error": str(exc)}, status=400)

            self._send_json(response.body, status=response.status)

        def _send_json(self, body: object, *, status: int) -> None:
            payload = json.dumps(body, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_lab_output_file(self, request_path: str) -> None:
            try:
                file_path = resolve_lab_output_file(output_root, request_path)
            except ValueError:
                self.send_error(404)
                return

            content_type = (
                mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            )
            payload = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
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


def render_sample_payload(
    samples_root: Path,
    lab_output_root: Path,
    request_body: object,
) -> ApiResponse:
    request = validate_render_request(request_body)
    sample_path = resolve_allowed_sample_path(
        samples_root,
        request["sample_path"],
        category_id=request["category_id"],
    )
    analysis = analyze_audio_file(sample_path)
    run_dir = create_lab_output_run_dir(
        lab_output_root,
        category_id=request["category_id"],
        sample_stem=sample_path.stem,
        seed=request["seed"],
    )
    relative_output_dir = _relative_lab_output_path(run_dir, lab_output_root)

    render_result = render_source_round_robins(
        sample_path,
        run_dir,
        analysis=analysis,
        category_id=request["category_id"],
        source_note=request["source_note"],
        seed=request["seed"],
        render_recipe_range_overrides=request["parameter_ranges"],
    )
    render_result_payload = _relative_render_result_payload(
        render_result.to_dict(),
        lab_output_root,
    )
    audio_urls = [
        file_payload["audio_url"]
        for file_payload in render_result_payload["files"]
    ]
    warnings = list(render_result_payload.pop("warnings"))
    response_body = {
        "sample_path": request["sample_path"],
        "category_id": request["category_id"],
        "source_note": request["source_note"],
        "seed": request["seed"],
        "analysis": analysis.to_dict(),
        "parameter_ranges": request["parameter_ranges"],
        "parameter_limits": {
            name: _range_to_list(value_range)
            for name, value_range in RECIPE_PARAMETER_LIMITS.items()
        },
        "output_dir": relative_output_dir,
        "render_result": render_result_payload,
        "audio_urls": audio_urls,
        "warnings": warnings,
    }

    render_json_path = run_dir / "render.json"
    render_json_path.write_text(
        json.dumps(response_body, indent=2) + "\n",
        encoding="utf-8",
    )
    return ApiResponse(response_body)


def validate_render_request(request_body: object) -> dict[str, object]:
    if not isinstance(request_body, dict):
        raise ValueError("Render request body must be a JSON object")

    category_id = _required_body_string(request_body, "category_id")
    get_instrument_category(category_id)

    sample_path = _required_body_string(request_body, "sample_path")
    source_note = _required_body_string(request_body, "source_note")
    try:
        parse_note_name(source_note)
    except InvalidNoteNameError as exc:
        raise ValueError(str(exc)) from exc

    seed = request_body.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    parameter_ranges = request_body.get("parameter_ranges", {})
    validated_ranges = validate_render_recipe_range_overrides(parameter_ranges)
    return {
        "category_id": category_id,
        "sample_path": sample_path,
        "source_note": source_note,
        "seed": seed,
        "parameter_ranges": {
            name: _range_to_list(value_range)
            for name, value_range in validated_ranges.items()
        },
    }


def resolve_allowed_sample_path(
    samples_root: Path,
    sample_path: str,
    category_id: str | None = None,
) -> Path:
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

    sample_category_id = parts[1]
    get_instrument_category(sample_category_id)
    if category_id is not None and sample_category_id != category_id:
        raise ValueError("Invalid sample path")

    resolved_root = samples_root.resolve()
    resolved_path = (samples_root / sample_category_id / parts[2]).resolve()

    try:
        resolved_path.relative_to(resolved_root / sample_category_id)
    except ValueError as exc:
        raise ValueError("Invalid sample path") from exc

    if not resolved_path.is_file():
        raise ValueError("Invalid sample path")

    return resolved_path


def resolve_lab_output_file(lab_output_root: Path, request_path: str) -> Path:
    decoded_path = unquote(request_path).replace("\\", "/")
    parts = decoded_path.split("/")
    if (
        len(parts) < 4
        or parts[0] != ""
        or parts[1] != "lab-output"
        or any(part in {"", ".", ".."} for part in parts[2:])
    ):
        raise ValueError("Invalid lab output path")

    resolved_root = lab_output_root.resolve()
    file_path = resolved_root.joinpath(*parts[2:]).resolve()
    try:
        file_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Invalid lab output path") from exc

    if not file_path.is_file():
        raise ValueError("Invalid lab output path")

    return file_path


def create_lab_output_run_dir(
    lab_output_root: Path,
    *,
    category_id: str,
    sample_stem: str,
    seed: int,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = _slugify_path_segment(sample_stem)
    base_name = f"{stem}_seed-{seed}_{timestamp}"
    category_path = lab_output_root / category_id

    for index in range(100):
        suffix = "" if index == 0 else f"-{index + 1:02d}"
        candidate = category_path / f"{base_name}{suffix}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue

    raise ValueError("Could not create a unique lab output directory")


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


def _required_body_string(request_body: dict[str, object], name: str) -> str:
    value = request_body.get(name)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"Missing required request field: {name}")
    return value


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


def _relative_lab_output_path(path: Path, lab_output_root: Path) -> str:
    relative_path = path.resolve().relative_to(lab_output_root.resolve())
    return _api_path(Path("lab_output"), relative_path)


def _lab_output_audio_url(relative_lab_output_path: str) -> str:
    return "/" + relative_lab_output_path.replace("lab_output/", "lab-output/", 1)


def _relative_render_result_payload(
    render_result: dict[str, object],
    lab_output_root: Path,
) -> dict[str, object]:
    output_dir = _relative_lab_output_path(
        Path(str(render_result["output_dir"])),
        lab_output_root,
    )
    render_result["output_dir"] = output_dir
    files = []
    for file_payload in render_result["files"]:
        if not isinstance(file_payload, dict):
            continue

        relative_path = _relative_lab_output_path(
            Path(str(file_payload["path"])),
            lab_output_root,
        )
        file_payload["path"] = relative_path
        file_payload["audio_url"] = _lab_output_audio_url(relative_path)
        files.append(file_payload)

    render_result["files"] = files
    return render_result


def _api_path(*parts: Path) -> str:
    return "/".join(
        str(part).replace("\\", "/").strip("/")
        for part in parts
        if str(part) != ""
    )


def _slugify_path_segment(value: str) -> str:
    allowed_chars = []
    for char in value.lower():
        if char.isalnum():
            allowed_chars.append(char)
        elif char in {"-", "_"}:
            allowed_chars.append(char)
        elif char.isspace():
            allowed_chars.append("-")

    slug = "".join(allowed_chars).strip("-_")
    return slug or "sample"
