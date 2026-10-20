import argparse
import os
import getpass
import sys
from pathlib import Path

from .client import DeepSeekClient, DeepSeekError
from .output import render


def main(argv=None):
    # UTF-8 also applies to help and errors when redirected on Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="dsweb", description="DeepSeek 网页搜索与抓取：CLI / GUI / MCP")
    parser.add_argument("--config", type=Path, help="使用指定的 JSON 配置文件")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="搜索网页，支持 site: / lang: / after: 等语法")
    search.add_argument("query")
    search.add_argument("--count", type=int, default=10)
    search.add_argument("--need-content", action="store_true")
    search.add_argument("--ori-question")
    search.add_argument("--localization", default="", help="优先本地结果的 IPv4/IPv6 地址")
    fetch = sub.add_parser("fetch", help="抓取单个网页的 Markdown 正文")
    fetch.add_argument("url")
    for command in (search, fetch):
        command.add_argument("--format", choices=("json", "markdown"), default="json")
        command.add_argument("-o", "--output", type=Path)
        command.add_argument("--timeout", type=float, default=20)
        command.add_argument("--retries", type=int, default=2)
    sub.add_parser("gui", help="打开交互式桌面界面")
    sub.add_parser("mcp", help="启动供 Harness 使用的 MCP stdio 服务")
    config = sub.add_parser("harness-config", help="生成本机 Harness --patch 配置（不含密钥）")
    config.add_argument("-o", "--output", type=Path)
    settings = sub.add_parser("config", help="显示配置路径，创建文件或安全输入 API Key")
    group = settings.add_mutually_exclusive_group()
    group.add_argument("--init", action="store_true")
    group.add_argument("--set-key", action="store_true")
    args = parser.parse_args(argv)
    if args.config:
        os.environ["DEEPSEEK_WEB_CONFIG"] = str(args.config.expanduser().resolve())
    try:
        if args.command == "config":
            from .config import config_path, save_api_key
            if args.init:
                save_api_key("", overwrite=False)
            elif args.set_key:
                key = getpass.getpass("DeepSeek API Key（输入不回显）: ").strip()
                if not key:
                    raise ValueError("API Key 不能为空")
                save_api_key(key)
            print(config_path())
            return 0
        if args.command == "harness-config":
            from .harness import configuration
            text = configuration()
            if args.output:
                with args.output.open("x", encoding="utf-8") as handle:
                    handle.write(text)
            else:
                print(text, end="")
            return 0
        if args.command == "gui":
            from .gui import main as run_gui
            run_gui()
            return 0
        if args.command == "mcp":
            from .mcp_server import main as run_mcp
            run_mcp()
            return 0
        client = DeepSeekClient(timeout=args.timeout, retries=args.retries)
        if args.command == "search":
            result = client.search(args.query, args.count, args.need_content, args.ori_question, args.localization)
        else:
            result = client.fetch(args.url)
        text = render(result, args.format)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return 0
    except (ValueError, DeepSeekError, OSError, ImportError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
