from __future__ import annotations

from pathlib import Path

from .errors import CleanupError


def validate_input(path: Path) -> Path:
    source = path.expanduser()
    if not source.exists():
        raise CleanupError(f"input PDF does not exist: {source}")
    if not source.is_file():
        raise CleanupError(f"input PDF is not a file: {source}")
    if source.suffix.lower() != ".pdf":
        raise CleanupError(f"input must be a PDF file: {source}")
    return source.resolve()


def resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    source = input_path.expanduser().absolute()
    if output_arg is None:
        output = source.with_name(f"{source.stem}-cleaned{source.suffix}")
    else:
        requested = Path(output_arg).expanduser()
        output = requested / source.name if requested.is_dir() else requested
        output = output.absolute()
    if output.resolve() == source.resolve():
        raise CleanupError("output path would overwrite the input PDF")
    if not output.parent.exists():
        raise CleanupError(f"output directory does not exist: {output.parent}")
    return output
