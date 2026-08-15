from unittest import TestCase

from pdf_cleanup.markdown import article_to_markdown
from pdf_cleanup.models import Article, BlockKind, ContentBlock


class MarkdownTests(TestCase):
    def test_renders_article_metadata_and_body(self):
        article = Article("Title", "Ada Example", "https://example.com/article", "example.com", (ContentBlock(BlockKind.HEADING, "Section", 2), ContentBlock(BlockKind.PARAGRAPH, "Body.")))
        output = article_to_markdown(article)
        self.assertIn("# Title", output)
        self.assertIn("**Author:** Ada Example", output)
        self.assertIn("## Section", output)
        self.assertIn("Body.", output)
