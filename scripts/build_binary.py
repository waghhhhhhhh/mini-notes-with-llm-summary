from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTA_DIR = ROOT / "executas" / "mini-notes-summarizer"
DIST_DIR = ROOT / "dist"
TOOL_ID = "tool-dev-mini-notes-summarizer"
TOOL_VERSION = "0.1.0"


def _platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "darwin-arm64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "darwin-x86_64"
    if system == "windows" and machine in {"x86_64", "amd64"}:
        return "windows-x86_64"

    raise RuntimeError(f"Unsupported host for binary build: {system}-{machine}")


def _install_manifest() -> dict:
    return {
        "name": TOOL_ID,
        "version": TOOL_VERSION,
        "runtime": {
            "binary": {
                "entrypoint": {
                    "default": "bin/mini-notes-summarizer",
                    "windows-x86_64": "bin/mini-notes-summarizer.exe",
                },
                "permissions": {
                    "bin/mini-notes-summarizer": "0o755",
                },
            }
        },
    }


def _build_binary() -> Path:
    raw_dir = DIST_DIR / "raw"
    work_dir = DIST_DIR / "work"
    raw_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--name",
        "mini-notes-summarizer",
        "--distpath",
        str(raw_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(DIST_DIR),
        "mini_notes_summarizer.py",
    ]
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(ROOT / ".cache" / "pyinstaller")
    subprocess.run(command, cwd=EXECUTA_DIR, env=env, check=True)

    suffix = ".exe" if platform.system().lower() == "windows" else ""
    binary = raw_dir / f"mini-notes-summarizer{suffix}"
    if not binary.is_file():
        raise RuntimeError(f"PyInstaller did not create {binary}")
    return binary


def _stage_binary(binary: Path, platform_key: str) -> tuple[Path, Path]:
    stage_dir = DIST_DIR / "stage" / platform_key
    if stage_dir.exists():
        shutil.rmtree(stage_dir)

    bin_dir = stage_dir / "bin"
    bin_dir.mkdir(parents=True)
    staged_binary = bin_dir / binary.name
    shutil.copy2(binary, staged_binary)
    staged_binary.chmod(0o755)
    (stage_dir / "manifest.json").write_text(
        json.dumps(_install_manifest(), indent=2) + "\n",
        encoding="utf-8",
    )
    return stage_dir, staged_binary


def _archive(stage_dir: Path, platform_key: str) -> Path:
    assets_dir = DIST_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    if platform_key.startswith("windows-"):
        archive_path = assets_dir / f"mini-notes-summarizer-{platform_key}.zip"
        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path in sorted(stage_dir.rglob("*")):
                if not path.is_file():
                    continue
                arcname = path.relative_to(stage_dir).as_posix()
                info = zipfile.ZipInfo(arcname)
                info.external_attr = (
                    (0o755 if path.suffix == ".exe" else 0o644) << 16
                )
                archive.writestr(info, path.read_bytes())
        return archive_path

    archive_path = assets_dir / f"mini-notes-summarizer-{platform_key}.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        for path in sorted(stage_dir.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(stage_dir).as_posix())
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", help="Required Anna platform key")
    args = parser.parse_args()

    detected = _platform_key()
    if args.platform and args.platform != detected:
        raise RuntimeError(
            f"Cannot build {args.platform} on {detected}; use a native runner."
        )
    platform_key = args.platform or detected

    binary = _build_binary()
    stage_dir, staged_binary = _stage_binary(binary, platform_key)
    archive_path = _archive(stage_dir, platform_key)

    subprocess.run(
        [sys.executable, str(ROOT / "tests" / "smoke_executa.py"), str(staged_binary)],
        check=True,
    )
    print(f"archive: {archive_path}")


if __name__ == "__main__":
    main()
