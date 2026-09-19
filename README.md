# clean-web-pdf

Clean browser-printed article PDFs and render a readable copy containing the
article title, author, source, headings, and prose.

## Usage

```sh
clean-web-pdf <input.pdf> [output]
```

Requires Python 3.10+ and `markdown-to-pdf`. With no output argument,
`article.pdf` becomes `article-cleaned.pdf` beside the source. An existing
directory keeps the source filename; another path is the exact output filename.

```sh
./install.sh
clean-web-pdf article.pdf
clean-web-pdf article.pdf ~/Documents/clean/
clean-web-pdf article.pdf ~/Documents/article-readable.pdf
clean-web-pdf --help
```

## Prerequisites

`clean-web-pdf` uses the `markdown-to-pdf` command to render the cleaned
Markdown back into a PDF. Install it before running `clean-web-pdf`.

If you do not already have the renderer checkout, clone it and install it:

```sh
git clone https://github.com/jpsyx/markdown-to-pdf.git markdown-to-pdf
cd markdown-to-pdf
./install.sh
```

If the checkout already exists, just update and reinstall it:

```sh
cd markdown-to-pdf
git pull
./install.sh
```

The installer places the `markdown-to-pdf` executable in
`$HOME/.local/bin` by default. Make sure that directory is on your `PATH`.

The tool tries a source URL printed in the PDF, accepting webpage content only
when it matches the saved PDF text. Otherwise it uses the PDF's layout and text
layer. Scanned or image-only PDFs are not supported yet.

## Development

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
```
