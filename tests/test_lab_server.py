import json
import threading
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

import numpy as np
import soundfile as sf

from variation_engine.analysis.categories import INSTRUMENT_CATEGORIES
from variation_engine.cli import build_parser
from variation_engine.lab.server import (
    DEFAULT_LAB_HOST,
    DEFAULT_LAB_PORT,
    build_lab_handler,
    ensure_sample_category_folders,
)


class LabCliParserTest(unittest.TestCase):
    def test_lab_command_uses_default_host_and_port(self) -> None:
        args = build_parser().parse_args(["lab"])

        self.assertEqual(args.command, "lab")
        self.assertEqual(args.host, DEFAULT_LAB_HOST)
        self.assertEqual(args.port, DEFAULT_LAB_PORT)

    def test_lab_command_accepts_host_and_port_overrides(self) -> None:
        args = build_parser().parse_args(["lab", "--host", "localhost", "--port", "9000"])

        self.assertEqual(args.host, "localhost")
        self.assertEqual(args.port, 9000)


class LabSampleFolderTest(unittest.TestCase):
    def test_ensure_sample_category_folders_creates_expected_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            samples_root = Path(tmp_dir) / "samples"

            created_paths = ensure_sample_category_folders(samples_root)

            self.assertEqual(
                [path.name for path in created_paths],
                [category.id for category in INSTRUMENT_CATEGORIES],
            )
            for category in INSTRUMENT_CATEGORIES:
                self.assertTrue((samples_root / category.id).is_dir())


class LabApiEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.samples_root = Path(self.tmp_dir.name) / "samples"
        category_path = self.samples_root / "plucked_string"
        category_path.mkdir(parents=True)
        (category_path / "ignore.txt").write_text("not audio", encoding="utf-8")
        self.sample_path = category_path / "Test.wav"
        self._write_wav_fixture(self.sample_path)

        handler = build_lab_handler(self.samples_root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)
        self.tmp_dir.cleanup()

    def test_categories_endpoint_returns_known_categories(self) -> None:
        body = self.get_json("/api/categories")

        self.assertIn(
            {
                "id": "plucked_string",
                "label": "Plucked String",
                "default_profile": "tonal_percussive",
            },
            body,
        )

    def test_samples_endpoint_only_returns_wav_files_from_selected_category(self) -> None:
        body = self.get_json("/api/samples?category=plucked_string")

        self.assertEqual(
            body,
            [{"label": "Test.wav", "path": "samples/plucked_string/Test.wav"}],
        )

    def test_render_recipe_endpoint_returns_ranges_and_parameter_limits(self) -> None:
        body = self.get_json("/api/render-recipe?category=plucked_string")

        self.assertEqual(body["recipe_id"], "plucked_string")
        self.assertEqual(body["ranges"]["micropitch_cents"], [-4.0, 4.0])
        self.assertEqual(body["parameter_limits"]["micropitch_cents"], [-12.0, 12.0])

    def test_analyze_endpoint_rejects_unsafe_paths(self) -> None:
        body = self.get_json_error("/api/analyze?sample_path=../secret.wav")

        self.assertEqual(body, {"error": "Invalid sample path"})

    def test_analyze_endpoint_works_for_allowed_sample_fixture(self) -> None:
        sample_path = quote("samples/plucked_string/Test.wav")
        body = self.get_json(f"/api/analyze?sample_path={sample_path}")

        self.assertEqual(body["summary"]["sample_rate"], 22050)
        self.assertEqual(body["summary"]["channels"], 1)
        self.assertEqual(body["analysis"]["file"]["sample_count"], 2205)

    def get_json(self, path: str) -> object:
        with urlopen(f"{self.base_url}{path}", timeout=10) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def get_json_error(self, path: str) -> object:
        with self.assertRaises(HTTPError) as error_context:
            urlopen(f"{self.base_url}{path}", timeout=10)

        error = error_context.exception
        self.assertEqual(error.status, 400)
        return json.loads(error.read().decode("utf-8"))

    def _write_wav_fixture(self, path: Path) -> None:
        sample_rate = 22050
        time = np.linspace(0.0, 0.1, int(sample_rate * 0.1), endpoint=False)
        audio = (0.2 * np.sin(2.0 * np.pi * 440.0 * time)).astype(np.float32)
        sf.write(path, audio, sample_rate)


if __name__ == "__main__":
    unittest.main()
