import argparse
import json
import sys
from collections.abc import Sequence

from variation_engine.analysis.io import AudioMetadataError, analyze_audio_file
from variation_engine.lab.server import DEFAULT_LAB_HOST, DEFAULT_LAB_PORT, run_lab_server
from variation_engine.variation.planner import InvalidNoteNameError, create_variation_plan
from variation_engine.variation.renderer import DEFAULT_RENDER_SEED, render_source_round_robins


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="variation-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze an audio file and print metadata as JSON.",
    )
    analyze_parser.add_argument("path", help="Path to a WAV, AIFF, FLAC, or supported audio file.")

    plan_parser = subparsers.add_parser(
        "plan",
        help="Analyze an audio file and print a dry-run variation plan as JSON.",
    )
    plan_parser.add_argument("path", help="Path to a WAV, AIFF, FLAC, or supported audio file.")
    plan_parser.add_argument(
        "--category",
        help="Optional instrument category id used to select the default variation profile.",
    )
    plan_parser.add_argument(
        "--source-note",
        help="Optional source note override such as C3, C#3, or Db3.",
    )

    render_parser = subparsers.add_parser(
        "render",
        help="Render source-only round-robin WAV variations.",
    )
    render_parser.add_argument("path", help="Path to a WAV, AIFF, FLAC, or supported audio file.")
    render_parser.add_argument(
        "--output",
        required=True,
        help="Output directory for rendered round-robin WAV files.",
    )
    render_parser.add_argument(
        "--category",
        help="Optional instrument category id used to select the default variation profile.",
    )
    render_parser.add_argument(
        "--source-note",
        help="Optional source note override such as C3, C#3, or Db3.",
    )
    render_parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RENDER_SEED,
        help=f"Deterministic render seed. Defaults to {DEFAULT_RENDER_SEED}.",
    )

    lab_parser = subparsers.add_parser(
        "lab",
        help="Start the local dependency-free Audio Lab web server.",
    )
    lab_parser.add_argument(
        "--host",
        default=DEFAULT_LAB_HOST,
        help=f"Host address to bind. Defaults to {DEFAULT_LAB_HOST}.",
    )
    lab_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_LAB_PORT,
        help=f"Port to bind. Defaults to {DEFAULT_LAB_PORT}.",
    )

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

    if args.command == "plan":
        try:
            analysis = analyze_audio_file(args.path)
            result = create_variation_plan(
                analysis,
                category_id=args.category,
                source_note=args.source_note,
            )
        except (AudioMetadataError, InvalidNoteNameError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "render":
        try:
            analysis = analyze_audio_file(args.path)
            result = render_source_round_robins(
                args.path,
                args.output,
                analysis,
                category_id=args.category,
                source_note=args.source_note,
                seed=args.seed,
            )
        except (AudioMetadataError, InvalidNoteNameError, OSError, RuntimeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "lab":
        try:
            run_lab_server(host=args.host, port=args.port)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
