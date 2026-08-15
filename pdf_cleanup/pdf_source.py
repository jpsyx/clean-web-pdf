from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pdfplumber

from .errors import CleanupError
from .models import PageSnapshot, PdfSnapshot, TextSpan

URL_RE = re.compile(r"https?://[^\s<>\]\[)]+")
TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip().rstrip(".,;"))
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in TRACKING]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def rank_source_urls(urls: list[str], document_title: str | None) -> tuple[str, ...]:
    title_tokens = set(re.findall(r"[a-z0-9]+", (document_title or "").lower()))
    counts = Counter(url for raw in urls if (url := normalize_url(raw)))

    def score(item: tuple[str, int]) -> tuple[float, str]:
        url, count = item
        parts = urlsplit(url)
        path_tokens = set(re.findall(r"[a-z0-9]+", parts.path.lower()))
        penalty = 2.0 if any(word in parts.path.lower() for word in ("login", "signup", "share", "privacy", "terms")) else 0
        penalty += 3.0 if parts.netloc.lower().startswith(("www.facebook.", "twitter.", "x.com")) else 0
        return (count * 5 + len(title_tokens & path_tokens) - penalty, url)

    return tuple(url for url, _ in sorted(counts.items(), key=score, reverse=True))


def inspect_pdf(path: Path) -> PdfSnapshot:
    try:
        with pdfplumber.open(path) as pdf:
            pages: list[PageSnapshot] = []
            urls: list[str] = []
            metadata = pdf.metadata or {}
            for key, value in metadata.items():
                if isinstance(value, str):
                    urls.extend(URL_RE.findall(value))
            for index, page in enumerate(pdf.pages):
                words = page.extract_words(extra_attrs=["fontname", "size"], keep_blank_chars=False)
                spans: list[TextSpan] = []
                for word in words:
                    text = str(word.get("text", "")).strip()
                    if not text:
                        continue
                    spans.append(TextSpan(index, text, float(word["x0"]), float(word["top"]), float(word["x1"]), float(word["bottom"]), str(word.get("fontname", "")), float(word.get("size", 0)), float(page.width), float(page.height)))
                    urls.extend(URL_RE.findall(text))
                links = tuple(str(link["uri"]) for link in (page.hyperlinks or []) if link.get("uri"))
                urls.extend(links)
                pages.append(PageSnapshot(index, float(page.width), float(page.height), tuple(spans), links))
            text_size = sum(len(span.text) for page in pages for span in page.spans)
            if text_size < 100:
                raise CleanupError("PDF has no usable text layer; scanned PDFs are not supported")
            title = str(metadata.get("Title") or metadata.get("title") or "").strip() or None
            author = str(metadata.get("Author") or metadata.get("author") or "").strip() or None
            return PdfSnapshot(title, author, tuple(pages), rank_source_urls(urls, title))
    except CleanupError:
        raise
    except Exception as error:
        raise CleanupError(f"could not read PDF: {error}") from error
