import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from deepseek_web.client import Cancelled, DeepSeekClient, DeepSeekError, RateLimiter, search_payload, validate_url
from deepseek_web.output import render


RESULT = {"results": [{"title": "测试页面", "url": "https://example.com", "snippet": "短摘要",
                       "summary": "长摘要", "content": "", "rerank_score": 2.4, "authority": 3,
                       "site_name": None, "date": None, "site_icon": None}]}


class MockAPI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.requests.append((self.path, self.headers, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                status, body, headers = owner.responses.pop(0)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def client(self, **kwargs):
        return DeepSeekClient("test-key", base_url=self.url, limiter=RateLimiter(0), **kwargs)


class ValidationTests(unittest.TestCase):
    def test_unicode_and_operator_preservation(self):
        query = '中文 site:github.com OR site:example.com lang:zh after:2026'
        self.assertEqual(search_payload(query)["query"], query)
        self.assertEqual(search_payload("😀" * 128)["count"], 10)

    def test_invalid_search(self):
        for kwargs in ({"query": " "}, {"query": "字" * 129}, {"query": "q", "count": True},
                       {"query": "q", "count": 51}, {"query": "q", "need_content": 1},
                       {"query": "q", "ori_question": ""}, {"query": "q", "localization": "China"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_payload(**kwargs)

    def test_urls(self):
        for url in ("file:///a", "https://user:password@host", "https://", "https://a:bad", "https://a/\n"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        self.assertEqual(validate_url("https://example.com/中文"), "https://example.com/中文")

    def test_configuration(self):
        for kwargs in ({"api_key": ""}, {"api_key": "secret\nheader"},
                       {"api_key": "x", "base_url": "http://remote.example"},
                       {"api_key": "x", "base_url": "https://example.com/v1?x=y"},
                       {"api_key": "x", "timeout": float("nan")}):
            with self.assertRaises(ValueError):
                DeepSeekClient(**kwargs)
        self.assertEqual(DeepSeekClient("x", base_url="https://api.deepseek.com/v1/").base_url,
                         "https://api.deepseek.com/v1")


class TransportTests(unittest.TestCase):
    def test_search_contract(self):
        with MockAPI([(200, RESULT, {})]) as api:
            self.assertEqual(api.client().search("中文", 5, True, "问题", "::1"), RESULT)
            path, headers, body = api.requests[0]
            self.assertEqual(path, "/v1/tools/search")
            self.assertEqual(headers["Authorization"], "Bearer test-key")
            self.assertEqual(body, {"query": "中文", "count": 5, "need_content": True,
                                    "ori_question": "问题", "localization": "::1"})

    def test_fetch_contract(self):
        page = {"title": "Title", "content": "# Markdown"}
        with MockAPI([(200, page, {})]) as api:
            self.assertEqual(api.client().fetch("https://example.com"), page)
            self.assertEqual(api.requests[0][0], "/v1/tools/fetch")
            self.assertEqual(api.requests[0][2], {"url": "https://example.com"})

    def test_retry(self):
        for status in (408, 429, 500, 504):
            with self.subTest(status=status), MockAPI([(status, {}, {"Retry-After": "0"}), (200, RESULT, {})]) as api:
                self.assertEqual(api.client().search("q"), RESULT)
                self.assertEqual(len(api.requests), 2)

    def test_non_retryable_and_secret_redaction(self):
        for status in (400, 401, 402, 403, 404, 413):
            with self.subTest(status=status), MockAPI([(status, {"error": {"message": "test-key"}}, {})]) as api:
                with self.assertRaises(DeepSeekError) as caught:
                    api.client().search("q")
                self.assertEqual(caught.exception.status, status)
                self.assertNotIn("test-key", str(caught.exception))
                self.assertEqual(len(api.requests), 1)

    def test_redirect_is_not_followed(self):
        with MockAPI([(307, {}, {"Location": "https://example.com"})]) as api:
            with self.assertRaises(DeepSeekError) as caught:
                api.client().search("q")
            self.assertEqual(caught.exception.status, 307)

    def test_malformed_response(self):
        for body in (b"not json", [], {"results": [None]}, {"results": [{}]}):
            with MockAPI([(200, body, {})]) as api, self.assertRaises(DeepSeekError):
                api.client().search("q")

    def test_empty_results(self):
        with MockAPI([(200, {"results": []}, {})]) as api:
            self.assertEqual(api.client().search("q"), {"results": []})

    def test_cancel_before_request(self):
        event = threading.Event()
        event.set()
        with MockAPI([]) as api, self.assertRaises(Cancelled):
            api.client().search("q", cancel=event)
        self.assertEqual(api.requests, [])

    def test_long_retry_after_stops(self):
        with MockAPI([(429, {}, {"Retry-After": "120"})]) as api, self.assertRaises(DeepSeekError):
            api.client().search("q")
        self.assertEqual(len(api.requests), 1)

    def test_cli_subprocess(self):
        with MockAPI([(200, RESULT, {})]) as api:
            env = dict(os.environ, DEEPSEEK_API_KEY="test-key", DEEPSEEK_BASE_URL=api.url)
            run = subprocess.run([sys.executable, "-m", "deepseek_web", "search", "中文"],
                                 env=env, capture_output=True, encoding="utf-8", timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), RESULT)

    def test_cli_error_is_on_stderr(self):
        env = dict(os.environ, DEEPSEEK_API_KEY="", DEEPSEEK_WEB_CONFIG=str(__import__("pathlib").Path(__file__).parent / "missing-config-for-test.json"))
        run = subprocess.run([sys.executable, "-m", "deepseek_web", "search", "q"],
                             env=env, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(run.stdout, b"")
        self.assertTrue(run.stderr)

    def test_cli_help_is_utf8(self):
        run = subprocess.run([sys.executable, "-m", "deepseek_web", "--help"],
                             capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(run.returncode, 0)
        self.assertIn("网页搜索", run.stdout)

    def test_markdown_export(self):
        text = render(RESULT, "markdown")
        self.assertIn("https://example.com", text)
        self.assertIn("长摘要", text)


if __name__ == "__main__":
    unittest.main()
