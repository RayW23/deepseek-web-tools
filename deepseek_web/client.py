"""Shared transport and validation for the official DeepSeek web APIs."""

from __future__ import annotations

from .config import resolve_api_key

import ipaddress
import json
import math
import os
import random
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class DeepSeekError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class Cancelled(DeepSeekError):
    pass


def validate_url(url: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 8192:
        raise ValueError("URL 必须为 1～8192 个字符")
    try:
        parts = urlsplit(url)
        port = parts.port
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username is not None or parts.password is not None
                or any(c.isspace() or ord(c) < 32 for c in url)):
            raise ValueError
    except ValueError:
        raise ValueError("请输入含主机名且不带用户名或密码的 HTTP/HTTPS URL") from None
    return url


def search_payload(query: str, count: int = 10, need_content: bool = False,
                   ori_question: str | None = None, localization: str = "") -> dict:
    if not isinstance(query, str) or not query.strip() or not 1 <= len(query) <= 128:
        raise ValueError("query 必须为 1～128 个 Unicode 字符，且不能全为空白")
    if type(count) is not int or not 1 <= count <= 50:
        raise ValueError("count 必须为 1～50 的整数")
    if type(need_content) is not bool:
        raise ValueError("need_content 必须为布尔值")
    if ori_question is not None and (not isinstance(ori_question, str)
                                     or not 1 <= len(ori_question) <= 128):
        raise ValueError("ori_question 必须为 1～128 个字符或 null")
    if not isinstance(localization, str):
        raise ValueError("localization 必须是 IP 地址字符串")
    if localization:
        try:
            ipaddress.ip_address(localization)
        except ValueError:
            raise ValueError("localization 必须是有效的 IPv4/IPv6 地址") from None
    payload = dict(query=query, count=count, need_content=need_content, localization=localization)
    if ori_question is not None:
        payload["ori_question"] = ori_question
    return payload


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the API key through a redirect.


class RateLimiter:
    """Process-local spacing, independently for search and fetch (below 5 QPS)."""
    def __init__(self, interval: float = 0.21):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_at: dict[str, float] = {}

    def wait(self, operation: str, cancel: threading.Event):
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_at.get(operation, now))
            self.next_at[operation] = slot + self.interval
        if cancel.wait(max(0, slot - now)):
            raise Cancelled("操作已取消")


_LIMITER = RateLimiter()
_HINTS = {401: "API Key 缺失或无效", 402: "余额不足，请充值后重试",
          403: "抓取被安全策略拒绝", 404: "未能提取目标网页正文",
          429: "请求过于频繁，请稍后重试"}


class DeepSeekClient:
    def __init__(self, api_key: str | None = None, *, base_url: str | None = None,
                 timeout: float = 20, retries: int = 2, limiter: RateLimiter | None = None):
        self.api_key = resolve_api_key(api_key)
        if not self.api_key or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key):
            raise ValueError("请在配置文件、DEEPSEEK_API_KEY 或界面中设置有效 API Key")
        base = (base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
        validate_url(base)
        parts = urlsplit(base)
        if parts.query or parts.fragment or parts.path not in ("", "/v1"):
            raise ValueError("Base URL 必须为服务根地址或以 /v1 结尾")
        if parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("非本机 API 地址必须使用 HTTPS")
        self.base_url = base if parts.path == "/v1" else base + "/v1"
        if not math.isfinite(timeout) or timeout <= 0 or type(retries) is not int or not 0 <= retries <= 5:
            raise ValueError("timeout 必须为正数，retries 必须为 0～5 的整数")
        self.timeout, self.retries = timeout, retries
        self.limiter = limiter or _LIMITER
        self.opener = build_opener(_NoRedirect())

    def search(self, query: str, count: int = 10, need_content: bool = False,
               ori_question: str | None = None, localization: str = "", *,
               cancel: threading.Event | None = None) -> dict:
        data = self._post("search", search_payload(query, count, need_content, ori_question, localization), cancel)
        if not isinstance(data.get("results"), list) or any(
                not isinstance(r, dict) or not all(isinstance(r.get(k), str) for k in
                ("title", "url", "snippet", "summary", "content")) for r in data["results"]):
            raise DeepSeekError("Search 响应格式不正确")
        return data

    def fetch(self, url: str, *, cancel: threading.Event | None = None) -> dict:
        data = self._post("fetch", {"url": validate_url(url)}, cancel)
        if not all(isinstance(data.get(k), str) for k in ("title", "content")):
            raise DeepSeekError("Fetch 响应格式不正确")
        return data

    def _post(self, operation: str, payload: dict, cancel: threading.Event | None) -> dict:
        cancel = cancel or threading.Event()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        for attempt in range(self.retries + 1):
            self.limiter.wait(operation, cancel)
            request = Request(self.base_url + "/tools/" + operation, data=body,
                              headers={"Authorization": "Bearer " + self.api_key,
                                       "Content-Type": "application/json", "Accept": "application/json"})
            retry_after = None
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    raw = response.read()
                if cancel.is_set():
                    raise Cancelled("操作已取消")
                try:
                    data = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise DeepSeekError("API 返回了无效的 JSON") from None
                if not isinstance(data, dict):
                    raise DeepSeekError("API 响应必须为 JSON 对象")
                return data
            except HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get("Retry-After")
                # Do not echo arbitrary upstream error bodies which can contain secrets.
                exc.close()
                error = DeepSeekError(f"HTTP {status}：" + _HINTS.get(status, "DeepSeek API 请求失败"), status)
                retryable = status in (408, 429) or 500 <= status <= 599
            except (URLError, TimeoutError, OSError):
                error = DeepSeekError("网络连接失败或超时，请检查网络和 API 地址")
                retryable = True
            if not retryable or attempt == self.retries:
                raise error
            delay = min(8, 2 ** attempt) + random.uniform(0, 0.25)
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    try:
                        delay = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        pass
                if not math.isfinite(delay):
                    delay = 1
                # Avoid sleeping indefinitely; report long rate limits instead of retrying early.
                if delay > 30:
                    raise error
            if cancel.wait(max(0, delay)):
                raise Cancelled("操作已取消")
        raise AssertionError("unreachable")
