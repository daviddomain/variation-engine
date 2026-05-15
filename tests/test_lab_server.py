import json
import threading
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

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
        self.lab_output_root = Path(self.tmp_dir.name) / "lab_output"
        category_path = self.samples_root / "plucked_string"
        category_path.mkdir(parents=True)
        (category_path / "ignore.txt").write_text("not audio", encoding="utf-8")
        self.sample_path = category_path / "Test.wav"
        self._write_wav_fixture(self.sample_path)

        handler = build_lab_handler(self.samples_root, self.lab_output_root)
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

    def test_static_lab_files_are_served(self) -> None:
        page = self.get_text("/")
        script = self.get_text("/app.js")

        self.assertIn('<select id="category" name="category"></select>', page)
        self.assertIn('fetchJson("/api/categories")', script)

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

    def test_render_endpoint_rejects_unsafe_sample_paths(self) -> None:
        body = self.post_json_error(
            "/api/render",
            {
                **self.valid_render_request(),
                "sample_path": "samples/plucked_string/../secret.wav",
            },
        )

        self.assertEqual(body, {"error": "Invalid sample path"})

    def test_render_endpoint_rejects_invalid_source_note(self) -> None:
        body = self.post_json_error(
            "/api/render",
            {
                **self.valid_render_request(),
                "source_note": "H3",
            },
        )

        self.assertIn("Invalid note name", body["error"])

    def test_render_endpoint_rejects_invalid_parameter_ranges(self) -> None:
        body = self.post_json_error(
            "/api/render",
            {
                **self.valid_render_request(),
                "parameter_ranges": {"micropitch_cents": [-99.0, 99.0]},
            },
        )

        self.assertIn("micropitch_cents range override must stay within", body["error"])

    def test_render_endpoint_rejects_missing_parameter_ranges(self) -> None:
        request = self.valid_render_request()
        del request["parameter_ranges"]

        body = self.post_json_error("/api/render", request)

        self.assertEqual(
            body,
            {"error": "Missing required request field: parameter_ranges"},
        )

    def test_render_endpoint_writes_run_files_and_render_json(self) -> None:
        body = self.post_json("/api/render", self.valid_render_request())

        output_dir = body["output_dir"]
        self.assertTrue(output_dir.startswith("lab_output/plucked_string/test_seed-0_"))
        self.assertFalse(Path(output_dir).is_absolute())

        physical_output_dir = self.lab_output_root / Path(output_dir).relative_to("lab_output")
        self.assertTrue(physical_output_dir.is_dir())
        self.assertEqual(
            sorted(path.name for path in physical_output_dir.glob("*.wav")),
            [
                "rr_01.wav",
                "rr_02.wav",
                "rr_03.wav",
                "rr_04.wav",
                "rr_05.wav",
                "rr_06.wav",
                "rr_07.wav",
                "rr_08.wav",
            ],
        )

        saved_render = json.loads(
            (physical_output_dir / "render.json").read_text(encoding="utf-8")
        )
        self.assertEqual(body, saved_render)
        self.assertEqual(body["render_result"]["round_robin_count"], 8)
        self.assertEqual(len(body["render_result"]["files"]), 8)
        self.assertEqual(len(body["audio_urls"]), 8)

        first_file = body["render_result"]["files"][0]
        self.assertEqual(first_file["audio_url"], body["audio_urls"][0])
        self.assertTrue(first_file["audio_url"].startswith("/lab-output/plucked_string/"))
        self.assertTrue(first_file["path"].startswith("lab_output/plucked_string/"))
        self.assertFalse(Path(first_file["path"]).is_absolute())

        served_audio = self.get_bytes(first_file["audio_url"])
        self.assertGreater(len(served_audio), 0)

    def test_render_endpoint_creates_unique_run_directories(self) -> None:
        first = self.post_json("/api/render", self.valid_render_request())
        second = self.post_json("/api/render", self.valid_render_request())

        self.assertNotEqual(first["output_dir"], second["output_dir"])

    def get_json(self, path: str) -> object:
        with urlopen(f"{self.base_url}{path}", timeout=10) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, path: str, body: dict[str, object]) -> object:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def get_json_error(self, path: str) -> object:
        with self.assertRaises(HTTPError) as error_context:
            urlopen(f"{self.base_url}{path}", timeout=10)

        error = error_context.exception
        self.assertEqual(error.status, 400)
        return json.loads(error.read().decode("utf-8"))

    def post_json_error(self, path: str, body: dict[str, object]) -> object:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error_context:
            urlopen(request, timeout=10)

        error = error_context.exception
        self.assertEqual(error.status, 400)
        return json.loads(error.read().decode("utf-8"))

    def get_bytes(self, path: str) -> bytes:
        with urlopen(f"{self.base_url}{path}", timeout=10) as response:
            self.assertEqual(response.status, 200)
            return response.read()

    def get_text(self, path: str) -> str:
        return self.get_bytes(path).decode("utf-8")

    def valid_render_request(self) -> dict[str, object]:
        return {
            "category_id": "plucked_string",
            "sample_path": "samples/plucked_string/Test.wav",
            "source_note": "A4",
            "seed": 0,
            "parameter_ranges": {
                "micropitch_cents": [-4.0, 4.0],
                "timing_shift_ms": [-2.0, 2.0],
                "gain_db": [-0.8, 0.8],
                "attack_amount": [-0.15, 0.15],
                "brightness_amount": [-0.2, 0.2],
                "decay_amount": [-0.08, 0.08],
                "saturation_amount": [0.0, 0.05],
                "stereo_balance_amount": [-0.08, 0.08],
            },
        }

    def _write_wav_fixture(self, path: Path) -> None:
        sample_rate = 22050
        time = np.linspace(0.0, 0.1, int(sample_rate * 0.1), endpoint=False)
        audio = (0.2 * np.sin(2.0 * np.pi * 440.0 * time)).astype(np.float32)
        sf.write(path, audio, sample_rate)


if __name__ == "__main__":
    unittest.main()
