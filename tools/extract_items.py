#!/usr/bin/env python3
"""Extract canonical vanilla Minecraft item IDs for the latest stable Java release."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MIRROR_VERSIONS_URL = "https://raw.githubusercontent.com/misode/mcmeta/summary/versions/data.json"
MIRROR_ITEM_DEFINITIONS_URL = "https://raw.githubusercontent.com/misode/mcmeta/summary/assets/item_definition/data.json"


class ExtractionError(RuntimeError):
    """Raised when extraction cannot complete."""


def fetch_json(url: str) -> Any:
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                raise ExtractionError(f"HTTP {response.status} while fetching JSON from {url}")
            return json.load(response)
    except urllib.error.URLError as exc:
        raise ExtractionError(f"Failed to fetch JSON from {url}: {exc}") from exc


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as out_file:
            if response.status != 200:
                raise ExtractionError(f"HTTP {response.status} while downloading {url}")
            shutil.copyfileobj(response, out_file)
    except urllib.error.URLError as exc:
        raise ExtractionError(f"Failed to download {url}: {exc}") from exc


def resolve_latest_release() -> tuple[str, dict[str, Any]]:
    manifest = fetch_json(VERSION_MANIFEST_URL)
    if not isinstance(manifest, dict):
        raise ExtractionError("Unexpected Mojang version manifest format")

    latest_release_id = manifest.get("latest", {}).get("release")
    if not latest_release_id:
        raise ExtractionError("Could not find latest stable release in Mojang version manifest")

    versions = manifest.get("versions", [])
    version_entry = next((entry for entry in versions if entry.get("id") == latest_release_id), None)
    if version_entry is None or "url" not in version_entry:
        raise ExtractionError(f"Could not find metadata URL for release {latest_release_id}")

    version_meta = fetch_json(version_entry["url"])
    if not isinstance(version_meta, dict):
        raise ExtractionError(f"Unexpected version metadata format for release {latest_release_id}")

    return latest_release_id, version_meta


def resolve_latest_release_from_mirror() -> str:
    versions = fetch_json(MIRROR_VERSIONS_URL)
    if not isinstance(versions, list):
        raise ExtractionError("Unexpected mirror versions format")

    for version in versions:
        if version.get("type") == "release" and version.get("stable"):
            release_id = version.get("id")
            if release_id:
                return release_id

    raise ExtractionError("Could not resolve latest stable release from fallback mirror")


def run_report_generation(server_jar: Path, work_dir: Path) -> Path:
    report_output_root = work_dir / "generated"

    commands: list[list[str]] = [
        [
            "java",
            "-DbundlerMainClass=net.minecraft.data.Main",
            "-jar",
            str(server_jar),
            "--reports",
            "--output",
            str(report_output_root),
        ],
        [
            "java",
            "-cp",
            str(server_jar),
            "net.minecraft.data.Main",
            "--reports",
            "--output",
            str(report_output_root),
        ],
    ]

    last_error: str | None = None
    for command in commands:
        process = subprocess.run(
            command,
            cwd=work_dir,
            capture_output=True,
            text=True,
            env={**os.environ, "JAVA_TOOL_OPTIONS": ""},
        )
        report_file = report_output_root / "reports" / "items.json"
        if process.returncode == 0 and report_file.exists():
            return report_file

        last_error = (
            f"Command failed ({' '.join(command)})\n"
            f"exit={process.returncode}\n"
            f"stdout:\n{process.stdout}\n"
            f"stderr:\n{process.stderr}"
        )

    raise ExtractionError(
        "Failed to generate reports/items.json from vanilla server jar. "
        f"Last attempt details:\n{last_error}"
    )


def parse_report_items(report_file: Path) -> list[str]:
    with report_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ExtractionError(f"Unexpected format in {report_file}: expected top-level object")

    item_ids = [key for key in payload.keys() if isinstance(key, str) and key.startswith("minecraft:")]
    if not item_ids:
        raise ExtractionError(f"No minecraft:* item IDs found in {report_file}")

    return sorted(set(item_ids))


def parse_mirror_items() -> list[str]:
    payload = fetch_json(MIRROR_ITEM_DEFINITIONS_URL)
    if not isinstance(payload, dict):
        raise ExtractionError("Unexpected format in mirror item definitions")

    item_ids = [f"minecraft:{key}" for key in payload.keys() if isinstance(key, str)]
    if not item_ids:
        raise ExtractionError("No item IDs found in mirror item definitions")

    return sorted(set(item_ids))


def extract_items() -> tuple[list[str], str, str]:
    """Return (items, release_id, source)."""
    try:
        release_id, version_meta = resolve_latest_release()
        server_url = version_meta.get("downloads", {}).get("server", {}).get("url")
        if not server_url:
            raise ExtractionError(f"Release {release_id} does not expose a server download URL")

        with tempfile.TemporaryDirectory(prefix="mc-items-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            server_jar = temp_dir / "server.jar"
            download_file(server_url, server_jar)
            report_file = run_report_generation(server_jar=server_jar, work_dir=temp_dir)
            items = parse_report_items(report_file)

        return items, release_id, "mojang-reports"
    except ExtractionError as primary_error:
        # Fallback keeps the pipeline operating in environments where Mojang domains are blocked.
        release_id = resolve_latest_release_from_mirror()
        items = parse_mirror_items()
        print(f"Warning: primary extraction failed, using mirror fallback: {primary_error}", file=sys.stderr)
        return items, release_id, "mirror-item_definition"


def write_outputs(items: list[str], mc_version: str, source: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    items_json_path = output_dir / "items.json"
    items_txt_path = output_dir / "items.txt"
    version_json_path = output_dir / "version.json"

    items_json_path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    items_txt_path.write_text("\n".join(items) + "\n", encoding="utf-8")
    version_json_path.write_text(
        json.dumps(
            {
                "minecraft_release": mc_version,
                "item_count": len(items),
                "source": source,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory where items.json/items.txt will be written (default: data)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    try:
        items, mc_version, source = extract_items()
        write_outputs(items=items, mc_version=mc_version, source=source, output_dir=output_dir)
    except ExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Updated item dataset for Minecraft {mc_version} with {len(items)} items ({source}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
