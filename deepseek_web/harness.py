"""Generate a Cordis overlay using this installation's executable."""
import json
import sys
from pathlib import Path

from .config import config_path


def configuration() -> str:
    executable = str(Path(sys.executable).resolve())
    args = ["mcp"] if getattr(sys, "frozen", False) else ["-m", "deepseek_web", "mcp"]
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    return (
        "# Generated for this installation; regenerate after moving it. No secrets included.\n"
        "- insert:\n"
        "    - id: deepseek-web\n"
        "      name: '@deepseek-ai/dsh-mcp-client'\n"
        "      config:\n"
        "        serverName: deepseek_web\n"
        "        transport: stdio\n"
        f"        command: {quote(executable)}\n"
        f"        args: {quote(args)}\n"
        "        env:\n"
        f"          DEEPSEEK_WEB_CONFIG: {quote(str(config_path()))}\n"
        "          DEEPSEEK_API_KEY: !!js process.env.DEEPSEEK_API_KEY || ''\n"
        "        toolCallTimeoutMs: 180000\n"
        "        failOnStartupError: true\n"
    )
