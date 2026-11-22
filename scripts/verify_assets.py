# SPDX-License-Identifier: GPL-2.0-only
"""Check the curated distribution assets and their native encodings."""
import argparse
from collections import Counter
from pathlib import Path

from native_profile import encode_profile, json_bytes, read_json, require, sha256

ROOT = Path(__file__).resolve().parents[1]


def validate_selection(library):
    uids = {film["uid"] for film in library["films"]}
    selected = library.get("selected", sorted(uids))
    defaults = library["defaults"]
    require(type(selected) is list and selected and all(type(uid) is int and uid in uids for uid in selected)
            and len(selected) == len(set(selected)), "Selection contains duplicate or unknown film UIDs")
    require(type(defaults) is list and len(defaults) == 6
            and all(type(uid) is int and uid in selected for uid in defaults),
            "Each default slot must point to a selected film UID")
    return selected


def verify_assets(root=ROOT):
    root = root.resolve()
    prepared = root != ROOT and (root / "library.json").is_file()
    library = read_json(root / ("library.json" if prepared else "assets/library.json"))
    films = library["films"]
    uids = {film["uid"] for film in films}
    next_uid = library["next_uid"]
    retired = library["retired_uids"]
    require(type(next_uid) is int and 39 <= next_uid <= 65536
            and len(uids) == len(films)
            and all(type(uid) is int and 0 < uid < next_uid for uid in [*uids, *retired])
            and len(set(retired)) == len(retired) and uids.isdisjoint(retired),
            "Invalid persistent UID registry")
    require(len({f["key"] for f in films}) == len(films), "Duplicate logical film")
    selected = validate_selection(library)
    defaults = library["defaults"]
    if not prepared:
        require(defaults == [39, 40, 88, 41, 5, 86], "Unexpected curated defaults")
        require(Counter(f["license"] for f in films) == {
            "CC-BY-SA-4.0": 16, "MIT": 35, "MAINTAINER_APPROVED_FOR_PUBLIC_DISTRIBUTION": 8,
        }, "Unexpected film counts by license")
    for film in films:
        profile_path = root / film["profile"]
        require(profile_path.name == "profile.json"
                and profile_path.resolve().is_relative_to(root / "assets"),
                "Profile must be under assets")
        profile = read_json(profile_path)
        require(profile["provenance"]["source_sha256"] == film["source_sha256"],
                "Source identity mismatch")
        encoded = encode_profile(profile)
        custom = film["license"] == "USER_SUPPLIED_REVIEW_REQUIRED"
        needed = {"profile.json", *encoded}
        if not custom:
            needed.remove("CSP_ENCODING.json")
        require(set(film["files"]) == needed, "Incomplete or unexpected file set: " + film["key"])
        for name, expected in film["files"].items():
            path = profile_path.with_name(name)
            require(path.resolve().is_relative_to(root / "assets"), "Parameter path leaves assets")
            raw = path.read_bytes()
            require(sha256(raw) == expected, "Asset hash mismatch: " + film["key"] + "/" + name)
            if name in encoded:
                require(raw == encoded[name], "Native ABI mismatch: " + name)
            if name == "profile.json" and "profile_sha256" in film:
                require(expected == film["profile_sha256"], "Profile hash differs")
        if custom and film["icon"] is None:
            continue
        icon = (root / film["icon"]).resolve()
        require(icon.is_relative_to(root / "assets"), "Icon path leaves assets")
        raw = icon.read_bytes()
        require(len(raw) == 40 * 40 * 4, "Film icon must be 40x40 RGBA")
        require(sha256(raw) == film["icon_sha256"], "Film icon hash differs")
    return {"status": ("PASS_PREPARED_ASSETS_AND_NATIVE_ENCODING" if prepared
                       else "PASS_CURATED_ASSETS_AND_NATIVE_ENCODING"), "films": len(films),
            "selected": len(selected),
            "defaults": [next(f["name"] for f in films if f["uid"] == uid)
                         for uid in defaults], "firmware_generated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json_bytes(verify_assets(args.directory)).decode(), end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
