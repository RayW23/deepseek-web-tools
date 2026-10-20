"""Build a Windows portable zip from an environment containing .[mcp,build]."""
import hashlib
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "win32":
        raise SystemExit("Build this Windows artifact on Windows.")
    version = importlib.metadata.version("deepseek-web-tools")
    name = f"deepseek-web-tools-{version}-windows-{platform.machine().lower()}"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
                    "--name", "dsweb", "--paths", str(ROOT), "--collect-data", "mcp",
                    "--recursive-copy-metadata", "mcp", "--hide-console", "hide-early",
                    "--specpath", str(ROOT / "build"),
                    str(ROOT / "scripts" / "portable_cli.py")], cwd=ROOT, check=True)
    bundle = ROOT / "dist" / "dsweb"
    for file in ("README.md", "LICENSE"):
        shutil.copy2(ROOT / file, bundle / file)
    shutil.copytree(ROOT / "docs", bundle / "docs", dirs_exist_ok=True)
    notices = bundle / "THIRD_PARTY_LICENSES"
    notices.mkdir(exist_ok=True)
    for dist in importlib.metadata.distributions():
        package = dist.metadata.get("Name", "unknown")
        for file in dist.files or []:
            if any(token in str(file).lower() for token in ("license", "copying", "notice")):
                src = Path(dist.locate_file(file))
                if src.is_file() and ".dist-info" in str(file):
                    dest = notices / package / Path(str(file)).name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, notices / "Python-LICENSE.txt")
    archive = Path(shutil.make_archive(str(ROOT / "dist" / name), "zip", bundle.parent, bundle.name))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
