# Architecture

`pdf-cleanup` extracts an article from a browser-printed PDF and renders a
clean PDF through the installed `markdown-to-pdf` command.

## Flow

```
run.sh <input.pdf> [output]
  → main.py
    → pdf_source.py (layout and URL inspection)
    → web_article.py (validated webpage extraction)
    → pdf_article.py (layout fallback)
    → markdown.py (article model to Markdown)
    → pipeline.py (temporary Markdown and renderer process)
```

The web path is accepted only when title and ordered body shingles overlap the
PDF snapshot. The fallback removes repeated page chrome, isolates the principal
prose column, infers typography-based headings, and stops before related-content
or call-to-action regions. Images and active HTML are never copied to output.
