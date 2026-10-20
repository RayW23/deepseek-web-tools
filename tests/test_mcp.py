import os
import json
import tempfile
from pathlib import Path
import sys
import unittest

from test_client import MockAPI, RESULT

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@unittest.skipUnless(HAS_MCP, 'Install .[mcp] to test the MCP stdio adapter')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_discovery_and_calls(self):
        with MockAPI([(200, RESULT, {}), (200, {"title": "Page", "content": "# Body"}, {}),
                      (402, {}, {})]) as api:
            binary = os.getenv("DSWEB_TEST_EXE")
            params = StdioServerParameters(command=binary or sys.executable, args=["mcp"] if binary else ["-m", "deepseek_web", "mcp"],
                env=dict(os.environ, DEEPSEEK_API_KEY="test-key", DEEPSEEK_BASE_URL=api.url))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self.assertEqual({t.name for t in listed.tools}, {"search", "fetch"})
                    result = await session.call_tool("search", {"query": "中文"})
                    self.assertFalse(result.isError)
                    self.assertIn("example.com", str(result.content))
                    result = await session.call_tool("fetch", {"url": "https://example.com"})
                    self.assertFalse(result.isError)
                    self.assertIn("Body", str(result.content))
                    invalid = await session.call_tool("search", {"query": ""})
                    self.assertTrue(invalid.isError)
                    failed = await session.call_tool("fetch", {"url": "https://example.com"})
                    self.assertTrue(failed.isError)
                    self.assertIn("402", str(failed.content))


    async def test_config_key_reloads_without_server_restart(self):
        with tempfile.TemporaryDirectory() as directory, MockAPI([(200, RESULT, {}), (200, RESULT, {})]) as api:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"api_key": "first-key"}), encoding="utf-8")
            binary = os.getenv("DSWEB_TEST_EXE")
            params = StdioServerParameters(command=binary or sys.executable,
                args=["mcp"] if binary else ["-m", "deepseek_web", "mcp"],
                env=dict(os.environ, DEEPSEEK_API_KEY="", DEEPSEEK_WEB_CONFIG=str(config), DEEPSEEK_BASE_URL=api.url))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.assertFalse((await session.call_tool("search", {"query": "q"})).isError)
                    config.write_text(json.dumps({"api_key": "second-key"}), encoding="utf-8")
                    self.assertFalse((await session.call_tool("search", {"query": "q"})).isError)
            self.assertEqual([r[1]["Authorization"] for r in api.requests], ["Bearer first-key", "Bearer second-key"])


if __name__ == "__main__":
    unittest.main()
