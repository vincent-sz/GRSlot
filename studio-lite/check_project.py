# SPDX-License-Identifier: GPL-2.0-only
"""Validate a saved Studio project and its local official GR III input."""
import argparse
import base64
from pathlib import Path
import sys

from app import DEFAULT_LIBRARY, Studio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_firmware import inspect_firmware
from native_profile import json_bytes, parse_json, sha256
from verify_assets import verify_assets


def load_checked_project(project_path, firmware, library_path=DEFAULT_LIBRARY):
    studio = Studio(library_path, project_path.parent)
    raw = project_path.read_bytes()
    project = studio.validate(parse_json(raw.decode("utf-8")))
    package = studio.library_path.parent
    if studio.library_path == DEFAULT_LIBRARY:
        package = DEFAULT_LIBRARY.parents[1]
    elif studio.library_path.name != "library.json" or not (package / "assets").is_dir():
        raise ValueError("Provide the root library.json from the prepared local library.")
    assets = verify_assets(package)
    if sha256(studio.library_path.read_bytes()) != studio.library_id:
        raise ValueError("Film library changed during validation. Reopen Studio and retry.")
    official = inspect_firmware(firmware / "fwdc239b.bin" if firmware.is_dir() else firmware)
    films = {film["uid"]: film for film in studio.films}
    selected = []
    for uid in project["selected"]:
        film = films[uid]
        overrides = project["overrides"].get(str(uid), {})
        selected.append(dict(
            uid=uid, name=overrides.get("name", film["name"]),
            category=overrides.get("category", film["category"]),
            notes=overrides.get("notes", ""),
            icon="custom" if "icon" in overrides else "library",
            icon_sha256=sha256(base64.b64decode(overrides["icon"].split(",", 1)[1]) if "icon" in overrides
                               else studio.icons[uid].read_bytes()),
        ))
    receipt = dict(status="PASS_STUDIO_PROJECT_ONLY", project_sha256=sha256(raw),
                   library_id=project["library_id"], revision=project["revision"],
                   selected=selected, slots=project["slots"], asset_validation=assets["status"],
                   official=official, firmware_generated=False)
    return project, receipt


def check_project(project_path, firmware, library_path=DEFAULT_LIBRARY):
    _, receipt = load_checked_project(project_path, firmware, library_path)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--firmware", required=True, type=Path, help="Official BIN or its folder")
    parser.add_argument("--library", default=DEFAULT_LIBRARY, type=Path)
    args = parser.parse_args()
    try:
        print(json_bytes(check_project(args.project, args.firmware, args.library)).decode(), end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
