# SPDX-License-Identifier: GPL-2.0-only
"""Rebuild the FilmInfo runtime in its original ROM layout."""

import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zlib

from app import DEFAULT_LIBRARY, icon_rgba
from arm_link import link_arm_object
from container_codec import DECODED, FACTORY, blocks, verify_package
from native_profile import require, sha256
from native_registry import COLOUR_FILES, ROM_BASE


ROOT = DEFAULT_LIBRARY.parents[1]
ASSETS = ROOT / "assets/runtime"
SOURCE = ROOT / "source/filminfo"
WORD = struct.Struct("<I")
SPAN = struct.Struct("<II")


def load_delta(path, digest):
    compressed = path.read_bytes()
    require(sha256(compressed) == digest, f"{path.name} failed SHA-256 validation")
    return zlib.decompress(compressed)


def restore_foundation(stock, layout):
    require(sha256(stock) == layout["factory_rtos_sha256"], "Unexpected original RTOS")
    image = bytearray(stock)
    image.extend(bytes(layout["rtos_size"] - len(image)))
    delta = load_delta(ASSETS / "filminfo-rtos.zlib", layout["runtime_delta_sha256"])
    cursor = previous = 0
    while cursor < len(delta):
        require(cursor + SPAN.size <= len(delta), "Truncated RTOS edit header")
        offset, size = SPAN.unpack_from(delta, cursor)
        cursor += SPAN.size
        require(size > 0 and previous <= offset <= len(image) - size and cursor + size <= len(delta),
                "Invalid FilmInfo RTOS edit range")
        image[offset:offset + size] = delta[cursor:cursor + size]
        cursor += size
        previous = offset + size
    require(sha256(image) == layout["runtime_foundation_sha256"], "FilmInfo RTOS restoration mismatch")
    return image


def initialize_headers(work, selected, defaults):
    def replace(path, replacement):
        original = path.read_text(encoding="utf-8")
        path.write_text(replacement(original), encoding="utf-8")

    def update_bank(source):
        source = re.sub(r'^.*\bfilm_(?:text|name)_(\d+)\b.*\n',
                        lambda row: row[0] if int(row[1]) in selected else "", source, flags=re.M)
        return re.sub(r"(defaults\[6\]=)\{[^}]+\}",
                      lambda row: row[1] + "{" + ",".join(map(str, defaults)) + "}", source)

    def update_library(source):
        metadata = re.search(r"(metadata\[\]=)\{(.*?)\};", source)
        rows = [(int(cat), int(favorite), int(uid)) for cat, favorite, uid in
                re.findall(r"\{(\d+)u,(\d+)u,film_name_(\d+)\}", metadata[2]) if int(uid) in selected]
        require({uid for _, _, uid in rows} == selected, "Incomplete FilmInfo library metadata")
        source = source[:metadata.start(2)] + ",".join(
            f"{{{cat}u,{favorite}u,film_name_{uid}}}" for cat, favorite, uid in rows
        ) + source[metadata.end(2):]
        counts = [len(rows), sum(favorite for _, favorite, _ in rows)]
        counts.extend(sum(cat == index for cat, _, _ in rows) for index in range(2, 8))
        for name, values in (("film_order", range(len(rows))), ("category_counts", counts)):
            source = re.sub(rf"({name}\[\]=)\{{[^}}]+\}}",
                            lambda row: row[1] + "{" + ",".join(map(str, values)) + "}", source)
        return source

    def update_families(source):
        # Compact each family so its menu can index variants consecutively.
        families = re.search(r"(family_variants[^=]+=)\{(.*?)\};", source)
        rows = re.findall(r"\{([\d,]*)\}", families[2])
        variants = []
        for row in rows:
            chosen = [uid for uid in map(int, filter(None, row.split(","))) if uid in selected]
            variants.append("{" + ",".join(map(str, chosen or [0])) + "}")
        return source[:families.start(2)] + ",".join(variants) + source[families.end(2):]

    replace(work / "film_bank.h", update_bank)
    replace(work / "library_data.h", update_library)
    replace(work / "families.h", update_families)


def compile_menu(layout, selected, defaults):
    with tempfile.TemporaryDirectory(prefix="grslot-filminfo-") as temp:
        work = Path(temp)
        for path in SOURCE.iterdir():
            if path.suffix in {".c", ".h", ".inc"}:
                shutil.copyfile(path, work / path.name)
        initialize_headers(work, selected, defaults)
        obj = work / "menu.o"
        subprocess.run(
            ["xcrun", "clang", "-target", "armv7-none-eabi", "-marm", "-mfloat-abi=soft", "-Os",
             "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-fno-unwind-tables",
             "-fno-optimize-sibling-calls", "-Wall", "-Wextra", "-Werror",
             "-c", str(work / "menu.c"), "-o", str(obj)],
            check=True,
        )
        object_data = obj.read_bytes()
    code, symbols = link_arm_object(object_data, layout["menu_origin"])
    require(len(code) <= layout["menu_capacity"], "Menu would overlap the retained native icon bridge")
    return code, symbols, sha256(object_data)


def verify_film_parameters(image, uid_map):
    """Bind the retained FilmInfo colour graphs to the public asset hashes."""
    film_bank = (SOURCE / "film_bank.h").read_text(encoding="utf-8")
    graph_addresses = {}
    for line in film_bank.splitlines():
        if re.match(r"^\{\d+,", line):
            uid = int(line[1:].split(",", 1)[0])
            graph_addresses[uid] = [int(addr, 16) for addr in re.findall(r"0x([0-9a-f]+)u", line)][2:]
    library = json.loads(DEFAULT_LIBRARY.read_bytes())
    require({film["uid"] for film in library["films"]} == set(uid_map)
            and set(graph_addresses) == set(uid_map.values()) and len(uid_map) == len(graph_addresses),
            "FilmInfo IDs do not match the public library")
    for film in library["films"]:
        addresses = graph_addresses[uid_map[film["uid"]]]
        require(len(addresses) == len(COLOUR_FILES), "Incomplete FilmInfo colour graph")
        for address, (_, name, size) in zip(addresses, COLOUR_FILES):
            offset = address - ROM_BASE
            require(0 <= offset <= len(image) - size
                    and sha256(image[offset:offset + size]) == film["files"][name],
                    f"FilmInfo colour graph mismatch for public UID {film['uid']}")


def build_runtime(factory, project):
    require(sha256(factory) == FACTORY, "Expected the exact official GR III 2.10 input")
    decoded, _ = verify_package(factory)
    require(sha256(decoded) == DECODED, "Unexpected decoded original firmware")
    directory = blocks(decoded)
    _, start, end, _, _ = directory["RTOS"]
    _, icon_start, icon_end, _, _ = directory["ICONBIN"]
    layout = json.loads((ASSETS / "filminfo-layout.json").read_bytes())
    require(layout["format"] == 1, "Unsupported FilmInfo layout")
    require(sha256(decoded[icon_start:icon_end]) == layout["factory_iconbin_sha256"],
            "Unexpected original ICONBIN")
    image = restore_foundation(decoded[start:end], layout)
    icon_tail = load_delta(ASSETS / "filminfo-icons.zlib", layout["icon_delta_sha256"])
    require(sha256(decoded[icon_start:icon_end] + icon_tail) == layout["reference_iconbin_sha256"],
            "Original native icon addresses do not reproduce the FilmInfo reference")
    uid_map = {int(key): uid for key, uid in layout["studio_to_native_uid"].items()}
    verify_film_parameters(image, uid_map)
    selected = {uid_map[uid] for uid in project["selected"]}
    defaults = [uid_map[uid] for uid in project["slots"]]
    require(len(defaults) == 6 and set(defaults) <= selected, "Invalid FilmInfo slots")
    icon_changes = {}
    for key, values in project["overrides"].items():
        uid = int(key)
        require(values.keys() <= {"icon", "icon_design"}, "Firmware supports icon overrides only")
        if uid in project["selected"] and "icon" in values:
            native_uid = uid_map[uid]
            pointer, = WORD.unpack_from(image, layout["icon_pixels"] - ROM_BASE + (native_uid - 1) * 4)
            offset = pointer - ROM_BASE
            rgba = icon_rgba(values["icon"])
            require(len(rgba) == 6400 and 0 <= offset <= len(image) - len(rgba), "Invalid FilmInfo artwork pointer")
            # Give each changed icon its own allocation to preserve shared defaults.
            new_pointer = ROM_BASE + len(image)
            image.extend(rgba)
            WORD.pack_into(image, layout["icon_pixels"] - ROM_BASE + (native_uid - 1) * 4, new_pointer)
            icon_changes[uid] = {"address": new_pointer, "sha256": sha256(rgba)}
    require(len(image) % 32 == 0 and ROM_BASE + len(image) < 0x55000000, "FilmInfo exceeds its ROM window")
    module, symbols, object_hash = compile_menu(layout, selected, defaults)
    first = layout["menu_origin"] - ROM_BASE
    require(not any(image[first:first + layout["menu_capacity"]]), "FilmInfo menu region is occupied")
    image[first:first + len(module)] = module
    routes = {}
    for address, symbol in layout["entries"].items():
        address = int(address, 16)
        target = symbols[symbol]
        offset = address - ROM_BASE
        delta = target - address - 8
        require(0 <= offset <= len(image) - 4 and offset % 4 == 0 and
                not WORD.unpack_from(image, offset)[0] and
                delta % 4 == 0 and -(1 << 25) <= delta < (1 << 25) and
                layout["menu_origin"] <= target < layout["menu_origin"] + len(module),
                f"FilmInfo entry {address:#x} differs from its recorded layout")
        instruction = 0xEA000000 | (delta // 4 & 0xFFFFFF)
        WORD.pack_into(image, offset, instruction)
        routes[address] = instruction
    return bytes(image), icon_tail, {
        "reference_firmware_sha256": layout["reference_firmware_sha256"],
        "rtos_sha256": sha256(image),
        "object_sha256": object_hash,
        "menu_sha256": sha256(module),
        "menu_offset": first,
        "menu_bytes": len(module),
        "native_slots": defaults,
        "native_selected": sorted(selected),
        "icon_overrides": icon_changes,
        "verified_entries": routes,
        "symbols": symbols,
    }
