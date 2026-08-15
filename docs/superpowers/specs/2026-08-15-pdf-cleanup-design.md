# PDF Cleanup Design

## Summary

`pdf-cleanup` converts a browser-generated article PDF into a cleaner PDF that
contains only the article title, author, source website, and article text. It
reconstructs the content as temporary Markdown and delegates final rendering to
the existing `markdown-to-pdf` command.

The first release targets PDFs produced by a browser's print dialog that contain
a usable text layer. It does not support scanned or image-only PDFs.

## Goals

- Provide one reproducible command for removing website chrome from article
  PDFs.
- Preserve the article's words and meaningful structure rather than paraphrasing
  it.
- Retain the title, author, source URL, headings, paragraphs, lists, quotes, and
  code blocks when they can be identified reliably.
- Remove navigation, sidebars, advertisements, calls to action, related-content
  sections, browser headers and footers, page numbers, and images.
- Prefer structured content from the source webpage when it still matches the
  PDF snapshot.
- Fall back to layout-aware extraction from the PDF when the source webpage is
  unavailable, changed, or absent.
- Install `pdf-cleanup` as a normal executable on `PATH`.

## Non-goals

- OCR for scanned or image-only PDFs.
- Pixel-perfect reproduction of the source website.
- Retaining decorative or article images in the output.
- Semantic rewriting, summarization, or correction of the author's prose.
- General-purpose extraction from arbitrary reports, forms, books, slide decks,
  or multi-column academic papers.
- Bundling or reimplementing the PDF renderer.

## Command-line interface

```text
pdf-cleanup <input.pdf> [output]
```

Arguments:

- `input.pdf` is the browser-generated PDF to clean.
- `output` is optional. If it names an existing directory, the output uses the
  input filename inside that directory. Otherwise it is treated as the exact
  output filename.

Output resolution:

```text
article.pdf                         -> article-cleaned.pdf
article.pdf /tmp/clean/             -> /tmp/clean/article.pdf
article.pdf /tmp/nicer.pdf          -> /tmp/nicer.pdf
```

The command refuses to overwrite the input path. Existing output files follow
the collision behavior of `markdown-to-pdf`, including its interactive prompt
and non-interactive versioned filename behavior.

`-h` and `--help` are handled before dependency checks or other side effects.
Help includes a summary, synopsis, argument descriptions, requirements, and
worked examples. Missing arguments print the same usage content to standard
error and exit nonzero.

## Implementation choice

The implementation uses Python 3. This gives the shortest path to mature,
layout-aware PDF extraction and article extraction while matching the
installation conventions of the renderer it invokes.

Initial runtime dependencies:

- pdfplumber for PDF metadata, text blocks, font information, links,
  coordinates, and text-layer detection.
- Trafilatura for fetching and extracting structured article content and
  metadata from a source webpage.
- The external `markdown-to-pdf` executable for final PDF rendering.

The exact Python dependency versions are pinned in `requirements.txt` so a
fresh installation is repeatable.

## Architecture

The implementation is divided into small units with pure logic separated from
filesystem, network, PDF, and process boundaries.

```text
CLI and path resolution
        |
        v
PDF inspection -----> source URL candidates
        |                       |
        |                       v
        |               webpage extraction
        |                       |
        |               snapshot validation
        |                       |
        +----------+------------+
                   |
          accepted article model
                   |
                   v
             Markdown writer
                   |
                   v
        markdown-to-pdf subprocess
                   |
                   v
             cleaned PDF
```

### Article model

Both extraction paths produce the same internal article model:

- title
- author, when available
- source URL, when available
- source site or hostname
- ordered content blocks

Content blocks represent headings, paragraphs, lists, block quotes, and code.
The Markdown writer depends only on this model, not on PDF or HTML objects.

### PDF inspection

Inspection opens the document once and records:

- document metadata and page count
- link annotations and printed URLs
- text blocks with bounding boxes, font sizes, and font styles
- normalized page text for source-validation and fallback extraction

A browser-print PDF is considered usable when it has enough extractable text to
form prose. An empty or negligible text layer returns an error explaining that
OCR is not supported yet.

### Source URL discovery

URL candidates come from link annotations, printed footer URLs, and document
metadata. Candidates are ranked using these signals:

1. Repetition across pages
2. A path that resembles the document title
3. Same-site frequency across links
4. Penalties for account, sign-in, social, tracking, and asset URLs

Only HTTP and HTTPS URLs are eligible. Fragments and common tracking parameters
are removed before comparison and display.

### Webpage extraction and validation

When a plausible source URL is available, the command fetches it with bounded
timeouts and redirects, then asks Trafilatura for article content and metadata.
Network or parsing failures are warnings and automatically select the PDF
fallback.

Webpage content is accepted only when it still represents the PDF snapshot.
Validation compares normalized title text and multiple samples from the PDF
body against the extracted webpage prose. It requires strong title agreement
and substantial ordered-text overlap. This prevents a redirected, redesigned,
or replaced page from silently changing the saved article.

The accepted webpage representation supplies headings, lists, quotes, code,
author metadata, and content boundaries. Links inside article prose may be
retained, but images and embedded media are always discarded.

### Layout-aware PDF fallback

The fallback reconstructs the article from text blocks and typography:

1. Detect the dominant body font size and principal prose column.
2. Remove repeated blocks in top and bottom page bands, including browser
   timestamps, titles, source URLs, and page numbers.
3. Exclude blocks outside the principal article column when they behave like a
   sidebar or navigation rail.
4. Infer the title from the strongest early heading and infer the byline from
   nearby author-labelled or typographically distinct text.
5. Classify headings relative to the body font and preserve paragraph, list,
   quote, and code boundaries where the layout provides enough evidence.
6. Stop before common post-article regions such as author cards, related
   content, newsletter calls to action, and site-wide footers.

Boundary phrases are signals rather than the sole decision. Typography,
position, link density, prose density, and cross-page continuity contribute to
the decision so the fallback is not tied to one website.

### Markdown generation

The generated Markdown begins with the title and a compact metadata block for
the author and source. The body follows with normalized structural markup.

Markdown is written to a temporary directory and is deleted after successful or
failed rendering. It is not placed beside the source PDF. Text normalization is
limited to repairing extraction artifacts such as wrapped lines, repeated
whitespace, and soft hyphenation. It must not rewrite the prose.

### Rendering

The renderer is discovered with `PATH`. Its absence is reported before network
access or output creation, with an actionable message naming the missing
`markdown-to-pdf` command.

The command invokes:

```text
markdown-to-pdf <temporary.md> --out <resolved-output.pdf>
```

Subprocess output is streamed to the caller. A nonzero renderer exit is returned
as a `pdf-cleanup` failure, and no success message is printed.

## Installation

`run.sh` resolves the repository root with `BASH_SOURCE`, selects the private
virtual environment when present, and otherwise uses `python3`.

`install.sh`:

1. Handles help before side effects.
2. Creates or repairs a private virtual environment in the checkout.
3. Installs the pinned requirements.
4. Writes one executable launcher at `$BIN_DIR/pdf-cleanup`, defaulting to
   `$HOME/.local/bin`.
5. Overwrites that same launcher on repeated runs.
6. Warns with an actionable fix when `BIN_DIR` is not on `PATH`.

Both scripts work from any current directory and contain no machine-specific
paths.

## Error handling

Errors are concise and sent to standard error. The command fails for:

- missing or unreadable input
- a non-PDF input
- encrypted PDFs that cannot be opened
- image-only or effectively empty PDFs
- an output path equal to the input path
- an invalid or unwritable output parent
- missing Python runtime dependencies
- a missing `markdown-to-pdf` executable
- renderer failure

Source fetching and HTML extraction failures do not fail the command when PDF
fallback remains possible. The command reports that it used the fallback.

Temporary files are cleaned up in every exit path. Partial output produced by a
failed renderer is removed only when it was created by the current invocation
and did not exist before the invocation.

## Security and public-repository safety

- HTML is treated as untrusted input and is never executed.
- Fetching does not enable browser scripting.
- Network requests use timeouts, a redirect limit, and HTTP or HTTPS only.
- The generated Markdown contains only the extracted article representation,
  not arbitrary active HTML.
- Logs do not include environment variables, credentials, or response bodies.
- Tracked files contain no personal names, machine-specific paths, secrets, or
  project-specific references.

## Testing strategy

Development follows red-green TDD. Every behavior begins with a failing test,
the failure is checked for the intended reason, and only then is implementation
added.

### Unit tests

- CLI parsing and complete help behavior
- default, directory, and exact-file output resolution
- rejection of input/output path collisions
- URL normalization and candidate ranking
- repeated header and footer detection
- title, author, heading, and end-boundary inference
- webpage/PDF snapshot overlap scoring
- article-model-to-Markdown rendering
- cleanup of temporary files and partial outputs

### Integration tests

- A synthetic browser-style PDF with repeated browser chrome and unrelated
  post-article sections
- Web extraction accepted for matching fixture HTML
- Web extraction rejected for changed fixture HTML
- Automatic fallback when networking fails
- Invocation of a fake `markdown-to-pdf` executable with the expected Markdown
  and output arguments
- Installer behavior in a temporary `BIN_DIR`, including two consecutive runs
- Direct invocation from an unrelated current directory
- The representative browser-print article PDF used during development

Tests that require network access are excluded from the normal suite. Webpage
responses are fixture-backed so the suite is deterministic.

## Acceptance criteria

- The representative article PDF produces a readable PDF containing its title,
  author, source, section headings, and complete article prose.
- The result excludes browser headers and footers, page numbers, promotional
  banners, related articles, navigation, site footer, sidebars, and images.
- The original PDF is never overwritten by default.
- Help succeeds without performing dependency checks or side effects.
- Missing required arguments print usage to standard error and exit nonzero.
- The complete deterministic test suite passes.
- The installer is idempotent and leaves exactly one working executable in a
  temporary binary directory.
- A tracked-content scan finds no personal data, machine-specific paths,
  secrets, or project-specific terms.
