from unittest import TestCase

from pdf_cleanup.web_article import extract_web_article, parse_markdown_blocks
from pdf_cleanup.models import BlockKind


class WebArticleTests(TestCase):
    def test_extracts_metadata_and_stops_at_related_content(self):
        html = """
        <html><head><title>Clean Article | Blog</title>
        <meta name="author" content="Ada Example"></head><body>
        <nav>Navigation noise</nav><article><h1>Clean Article</h1>
        <p>The first paragraph has enough article text for extraction.</p>
        <h2>A section</h2><p>The second paragraph continues the saved article text.</p>
        <h2>You might also like</h2><h2>Unrelated story</h2></article></body></html>
        """
        article = extract_web_article("https://example.com/clean", lambda _url: html)
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article.title, "Clean Article")
        self.assertEqual(article.author, "Ada Example")
        self.assertTrue(all("Unrelated" not in block.text for block in article.blocks))

    def test_markdown_blocks_preserve_headings_lists_and_quotes(self):
        blocks = parse_markdown_blocks("# Title\n\nBody\n\n- one\n- two\n\n> quote")
        self.assertEqual([block.kind for block in blocks], [BlockKind.HEADING, BlockKind.PARAGRAPH, BlockKind.LIST_ITEM, BlockKind.LIST_ITEM, BlockKind.QUOTE])
