from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliInstallTests(TestCase):
    def test_named_install_replaces_only_the_requested_launcher(self):
        with TemporaryDirectory() as directory:
            environment = dict(os.environ, BIN_DIR=directory)
            for _ in range(2):
                result = subprocess.run(
                    [REPO_ROOT / "install.sh", "--name", "contract-probe"],
                    cwd="/", env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(list(Path(directory).iterdir()), [Path(directory) / "contract-probe"])
                help_result = subprocess.run(
                    [Path(directory) / "contract-probe", "--help"],
                    cwd="/", capture_output=True, text=True,
                )
                self.assertEqual(help_result.returncode, 0, help_result.stderr)

    def test_help_and_invalid_arguments_do_not_create_the_destination(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "absent"
            for args, success in [
                (["--help"], True), (["-h"], True),
                (["--name", "custom", "--help"], True),
                (["--unknown"], False), (["--name"], False),
                (["--name", "../escape"], False), (["--name", ""], False),
            ]:
                with self.subTest(args=args):
                    result = subprocess.run(
                        ["/bin/bash", REPO_ROOT / "install.sh", *args],
                        env=dict(os.environ, BIN_DIR=str(destination), PATH=""),
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode == 0, success, result.stderr)
                    self.assertIn("Usage:", result.stdout if success else result.stderr)
                    self.assertFalse(destination.exists())

    def test_named_install_repairs_an_unusable_venv_and_installs_dependencies(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["install.sh", "run.sh", "main.py", "requirements.txt"]:
                shutil.copy2(REPO_ROOT / name, root / name)
            shutil.copytree(REPO_ROOT / "pdf_cleanup", root / "pdf_cleanup")
            python = root / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\nexit 1\n")
            python.chmod(0o755)
            result = subprocess.run(
                [root / "install.sh", "--name", "repaired"],
                env=dict(os.environ, BIN_DIR=str(root / "bin")),
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [python, "-c", "import pdfplumber, trafilatura"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([root / "bin/repaired", "--help"], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

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
