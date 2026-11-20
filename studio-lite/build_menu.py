# SPDX-License-Identifier: GPL-2.0-only
"""Compile the existing P5 menu against the verified public film data."""

from collections import Counter
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from build_inputs import prepare_build_inputs
from check_project import DEFAULT_LIBRARY
from arm_link import link_arm_object
from container_codec import blocks, verify_package
from native_parameters import compile_routes
from native_profile import parse_json, require, sha256
from native_registry import ROM_BASE
from raw_platform import RAW_MODEL_END, prepare_playback_tables, prepare_raw_layout


ROOT = DEFAULT_LIBRARY.parents[1]
CATEGORIES = (
    ("all", "All Films", 2), ("favorites", "Favorites", 1),
    ("kodak", "Kodak", 0), ("fujifilm", "Fujifilm", 0), ("bw", "B&W", 0),
    ("digital", "Digital Cameras", 0), ("other", "Other Films", 0), ("my-luts", "My LUTs", 0),
)
FAMILIES = {
    "Ektar 100": (11, 68), "Ultramax 400": (18, 39), "Gold 200": (12, 40, 71),
    "Portra 160": (13, 72), "Portra 400": (14, 43, 73), "Portra 800": (15, 16, 17, 74, 75, 76),
    "Pro 400H": (9, 41, 57), "Vision3 5207": (5, 81), "C200": (8, 51),
    "X-Tra 400": (10, 59), "5247": (60, 61, 62), "Aerocolor IV 2460": (65, 66, 67),
}


# Stock entry instructions from the original 2.10 port of the native adapters.
STOCK_NATIVE_ROUTES = (
    (0x5318DEA0, 0xE241100B, "grs_public_to_raw_menu", 0xEA000000),
    (0x53209FB8, 0xE300329E, "grs_icon_width", 0xEA000000),
    (0x53209FEC, 0xE300329E, "grs_icon_height", 0xEA000000),
    (0x5320A020, 0xE1A0C00D, "grs_icon_blit", 0xEA000000),
    (0x5320A7CC, 0xE300129E, "grs_icon_draw_limit", 0xEA000000),
    (0x5320A804, 0xE30220FC, "grs_icon_token", 0xEA000000),
    (0x5324B42C, 0xE24BD028, "grs_boot_assignments", 0xEA000000),
    (0x53288D5C, 0xE241100B, "grs_public_to_raw", 0xEA000000),
    (0x53289038, 0xE51B3060, "grs_raw_seed_tail", 0xEA000000),
    (0x53289058, 0xE1A0C00D, "grs_raw_to_public", 0xEA000000),
    (0x53289304, 0xE080C001, "grs_raw_select_guard", 0xEA000000),
    (0x532922B4, 0xE351000A, "grs_list_name", 0xEA000000),
    (0x532935DC, 0xE351000A, "grs_list_icon", 0xEA000000),
    (0x535BF7C4, 0xE2400C01, "grs_dng_tone_read", 0xEA000000),
    (0x532A985C, 0xE1A0C00D, "grs_shoot_name", 0xEA000000),
    (0x532A9988, 0xE1A0C00D, "grs_shoot_icon", 0xEA000000),
    (0x532B6F34, 0xE2433008, "grs_playback_icon", 0xEA000000),
    (0x532B7D10, 0xE352000E, "grs_playback_parameters", 0xEA000000),
    (0x532B827C, 0xE24BD028, "grs_playback_grain_row", 0xEA000000),
    (0x535C3E6C, 0xE5943008, "grs_playback_import_grain", 0xEA000000),
    (0x532C2ACC, 0x93A0000C, "grs_native_slot_count", 0xEA000000),
    (0x532C2C80, 0xE1A0C00D, "grs_native_slot_forward", 0xEA000000),
    (0x532C2F08, 0xE1A0C00D, "grs_native_slot_reverse", 0xEA000000),
    (0x535131EC, 0xE2432011, "grs_grain_enable", 0xEA000000),
    (0x53608080, 0xEBFEFDE1, "grs_dng_tone_write", 0xEB000000),
    (0x536DB7FC, 0xE352000B, "grs_colour_converter", 0xEA000000),
    (0x536DB9C8, 0xE5C36795, "grs_grain_prepare", 0xEA000000),
    (0x536DC28C, 0xE3080D94, "grs_processing_index", 0xEA000000),
    (0x536DC2A4, 0xE3080E4C, "grs_processing_aux", 0xEA000000),
    (0x536DC2C8, 0x130F15EC, "grs_colour_source", 0xEA000000),
    (0x536DCB80, 0xE50B30CC, "grs_colour_refresh", 0xEA000000),
    (0x536E8694, 0xE5D4309B, "grs_gamma_gate", 0xEA000000),
    (0x536E87C4, 0xEB001989, "grs_gamma_getter", 0xEB000000),
)

def quote(value):
    return json.dumps(value, ensure_ascii=True)


def make_headers(rom_data, registry, films):
    """Bind the existing C menu ABI to the selected public data."""
    data = bytearray(rom_data)
    origin = registry["origin"]

    def put(raw):
        data.extend(bytes(-len(data) % 4))
        address = origin + len(data)
        data.extend(raw)
        return address

    film_bank = []
    rows = []
    for i, native in enumerate(registry["films"]):
        uid = native["uid"]
        name = films[uid]["name"]
        require(name.isascii() and 1 <= len(name) <= 32, "Native display name exceeds its text field")
        film_bank.extend((f'static const uint16_t name_{uid}[]=u{quote(name)};',
                          f'static const U text_{uid}[]={{0x100u|{len(name) + 1}u,(U)name_{uid}}};'))
        pointers = ",".join(f"(const void*){native[field]:#x}u" for field in ("basis", "aux", "m1", "gamma", "m2"))
        rows.append(f"{{{uid}u,{quote(name)},text_{uid},{0x10000 + i}u,{pointers}}}")
    film_bank.extend(("static const struct film films[]={" + ",\n".join(rows) + "};",
                      "static const U defaults[6]={" + ",".join(map(str, registry["defaults"])) + "};"))

    pixels = []
    for native in registry["films"]:
        film = films[native["uid"]]
        raw = (ROOT / film["icon"]).read_bytes()
        require(len(raw) == 6400 and sha256(raw) == film["icon_sha256"], "Film icon changed")
        pixels.append(put(raw))
    descriptor_base = put(struct.pack("<II", 0x00280028, 0) * len(pixels))
    pixel_table = put(struct.pack(f"<{len(pixels)}I", *pixels))
    library = [f"#define P5_DESC_BASE {descriptor_base:#x}u", f"#define P5_PIXELS {pixel_table:#x}u"]

    glyphs = {}
    for name in (*("category-" + item[0] for item in CATEGORIES), "action-back", "action-info", "action-install"):
        raw = (ROOT / f"assets/icons/ui/{name}/icon.rgba").read_bytes()
        require(len(raw) == 6400, "UI glyph must be 40x40 RGBA")
        # The existing menu glyph blitter consumes 32x32 RGBA.
        scaled = bytearray()
        for y in range(32):
            for x in range(32):
                offset = (y * 40 // 32 * 40 + x * 40 // 32) * 4
                scaled.extend(raw[offset:offset + 4])
        glyphs[name] = "GLYPH_" + name.upper().replace("-", "_")
        library.append(f"#define {glyphs[name]} ((const U*){put(scaled):#x}u)")
    library.extend(("struct category {const char*id;const uint16_t*name;U kind;const U*glyph;};",
                    "static const struct category categories[]={"))
    library.extend(f'{{"{key}",u{quote(name)},{kind}u,{glyphs["category-" + key]}}},'
                   for key, name, kind in CATEGORIES)
    library.extend(("};", "#define CATEGORY_COUNT (sizeof(categories)/sizeof(categories[0]))",
                    "struct metadata {U category,favorite;const uint16_t*short_name;const uint16_t*const*info;U info_count;};"))
    indices = {key: i for i, (key, _, _) in enumerate(CATEGORIES)}
    rows = []
    counts = Counter()
    uids = [row["uid"] for row in registry["films"]]
    for uid in uids:
        film = films[uid]
        category = indices[film["category"]]
        counts[category] += 1
        source = "Spektrafilm" if film["license"] == "CC-BY-SA-4.0" else "Spectral Film LUT"
        library.append(f'static const uint16_t*const info_{uid}[]={{name_{uid},u"{source}"}};')
        rows.append(f"{{{category}u,0u,name_{uid},info_{uid},2u}}")
    counts[0] = len(uids)
    library.extend(("static const struct metadata metadata[]={" + ",\n".join(rows) + "};",
                    "static const U category_counts[]={" + ",".join(str(counts[i]) for i in range(len(CATEGORIES))) + "};",
                    "static const uint16_t*const count_labels[]={" + ",".join(f'u"{n}"' for n in range(102)) + "};",
                    "static const U film_order[]={" + ",".join(map(str, range(len(uids)))) + "};"))

    group_names = {uid: name for name, members in FAMILIES.items() for uid in members}
    families = {}
    for uid in uids:
        film = films[uid]
        key = film["category"], group_names.get(uid, film["name"])
        families.setdefault(key, []).append(uid)
    capacity = max(map(len, families.values()))
    uid_family = [255] * (max(uids) + 1)
    for family, members in enumerate(families.values()):
        for uid in members:
            uid_family[uid] = family
    family_header = [f"#define FAMILY_COUNT {len(families)}u", f"#define FAMILY_VARIANT_CAPACITY {capacity}u",
                     "static const uint16_t*const family_names[]={" + ",".join("u" + quote(name) for _, name in families) + "};",
                     "static const uint8_t uid_family[]={" + ",".join(map(str, uid_family)) + "};",
                     "static const uint8_t family_variants[FAMILY_COUNT][FAMILY_VARIANT_CAPACITY]={" +
                     ",".join("{" + ",".join(map(str, members)) + "}" for members in families.values()) + "};"]
    data.extend(bytes(-len(data) % 32))
    require(origin + len(data) <= 0x55000000, "Public menu assets exceed the ROM window")
    headers = {name: "\n".join(lines) + "\n" for name, lines in
               (("film_bank.h", film_bank), ("library_data.h", library), ("families.h", family_header))}
    return bytes(data), headers, descriptor_base, pixel_table



def compile_menu(project_path, firmware_path):
    """Return the prepared assets and linked module, without installing them."""
    factory, project, receipt, payload, registry = prepare_build_inputs(project_path, firmware_path)
    decoded, _ = verify_package(factory)
    _, start, end, _, _ = blocks(decoded)["RTOS"]
    return compile_checked_menu(project, receipt, payload, registry, memoryview(decoded)[start:end])[:4]


def compile_checked_menu(project, receipt, payload, registry, stock):
    require(not project["overrides"], "The menu build currently supports the bundled presets without overrides")
    library_raw = DEFAULT_LIBRARY.read_bytes()
    require(sha256(library_raw) == receipt["library_id"], "Film library changed during menu compilation")
    library = parse_json(library_raw.decode("utf-8"))
    films = {film["uid"]: film for film in library["films"]}
    assets, headers, descriptors, pixels = make_headers(payload, registry, films)
    raw_data, raw_patches = prepare_raw_layout(stock, registry["origin"] + len(assets))
    assets += raw_data
    playback_data, playback_patches = prepare_playback_tables(stock, registry["origin"] + len(assets))
    assets += playback_data
    origin = registry["origin"] + len(assets)

    with tempfile.TemporaryDirectory(prefix="grslot-menu-") as temporary:
        work = Path(temporary)
        for path in (ROOT / "source/p5").iterdir():
            if path.is_file() and path.name not in headers:
                shutil.copyfile(path, work / path.name)
        for name, content in headers.items():
            (work / name).write_text(content, encoding="utf-8")

        obj = work / "menu.o"
        subprocess.run(
            ["xcrun", "clang", "-target", "armv7-none-eabi", "-marm", "-mfloat-abi=soft", "-Os",
             "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-fno-unwind-tables",
             "-fno-optimize-sibling-calls", "-Wall", "-Wextra", "-Werror",
             "-c", str(work / "menu.c"), "-o", str(obj)],
            check=True,
        )
        object_bytes = obj.read_bytes()
        module, symbols = link_arm_object(object_bytes, origin)
        parameter_assembly, parameter_routes = compile_routes(stock, symbols)
        (work / "parameter_routes.s").write_text(parameter_assembly, encoding="utf-8")
        hooks = {
            "GRS_CURVE_TABLE": registry["curve_table"], "GRS_FILM_COUNT": len(registry["films"]),
            "GRS_CHANGED": symbols["p4_changed"], "GRS_LOAD": symbols["p4_load"],
            "GRS_PARAMETER_RESTORE": symbols["grs_parameter_restore_current"],
            "GRS_NATIVE_FILM": symbols["p4_native_film"], "GRS_ICON": symbols["p4_icon"],
            "GRS_PROCESSING_BASIS": registry["processing_basis"],
            "GRS_PROCESSING_DESCRIPTORS": registry["processing_descriptors"],
            "GRS_PROCESSING_AUX": registry["processing_aux"],
            "GRS_RESOURCE_OVERRIDE": symbols["grs_resource_override"],
            "GRS_ICON_DESCRIPTORS": descriptors, "GRS_ICON_PIXELS": pixels,
        }
        for name, defines in (
            ("native_menu_tables", ()),
            ("native_menu_text", (f'-DGRS_COMMON_TEXT={symbols["grs_common_text"]:#x}',)),
            ("native_hooks", tuple(f"-D{key}={value:#x}" for key, value in hooks.items())),
            ("parameter_routes", ()),
            ("raw_hooks", (f'-DGRS_SEED_RAW={symbols["grs_seed_raw_slots"]:#x}',)),
            ("playback_grain", ()),
        ):
            adapter = work / f"{name}.o"
            subprocess.run(
                ["xcrun", "clang", "-target", "armv7-none-eabi", "-x", "assembler-with-cpp",
                 *defines, "-c", str(work / f"{name}.s"), "-o", str(adapter)],
                check=True,
            )
            padding = bytes(-len(module) % 4)
            code, adapter_symbols = link_arm_object(
                adapter.read_bytes(), origin + len(module) + len(padding)
            )
            require(symbols.keys().isdisjoint(adapter_symbols), "Duplicate native menu symbols")
            module += padding + code
            symbols.update(adapter_symbols)
    bindings = {
        **registry,
        "assets_origin": registry["origin"],
        "module_origin": origin,
        "slots": registry["defaults"],
        "icon_descriptors": descriptors,
        "icon_pixels": pixels,
        "parameter_routes": parameter_routes,
        "raw_patches": raw_patches,
        "playback_patches": playback_patches,
        "object_sha256": sha256(object_bytes),
    }
    return assets, module, symbols, origin, bindings


def native_menu_descriptors(stock, symbols):
    """Extend the two factory descriptor arrays, preserving the stock rows."""
    select_start = 0x53B3C6C0 - ROM_BASE
    submenu_start = 0x53B3FB10 - ROM_BASE
    select_size, submenu_size = 64, 100
    select_count, submenu_count = 117, 17
    require(submenu_start + submenu_count * submenu_size <= len(stock),
            "Native descriptor arrays exceed the stock RTOS")

    select = bytearray(stock[select_start:select_start + select_count * select_size])
    select_row = bytearray(select[:select_size])
    for offset, callback in (
        (8, "grs_menu_count"), (16, "grs_menu_label"),
        (24, "grs_menu_commit"), (32, "grs_menu_selected"),
    ):
        struct.pack_into("<II", select_row, offset, symbols[callback], 0)
    struct.pack_into("<H", select_row, 4, 900)
    select_row[48:56] = bytes(8)
    select.extend(select_row)

    submenu = bytearray(stock[submenu_start:submenu_start + submenu_count * submenu_size])
    submenu_row = bytearray(submenu[2 * submenu_size:3 * submenu_size])
    struct.pack_into("<H", submenu_row, 2, 907)
    submenu_row[6] = 1
    submenu_row[8:] = bytes(submenu_size - 8)
    struct.pack_into("<H", submenu_row, 8, 908)
    struct.pack_into("<I", submenu_row, 20, 0x02000141)
    struct.pack_into("<I", submenu_row, 40, 540)
    submenu.extend(submenu_row)
    return bytes(select), bytes(submenu)


def compile_menu_layout(origin, stock):
    layout_path = ROOT / "source/p5/native_menu_layout.json"
    layout = parse_json(layout_path.read_text(encoding="utf-8"))
    addresses = {int(entry["address"], 16) for entry in layout}
    require(len(layout) == len(addresses) == 43, "Invalid native menu layout patch table")
    lines = [(ROOT / "source/p5/native_menu_layout.s").read_text(encoding="utf-8")]
    routes = []
    for entry in layout:
        address = int(entry["address"], 16)
        offset = address - ROM_BASE
        before, after = (bytes.fromhex(entry[key]) for key in ("before", "after"))
        require(0 <= offset <= len(stock) - 4 and offset % 4 == 0
                and len(before) == len(after) == 4 and stock[offset:offset + 4] == before,
                f'Unexpected native menu layout at {entry["address"]}')
        original = int.from_bytes(before, "little")
        replacement = int.from_bytes(after, "little")
        lines.append(f"layout_reader {address:x}, {original:#x}, {replacement:#x}")
        routes.append((address, original, f"grs_layout_{address:x}", 0xEA000000))
    with tempfile.TemporaryDirectory(prefix="grslot-menu-layout-") as temporary:
        folder = Path(temporary)
        source = folder / "layout.s"
        source.write_text("\n".join(lines) + "\n", encoding="utf-8")
        obj = folder / "layout.o"
        subprocess.run(
            ["xcrun", "clang", "-target", "armv7-none-eabi", "-c", str(source), "-o", str(obj)],
            check=True,
        )
        module, symbols = link_arm_object(obj.read_bytes(), origin)
    return module, symbols, routes


def compile_menu_bootstrap(origin, select, submenu, publish, resume):
    source = ROOT / "source/p5/native_menu_bootstrap.s"
    with tempfile.TemporaryDirectory(prefix="grslot-menu-bootstrap-") as temporary:
        obj = Path(temporary) / "bootstrap.o"
        subprocess.run(
            ["xcrun", "clang", "-target", "armv7-none-eabi", "-x", "assembler-with-cpp",
             f"-DGRS_SELECT={select:#x}", f"-DGRS_SUBMENU={submenu:#x}",
             f"-DGRS_PUBLISH={publish:#x}", f"-DGRS_RESUME={resume:#x}",
             "-c", str(source), "-o", str(obj)],
            check=True,
        )
        return link_arm_object(obj.read_bytes(), origin)


def prepare_menu_image(project_path, firmware_path):
    """Stage native paint and input in an offline RTOS, with no upgrade output."""
    factory, project, receipt, payload, registry = prepare_build_inputs(project_path, firmware_path)
    decoded, _ = verify_package(factory)
    _, start, end, _, _ = blocks(decoded)["RTOS"]
    stock = memoryview(decoded)[start:end]
    assets, module, symbols, origin, bindings = compile_checked_menu(
        project, receipt, payload, registry, stock
    )
    assets_offset = registry["origin"] - ROM_BASE
    require(len(stock) <= assets_offset and registry["origin"] + len(assets) == origin,
            "Menu placement does not match the stock RTOS")

    # The P5 List callback retains the factory underlay and checks the active
    # panel before drawing its own row. It is stored in a native vtable.
    callback_offset = 0x53C0A34C - ROM_BASE
    factory_callback = 0x5339567C
    target = symbols["grs_change_frame"]
    require(struct.unpack_from("<I", stock, callback_offset)[0] == factory_callback,
            "The original List paint callback differs from the supported build")
    require(origin <= target < origin + len(module) and target % 4 == 0,
            "The replacement paint callback is outside the linked ARM module")

    image = bytearray(stock)
    struct.pack_into("<I", image, callback_offset, target)
    image.extend(bytes(assets_offset - len(image)))
    image.extend(assets)
    image.extend(module)
    image.extend(bytes(-len(image) % 4))
    select, submenu = native_menu_descriptors(stock, symbols)
    select_address = ROM_BASE + len(image)
    image.extend(select)
    submenu_address = ROM_BASE + len(image)
    image.extend(submenu)
    layout_origin = ROM_BASE + len(image)
    layout, layout_symbols, layout_routes = compile_menu_layout(layout_origin, stock)
    image.extend(layout)
    bootstrap_origin = ROM_BASE + len(image)
    bootstrap, bootstrap_symbols = compile_menu_bootstrap(
        bootstrap_origin, select_address, submenu_address,
        symbols["grs_publish_menu"], layout_symbols["grs_layout_5316fcec"],
    )
    image.extend(bootstrap)
    bss_offset = 0x53000460 - ROM_BASE
    require(struct.unpack_from("<I", stock, bss_offset)[0] == 0x55804374,
            "Factory BSS boundary does not match the native menu state")
    struct.pack_into("<I", image, bss_offset, RAW_MODEL_END)

    core_routes = (
        (0x5316F3B8, 0xE300313B, "grs_factory_entry", 0xEA000000),
        (0x53221A38, 0xE1A05001, "grs_action_input", 0xEB000000),
        (0x53221A4C, 0xEB001C7E, "grs_action_model_id", 0xEB000000),
        (0x531B9640, 0xE28134FE, "grs_select_model", 0xEA000000),
        (0x531C5950, 0xE28134FE, "grs_submenu_model", 0xEA000000),
        (0x533966D4, 0xE3003311, "grs_measure_name", 0xEA000000),
        (0x533970EC, 0xE3003311, "grs_draw_name", 0xEA000000),
    )
    table_routes = []
    for symbol in sorted(symbols):
        if symbol.startswith("grs_table_"):
            address = int(symbol.removeprefix("grs_table_"), 16)
            word = struct.unpack_from("<I", stock, address - ROM_BASE)[0]
            require(word & 0xFFFF0FFF == 0xE34503B3,
                    f"Unexpected factory descriptor reader at {address:#x}")
            table_routes.append((address, word, symbol, 0xEA000000))
    require(len(table_routes) == 20, "Missing native descriptor readers")

    touched = {ROM_BASE + callback_offset, ROM_BASE + bss_offset}
    for address, before, after in (*bindings["raw_patches"], *bindings["playback_patches"]):
        offset = address - ROM_BASE
        require(address not in touched and struct.unpack_from("<I", stock, offset)[0] == before,
                f"Unexpected factory RAW or Playback instruction at {address:#x}")
        touched.add(address)
        struct.pack_into("<I", image, offset, after)
    native_parameters = tuple(
        (address, before, symbol, 0xEB000000 if link else 0xEA000000)
        for address, before, symbol, link in bindings["parameter_routes"]
    )
    routes = {}
    all_symbols = {**symbols, **layout_symbols, **bootstrap_symbols}
    for address, original, symbol, opcode in (
        *core_routes, *table_routes, *layout_routes, *STOCK_NATIVE_ROUTES, *native_parameters
    ):
        if address == 0x5316FCEC:
            symbol = "grs_menu_bootstrap"
        offset = address - ROM_BASE
        require(address not in touched and struct.unpack_from("<I", stock, offset)[0] == original,
                f"Unexpected factory instruction at {address:#x} for {symbol}")
        touched.add(address)
        destination = all_symbols[symbol]
        displacement = destination - address - 8
        require(origin <= destination < ROM_BASE + len(image)
                and displacement % 4 == 0 and -(1 << 25) <= displacement < 1 << 25,
                f"Invalid ARM branch at {address:#x} for {symbol}")
        branch = opcode | ((displacement // 4) & 0xFFFFFF)
        struct.pack_into("<I", image, offset, branch)
        routes[symbol] = {"address": address, "before": original, "after": branch, "target": destination}
    image.extend(bytes(-len(image) % 32))
    require(ROM_BASE + len(image) <= 0x55000000, "Menu image exceeds the ROM window")
    return bytes(image), {
        "status": "OFFLINE_MENU_IMAGE_ONLY",
        "firmware_generated": False,
        "project_sha256": receipt["project_sha256"],
        "factory_sha256": registry["source_sha256"],
        "rtos_sha256": sha256(image),
        "callback": {"address": ROM_BASE + callback_offset, "before": factory_callback, "after": target},
        "routes": routes,
        "layout_edits": len(layout_routes),
        "raw_edits": len(bindings["raw_patches"]),
        "select_descriptors": select_address,
        "submenu_descriptors": submenu_address,
        "symbols": all_symbols,
        "bindings": bindings,
        "components": {
            "assets": {"address": registry["origin"], "size": len(assets), "sha256": sha256(assets)},
            "menu": {"address": origin, "size": len(module), "sha256": sha256(module)},
            "layout": {"address": layout_origin, "size": len(layout), "sha256": sha256(layout)},
            "bootstrap": {"address": bootstrap_origin, "size": len(bootstrap), "sha256": sha256(bootstrap)},
        },
    }
