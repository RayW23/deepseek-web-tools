import time
import tempfile
import json
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import patch

from deepseek_web.gui import App
from test_client import MockAPI, RESULT


class GUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.app = App(self.root)
        self.app.key.set("test-key")

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def finish_request(self):
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.root.update()
        self.assertFalse(self.app.busy)

    def test_search_select_fetch_and_export_state(self):
        page = {"title": "Fetched page", "content": "# Full body"}
        with MockAPI([(200, RESULT, {}), (200, page, {})]) as api:
            with patch.dict("os.environ", {"DEEPSEEK_BASE_URL": api.url}):
                self.app.query.set("中文")
                self.app.search_button.invoke()
                self.finish_request()
                self.assertEqual(len(self.app.tree.get_children()), 1)
                self.app.tree.selection_set("0")
                self.root.update()
                self.assertIn("长摘要", self.app.preview.get("1.0", "end"))
                self.app.selected_button.invoke()
                self.finish_request()
                self.assertEqual(self.app.export_data, page)
                self.assertIn("Full body", self.app.preview.get("1.0", "end"))
                self.app.show_json()
                self.assertIn('"title"', self.app.preview.get("1.0", "end"))


    def test_save_key_button_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            with patch.dict("os.environ", {"DEEPSEEK_WEB_CONFIG": str(config)}):
                self.app.key.set("gui-test-key")
                self.app.save_config()
                self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["api_key"], "gui-test-key")
                self.assertIn(str(config.resolve()), self.app.status.get())


if __name__ == "__main__":
    unittest.main()
