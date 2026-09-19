from __future__ import annotations

import re
from urllib.request import Request, urlopen
from copy import deepcopy
from html import unescape
from typing import Callable
from urllib.parse import urlsplit

from trafilatura import bare_extraction, extract, fetch_url
from trafilatura.settings import DEFAULT_CONFIG

from .models import Article, BlockKind, ContentBlock, PdfSnapshot

FETCH_CONFIG = deepcopy(DEFAULT_CONFIG)
FETCH_CONFIG["DEFAULT"]["DOWNLOAD_TIMEOUT"] = "10"
FETCH_CONFIG["DEFAULT"]["MAX_REDIRECTS"] = "10"


def _download(url: str) -> str | None:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 clean-web-pdf"})
    with urlopen(request, timeout=10) as response:
        return response.read(20_000_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")


# A complete `*…*`/`**…**` run whose closing marker is glued to the next word.
# HTML-to-markdown conversion drops the space that sat outside the `<strong>`
# or `<em>` tag, so `<strong>Grill the plan</strong> until …` comes back as
# `**Grill the plan**until …` and renders without the space. Requiring a whole
# well-formed run (rather than a bare marker) keeps opening markers such as the
# one in `(**bold**)` and stray arithmetic asterisks untouched.
GLUED_EMPHASIS_RE = re.compile(r"(\*{1,2})(?=\S)([^*]+?)(?<=\S)\1(?=[0-9A-Za-z])")


def repair_emphasis_spacing(line: str) -> str:
    return GLUED_EMPHASIS_RE.sub(r"\1\2\1 ", line)


def parse_markdown_blocks(value: str) -> tuple[ContentBlock, ...]:
    blocks: list[ContentBlock] = []
    paragraph: list[str] = []
    in_code = False
    code: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(ContentBlock(BlockKind.PARAGRAPH, " ".join(paragraph).strip()))
            paragraph.clear()

    for raw in value.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            if in_code:
                blocks.append(ContentBlock(BlockKind.CODE, "\n".join(code)))
                code.clear()
            else:
                flush()
            in_code = not in_code
            continue
        if in_code:
            code.append(raw)
            continue
        line = repair_emphasis_spacing(line)
        if not line:
            flush()
        elif match := re.match(r"^(#{1,6})\s+(.+)$", line):
            flush()
            blocks.append(ContentBlock(BlockKind.HEADING, match.group(2).strip(), len(match.group(1))))
        elif re.match(r"^(?:[-*+] |\d+[.)] )", line):
            flush()
            blocks.append(ContentBlock(BlockKind.LIST_ITEM, re.sub(r"^(?:[-*+] |\d+[.)] )", "", line)))
        elif line.startswith(">"):
            flush()
            blocks.append(ContentBlock(BlockKind.QUOTE, line[1:].strip()))
        else:
            paragraph.append(line)
    if in_code:
        blocks.append(ContentBlock(BlockKind.CODE, "\n".join(code)))
    flush()
    return tuple(block for block in blocks if block.text)


def extract_web_article(url: str, downloader: Callable[[str], str | None] = _download) -> Article | None:
    try:
        html = downloader(url)
        if not html:
            return None
        document = bare_extraction(html, url=url)
        markdown = extract(html, url=url, output_format="markdown", include_comments=False, include_images=False, include_links=True)
        if document is None or not markdown:
            return None
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        author_match = re.search(r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)', html, re.I)
        title = unescape(str(getattr(document, "title", None) or (title_match.group(1) if title_match else ""))).strip()
        title = re.sub(r"\s*\|\s*Blog\s*$", "", title, flags=re.I)
        blocks = parse_markdown_blocks(markdown)
        for index, block in enumerate(blocks):
            if block.kind == BlockKind.HEADING and block.text.casefold() == title.casefold():
                blocks = blocks[index + 1:]
                break
        boundary = ("you might also like", "related", "recommended", "make your company", "more from")
        for index, block in enumerate(blocks):
            if block.kind == BlockKind.HEADING and block.text.casefold().strip().startswith(boundary):
                blocks = blocks[:index]
                break
        if not title or not blocks:
            return None
        author = str(getattr(document, "author", None) or (author_match.group(1) if author_match else "")).strip() or None
        site = str(getattr(document, "sitename", None) or "").strip() or urlsplit(url).netloc
        return Article(title, author, url, site, tuple(blocks))
    except Exception:
        return None


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def web_matches_snapshot(article: Article, snapshot: PdfSnapshot) -> bool:
    title = set(_tokens(article.title))
    pdf_title = set(_tokens(snapshot.title or ""))
    if not title or not pdf_title or len(title & pdf_title) / len(title | pdf_title) < 0.60:
        return False
    body = _tokens(" ".join(block.text for block in article.blocks))
    pdf = _tokens(snapshot.text)
    if len(body) < 20 or len(pdf) < 20:
        return False
    shingles = {tuple(body[index:index + 5]) for index in range(len(body) - 4)}
    pdf_shingles = {tuple(pdf[index:index + 5]) for index in range(len(pdf) - 4)}
    return bool(shingles) and len(shingles & pdf_shingles) / len(shingles) >= 0.55
