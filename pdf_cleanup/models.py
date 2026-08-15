from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BlockKind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    QUOTE = "quote"
    CODE = "code"


@dataclass(frozen=True)
class ContentBlock:
    kind: BlockKind
    text: str
    level: int = 0


@dataclass(frozen=True)
class TextSpan:
    page_index: int
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    font_name: str
    font_size: float
    page_width: float
    page_height: float


@dataclass(frozen=True)
class PageSnapshot:
    index: int
    width: float
    height: float
    spans: tuple[TextSpan, ...]
    hyperlinks: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfSnapshot:
    title: str | None
    author: str | None
    pages: tuple[PageSnapshot, ...]
    source_candidates: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(span.text for page in self.pages for span in page.spans)


@dataclass(frozen=True)
class Article:
    title: str
    author: str | None
    source_url: str | None
    site: str | None
    blocks: tuple[ContentBlock, ...]
