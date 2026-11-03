"""Build the self-contained runpack for external distribution.

Target: 发布与材料/完整Demo运行包

The runpack includes all source code and runtime artifacts needed to launch
the demo with 一键启动.bat. Optional Hugging Face enhancement datasets, local
virtualenvs, runtime caches and secrets are intentionally excluded; the app
degrades gracefully without them.
"""

from __future__ import annotations

import argparse
import shutil
import stat
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET = PROJECT_ROOT / "发布与材料" / "完整Demo运行包"

ROOT_FILES = [
    "一键启动.bat",
    "停止完整Demo.bat",
    "start_complete_demo.ps1",
    "stop_complete_demo.ps1",
    "requirements.txt",
    "requirements.lock",
    ".env.example",
    ".gitignore",
    "LICENSE",
    "README.md",
    "AGENTS.md",
    "CONTEXT.md",
    "index.html",
    "logo.jpg",
    "pytest.ini",
    "跨境电商智能选品决策系统_商业计划书.pdf",
]

DIR_COPIES = [
    "src",
    "scripts",
    "tests",
    "docs",
    "assets",
    "third_party",
    "models",
    "data",
    "output",
    "frontend",
    ".github",
    ".streamlit",
    "训练数据集",
    "小助手",
]

IGNORED_NAMES = {
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".git",
    "node_modules",
    "dist",
    "dist-offline",
    ".vite",
    "crawlee_storage",
    "hf",
}


def _ignore(_dirpath: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES}


def _dir_size(path: Path) -> tuple[int, int]:
    files = list(path.rglob("*"))
    return len([f for f in files if f.is_file()]), sum(
        f.stat().st_size for f in files if f.is_file()
    )


def _rmtree_force(target: Path) -> None:
    """Remove a generated runpack even when copied files are read-only."""
    for path in target.rglob("*"):
        if path.is_file():
            try:
                path.chmod(path.stat().st_mode | stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(target)


def build(clean: bool = False) -> int:
    if TARGET.resolve() == PROJECT_ROOT.resolve():
        print("Refusing to build runpack at project root.")
        return 1
    if clean and TARGET.exists():
        _rmtree_force(TARGET)
    TARGET.mkdir(parents=True, exist_ok=True)

    for name in ROOT_FILES:
        source = PROJECT_ROOT / name
        if not source.exists():
            print(f"skip root file (missing): {name}")
            continue
        shutil.copy2(source, TARGET / name)

    for name in DIR_COPIES:
        source = PROJECT_ROOT / name
        if not source.exists():
            print(f"skip dir (missing): {name}")
            continue
        target = TARGET / name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=_ignore,
        )

    template = PROJECT_ROOT / "docs" / "distribution" / "运行Demo完整说明.md"
    if template.exists():
        shutil.copy2(template, TARGET / "运行Demo完整说明.md")

    count, size = _dir_size(TARGET)
    print(f"runpack ready: {TARGET}")
    print(f"files={count}, size={size / 1024 / 1024:.1f} MB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        dest="clean",
        action="store_true",
        default=True,
        help="remove the existing runpack before copying (default)",
    )
    parser.add_argument(
        "--no-clean",
        dest="clean",
        action="store_false",
        help="merge into the existing runpack without removing it first",
    )
    args = parser.parse_args()
    return build(clean=args.clean)


if __name__ == "__main__":
    sys.exit(main())
