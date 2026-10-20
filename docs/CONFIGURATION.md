# API Key 配置文件

CLI、桌面 GUI、MCP 共用配置，默认位置：

- Windows：`%USERPROFILE%\.deepseek-web\config.json`
- macOS / Linux：`~/.deepseek-web/config.json`

```json
{
  "api_key": "在本地填入你的 DeepSeek API Key"
}
```

文件为本地明文，不要上传、分享或放入公共同步目录。`examples/config.example.json` 是空密钥示例。

## 保存方式

GUI 输入 Key 后点击 **保存配置**。未点击保存时，只作用于当前会话。

便携版命令：`dsweb.exe config --set-key`，输入不回显，也不会进入命令历史。
源码安装版：`python -m deepseek_web config --set-key`。

`dsweb config` 显示路径；`dsweb config --init` 创建空文件，拒绝覆盖已有文件。

## 优先级

1. Python 显式传入的 Key / GUI 输入框。
2. 非空环境变量 `DEEPSEEK_API_KEY`。
3. 配置文件的 `api_key`。

MCP 每次调用重新读取配置，改 Key 后不必重启 Harness。若旧密钥仍生效，请检查环境变量。

## 指定路径

```powershell
.\dsweb.exe --config 'D:\private\dsweb.json' config --set-key
.\dsweb.exe --config 'D:\private\dsweb.json' search 'DeepSeek'
.\dsweb.exe --config 'D:\private\dsweb.json' harness-config -o deepseek-web.local.yml
```

也可设置 `DEEPSEEK_WEB_CONFIG` 环境变量；`--config` 放在子命令前。
默认路径不依赖当前工作目录。Harness 配置生成器将文件绝对路径放进 env，不复制其中的 Key。

JSON 使用 UTF-8（允许 BOM）。格式错误只报告路径，不回显内容；保存保留额外字段。
没有 Key 时 MCP 仍可启动和发现工具，实际调用会提示配置 Key。
