from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .errors import CleanupError
from .markdown import article_to_markdown
from .models import Article, PdfSnapshot
from .pdf_article import extract_pdf_article
from .pdf_source import inspect_pdf
from .web_article import extract_web_article, web_matches_snapshot


def select_article(snapshot: PdfSnapshot, web_extractor: Callable[[str], Article | None]) -> tuple[Article, str]:
    for url in snapshot.source_candidates:
        article = web_extractor(url)
        if article is not None and web_matches_snapshot(article, snapshot):
            return article, "web"
    return extract_pdf_article(snapshot), "pdf"


def render_with_markdown_to_pdf(markdown: str, output: Path, renderer: str) -> Path:
    existed = output.exists()
    with tempfile.TemporaryDirectory(prefix="clean-web-pdf-") as directory:
        markdown_path = Path(directory) / "article.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        process = subprocess.Popen([renderer, str(markdown_path), "--out", str(output)], stdout=subprocess.PIPE, text=True)
        final: Path | None = None
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            if line.startswith("Wrote "):
                final = Path(line.removeprefix("Wrote ").strip())
        status = process.wait()
    if status != 0:
        if not existed and output.exists():
            output.unlink()
        raise CleanupError(f"markdown-to-pdf failed with exit code {status}")
    final = final or output
    if not final.exists():
        raise CleanupError("markdown-to-pdf reported success but produced no PDF")
    return final


def cleanup_pdf(input_path: Path, output_path: Path, renderer: str | None = None, *, pdf_inspector=inspect_pdf, web_extractor=extract_web_article) -> tuple[Path, str]:
    executable = renderer or shutil.which("markdown-to-pdf")
    if executable is None:
        raise CleanupError("markdown-to-pdf was not found on PATH")
    snapshot = pdf_inspector(input_path)
    article, source = select_article(snapshot, web_extractor)
    return render_with_markdown_to_pdf(article_to_markdown(article), output_path, executable), source
