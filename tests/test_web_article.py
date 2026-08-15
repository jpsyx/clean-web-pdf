from unittest import TestCase

from pdf_cleanup.web_article import (
    extract_web_article,
    parse_markdown_blocks,
    repair_emphasis_spacing,
)
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


class EmphasisSpacingTests(TestCase):
    """HTML-to-markdown conversion drops the space that sat outside a
    `<strong>`/`<em>` tag, gluing the emphasised run to the next word."""

    def test_space_restored_after_a_bold_run(self):
        self.assertEqual(
            repair_emphasis_spacing("- **Grill the plan**until it has real decisions"),
            "- **Grill the plan** until it has real decisions",
        )

    def test_space_restored_after_an_italic_run(self):
        self.assertEqual(repair_emphasis_spacing("*demo*before review"), "*demo* before review")

    def test_punctuation_after_a_run_is_left_alone(self):
        self.assertEqual(repair_emphasis_spacing("**Merge, cleanup last**: pure deletion"), "**Merge, cleanup last**: pure deletion")
        self.assertEqual(repair_emphasis_spacing("**done**, then ship"), "**done**, then ship")

    def test_a_run_already_followed_by_a_space_is_unchanged(self):
        self.assertEqual(repair_emphasis_spacing("**Build wide** and ship narrow"), "**Build wide** and ship narrow")

    def test_a_parenthesised_run_does_not_gain_a_leading_space(self):
        self.assertEqual(repair_emphasis_spacing("(**bold**) and on"), "(**bold**) and on")

    def test_text_without_emphasis_is_untouched(self):
        self.assertEqual(repair_emphasis_spacing("a plain line with 2 * 3 arithmetic"), "a plain line with 2 * 3 arithmetic")

    def test_parse_markdown_blocks_applies_the_repair(self):
        blocks = parse_markdown_blocks("- **Grill the plan**until it has real decisions in it")
        self.assertEqual(blocks[0].text, "**Grill the plan** until it has real decisions in it")

    def test_fenced_code_keeps_its_asterisks_verbatim(self):
        blocks = parse_markdown_blocks("```\nrate = **base**mult\n```")
        self.assertEqual(blocks[0].kind, BlockKind.CODE)
        self.assertEqual(blocks[0].text, "rate = **base**mult")
