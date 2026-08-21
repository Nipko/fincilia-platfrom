from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import DEFAULT_SEED, generate_corpus
from .linter import lint_corpus, verify_corpus

DEFAULT_ROOT = Path("tests/golden/synthetic")


def _print_report(report: object) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fincilia deterministic synthetic corpus tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="generate deterministic fixtures")
    generate_parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    generate_parser.add_argument("--seed", default=DEFAULT_SEED)

    lint_parser = subparsers.add_parser("lint", help="lint provenance and fixture integrity")
    lint_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)

    verify_parser = subparsers.add_parser("verify", help="lint and compare with regeneration")
    verify_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)

    args = parser.parse_args()
    if args.command == "generate":
        corpus = generate_corpus(args.output, args.seed)
        _print_report(
            {
                "files_written": len(corpus),
                "output": str(args.output),
                "seed": args.seed,
                "synthetic": True,
            }
        )
        return 0

    report = lint_corpus(args.root) if args.command == "lint" else verify_corpus(args.root)
    _print_report(report.as_dict())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
