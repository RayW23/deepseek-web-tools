import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deepseek_web.config import config_path, load_config, resolve_api_key, save_api_key
from deepseek_web.client import DeepSeekClient


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / "private" / "config.json"
        self.env = patch.dict(os.environ, {"DEEPSEEK_WEB_CONFIG": str(self.file), "DEEPSEEK_API_KEY": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_missing_file(self):
        self.assertEqual(load_config(), {})
        self.assertEqual(resolve_api_key(), "")

    def test_save_and_load_shared_by_client(self):
        self.assertEqual(save_api_key("file-key"), self.file)
        self.assertEqual(DeepSeekClient().api_key, "file-key")
        self.assertEqual(config_path(), self.file)
        self.assertEqual(load_config(), {"api_key": "file-key"})

    def test_precedence(self):
        save_api_key("file-key")
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-key"}):
            self.assertEqual(resolve_api_key(), "env-key")
            self.assertEqual(resolve_api_key("explicit-key"), "explicit-key")
        self.assertEqual(resolve_api_key(""), "")

    def test_malformed_config_does_not_echo_secret(self):
        self.file.parent.mkdir()
        self.file.write_text('{"api_key": "secret-private", broken', encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            load_config()
        self.assertNotIn("secret-private", str(caught.exception))
        self.assertEqual(resolve_api_key("explicit"), "explicit")

    def test_preserves_other_fields(self):
        save_api_key("old")
        self.file.write_text(json.dumps({"api_key": "old", "note": "keep"}), encoding="utf-8")
        save_api_key("new")
        self.assertEqual(load_config()["note"], "keep")

    def test_init_refuses_overwrite(self):
        save_api_key("", overwrite=False)
        with self.assertRaises(FileExistsError):
            save_api_key("new", overwrite=False)

    def test_bad_type_and_whitespace(self):
        for value in ("bad key", "line\nbreak", 123):
            with self.assertRaises(ValueError):
                save_api_key(value)
        self.file.parent.mkdir(exist_ok=True)
        self.file.write_text('{"api_key": 123}')
        with self.assertRaises(ValueError):
            load_config()
