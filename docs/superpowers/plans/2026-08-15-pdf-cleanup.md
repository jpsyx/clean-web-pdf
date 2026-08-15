# PDF Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an installed `pdf-cleanup` command that extracts a browser-printed article into clean Markdown and renders a new PDF containing only its title, author, source, and prose.

**Architecture:** A Python CLI inspects the source PDF into immutable layout records, tries a validated network article extraction, and falls back to deterministic PDF-layout heuristics. Both paths produce the same article model, which is rendered to temporary Markdown and passed to the external `markdown-to-pdf` executable.

**Tech Stack:** Python 3.10+, standard-library `argparse` and `unittest`, `pdfplumber==0.11.10`, `trafilatura==2.1.0`, Bash entry points, and the external `markdown-to-pdf` command.

## Global Constraints

- The first release supports browser-generated article PDFs with a usable text layer; scanned and image-only PDFs return a clear unsupported-input error.
- Preserve prose and structure without paraphrasing, summarizing, or correcting the author.
- Keep only the title, author, source website or URL, and article body; remove website chrome and all images.
- The default output for `article.pdf` is `article-cleaned.pdf` beside it.
- An existing directory output preserves the input filename; any other second positional argument is the exact output filename.
- Never overwrite the input PDF.
- `-h` and `--help` must exit successfully before dependency checks, network access, or other side effects.
- Missing required arguments must print usage to standard error and exit nonzero.
- `install.sh` installs one fixed `$BIN_DIR/pdf-cleanup` launcher and defaults `BIN_DIR` to `$HOME/.local/bin`.
- Every entry point must resolve its own directory and work from an arbitrary current directory.
- Runtime dependencies are pinned exactly in `requirements.txt`.
- Tests are deterministic and do not require network access.
- Tracked files must be safe for a public repository: no secrets, personal names, machine-specific paths, or project-specific terms.
- Do not create a GitHub repository, push, merge, or open a pull request.
- Do not commit during execution unless the user separately gives explicit commit authorization.

## File Structure

```text
pdf-cleanup/
├── AGENTS.md                         # Public-safe contributor and development rules
├── LICENSE                           # MIT license
├── README.md                         # Installation, CLI usage, limits, and examples
├── docs/architecture.md              # Component boundaries and data flow
├── install.sh                        # Idempotent virtualenv and PATH launcher installer
├── main.py                           # Argument parser, top-level errors, and process exit code
├── pdf_cleanup/
│   ├── __init__.py                   # Version constant
│   ├── errors.py                     # User-facing CleanupError type
│   ├── models.py                     # Immutable PDF and article records
│   ├── paths.py                      # Input validation and output resolution
│   ├── pdf_source.py                 # PDF inspection and source URL discovery
│   ├── web_article.py                # Safe fetch, extraction, and snapshot validation
│   ├── pdf_article.py                # Layout-aware fallback extraction
│   ├── markdown.py                   # Article model to Markdown
│   └── pipeline.py                   # Extraction selection, temp files, and renderer process
├── requirements.txt                  # Exact runtime dependency pins
├── requirements-dev.txt              # Exact test-only dependency pins
├── run.sh                            # Clone-local executable entry point
└── tests/
    ├── __init__.py
    ├── helpers.py                    # Synthetic snapshots and PDFs
    ├── fixtures/article.html         # Deterministic matching webpage fixture
    ├── test_paths.py
    ├── test_pdf_source.py
    ├── test_web_article.py
    ├── test_pdf_article.py
    ├── test_markdown.py
    ├── test_pipeline.py
    └── test_cli_install.py
```

---

### Task 1: Core Models, Errors, and Output Paths

**Files:**

- Create: `pdf_cleanup/__init__.py`
- Create: `pdf_cleanup/errors.py`
- Create: `pdf_cleanup/models.py`
- Create: `pdf_cleanup/paths.py`
- Create: `tests/__init__.py`
- Create: `tests/test_paths.py`

**Interfaces:**

- Produces: `CleanupError(message: str)` for expected user-facing failures.
- Produces: `BlockKind`, `ContentBlock`, `TextSpan`, `PageSnapshot`, `PdfSnapshot`, and `Article` immutable dataclasses.
- Produces: `validate_input(path: Path) -> Path` and `resolve_output_path(input_path: Path, output_arg: str | None) -> Path`.
- Later tasks must not import `pdfplumber` or Trafilatura objects into the model layer.

- [ ] **Step 1: Write failing output-path tests**

```python
# tests/test_paths.py
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from pdf_cleanup.errors import CleanupError
from pdf_cleanup.paths import resolve_output_path, validate_input


class PathTests(TestCase):
    def test_default_output_is_cleaned_sibling(self):
        source = Path("/tmp/article.pdf")
        self.assertEqual(
            resolve_output_path(source, None),
            Path("/tmp/article-cleaned.pdf"),
        )

    def test_existing_directory_preserves_input_filename(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(
                resolve_output_path(Path("/tmp/article.pdf"), directory),
                Path(directory) / "article.pdf",
            )

    def test_exact_file_is_preserved(self):
        self.assertEqual(
            resolve_output_path(Path("/tmp/article.pdf"), "/tmp/nicer.pdf"),
            Path("/tmp/nicer.pdf"),
        )

    def test_input_output_collision_is_rejected(self):
        with self.assertRaisesRegex(CleanupError, "overwrite the input"):
            resolve_output_path(Path("/tmp/article.pdf"), "/tmp/article.pdf")

    def test_validate_input_rejects_missing_file(self):
        with self.assertRaisesRegex(CleanupError, "does not exist"):
            validate_input(Path("/definitely/missing/article.pdf"))
```

- [ ] **Step 2: Run the path tests and confirm RED**

Run: `python3 -m unittest tests.test_paths -v`

Expected: import failure for the missing `pdf_cleanup` package.

- [ ] **Step 3: Add the minimal models and error type**

```python
# pdf_cleanup/errors.py
class CleanupError(Exception):
    """An expected failure that can be shown without a traceback."""
```

```python
# pdf_cleanup/models.py
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
```

Set `__version__ = "0.1.0"` in `pdf_cleanup/__init__.py`.

- [ ] **Step 4: Implement path validation and resolution**

```python
# pdf_cleanup/paths.py
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
    source = input_path.expanduser().resolve()
    if output_arg is None:
        output = source.with_name(f"{source.stem}-cleaned{source.suffix}")
    else:
        requested = Path(output_arg).expanduser()
        output = requested / source.name if requested.is_dir() else requested
        output = output.resolve()
    if output == source:
        raise CleanupError("output path would overwrite the input PDF")
    if not output.parent.exists():
        raise CleanupError(f"output directory does not exist: {output.parent}")
    return output
```

- [ ] **Step 5: Run tests and confirm GREEN**

Run: `python3 -m unittest tests.test_paths -v`

Expected: all path tests pass.

- [ ] **Step 6: Check the task diff**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only Task 1 files plus the approved spec and plan are uncommitted. If commit authorization exists at execution time, commit with `git add pdf_cleanup tests/__init__.py tests/test_paths.py && git commit -m "feat: define cleanup paths and models"`; otherwise do not commit.

---

### Task 2: PDF Inspection and Source URL Discovery

**Files:**

- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pdf_cleanup/pdf_source.py`
- Create: `tests/helpers.py`
- Create: `tests/test_pdf_source.py`

**Interfaces:**

- Consumes: immutable snapshot types and `CleanupError` from Task 1.
- Produces: `normalize_url(value: str) -> str | None`.
- Produces: `rank_source_urls(urls: list[str], document_title: str | None) -> tuple[str, ...]`.
- Produces: `inspect_pdf(path: Path) -> PdfSnapshot`.
- Produces test helpers with these exact signatures:
  `make_browser_pdf(path: Path) -> None`,
  `snapshot_fixture(*, title: str, lines: tuple[str, ...], source_candidates: tuple[str, ...] = ()) -> PdfSnapshot`,
  `article_fixture(*, title: str, author: str | None = "Ada Example", source_url: str | None = "https://example.com/blog/synthetic-article", blocks: tuple[ContentBlock, ...] | None = None, paragraphs: tuple[str, ...] = ()) -> Article`,
  `browser_snapshot_fixture(*, source_candidates: tuple[str, ...] | None = None) -> PdfSnapshot`,
  `matching_article_fixture() -> Article`, and
  `unrelated_article_fixture() -> Article`.
- `inspect_pdf` is the only unit allowed to depend directly on `pdfplumber`.

- [ ] **Step 1: Pin runtime dependencies**

```text
# requirements.txt
pdfplumber==0.11.10
trafilatura==2.1.0
```

```text
# requirements-dev.txt
-r requirements.txt
reportlab==5.0.0
```

Create a temporary development environment and install the pins:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-dev.txt
```

Expected: both imports succeed with `.venv/bin/python -c 'import pdfplumber, trafilatura'`.

- [ ] **Step 2: Write failing URL tests**

```python
# tests/test_pdf_source.py
from unittest import TestCase

from pdf_cleanup.pdf_source import normalize_url, rank_source_urls


class UrlDiscoveryTests(TestCase):
    def test_normalize_url_removes_fragment_and_tracking(self):
        self.assertEqual(
            normalize_url("https://example.com/post?id=7&utm_source=print#comments"),
            "https://example.com/post?id=7",
        )

    def test_non_http_url_is_rejected(self):
        self.assertIsNone(normalize_url("mailto:author@example.com"))

    def test_repeated_article_url_outranks_social_link(self):
        urls = [
            "https://example.com/blog/build-wide-ship-narrow",
            "https://social.example/example",
            "https://example.com/blog/build-wide-ship-narrow",
        ]
        ranked = rank_source_urls(urls, "Build Wide, Ship Narrow | Blog")
        self.assertEqual(ranked[0], "https://example.com/blog/build-wide-ship-narrow")
```

- [ ] **Step 3: Run URL tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_source.UrlDiscoveryTests -v`

Expected: import failure for `pdf_cleanup.pdf_source`.

- [ ] **Step 4: Implement URL normalization and ranking**

Use `urllib.parse.urlsplit`, `parse_qsl`, `urlencode`, and `urlunsplit`. Remove fragments and query keys beginning with `utm_` plus `fbclid`, `gclid`, and `mc_cid`. Rank normalized URLs by occurrence count, title-token overlap with path segments, and penalties for known social hosts and paths containing `login`, `signup`, `share`, `privacy`, or `terms`. Preserve deterministic lexical ordering for tied scores.

Keep the exact public signatures declared in the Interfaces block so the PDF
adapter and unit tests depend only on normalized strings.

- [ ] **Step 5: Run URL tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_pdf_source.UrlDiscoveryTests -v`

Expected: all URL tests pass.

- [ ] **Step 6: Write a failing PDF inspection test**

In `tests/helpers.py`, add `make_browser_pdf(path: Path) -> None` using
`reportlab.pdfgen.canvas`. Generate two Letter pages with a repeated top title,
repeated bottom URL and page number, a large article title, byline, headings,
body paragraphs, and a URI link annotation over the footer URL.

```python
def test_inspect_pdf_collects_metadata_layout_and_links(self):
    with TemporaryDirectory() as directory:
        path = Path(directory) / "article.pdf"
        make_browser_pdf(path)
        snapshot = inspect_pdf(path)
    self.assertEqual(len(snapshot.pages), 2)
    self.assertGreater(len(snapshot.pages[0].spans), 3)
    self.assertEqual(snapshot.title, "Synthetic Article | Blog")
    self.assertIn("https://example.com/blog/synthetic-article", snapshot.source_candidates)
```

- [ ] **Step 7: Run the inspection test and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_source.PdfInspectionTests -v`

Expected: failure because `inspect_pdf` is missing or returns no snapshot.

- [ ] **Step 8: Implement PDF inspection**

Open with `pdfplumber.open(path)`, convert each text line into a `TextSpan` by
grouping words with matching `top`, `bottom`, `fontname`, and `size`, collect
`page.hyperlinks[*]["uri"]`, and scan extracted lines plus string-valued PDF
metadata fields with an HTTP URL regular expression. Copy metadata strings
before closing the PDF. Reject password errors, malformed documents, and fewer
than 100 non-whitespace extracted characters through `CleanupError`.

```python
def inspect_pdf(path: Path) -> PdfSnapshot:
    """Return layout records detached from the closed pdfplumber document."""
```

Pass every collected link and printed URL through `rank_source_urls`; store the ranked result on `PdfSnapshot.source_candidates`.

- [ ] **Step 9: Run PDF-source tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_pdf_source -v`

Expected: URL and inspection tests pass.

- [ ] **Step 10: Check the task diff**

Run: `git diff --check && git status --short`

Expected: dependency, source-inspection, and test-helper files are present. If commit authorization exists, commit with `git add requirements.txt requirements-dev.txt pdf_cleanup/pdf_source.py tests/helpers.py tests/test_pdf_source.py && git commit -m "feat: inspect PDF article sources"`.

---

### Task 3: Web Article Extraction and Snapshot Validation

**Files:**

- Create: `pdf_cleanup/web_article.py`
- Create: `tests/fixtures/article.html`
- Create: `tests/test_web_article.py`

**Interfaces:**

- Consumes: `Article`, `ContentBlock`, `BlockKind`, and `PdfSnapshot`.
- Produces: `parse_markdown_blocks(value: str) -> tuple[ContentBlock, ...]`.
- Produces: `extract_web_article(url: str, downloader: Callable[[str], str | None] = fetch_url) -> Article | None`.
- Produces: `web_matches_snapshot(article: Article, snapshot: PdfSnapshot) -> bool`.
- Network access remains injectable; tests pass local HTML through a fake downloader.

- [ ] **Step 1: Add a deterministic HTML fixture and failing extraction tests**

The fixture must include `<title>Synthetic Article | Blog</title>`, an author metadata tag, an `<article>` with two headings, three paragraphs, a list, and a quote, plus unrelated navigation, an image, a newsletter form, and related links outside the article.

```python
class WebExtractionTests(TestCase):
    def test_extract_web_article_keeps_article_and_drops_fluff(self):
        html = FIXTURE.read_text()
        article = extract_web_article(
            "https://example.com/blog/synthetic-article",
            downloader=lambda _url: html,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article.title, "Synthetic Article")
        self.assertEqual(article.author, "Ada Example")
        rendered_text = "\n".join(block.text for block in article.blocks)
        self.assertIn("First article paragraph", rendered_text)
        self.assertNotIn("Newsletter", rendered_text)
        self.assertNotIn("related story", rendered_text.lower())

    def test_downloader_failure_returns_none(self):
        self.assertIsNone(
            extract_web_article(
                "https://example.com/post",
                downloader=lambda _url: None,
            )
        )
```

- [ ] **Step 2: Run extraction tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_web_article.WebExtractionTests -v`

Expected: import failure for `pdf_cleanup.web_article`.

- [ ] **Step 3: Implement safe extraction and Markdown block parsing**

Copy Trafilatura's `DEFAULT_CONFIG` at import time, set `DOWNLOAD_TIMEOUT` to
`10` and `MAX_REDIRECTS` to `3`, and pass that private copy to `fetch_url`.
Call Trafilatura with comments and images disabled and links enabled. Obtain
metadata with `bare_extraction` and structured Markdown with
`extract(output_format="markdown")`. Convert Markdown headings, list items,
block quotes, fenced code, and paragraph groups into `ContentBlock` records.
Use extracted site metadata when present and otherwise use the source URL's
hostname. Remove a leading Markdown heading when it duplicates the article
model's title. Never pass raw HTML into the article model.

```python
from copy import deepcopy
from trafilatura import fetch_url
from trafilatura.settings import DEFAULT_CONFIG

FETCH_CONFIG = deepcopy(DEFAULT_CONFIG)
FETCH_CONFIG["DEFAULT"]["DOWNLOAD_TIMEOUT"] = "10"
FETCH_CONFIG["DEFAULT"]["MAX_REDIRECTS"] = "3"


def _download(url: str) -> str | None:
    return fetch_url(url, config=FETCH_CONFIG)
```

Catch Trafilatura and transport exceptions and return `None`; do not log response bodies.

- [ ] **Step 4: Run extraction tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_web_article.WebExtractionTests -v`

Expected: both extraction tests pass.

- [ ] **Step 5: Write failing snapshot-validation tests**

```python
class SnapshotValidationTests(TestCase):
    def test_matching_title_and_ordered_prose_are_accepted(self):
        article = article_fixture(
            title="Synthetic Article",
            paragraphs=("First article paragraph with enough words.",
                        "Second article paragraph continues the idea."),
        )
        snapshot = snapshot_fixture(
            title="Synthetic Article | Blog",
            lines=("First article paragraph with enough words.",
                   "Second article paragraph continues the idea."),
        )
        self.assertTrue(web_matches_snapshot(article, snapshot))

    def test_replaced_page_is_rejected(self):
        article = article_fixture(
            title="Different Article",
            paragraphs=("Unrelated replacement content lives here.",),
        )
        snapshot = snapshot_fixture(
            title="Synthetic Article | Blog",
            lines=("Original saved article body lives here.",),
        )
        self.assertFalse(web_matches_snapshot(article, snapshot))
```

- [ ] **Step 6: Run validation tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_web_article.SnapshotValidationTests -v`

Expected: failure because `web_matches_snapshot` is not implemented.

- [ ] **Step 7: Implement deterministic overlap scoring**

Normalize Unicode with NFKC, lowercase, discard punctuation, collapse
whitespace, and remove repeated browser footer lines. Require a title token
Jaccard score of at least `0.60`. Build ordered five-token shingles from article
body and PDF text and require at least `0.55` of article shingles to occur in
the PDF snapshot. Return `False` when either side has fewer than 20 normalized
body tokens.

Keep overlap scoring in `web_matches_snapshot` as a pure function so thresholds
are pinned by fixtures rather than live pages.

- [ ] **Step 8: Run the full web tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_web_article -v`

Expected: extraction and snapshot-validation tests pass without network access.

- [ ] **Step 9: Check the task diff**

Run: `git diff --check && git status --short`

If commit authorization exists, commit with `git add pdf_cleanup/web_article.py tests/fixtures/article.html tests/test_web_article.py tests/helpers.py && git commit -m "feat: extract and validate source articles"`.

---

### Task 4: Layout-Aware PDF Fallback

**Files:**

- Create: `pdf_cleanup/pdf_article.py`
- Create: `tests/test_pdf_article.py`
- Modify: `tests/helpers.py`

**Interfaces:**

- Consumes: `PdfSnapshot`, `PageSnapshot`, and `TextSpan` from Tasks 1 and 2.
- Produces: `repeated_margin_text(snapshot: PdfSnapshot) -> frozenset[str]`.
- Produces: `extract_pdf_article(snapshot: PdfSnapshot) -> Article`.
- All scoring helpers remain pure and accept snapshot records, never open files.

- [ ] **Step 1: Write failing repeated-chrome tests**

```python
class MarginNoiseTests(TestCase):
    def test_repeated_top_and_bottom_text_is_noise(self):
        snapshot = browser_snapshot_fixture()
        noise = repeated_margin_text(snapshot)
        self.assertIn("Synthetic Article | Blog", noise)
        self.assertIn("https://example.com/blog/synthetic-article", noise)
        self.assertNotIn("Second article paragraph continues here.", noise)
```

- [ ] **Step 2: Run the margin-noise test and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_article.MarginNoiseTests -v`

Expected: import failure for `pdf_cleanup.pdf_article`.

- [ ] **Step 3: Implement margin-noise detection**

Normalize span text and consider only spans whose `top` is in the first 12
percent of page height or whose `bottom` is in the last 10 percent. Mark text as
repeated when it appears in the same band on at least `max(2, ceil(page_count *
0.50))` pages. Independently mark bare page counters and HTTP URLs in the bottom
band.

Return the detected normalized strings from `repeated_margin_text` as a
`frozenset` so later classification cannot mutate them.

- [ ] **Step 4: Run the margin-noise test and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_pdf_article.MarginNoiseTests -v`

Expected: the repeated header and footer are detected, body prose is retained.

- [ ] **Step 5: Write failing article-boundary and structure tests**

Extend `browser_snapshot_fixture()` with title text at 24 points, a 10-point
byline, 11-point body prose, 18-point section headings, list items, an author
card, a `You might also like` heading, unrelated cards, and a footer.

```python
class PdfArticleTests(TestCase):
    def test_extracts_article_structure_and_stops_before_related_content(self):
        article = extract_pdf_article(browser_snapshot_fixture())
        self.assertEqual(article.title, "Synthetic Article")
        self.assertEqual(article.author, "Ada Example")
        self.assertEqual(article.source_url, "https://example.com/blog/synthetic-article")
        kinds = [block.kind for block in article.blocks]
        self.assertIn(BlockKind.HEADING, kinds)
        self.assertIn(BlockKind.LIST_ITEM, kinds)
        text = "\n".join(block.text for block in article.blocks)
        self.assertIn("Final article paragraph.", text)
        self.assertNotIn("You might also like", text)
        self.assertNotIn("Unrelated card", text)
```

- [ ] **Step 6: Run article fallback tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_article.PdfArticleTests -v`

Expected: failure because `extract_pdf_article` is absent.

- [ ] **Step 7: Implement fallback classification and boundaries**

Implement these pure helpers in `pdf_article.py`:

Create the pure helpers `dominant_body_size`, `principal_column`, `infer_title`,
`infer_author`, and `is_end_boundary`, followed by the public
`extract_pdf_article` function. Use the exact signatures declared in the
Interfaces block and the thresholds below.

Use character-count-weighted font-size frequency for `dominant_body_size`.
Choose the horizontal band containing the greatest amount of body-sized prose
as `principal_column`; admit headings that overlap that band. Join adjacent
same-style spans into lines, repair soft hyphenation only when a line ends in a
letter-hyphen and the next begins lowercase, and join wrapped prose with spaces.
Classify text above `body_size * 1.25` as a heading, leading bullet or numbered
markers as list items, leading `>` as quotes, and monospace font names as code.
Stop at a heading matching a case-insensitive boundary set that includes
`about the author`, `related`, `recommended`, `you might also like`, `more from`,
and `sign up`, but require heading typography or a sharp drop in prose density.
Use metadata author first, then byline patterns near the title. Set the source
to the first ranked candidate and the site to its hostname.

- [ ] **Step 8: Run fallback tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_pdf_article -v`

Expected: repeated chrome, title, author, structure, and end-boundary tests pass.

- [ ] **Step 9: Add failure coverage**

Add tests proving that fewer than two body paragraphs raises `CleanupError`
with `could not identify a complete article`, and that the error does not expose
raw object representations.

Run: `.venv/bin/python -m unittest tests.test_pdf_article -v`

Expected: all tests pass.

- [ ] **Step 10: Check the task diff**

Run: `git diff --check && git status --short`

If commit authorization exists, commit with `git add pdf_cleanup/pdf_article.py tests/helpers.py tests/test_pdf_article.py && git commit -m "feat: reconstruct articles from PDF layout"`.

---

### Task 5: Markdown Rendering and Cleanup Pipeline

**Files:**

- Create: `pdf_cleanup/markdown.py`
- Create: `pdf_cleanup/pipeline.py`
- Create: `tests/test_markdown.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**

- Consumes: article extraction functions from Tasks 2 through 4.
- Produces: `article_to_markdown(article: Article) -> str`.
- Produces: `select_article(snapshot: PdfSnapshot, web_extractor: Callable[[str], Article | None]) -> tuple[Article, str]`, where the second value is `"web"` or `"pdf"`.
- Produces: `render_with_markdown_to_pdf(markdown: str, output: Path, renderer: str) -> Path`.
- Produces: `cleanup_pdf(input_path: Path, output_path: Path, renderer: str | None = None) -> tuple[Path, str]`.

- [ ] **Step 1: Write failing Markdown tests**

```python
class MarkdownTests(TestCase):
    def test_renders_metadata_and_supported_blocks(self):
        article = article_fixture(
            title="Synthetic Article",
            author="Ada Example",
            source_url="https://example.com/blog/synthetic-article",
            blocks=(
                ContentBlock(BlockKind.PARAGRAPH, "Opening paragraph."),
                ContentBlock(BlockKind.HEADING, "A section", level=2),
                ContentBlock(BlockKind.LIST_ITEM, "First item"),
                ContentBlock(BlockKind.QUOTE, "A quoted thought."),
            ),
        )
        markdown = article_to_markdown(article)
        self.assertTrue(markdown.startswith("# Synthetic Article\n"))
        self.assertIn("**Author:** Ada Example", markdown)
        self.assertIn("**Source:** [example.com]", markdown)
        self.assertIn("## A section", markdown)
        self.assertIn("- First item", markdown)
        self.assertIn("> A quoted thought.", markdown)
```

- [ ] **Step 2: Run Markdown tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_markdown -v`

Expected: import failure for `pdf_cleanup.markdown`.

- [ ] **Step 3: Implement deterministic Markdown rendering**

Escape Markdown metacharacters in metadata and headings without altering prose
inside code. Render consecutive list items as one list and surround block types
with exactly one blank line. Always end with one newline.

Keep `article_to_markdown` pure and return the complete document string.

- [ ] **Step 4: Run Markdown tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_markdown -v`

Expected: all Markdown tests pass.

- [ ] **Step 5: Write failing extraction-selection tests**

```python
class SelectionTests(TestCase):
    def test_matching_web_article_wins(self):
        snapshot = snapshot_fixture(
            title="Synthetic Article | Blog",
            lines=(
                "First article paragraph with enough words for validation.",
                "Second article paragraph continues the saved article.",
            ),
            source_candidates=("https://example.com/blog/synthetic-article",),
        )
        web = matching_article_fixture()
        article, source = select_article(snapshot, lambda _url: web)
        self.assertIs(article, web)
        self.assertEqual(source, "web")

    def test_changed_web_article_falls_back_to_pdf(self):
        snapshot = browser_snapshot_fixture()
        changed = unrelated_article_fixture()
        article, source = select_article(snapshot, lambda _url: changed)
        self.assertEqual(source, "pdf")
        self.assertEqual(article.title, "Synthetic Article")

    def test_no_url_uses_pdf_without_calling_network(self):
        snapshot = browser_snapshot_fixture(source_candidates=())
        called = False
        def extractor(_url):
            nonlocal called
            called = True
        _article, source = select_article(snapshot, extractor)
        self.assertFalse(called)
        self.assertEqual(source, "pdf")
```

- [ ] **Step 6: Run selection tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pipeline.SelectionTests -v`

Expected: import failure for `pdf_cleanup.pipeline`.

- [ ] **Step 7: Implement extraction selection**

Try source candidates in ranked order. Accept the first non-`None` web article
that passes `web_matches_snapshot`; otherwise call `extract_pdf_article` once.
Return the source label for concise CLI reporting.

Keep the `select_article` signature from the Interfaces block; it returns the
chosen immutable article and the literal source label.

- [ ] **Step 8: Run selection tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_pipeline.SelectionTests -v`

Expected: selection tests pass.

- [ ] **Step 9: Write failing renderer and cleanup tests**

Create an executable fake renderer in a temporary directory. It records its
arguments, copies the Markdown input to a capture path supplied by the test, and
writes a minimal `%PDF-1.4` output. Test that temporary Markdown disappears,
the expected `--out` argument is used, the captured Markdown contains only the
article, and renderer failure removes only a newly created partial output.

Name the three tests
`test_renderer_receives_temporary_markdown_and_exact_output`,
`test_renderer_failure_raises_cleanup_error_and_removes_new_partial`, and
`test_renderer_failure_preserves_preexisting_output`.

- [ ] **Step 10: Run renderer tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pipeline.RendererTests -v`

Expected: failures because renderer orchestration is absent.

- [ ] **Step 11: Implement renderer orchestration**

Use `shutil.which("markdown-to-pdf")` when no renderer override is provided.
Check for the renderer before opening the PDF or fetching a URL. Use
`TemporaryDirectory(prefix="pdf-cleanup-")` and write `article.md` within it.
Call the renderer through `subprocess.Popen` with standard error inherited and
standard output piped in text mode. Print each stdout line immediately, and
recognize the renderer's final `Wrote <path>` line to return the actual path
when it chooses a versioned filename. Convert missing renderer, a missing final
path, and nonzero exit codes into `CleanupError` messages. Record whether the
requested output existed before invocation and unlink a partial requested file
only when it is new. The fake renderer must print the same `Wrote <path>`
contract so version-path handling is covered without using the real renderer.

Use the exact `render_with_markdown_to_pdf` and `cleanup_pdf` signatures from the
Interfaces block. Keep process execution in the former and orchestration in the
latter.

- [ ] **Step 12: Run Markdown and pipeline tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_markdown tests.test_pipeline -v`

Expected: all tests pass and no temporary Markdown remains.

- [ ] **Step 13: Check the task diff**

Run: `git diff --check && git status --short`

If commit authorization exists, commit with `git add pdf_cleanup/markdown.py pdf_cleanup/pipeline.py tests/test_markdown.py tests/test_pipeline.py tests/helpers.py && git commit -m "feat: render cleaned article PDFs"`.

---

### Task 6: CLI, Help, and Installed Entry Points

**Files:**

- Create: `main.py`
- Replace: `run.sh`
- Create: `install.sh`
- Create: `tests/test_cli_install.py`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: `validate_input`, `resolve_output_path`, and `cleanup_pdf`.
- Produces: `build_parser() -> argparse.ArgumentParser` and `main(argv: Sequence[str] | None = None) -> int`.
- Produces: clone-local `run.sh` and idempotent installed launcher at `$BIN_DIR/pdf-cleanup`.
- Produces test helper `run_command(*args: str, path: str) -> subprocess.CompletedProcess[str]`, which invokes the checkout's `run.sh` with captured text output and an explicitly supplied `PATH`.

- [ ] **Step 1: Write failing CLI tests**

Run `run.sh` through `subprocess.run` with an environment whose `PATH` omits
`markdown-to-pdf`. Assert:

```python
def test_help_succeeds_before_dependency_checks(self):
    result = run_command("--help", path="/usr/bin:/bin")
    self.assertEqual(result.returncode, 0)
    self.assertIn("Clean a browser-printed article PDF", result.stdout)
    self.assertIn("pdf-cleanup <input.pdf> [output]", result.stdout)
    self.assertEqual(result.stderr, "")

def test_missing_input_prints_usage_to_stderr(self):
    result = run_command(path="/usr/bin:/bin")
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("usage:", result.stderr.lower())
    self.assertEqual(result.stdout, "")
```

- [ ] **Step 2: Run CLI tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_cli_install.CliTests -v`

Expected: the starter `run.sh` does not provide the required interface.

- [ ] **Step 3: Implement the parser and top-level errors**

Use `argparse` with `prog="pdf-cleanup"`, one required `input` positional and
one optional `output` positional. The description, epilog examples, and argument
help must cover all output-resolution behavior and the `markdown-to-pdf`
requirement. Catch only `CleanupError`, print `error: <message>` to standard
error, and return `1`; unexpected exceptions retain tracebacks during
development.

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        source = validate_input(Path(args.input))
        output = resolve_output_path(source, args.output)
        result, extraction_source = cleanup_pdf(source, output)
    except CleanupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"cleaned ({extraction_source}) -> {result}")
    return 0
```

- [ ] **Step 4: Replace `run.sh` with the stable Python launcher**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || true)"
  if [[ -z "$PY" ]]; then
    echo "error: python3 not found; install Python 3.10 or newer, then run ./install.sh" >&2
    exit 1
  fi
fi
exec "$PY" "$SCRIPT_DIR/main.py" "$@"
```

Make it executable with `chmod 0755 run.sh`.

- [ ] **Step 5: Run CLI tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_cli_install.CliTests -v`

Expected: help passes without a renderer, and missing input prints usage only to
standard error.

- [ ] **Step 6: Write failing installer tests**

Use a temporary `BIN_DIR`, copy or invoke the real checkout without changing
the live user bin directory, and test:

Name the four tests `test_installer_help_has_no_side_effects`,
`test_installer_creates_one_working_launcher`,
`test_installing_twice_overwrites_the_same_launcher`, and
`test_installed_launcher_works_from_unrelated_directory`.

Run the real installer against the temporary destination. It may reuse the
repository's healthy `.venv`, but it must execute the normal dependency check
and must not add a test-only behavior to production entry points.

- [ ] **Step 7: Run installer tests and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_cli_install.InstallerTests -v`

Expected: failure because `install.sh` does not exist.

- [ ] **Step 8: Implement idempotent `install.sh`**

Follow the established renderer repository convention: handle `-h` and
`--help` first; reject all other arguments; resolve `SCRIPT_DIR`; require Python
3.10+; recreate a broken `.venv`; install `requirements.txt`; verify imports;
write a launcher that execs `run.sh`; use a fixed `$BIN_DIR/pdf-cleanup` path;
warn if `BIN_DIR` is absent from `PATH`; and print actionable recovery when the
checkout was moved. Do not include any private paths or orchestration terms.

Make it executable with `chmod 0755 install.sh` and add `.venv/`, `__pycache__/`,
`*.pyc`, and `.DS_Store` to `.gitignore`.

- [ ] **Step 9: Run CLI and installer tests and confirm GREEN**

Run: `.venv/bin/python -m unittest tests.test_cli_install -v`

Expected: all CLI and installation tests pass, including two consecutive
installs leaving one launcher.

- [ ] **Step 10: Check entry points manually from another directory**

```bash
REPO_DIR="$(pwd)"
cd /tmp
"$REPO_DIR/run.sh" --help
BIN_DIR="$(mktemp -d)" "$REPO_DIR/install.sh"
```

Expected: help exits `0`, the installer produces one executable, and its
`--help` also exits `0`.

- [ ] **Step 11: Check the task diff**

Run: `git diff --check && git status --short`

If commit authorization exists, commit with `git add main.py run.sh install.sh .gitignore tests/test_cli_install.py && git commit -m "feat: install pdf-cleanup on PATH"`.

---

### Task 7: End-to-End Fixtures, Documentation, and Public-Safety Verification

**Files:**

- Create: `LICENSE`
- Replace: `README.md`
- Replace: `docs/architecture.md`
- Modify: `AGENTS.md`
- Modify: `tests/helpers.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**

- Exercises the complete public CLI and installer; introduces no new runtime API.
- Documentation must describe the tool only and must not mention any private installation or repository-management system.

- [ ] **Step 1: Write a failing end-to-end synthetic PDF test**

Generate a three-page browser-style PDF at test runtime with repeated browser
headers and footers, article metadata, headings, prose, a list, an image, an
author card, related cards, and a site footer. Use a fake downloader returning
the fixture HTML and a fake renderer that captures Markdown. Define
`invoke_cli_with_synthetic_pdf() -> tuple[subprocess.CompletedProcess[str], str]`
in `tests/test_pipeline.py`; it creates all temporary inputs internally and
returns the completed CLI process plus captured Markdown.

```python
def test_end_to_end_keeps_article_and_removes_website_fluff(self):
    result, markdown = invoke_cli_with_synthetic_pdf()
    self.assertEqual(result.returncode, 0)
    self.assertIn("# Synthetic Article", markdown)
    self.assertIn("**Author:** Ada Example", markdown)
    self.assertIn("Final article paragraph.", markdown)
    self.assertNotIn("You might also like", markdown)
    self.assertNotIn("Newsletter", markdown)
    self.assertNotIn("1/3", markdown)
```

- [ ] **Step 2: Run the end-to-end test and confirm RED**

Run: `.venv/bin/python -m unittest tests.test_pipeline.EndToEndTests -v`

Expected: failure exposes whichever integration boundary is still incomplete;
verify the failure is about missing cleanup behavior, not a broken fixture.

- [ ] **Step 3: Make the minimum integration correction**

Wire dependency injection at `cleanup_pdf` through optional keyword-only
`web_extractor` and `pdf_inspector` callables so the test does not use network.
Do not add a public CLI flag for these internal test seams.

```python
def cleanup_pdf(
    input_path: Path,
    output_path: Path,
    renderer: str | None = None,
    *,
    pdf_inspector: Callable[[Path], PdfSnapshot] = inspect_pdf,
    web_extractor: Callable[[str], Article | None] = extract_web_article,
) -> tuple[Path, str]:
    snapshot = pdf_inspector(input_path)
    article, extraction_source = select_article(snapshot, web_extractor)
    executable = renderer or shutil.which("markdown-to-pdf")
    if executable is None:
        raise CleanupError("markdown-to-pdf was not found on PATH")
    result = render_with_markdown_to_pdf(
        article_to_markdown(article), output_path, executable
    )
    return result, extraction_source
```

- [ ] **Step 4: Run the complete deterministic suite**

Run: `.venv/bin/python -m unittest discover -s tests -v`

Expected: all unit, integration, CLI, and installer tests pass without network
access.

- [ ] **Step 5: Write public documentation and license**

Use an MIT `LICENSE`. Replace the starter README with:

- one-sentence purpose
- Python 3.10+ and `markdown-to-pdf` requirements
- clone-local and `install.sh` installation instructions
- complete synopsis and output-resolution table
- help, default output, directory output, and exact-file examples
- explanation of URL-assisted extraction with validated PDF fallback
- privacy note that source URLs may be fetched over the network
- browser-text-PDF limitation and explicit lack of OCR
- update and uninstall instructions
- development test command

Replace `docs/architecture.md` with the approved component flow, model
boundaries, validation algorithm, fallback heuristics, renderer process, and
test seams. Update `AGENTS.md` to name `install.sh`, `main.py`, the package
boundaries, red-green TDD command, versioning expectations, and public-safety
rules. Keep all documentation free of private terms and paths.

- [ ] **Step 6: Run the representative local article through the real renderer**

Set a shell variable to the representative browser-print PDF supplied with the
task, without copying it into the repository. Use a temporary output directory:

```bash
RESULT_DIR="$(mktemp -d)"
./run.sh "$ARTICLE_PDF" "$RESULT_DIR/cleaned.pdf"
pdfinfo "$RESULT_DIR/cleaned.pdf"
pdftotext "$RESULT_DIR/cleaned.pdf" -
```

Expected text: title, author, source, and all article sections. Forbidden text:
browser timestamp, page counters, promotional banner, `You might also like`,
related-card titles, navigation columns, privacy, and terms.

- [ ] **Step 7: Render and visually inspect every output page**

```bash
pdftoppm -png "$RESULT_DIR/cleaned.pdf" "$RESULT_DIR/page"
```

Inspect every rendered page. Expected: readable typography, no clipped or
overlapping text, no website images, no blank trailing page, and continuous
article section ordering. If inspection fails, add a regression test before
fixing the responsible extraction or Markdown logic.

- [ ] **Step 8: Verify installation using a temporary binary directory**

```bash
TEST_BIN="$(mktemp -d)"
BIN_DIR="$TEST_BIN" ./install.sh
BIN_DIR="$TEST_BIN" ./install.sh
cd /tmp
"$TEST_BIN/pdf-cleanup" --help
```

Expected: both installations succeed, `find "$TEST_BIN" -maxdepth 1 -type f`
lists exactly one launcher, and help exits `0` from an unrelated directory.

- [ ] **Step 9: Run final quality and public-safety checks**

```bash
.venv/bin/python -m unittest discover -s tests -v
git diff --check
git grep -Ein '/U[s]ers/|src/p[e]rsonal'
git status --short
```

Expected: tests pass; diff check is clean; the tracked-content scan returns no
matches; status contains only intentional project files and the approved design
documents. `markdown-to-pdf` is allowed because it is the public renderer's
command name, not a project-specific term.

- [ ] **Step 10: Leave publication to the user**

Do not create a GitHub repository, push, or open a pull request. Report the
verified test results, sample-PDF result, visual review, installed-command path,
and dirty working tree. Provide these user-run commands after replacing the
account placeholder themselves:

```bash
git add -A
git commit -m "feat: add browser article PDF cleanup"
gh repo create pdf-cleanup --public
git push -u origin main
```

The local repository already has an unpushed `origin` URL. The two publication
commands intentionally create the repository in the authenticated account and
then use that existing remote; do not mutate the remote automatically.
