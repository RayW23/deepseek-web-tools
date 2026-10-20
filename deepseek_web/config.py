"""User-owned plaintext configuration, independent of the current working directory."""
import json
import os
import tempfile
from pathlib import Path


def config_path() -> Path:
    override = os.getenv("DEEPSEEK_WEB_CONFIG")
    return Path(override).expanduser().resolve() if override else Path.home() / ".deepseek-web" / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        raise ValueError(f"无法读取配置文件或 JSON 格式错误：{path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("api_key", ""), str):
        raise ValueError(f"配置必须是 JSON 对象，api_key 必须是字符串：{path}")
    return data


def resolve_api_key(explicit: str | None = None) -> str:
    if explicit is not None:
        return explicit.strip()
    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    return env_key or load_config().get("api_key", "").strip()


def save_api_key(api_key: str, *, overwrite: bool = True) -> Path:
    if not isinstance(api_key, str) or any(ord(c) < 33 or ord(c) > 126 for c in api_key):
        raise ValueError("API Key 必须为不含空白的 ASCII 字符串")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve unrelated user fields; invalid files must be repaired by the user.
    data = load_config()
    data["api_key"] = api_key
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if not overwrite:
        with open(path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as handle:
            handle.write(content)
        return path
    descriptor, temporary = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
