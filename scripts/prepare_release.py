from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTA_DIR = ROOT / "executas" / "mini-notes-summarizer"
JSON_VERSION_FILES = [
    ROOT / "app.json",
    ROOT / "package.json",
    EXECUTA_DIR / "executa.json",
    EXECUTA_DIR / "manifest.json",
]
TOML_VERSION_FILE = EXECUTA_DIR / "pyproject.toml"
VERSION_FILE = EXECUTA_DIR / "version.txt"
VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
TOML_VERSION_PATTERN = re.compile(r'(?m)^version = "([^"]+)"$')


def _normalize_version(value: str) -> str:
    version = value.strip().removeprefix("v")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid Semantic Version: {value!r}")
    return version


def _read_json_version(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8")).get("version")
    if not isinstance(value, str):
        raise ValueError(f"{path}: missing string version")
    return value


def _read_toml_version(path: Path) -> str:
    match = TOML_VERSION_PATTERN.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{path}: missing project version")
    return match.group(1)


def _read_versions() -> dict[Path, str]:
    versions = {path: _read_json_version(path) for path in JSON_VERSION_FILES}
    versions[TOML_VERSION_FILE] = _read_toml_version(TOML_VERSION_FILE)
    versions[VERSION_FILE] = VERSION_FILE.read_text(encoding="utf-8").strip()
    return versions


def _write_json_version(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_toml_version(path: Path, version: str) -> None:
    source = path.read_text(encoding="utf-8")
    updated, count = TOML_VERSION_PATTERN.subn(
        f'version = "{version}"',
        source,
        count=1,
    )
    if count != 1:
        raise ValueError(f"{path}: missing project version")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    versions = _read_versions()
    if args.check:
        expected = (
            _normalize_version(args.version)
            if args.version
            else next(iter(versions.values()))
        )
        mismatches = [
            f"{path.relative_to(ROOT)}: {version}"
            for path, version in versions.items()
            if version != expected
        ]
        if mismatches:
            raise SystemExit(
                "version mismatch, expected "
                f"{expected}:\n  " + "\n  ".join(mismatches)
            )
        print(f"all source versions match {expected}")
        return

    if not args.version:
        parser.error("--version is required unless --check is used")
    version = _normalize_version(args.version)
    for path in JSON_VERSION_FILES:
        _write_json_version(path, version)
    _write_toml_version(TOML_VERSION_FILE, version)
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")
    print(f"updated source metadata to {version}")


if __name__ == "__main__":
    main()
