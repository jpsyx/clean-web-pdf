from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

from .errors import CleanupError
from .models import Article, BlockKind, ContentBlock, PdfSnapshot, TextSpan


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def repeated_margin_text(snapshot: PdfSnapshot) -> frozenset[str]:
    counts: Counter[str] = Counter()
    threshold = max(2, (len(snapshot.pages) + 1) // 2)
    for page in snapshot.pages:
        seen: set[str] = set()
        for span in page.spans:
            if span.top < page.height * 0.12 or span.bottom > page.height * 0.90:
                text = _norm(span.text)
                if text:
                    seen.add(text)
                    if span.bottom > page.height * 0.90 and (text.isdigit() or text.startswith("http")):
                        counts[text] = threshold
        for text in seen:
            counts[text] += 1
    return frozenset(text for text, count in counts.items() if count >= threshold)


def dominant_body_size(spans: tuple[TextSpan, ...]) -> float:
    counts: Counter[float] = Counter()
    for span in spans:
        if len(span.text) > 1:
            counts[round(span.font_size, 1)] += len(span.text)
    return counts.most_common(1)[0][0] if counts else 10.0


def principal_column(spans: tuple[TextSpan, ...]) -> tuple[float, float]:
    body = dominant_body_size(spans)
    body_spans = [span for span in spans if span.font_size <= body * 1.25 and len(span.text) > 2]
    if not body_spans:
        return (0.0, max((span.page_width for span in spans), default=612.0))
    return (min(span.x0 for span in body_spans), max(span.x1 for span in body_spans))


def infer_title(spans: tuple[TextSpan, ...], body_size: float) -> str:
    candidates = [span for span in spans if span.font_size >= body_size * 1.5 and span.top < spans[0].page_height * 0.45]
    if not candidates:
        raise CleanupError("could not identify a complete article title")
    return _norm(" ".join(span.text for span in sorted(candidates, key=lambda item: item.top)))


def infer_author(spans: tuple[TextSpan, ...], title: str) -> str | None:
    for index, span in enumerate(sorted(spans, key=lambda item: (item.page_index, item.top, item.x0))):
        if span.text.casefold() in {"by", "author"} and index + 1 < len(spans):
            return spans[index + 1].text
    for span in spans:
        if span.top < 250 and span.text.casefold() not in title.casefold() and len(span.text.split()) in {2, 3}:
            if span.font_size >= 9:
                return span.text
    return None


def is_end_boundary(text: str, font_size: float, body_size: float) -> bool:
    lowered = text.casefold().strip(" #: ")
    return font_size >= body_size * 1.15 and any(lowered.startswith(value) for value in ("about the author", "related", "recommended", "you might also like", "more from", "sign up"))


def extract_pdf_article(snapshot: PdfSnapshot) -> Article:
    spans = tuple(span for page in snapshot.pages for span in page.spans)
    body_size = dominant_body_size(spans)
    title = snapshot.title or infer_title(spans, body_size)
    noise = repeated_margin_text(snapshot)
    rows: list[tuple[int, float, float, str, float, str]] = []
    for page in snapshot.pages:
        page_spans = [span for span in page.spans if _norm(span.text) not in noise]
        for span in page_spans:
            rows.append((span.page_index, span.top, span.x0, span.text, span.font_size, span.font_name))
    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    blocks: list[ContentBlock] = []
    paragraph: list[str] = []
    author = snapshot.author
    saw_content = False
    for _page, _top, _x0, text, size, font in rows:
        clean = _norm(text)
        if not clean or clean.casefold() == title.casefold():
            continue
        if is_end_boundary(clean, size, body_size):
            break
        if re.match(r"^(?:[-*+] |\d+[.)] )", clean):
            if paragraph:
                blocks.append(ContentBlock(BlockKind.PARAGRAPH, " ".join(paragraph))); paragraph.clear()
            blocks.append(ContentBlock(BlockKind.LIST_ITEM, re.sub(r"^(?:[-*+] |\d+[.)] )", "", clean))); saw_content = True; continue
        if size >= body_size * 1.25 and len(clean) > 3:
            if paragraph:
                blocks.append(ContentBlock(BlockKind.PARAGRAPH, " ".join(paragraph))); paragraph.clear()
            blocks.append(ContentBlock(BlockKind.HEADING, clean, 2)); saw_content = True; continue
        if not author and clean.casefold().startswith("by "):
            author = clean[3:].strip(); continue
        paragraph.append(clean); saw_content = True
    if paragraph:
        blocks.append(ContentBlock(BlockKind.PARAGRAPH, " ".join(paragraph)))
    if len(" ".join(block.text for block in blocks)) < 100 or not saw_content:
        raise CleanupError("could not identify a complete article")
    source = snapshot.source_candidates[0] if snapshot.source_candidates else None
    site = urlsplit(source).netloc if source else None
    return Article(title, author, source, site, tuple(blocks))
