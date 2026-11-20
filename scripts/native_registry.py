# SPDX-License-Identifier: GPL-2.0-only
"""Build native colour data from factory resources and the selected presets."""

from pathlib import Path
import struct

from container_codec import DECODED, FACTORY, blocks, sha, verify_package
from native_profile import parse_json, require
from verify_assets import ROOT, validate_selection, verify_assets


ROM_BASE = 0x53000000
RAM_BASE = 0x55000000
RAM_INITIALIZER = 0x5407b540
RAM_INITIALIZER_SIZE = 0x3a080
STANDARD_BASIS = 0x550192f4
NATIVE_AUX = 0x53dc555c
COLOUR_FILES = (
    ("m1", "M1_Q13_s16.bin", 18),
    ("gamma", "RGB_GAMMA_u16.bin", 1536),
    ("m2", "M2_NATIVE_CSP_Q13_s32.bin", 36),
)


def build_native_registry(factory, library_path=ROOT / "assets/library.json", *, selected=None, defaults=None,
                          origin=None):
    """Return a ROM data section and its symbol map, without installing hooks."""
    require(sha(factory) == FACTORY, "Native registry requires the exact official GR III 2.10 input")
    decoded, _ = verify_package(factory)
    require(sha(decoded) == DECODED, "Decoded official input does not match")
    _, start, end, _, _ = blocks(decoded)["RTOS"]
    stock = memoryview(decoded)[start:end]
    minimum_origin = (ROM_BASE + len(stock) + 31) & ~31
    if origin is None:
        origin = minimum_origin
    require(type(origin) is int and minimum_origin <= origin < RAM_BASE and origin % 32 == 0,
            "Native registry origin must be aligned and outside the official RTOS")

    def stock_bytes(address, size):
        if RAM_BASE <= address < RAM_BASE + RAM_INITIALIZER_SIZE:
            require(address + size <= RAM_BASE + RAM_INITIALIZER_SIZE, "Factory initializer boundary")
            address = RAM_INITIALIZER + address - RAM_BASE
        offset = address - ROM_BASE
        require(0 <= offset <= len(stock) - size, "Factory resource outside the official RTOS")
        return stock[offset:offset + size].tobytes()

    basis = stock_bytes(STANDARD_BASIS, 84)
    aux = stock_bytes(NATIVE_AUX, 84)
    tuning_source = struct.unpack_from("<I", basis, 8)[0]
    tuning_pointers = struct.unpack("<9I", stock_bytes(tuning_source, 36))
    tuning_matrices = [stock_bytes(pointer, 18) for pointer in tuning_pointers]

    library_path = Path(library_path).resolve()
    if library_path == ROOT / "assets/library.json":
        root = ROOT
    else:
        require(library_path.name == "library.json", "Use the prepared library.json")
        root = library_path.parent
    library_raw = library_path.read_bytes()
    verify_assets(root)
    require(library_path.read_bytes() == library_raw, "Film library changed while preparing the registry")
    library = parse_json(library_raw.decode("utf-8"))
    if selected is not None:
        library["selected"] = selected
    if defaults is not None:
        library["defaults"] = defaults
    chosen = validate_selection(library)
    films = {film["uid"]: film for film in library["films"]}

    data = bytearray()

    def put(raw, alignment=4):
        data.extend(bytes(-len(data) % alignment))
        address = origin + len(data)
        data.extend(raw)
        return address

    tuning = [put(matrix, 2) for matrix in tuning_matrices]
    tuning_table = put(struct.pack("<9I", *tuning))
    entries = []
    curves = []
    for uid in chosen:
        film = films[uid]
        addresses = {}
        for field, filename, size in COLOUR_FILES:
            path = (root / film["profile"]).with_name(filename).resolve()
            require(path.is_relative_to(root / "assets"), "Colour file leaves library assets")
            raw = path.read_bytes()
            require(len(raw) == size and sha(raw) == film["files"][filename], "Colour file changed during build")
            addresses[field] = put(raw)
        csp_table = put(struct.pack("<9I", *[addresses["m2"]] * 9))
        film_basis = bytearray(basis)
        struct.pack_into("<II", film_basis, 4, addresses["m1"], tuning_table)
        addresses["basis"] = put(film_basis)
        film_aux = bytearray(aux)
        struct.pack_into("<I", film_aux, 0, csp_table)
        addresses["aux"] = put(film_aux)
        gamma = addresses["gamma"]
        curves.extend((addresses["aux"], gamma, gamma + 512, gamma + 1024))
        entries.append({"uid": uid, **addresses})
    curve_table = put(struct.pack(f"<{len(curves)}I", *curves))
    by_uid = {entry["uid"]: entry for entry in entries}
    default_rows = [by_uid[uid] for uid in library["defaults"]]
    processing_basis = put(stock_bytes(0x55018D94, 26 * 4) +
                           struct.pack("<6I", *(entry["basis"] for entry in default_rows)))
    processing_descriptors = put(stock_bytes(0x55018CF0, 26 * 4) + struct.pack("<6I", *[0x53DC2BA0] * 6))
    processing_aux = put(stock_bytes(0x55018E4C, 26 * 4) +
                         struct.pack("<6I", *(entry["aux"] for entry in default_rows)))
    data.extend(bytes(-len(data) % 32))
    require(origin + len(data) <= RAM_BASE, "Native registry exceeds the ROM window")
    return bytes(data), {"origin": origin, "defaults": list(library["defaults"]), "films": entries,
                         "curve_table": curve_table, "tuning_table": tuning_table,
                         "processing_basis": processing_basis, "processing_descriptors": processing_descriptors,
                         "processing_aux": processing_aux,
                         "source_sha256": FACTORY, "library_sha256": sha(library_raw), "data_sha256": sha(data)}
