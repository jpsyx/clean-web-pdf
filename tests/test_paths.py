from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from pdf_cleanup.errors import CleanupError
from pdf_cleanup.paths import resolve_output_path, validate_input


class PathTests(TestCase):
    def test_default_output_is_cleaned_sibling(self):
        self.assertEqual(resolve_output_path(Path("/tmp/article.pdf"), None), Path("/tmp/article-cleaned.pdf"))

    def test_existing_directory_preserves_input_filename(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(resolve_output_path(Path("/tmp/article.pdf"), directory), Path(directory) / "article.pdf")

    def test_exact_file_is_preserved(self):
        self.assertEqual(resolve_output_path(Path("/tmp/article.pdf"), "/tmp/nicer.pdf"), Path("/tmp/nicer.pdf"))

    def test_input_output_collision_is_rejected(self):
        with self.assertRaisesRegex(CleanupError, "overwrite the input"):
            resolve_output_path(Path("/tmp/article.pdf"), "/tmp/article.pdf")

    def test_validate_input_rejects_missing_file(self):
        with self.assertRaisesRegex(CleanupError, "does not exist"):
            validate_input(Path("/definitely/missing/article.pdf"))
