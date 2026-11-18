# SPDX-License-Identifier: GPL-2.0-only
"""Check the curated distribution assets and their native encodings."""
import argparse
from collections import Counter
from pathlib import Path

from native_profile import encode_profile, json_bytes, read_json, require, sha256

ROOT = Path(__file__).resolve().parents[1]


def verify_assets(root=ROOT):
    library = read_json(root / "assets/library.json")
    films = library["films"]
    identifiers = [film["uid"] for film in films]
    require(len(identifiers) == len(set(identifiers)), "Duplicate film UID")
    require(library["defaults"] == [18, 12, 14, 9, 5, 11], "Unexpected default slots")
    require(set(library["defaults"]) <= set(identifiers), "Default points outside the film library")
    require(not set(identifiers).intersection(library["retired_uids"])
            and library["next_uid"] == max(identifiers) + 1, "Invalid persistent UID registry")
    require(Counter(f["license"] for f in films) == {
        "CC-BY-SA-4.0": 16, "MIT": 35,
    }, "Unexpected film counts by license")
    require(len({f["key"] for f in films}) == len(films), "Duplicate logical film")
    for film in films:
        profile_path = root / film["profile"]
        require(profile_path.resolve().is_relative_to(root.resolve()), "Asset path leaves the package")
        profile = read_json(profile_path)
        require(profile["provenance"]["source_sha256"] == film["source_sha256"],
                "Source identity mismatch")
        encoded = encode_profile(profile)
        for name, expected in film["files"].items():
            raw = (profile_path.parent / name).read_bytes()
            require(sha256(raw) == expected, "Asset hash mismatch: " + film["key"] + "/" + name)
            if name != "profile.json":
                require(raw == encoded[name], "Native ABI mismatch: " + name)
        icon = root / film["icon"]
        require(len(icon.read_bytes()) == 40 * 40 * 4, "Film icon must be 40x40 RGBA")
        require(sha256(icon.read_bytes()) == film["icon_sha256"], "Film icon hash differs")
    return {"status": "PASS_CURATED_ASSETS_AND_NATIVE_ENCODING", "films": len(films),
            "defaults": [next(f["name"] for f in films if f["uid"] == uid)
                         for uid in library["defaults"]], "firmware_generated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(json_bytes(verify_assets()).decode(), end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
