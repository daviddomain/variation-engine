import tempfile
import unittest
from pathlib import Path

from variation_engine.analysis.categories import INSTRUMENT_CATEGORIES
from variation_engine.cli import build_parser
from variation_engine.lab.server import (
    DEFAULT_LAB_HOST,
    DEFAULT_LAB_PORT,
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


if __name__ == "__main__":
    unittest.main()
