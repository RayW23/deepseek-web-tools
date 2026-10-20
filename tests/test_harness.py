import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from deepseek_web.harness import configuration


class HarnessConfigTests(unittest.TestCase):
    def test_source_config_no_secret(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret-never-print"}):
            text = configuration()
        self.assertTrue("- insert:" in text)
        self.assertIn(json.dumps(str(Path(sys.executable).resolve()), ensure_ascii=False), text)
        self.assertIn('["-m", "deepseek_web", "mcp"]', text)
        self.assertNotIn("secret-never-print", text)

    def test_frozen_config(self):
        with patch.object(sys, "frozen", True, create=True):
            self.assertIn('args: ["mcp"]', configuration())

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "local.yml"
            command = [sys.executable, "-m", "deepseek_web", "harness-config", "-o", str(dest)]
            first = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = dest.read_bytes()
            second = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(second.returncode, 1)
            self.assertEqual(dest.read_bytes(), original)
