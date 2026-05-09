import argparse
import json
import sys
from collections.abc import Sequence

from variation_engine.analysis.io import AudioMetadataError, analyze_audio_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="variation-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze an audio file and print metadata as JSON.",
    )
    analyze_parser.add_argument("path", help="Path to a WAV, AIFF, FLAC, or supported audio file.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            result = analyze_audio_file(args.path)
        except AudioMetadataError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(result.to_dict(), indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
