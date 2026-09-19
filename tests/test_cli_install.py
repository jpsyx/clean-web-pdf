from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliInstallTests(TestCase):
    def test_help_uses_clean_web_pdf_command_name(self):
        result = subprocess.run(
            [REPO_ROOT / "run.sh", "--help"],
            cwd="/",
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: clean-web-pdf", result.stdout)
        self.assertIn("clean-web-pdf article.pdf", result.stdout)

    def test_installer_writes_one_clean_web_pdf_launcher(self):
        with TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["BIN_DIR"] = directory

            for _ in range(2):
                result = subprocess.run(
                    [REPO_ROOT / "install.sh"],
                    cwd="/",
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            launchers = list(Path(directory).iterdir())
            self.assertEqual(launchers, [Path(directory) / "clean-web-pdf"])
            self.assertTrue(os.access(launchers[0], os.X_OK))


if __name__ == "__main__":
    import unittest

    unittest.main()
