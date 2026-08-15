from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from pdf_cleanup.errors import CleanupError
from pdf_cleanup.paths import resolve_output_path, validate_input


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="pdf-cleanup",
        description="Clean a browser-printed article PDF and render a readable PDF.",
        epilog=("Examples:\n  pdf-cleanup article.pdf\n  pdf-cleanup article.pdf /tmp/clean/\n  pdf-cleanup article.pdf ~/Documents/article-clean.pdf"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.add_argument("input", metavar="<input.pdf>", help="Browser-printed PDF to clean.")
    parser.add_argument("output", nargs="?", metavar="[output]", help="Existing directory, or exact output PDF path. Defaults to a -cleaned sibling.")
    args = parser.parse_args(argv)
    try:
        from pdf_cleanup.pipeline import cleanup_pdf
        source = validate_input(Path(args.input))
        output = resolve_output_path(source, args.output)
        result, extraction_source = cleanup_pdf(source, output)
    except CleanupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"cleaned ({extraction_source}) -> {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
