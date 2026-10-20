# GitHub 发布与分发

本项目为独立社区工具，不代表 DeepSeek 官方产品。项目自有源码使用 MIT 许可证；
DeepSeek API 服务的账号、计费与使用条款仍由服务方决定。打包依赖保留各自许可证。

## 上传源码

新建 GitHub 仓库，例如 `deepseek-web-tools`。本地检查完成后：

```powershell
git add .gitignore README.md LICENSE pyproject.toml MANIFEST.in start-gui.cmd deepseek_web docs examples scripts tests .github
git diff --cached --stat
git commit -m "Release DeepSeek web tools"
git remote add origin https://github.com/YOUR_ACCOUNT/deepseek-web-tools.git
git push -u origin HEAD:main
```

将 YOUR_ACCOUNT 换成真实账号。仅在新仓库没有已有工作时按此流程发布；有 origin 时先核对，不覆盖他人分支。
发布操作由仓库拥有者执行；此工具不会自动创建远端或推送。

不要上传 API Key、.env、.venv、用户搜索导出和生成的本机配置。
.gitignore 已排除常见私密配置、build、dist、缓存与 exports；把搜索结果存入 exports 文件夹。
公开前仍需检查准备提交的内容。生成 YAML 只有环境变量引用，没有密钥。

## 构建安装包

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[mcp,build]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/build_windows.py
.\.venv\Scripts\python.exe -m build
```

产物位于 dist：
- Windows AMD64 便携 ZIP（包含 exe、运行库、文档与第三方许可）。
- ZIP 的 SHA256 校验文件。
- Python wheel 和源码 tar.gz，适用于 Python 环境安装。

Windows 包必须在 Windows 上构建。便携包未经代码签名；请将 ZIP 和校验文件一同提供。
在 GitHub Releases 手动上传 dist 中的 ZIP、sha256、whl、tar.gz。
可执行文件不要放进源码 Git 历史。仓库中的 CI 会测试并构建 Windows ZIP 为 workflow artifact；
此工作流不会自动公开 Release，也不会使用你的 API Key。

## 用户下载后

Windows 用户完整解压 ZIP，双击 dsweb.exe 即可打开图形界面，输入自己的 API Key。
命令行用户执行 `dsweb.exe --help`。
Harness 用户阅读 [HARNESS.md](HARNESS.md)。

wheel 安装示例：`python -m pip install "deepseek_web_tools-0.2.0-py3-none-any.whl[mcp]"`。
wheel 安装后运行 `dsweb gui` 或 `dsweb harness-config`。
