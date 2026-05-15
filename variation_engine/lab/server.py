from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from variation_engine.analysis.categories import INSTRUMENT_CATEGORIES


DEFAULT_LAB_HOST = "127.0.0.1"
DEFAULT_LAB_PORT = 8765
STATIC_DIR = Path(__file__).resolve().parent / "static"


def ensure_sample_category_folders(samples_root: str | Path = "samples") -> list[Path]:
    """Create the expected sample category folders and return their paths."""
    root = Path(samples_root)
    created_paths = []

    for category in INSTRUMENT_CATEGORIES:
        path = root / category.id
        path.mkdir(parents=True, exist_ok=True)
        created_paths.append(path)

    return created_paths


def run_lab_server(
    host: str = DEFAULT_LAB_HOST,
    port: int = DEFAULT_LAB_PORT,
    samples_root: str | Path = "samples",
) -> None:
    ensure_sample_category_folders(samples_root)

    handler_class = partial(SimpleHTTPRequestHandler, directory=str(STATIC_DIR))
    server = ThreadingHTTPServer((host, port), handler_class)

    print(f"Audio Lab running at http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
