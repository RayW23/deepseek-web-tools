# 接入 DeepSeek Harness

本项目通过官方 `@deepseek-ai/dsh-mcp-client` 插件接入。无需修改 Harness 源码。
配置生成器输出的是 Cordis **insert patch**，可以直接交给 `--patch`。

## Windows 便携版（无需 Python）

1. 下载发布 ZIP，**完整解压**到固定文件夹，例如 `C:\Tools\deepseek-web\dsweb`。保留 `_internal` 目录，不要只复制 exe。
2. 在该文件夹打开 PowerShell：

```powershell
.\dsweb.exe harness-config -o deepseek-web.local.yml
.\dsweb.exe config --set-key
npx @deepseek-ai/dsh web --patch "$PWD\deepseek-web.local.yml"
```

已有 `dsh` 命令也可运行：

```powershell
dsh web --patch "$PWD\deepseek-web.local.yml"
```

生成的 Harness 配置只包含本地文件路径和环境变量引用，不含密钥。config --set-key 保存后无需每次设置环境变量。详见 [配置文件说明](CONFIGURATION.md)。
如果目录移动了，删除自己生成的旧配置后重新生成，或使用新文件名；生成器不会覆盖已有文件。

## Python 源码版（Windows / macOS / Linux）

进入项目目录后安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[mcp]"
.\.venv\Scripts\python.exe -m deepseek_web harness-config -o deepseek-web.local.yml
$env:DEEPSEEK_API_KEY = '你的 DeepSeek API Key'
npx @deepseek-ai/dsh web --patch "$PWD\deepseek-web.local.yml"
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install '.[mcp]'
.venv/bin/python -m deepseek_web harness-config -o deepseek-web.local.yml
export DEEPSEEK_API_KEY='你的 DeepSeek API Key'
npx @deepseek-ai/dsh web --patch "$PWD/deepseek-web.local.yml"
```

配置使用当前 Python 的绝对路径，因此不要用没有安装本项目的其他 Python 来生成。
如果你只在源码目录直接运行、没有安装包，先执行安装步骤；生成器不依赖 Harness 的工作目录来导入项目。

## 生成结果示意

```yaml
- insert:
    - id: deepseek-web
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: deepseek_web
        transport: stdio
        command: "C:/Tools/deepseek-web/dsweb/dsweb.exe"
        args: ["mcp"]
        env:
          DEEPSEEK_WEB_CONFIG: 'C:/Users/YOUR_NAME/.deepseek-web/config.json'
          DEEPSEEK_API_KEY: !!js process.env.DEEPSEEK_API_KEY || ''
        toolCallTimeoutMs: 180000
        failOnStartupError: true
```

这是结构示例。实际使用生成命令，避免复制别人的绝对路径。

## 确认生效

启动后应发现两个工具：

- `mcp__deepseek_web__search`
- `mcp__deepseek_web__fetch`

给 Harness 发送：“请调用 deepseek_web 搜索 DeepSeek Search API 文档，再抓取其中一个页面并附链接。”
检查调用记录中实际使用了上述工具。首次验证会向 DeepSeek 发出真实请求，可能计费。
已在本机 Harness 0.1.1-rc.2 验证热加载 active，并用配置文件鉴权完成真实搜索和抓取。其他机器请按工具清单和调用记录验证。

## 每次启动自动启用

根据官方指南，可以将生成文件中的 `insert` 项合并进：
`$DSH_HOME/profiles/<name>/cordis.patch.yml`（单个 profile），或
`$DSH_HOME/cordis.patch.yml`（所有 profile）。

已有文件只能合并，不要覆盖；也不要同时通过全局 patch 和 `--patch` 重复注册相同 serverName。
不知道 DSH_HOME 时，先用上面的显式 `--patch` 命令即可。

## 排错

| 现象 | 检查 |
|---|---|
| 没有工具 | 查看 Harness MCP 启动日志；确认加载了生成的 insert patch |
| 找不到程序 / 模块 | 文件是否移动；Python 是否正确；是否安装 `.[mcp]` |
| 提示缺少 API Key | 执行 config --set-key，或在启动终端设置环境变量；检查配置中的文件路径 |
| HTTP 401 / 402 | 分别为密钥无效、余额不足 |
| HTTP 429 | 同账号或目标站点限流，稍后重试 |
| serverName 重复 | 删除重复配置，保留一个 deepseek_web 实例 |
| 直接运行 mcp 没有输出 | 正常，它在等待宿主发送协议消息；不适合手动输入搜索词 |
| 便携版启动失败 | 确认完整解压且包含 _internal，使用 Windows x64 |

官方依据：
[客户端配置](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)、
[使用 --patch 的官方示例](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md)。
