from __future__ import annotations

import argparse
import json
import re
import tarfile
import zipfile
from pathlib import Path


EXPECTED_ASSETS = {
    "mini-notes-summarizer-darwin-arm64.tar.gz": (
        "darwin-arm64",
        "bin/mini-notes-summarizer",
    ),
    "mini-notes-summarizer-darwin-x86_64.tar.gz": (
        "darwin-x86_64",
        "bin/mini-notes-summarizer",
    ),
    "mini-notes-summarizer-windows-x86_64.zip": (
        "windows-x86_64",
        "bin/mini-notes-summarizer.exe",
    ),
}
TOOL_ID = "tool-dev-mini-notes-summarizer"
VERSION_PATTERN = re.compile(
    r"^v?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$"
)


def _archive_files(path: Path) -> tuple[set[str], bytes]:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            return names, archive.read("manifest.json")

    with tarfile.open(path, mode="r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        manifest = members.get("manifest.json")
        if manifest is None or not manifest.isfile():
            raise RuntimeError(f"{path.name}: missing root manifest.json")
        extracted = archive.extractfile(manifest)
        if extracted is None:
            raise RuntimeError(f"{path.name}: could not read manifest.json")
        return set(members), extracted.read()


def verify_asset(path: Path, expected_version: str) -> None:
    platform_key, entrypoint = EXPECTED_ASSETS[path.name]
    files, raw_manifest = _archive_files(path)
    manifest = json.loads(raw_manifest)

    if manifest.get("name") != TOOL_ID:
        raise RuntimeError(f"{path.name}: unexpected tool identity")
    if manifest.get("version") != expected_version:
        raise RuntimeError(
            f"{path.name}: version {manifest.get('version')} "
            f"does not match {expected_version}"
        )
    if entrypoint not in files:
        raise RuntimeError(f"{path.name}: missing entrypoint {entrypoint}")
    declared_entrypoint = (
        manifest.get("runtime", {})
        .get("binary", {})
        .get("entrypoint", {})
        .get(platform_key)
    )
    if platform_key != "windows-x86_64":
        declared_entrypoint = (
            manifest.get("runtime", {})
            .get("binary", {})
            .get("entrypoint", {})
            .get("default")
        )
    if declared_entrypoint != entrypoint:
        raise RuntimeError(
            f"{path.name}: manifest entrypoint {declared_entrypoint!r} "
            f"does not match {entrypoint!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    match = VERSION_PATTERN.fullmatch(args.version.strip())
    if match is None:
        raise SystemExit(f"invalid release version: {args.version!r}")
    version = match.group(1)

    assets_dir = Path(args.assets_dir)
    missing = [name for name in EXPECTED_ASSETS if not (assets_dir / name).is_file()]
    if missing:
        raise SystemExit(f"missing release assets: {', '.join(missing)}")
    unexpected = [
        path.name
        for path in assets_dir.iterdir()
        if path.is_file() and path.name not in EXPECTED_ASSETS
    ]
    if unexpected:
        raise SystemExit(
            f"unexpected release assets: {', '.join(sorted(unexpected))}"
        )

    for name in EXPECTED_ASSETS:
        verify_asset(assets_dir / name, version)
        print(f"verified {name}")


if __name__ == "__main__":
    main()
