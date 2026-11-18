# SPDX-License-Identifier: GPL-2.0-only
# Darkslide-derived validation/parser portions: Copyright (C) 2026 LiorMoment.
"""Prepare V3 Native data from a fitted original Darkslide project.

This prepares a local data bundle. It does not generate a firmware container.
Validation follows Darkslide GR store.film_lut_profiles, pinned in SOURCES.md.
"""
import argparse
import copy
import re
import shutil
from pathlib import Path

from check_firmware import inspect_firmware
from native_profile import (BASE_MODEL, ENVELOPE_MODEL, FACTORY_SHA256, encode_profile,
                            json_bytes, read_json, require, sha256)
from cube_reader import parse_cube

ROOT = Path(__file__).resolve().parents[1]


def fitted_entry(project, ident):
    require(re.fullmatch(r"user_lut_[0-9a-f]{12}", ident) is not None, "Invalid user LUT ID")
    project_info = read_json(project / "project.json")
    require(project_info.get("input_sha256") == FACTORY_SHA256,
            "Darkslide project must use the supported official GR III 2.10 input")
    entries = read_json(project / "film_luts.json")
    require(type(entries) is dict and type(entries.get(ident)) is dict, "Selected LUT is missing")
    entry = entries[ident]
    cube_path = project / "luts" / (ident + ".cube")
    require(cube_path.resolve().is_relative_to(project.resolve()), "LUT path leaves the project")
    cube = cube_path.read_bytes()
    parse_cube(cube)
    digest = sha256(cube)
    require(ident == "user_lut_" + digest[:12] and entry.get("sha256") == digest,
            "Original LUT identity or SHA does not match")
    profile = entry.get("profile")
    require(type(profile) is dict, "LUT has no fitted camera profile")
    provenance = profile.get("provenance") or {}
    fit = entry.get("fit") or {}
    envelope = fit.get("envelope") or {}
    require(profile.get("id") == ident and provenance.get("kind") == "user_lut"
            and provenance.get("source_sha256") == digest
            and provenance.get("official_sha256") == FACTORY_SHA256,
            "Profile provenance does not match this project and LUT")
    require(provenance.get("fitter") == fit.get("fitter") == "darkslide-film-fit-v2"
            and provenance.get("base_model_id") == fit.get("base_model_id") == BASE_MODEL,
            "Unsupported fitter or base model")
    require(fit.get("layout") == "four_curve_v1"
            and provenance.get("target_input_encoding") == "srgb"
            and provenance.get("target_ev") == 0 and provenance.get("mid_index") == 7.8
            and re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("base_values_sha256", ""))),
            "Unsupported fitting assumptions or missing base identity")
    require(envelope.get("checked") is True and envelope.get("model_id") == ENVELOPE_MODEL
            and envelope.get("violations") == [], "Require a successful factory-envelope check")
    json_bytes(entry)
    files = encode_profile(profile)
    return entry, profile, files


def prepare(project, identifiers, firmware, output, previous=None, author="Unknown", name=None):
    require(output.is_absolute(), "Use an absolute output path")
    require(not output.resolve().is_relative_to(ROOT), "Keep private user imports outside the skill repository")
    require(not output.exists(), "Choose a fresh output directory")
    require(bool(identifiers) and len(set(identifiers)) == len(identifiers), "Select unique fitted LUT IDs")
    require(name is None or len(identifiers) == 1, "A display-name override requires one selected LUT")
    official = inspect_firmware(firmware)
    source = previous.resolve() if previous else ROOT
    require(not output.resolve().is_relative_to(source), "Output must be outside its source project")
    manifest_path = source / "library.json" if previous else source / "assets/library.json"
    manifest = copy.deepcopy(read_json(manifest_path))
    require(type(manifest.get("next_uid")) is int and manifest["next_uid"] >= 39,
            "Invalid persistent UID registry")
    existing_uids = [film["uid"] for film in manifest["films"]]
    require(len(existing_uids) == len(set(existing_uids))
            and all(type(uid) is int and 1 <= uid < manifest["next_uid"] for uid in existing_uids),
            "Corrupt or reused existing film UID")
    require(not set(existing_uids).intersection(manifest["retired_uids"]),
            "A retired film UID was reused")
    require(len(manifest["defaults"]) == 6 and set(manifest["defaults"]) <= set(existing_uids),
            "Default slot references a missing film")
    for film in manifest["films"]:
        stored_profile = source / film["profile"]
        require(stored_profile.resolve().is_relative_to(source.resolve()), "Stored profile path leaves project")
        encoded = encode_profile(read_json(stored_profile))
        for filename, digest in film["files"].items():
            require(Path(filename).name == filename, "Unsafe stored parameter filename")
            data = (stored_profile.parent / filename).read_bytes()
            require(sha256(data) == digest, "Existing parameter hash differs: " + filename)
            if filename in encoded:
                require(data == encoded[filename], "Existing parameter encoding differs: " + filename)
    pending = []
    for ident in identifiers:
        entry, profile, encoded = fitted_entry(project, ident)
        profile_bytes = json_bytes(profile)
        fingerprint = sha256(profile_bytes)
        match = next((f for f in manifest["films"] if f.get("profile_sha256") == fingerprint), None)
        if match:
            continue
        uid = manifest["next_uid"]
        require(type(uid) is int and 39 <= uid <= 65535, "No valid append-only UID available")
        display_name = name if name is not None else entry.get("name")
        require(type(display_name) is str and 0 < len(display_name) <= 32
                and all(32 <= ord(c) < 127 for c in display_name),
                "Provide an ASCII display name of 1..32 characters with --name")
        key = "user-" + str(uid)
        profile_path = f"assets/presets/{key}/profile.json"
        manifest["films"].append({"uid": uid, "key": key, "name": display_name,
                                  "category": "my-luts", "author": author,
                                  "license": "USER_SUPPLIED_REVIEW_REQUIRED",
                                  "source_sha256": entry["sha256"], "profile": profile_path,
                                  "profile_sha256": fingerprint,
                                  "files": {"profile.json": fingerprint,
                                            **{n: sha256(b) for n, b in encoded.items()}},
                                  "icon": None})
        manifest["next_uid"] = uid + 1
        pending.append((key, profile_bytes, encoded))
    manifest["status"] = "PREPARED_DATA_ONLY"
    # All input checks finish before creating the output. Existing projects are immutable.
    output.mkdir(parents=True, exist_ok=False)
    try:
        shutil.copytree(source / "assets", output / "assets")
        for key, profile_bytes, encoded in pending:
            folder = output / "assets/presets" / key
            folder.mkdir()
            (folder / "profile.json").write_bytes(profile_bytes)
            for name, content in encoded.items():
                (folder / name).write_bytes(content)
        (output / "library.json").write_bytes(json_bytes(manifest))
        receipt = {"status": "PASS_DATA_PREPARATION_ONLY", "official": official,
                   "new_films": len(pending), "film_count": len(manifest["films"]),
                   "defaults": manifest["defaults"], "firmware_generated": False,
                   "source_project_modified": False, "private_user_data": True}
        (output / "RECEIPT.json").write_bytes(json_bytes(receipt))
    except BaseException:
        shutil.rmtree(output)
        raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--firmware", required=True, type=Path)
    parser.add_argument("--id", action="append", required=True, dest="identifiers")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--previous", type=Path, help="Previous prepared local project directory")
    parser.add_argument("--author", default="Unknown")
    parser.add_argument("--name", help="ASCII display-name override for one selected LUT")
    args = parser.parse_args()
    try:
        receipt = prepare(args.project, args.identifiers, args.firmware, args.output,
                          args.previous, args.author, args.name)
        print(json_bytes(receipt).decode(), end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
