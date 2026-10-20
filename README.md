# DeepSeek Web Tools

为 DeepSeek 原生 Search / Fetch API 编写的工具，同一套请求核心提供三种入口：

- **CLI**：脚本调用、JSON 管道、Markdown 文件导出。
- **桌面 GUI**：中文交互界面，搜索参数、结果表格、摘要预览、双击抓取、原始 JSON、导出与取消。
- **Harness 集成**：MCP stdio 服务，通过官方 `@deepseek-ai/dsh-mcp-client` 插件注册 `search` 和 `fetch`。

采用 Python 3.11+。CLI 和 GUI 不需要第三方 Python 包；GUI 需要 Tk（Windows 官方 Python 安装器默认提供；Linux 通常需要安装 `python3-tk`）。MCP 使用官方 Python SDK v1，依赖限定 `<2`，避免 SDK v2 的破坏性 API 变更。

## 直接使用（Windows，无需安装 Python）

从 GitHub Releases 下载 Windows 便携 ZIP，完整解压，双击 `dsweb.exe`。
输入你自己的 DeepSeek API Key 即可搜索；点击“保存配置”可供下次启动和 Harness 共用。不要移走 `_internal` 文件夹。
本地构建产物也在 `dist` 文件夹；发布到 GitHub 后再从 Releases 下载。

在解压目录打开 PowerShell，可运行：

```powershell
$env:DEEPSEEK_API_KEY = '你的密钥'
.\dsweb.exe search 'DeepSeek' --count 5
.\dsweb.exe fetch 'https://example.com' --format markdown
.\dsweb.exe harness-config -o deepseek-web.local.yml
```

源码下载用户安装 Python 3.11+ 后可双击 `start-gui.cmd`。
[Harness 接入教程](docs/HARNESS.md) · [GitHub 发布与打包](docs/RELEASE.md)

本项目是社区独立工具，非 DeepSeek 官方产品；自有源码采用 MIT 许可证。

## 安装与启动

在 PowerShell 中进入本项目目录：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[mcp]'
$env:DEEPSEEK_API_KEY = '你的 DeepSeek API Key'

# 打开桌面 GUI，也可以在 GUI 中直接输入密钥
.\.venv\Scripts\python.exe -m deepseek_web gui

# CLI 搜索
.\.venv\Scripts\python.exe -m deepseek_web search 'DeepSeek site:github.com lang:zh' --count 5

# 搜索并包含正文，以 Markdown 导出
.\.venv\Scripts\python.exe -m deepseek_web search 'DeepSeek' --need-content --format markdown -o results.md

# 网页抓取
.\.venv\Scripts\python.exe -m deepseek_web fetch 'https://api-docs.deepseek.com/zh-cn/guides/search/' --format markdown -o page.md
```

安装后也可以使用虚拟环境中的 `dsweb`、`dsweb-gui` 命令。仅使用 CLI/GUI 时可执行 `python -m pip install -e .`，或直接在源码目录运行 `python -m deepseek_web gui`，无需安装依赖。

macOS / Linux 将 `.venv\Scripts\python.exe` 换成 `.venv/bin/python`，环境变量使用 `export DEEPSEEK_API_KEY='...'`。

## 保存 API Key

GUI 中点击“保存配置”，或执行 `dsweb config --set-key`（输入不回显）。
默认文件：Windows 的 `%USERPROFILE%\.deepseek-web\config.json`；其他系统的 `~/.deepseek-web/config.json`。
内容为 `{"api_key": "你的密钥"}`，是本地明文，不要上传。
环境变量优先于文件；支持 `dsweb --config PATH ...` 指定配置。
详见 [配置文件说明](docs/CONFIGURATION.md)。

## CLI 参数

```text
dsweb search QUERY [--count 1..50] [--need-content]
                  [--ori-question ORIGINAL] [--localization IP]
                  [--format json|markdown] [-o FILE]
                  [--timeout SECONDS] [--retries 0..5]
dsweb fetch URL    [--format json|markdown] [-o FILE]
                  [--timeout SECONDS] [--retries 0..5]
dsweb gui
dsweb mcp
```

JSON 为默认输出，保留上游所有字段，UTF-8 编码。CLI 成功退出码为 0，运行失败为 1，命令行解析错误为 2，中断为 130；错误写入 stderr。`-o` 会覆盖指定输出文件。

查询语法直接放在 QUERY 内并整体加引号，工具不会改写查询词。GUI 支持相同参数，搜索结果表展示相关性、权威性和日期；正文以 Markdown 源文本显示。选中搜索结果时导出整次搜索，抓取完成后导出当前网页，重新选中搜索结果可切回搜索数据。

## DeepSeek Harness 插件接入

安装 `.[mcp]` 后，在项目目录运行：

```powershell
.\.venv\Scripts\python.exe -m deepseek_web harness-config -o deepseek-web.local.yml
$env:DEEPSEEK_API_KEY = '你的密钥'
npx @deepseek-ai/dsh web --patch "$PWD\deepseek-web.local.yml"
```

便携版将配置生成命令换为 `.\dsweb.exe harness-config -o deepseek-web.local.yml`。
配置自动匹配当前程序绝对路径，不含密钥，也不会覆盖已有文件。
通过官方 MCP 插件注册 `mcp__deepseek_web__search` 和 `mcp__deepseek_web__fetch`。
更多内容见 [完整教程与排错](docs/HARNESS.md)。

## 请求行为与边界

- 默认调用 `https://api.deepseek.com/v1/tools/search` 和 `/v1/tools/fetch`，直接使用 Bearer 鉴权。无需模型名称，不通过聊天补全接口模拟搜索。
- `DEEPSEEK_BASE_URL` 可指定可信 API 服务的根地址或 `/v1` 地址；非本机必须 HTTPS。密钥会发送到该地址，因此只配置可信服务。不跟随重定向。
- 对搜索词、条数、原始问题、本地化 IP 和 URL 做本地校验，错误输入不会请求 API。
- Search / Fetch 分别在**本进程**内按 0.21 秒最小间隔调度。多个 CLI/GUI/MCP 进程及同账号其他应用不共享此限流器；仍可能收到账号或目标域名限流。
- 默认请求超时 20 秒、最多重试 2 次。408、429、5xx 和连接故障会退避重试；其余 HTTP 错误不自动重试。支持 `Retry-After` 秒数及 HTTP 日期，超过 30 秒则返回错误，不提前重试。
- GUI 网络工作在线程中执行。取消会停止排队、退避及后续处理；已发出的请求需等待返回或 socket 超时，不能撤回已经发生的服务端调用。socket 超时并非严格的整次操作总时限。
- API Key 可来自显式输入、环境或本地 JSON 配置；只有主动保存才会写入文件。配置为明文，不写入日志或分发包。上游错误响应正文不直接显示，避免回显密钥。
- 工具不执行返回的网页内容。将抓取结果用于 Agent 时，应把它视作不可信资料，而非系统指令。
- 请求可能产生 DeepSeek API 费用；以[官方 Search/Fetch 文档](https://api-docs.deepseek.com/zh-cn/guides/search/)的实时计费规则为准。

本项目未内置 API Key，安装与测试不会调用付费接口。需要有效密钥才能进行真实联网搜索与抓取。MCP 适配测试覆盖真实 stdio 握手、发现及调用；已在本机 Harness 0.1.1-rc.2 中验证插件热加载为 active，并验证真实 Search / Fetch 调用。其他安装仍需核对版本和配置。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q deepseek_web
```

测试使用本地 HTTP 服务器，覆盖请求契约、字段校验、限流重试、不重试状态码、重定向保护、响应异常、CLI 子进程、桌面搜索抓取流程，以及真实 MCP stdio 子进程。不安装 MCP 时协议测试会跳过；无显示环境时 GUI 测试会跳过。

```text
deepseek_web/client.py      参数校验、鉴权、限速和 HTTP 请求
deepseek_web/cli.py         命令行
deepseek_web/gui.py         Tk 桌面界面
deepseek_web/mcp_server.py  官方 MCP SDK 适配
deepseek_web/output.py      JSON / Markdown 输出
examples/harness.yml       Harness 插件条目
tests/                     本地模拟 API 和集成测试
```
