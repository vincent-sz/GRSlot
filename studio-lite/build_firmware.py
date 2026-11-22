# SPDX-License-Identifier: GPL-2.0-only
"""Generate an offline FilmInfo candidate from an original GR III 2.10 BIN."""

import argparse
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

from app import DEFAULT_LIBRARY, Studio
from check_project import load_checked_project
from container_codec import blocks, repack_official_rtos, verify_package
from filminfo_runtime import ASSETS, ROOT, SOURCE, build_runtime
from native_profile import json_bytes, require, sha256
from native_registry import ROM_BASE


OFFLINE_FILENAME = "GRSlot.NOT-INSTALLABLE"


def verify_container(stock, package, icon_tail, build):
    original, _ = verify_package(stock)
    decoded, _ = verify_package(package)
    stock_blocks = blocks(original)
    output_blocks = blocks(decoded)
    require(tuple(stock_blocks) == tuple(output_blocks), "Firmware block list changed")
    for name, (header, start, end, block_type, ident) in stock_blocks.items():
        new_header, new_start, new_end, new_type, new_ident = output_blocks[name]
        require((new_type, new_ident) == (block_type, ident), f"{name} type or ID changed")
        if name == "ICONBIN":
            require(decoded[new_start:new_end] == original[start:end] + icon_tail,
                    "Native ICONBIN addresses or pixels changed")
        elif name != "RTOS":
            require(original[header:end] == decoded[new_header:new_end], f"Original {name} changed")
    _, start, end, _, _ = output_blocks["RTOS"]
    image = decoded[start:end]
    require(sha256(image) == build["rtos_sha256"], "Rebuilt RTOS failed readback")
    offset = build["menu_offset"]
    require(sha256(image[offset:offset + build["menu_bytes"]]) == build["menu_sha256"],
            "FilmInfo ARM module failed readback")
    for address, instruction in build["verified_entries"].items():
        require(struct.unpack_from("<I", image, address - ROM_BASE)[0] == instruction,
                f"FilmInfo entry {address:#x} failed readback")
    for icon in build["icon_overrides"].values():
        offset = icon["address"] - ROM_BASE
        require(sha256(image[offset:offset + 6400]) == icon["sha256"], "Custom film icon failed readback")
    return image


def source_hashes():
    paths = [*SOURCE.iterdir(), *ASSETS.iterdir(), DEFAULT_LIBRARY,
             *ROOT.glob("scripts/*.py"), *ROOT.glob("studio-lite/*.py")]
    return {str(path.relative_to(ROOT)): sha256(path.read_bytes()) for path in sorted(paths) if path.is_file()}


def build_firmware(project_path, firmware, output):
    from filminfo_verification import verify_native_entry_points

    require(not output.exists(), f"Choose a fresh output directory: {output}")
    require(output.parent.is_dir(), f"Output parent does not exist: {output.parent}")
    if firmware.is_dir():
        firmware = firmware / "fwdc239b.bin"
    sources = source_hashes()
    project, project_check = load_checked_project(project_path, firmware)
    stock = firmware.read_bytes()
    image, icon_tail, build = build_runtime(stock, project)
    package = repack_official_rtos(stock, image, icon_tail=icon_tail)
    actual = verify_container(stock, package, icon_tail, build)
    verify_native_entry_points(actual, build)
    require(repack_official_rtos(stock, actual, icon_tail=icon_tail) == package,
            "Repacking the verified image did not reproduce the same container")
    require(source_hashes() == sources, "Build source changed during verification")
    project_bytes = project_path.read_bytes()
    require(sha256(project_bytes) == project_check["project_sha256"],
            "Studio project changed during verification")

    digest = sha256(package)
    receipt = {
        "status": "PASS_OFFLINE_ARM_CONTAINER",
        "camera_status": "NOT_TESTED",
        "firmware_generated": True,
        "upgrade_output": "BLOCKED_PENDING_CAMERA_VALIDATION",
        "firmware_path": str(output / OFFLINE_FILENAME),
        "firmware_sha256": digest,
        "stock_sha256": sha256(stock),
        "studio_project_sha256": project_check["project_sha256"],
        "library_sha256": project_check["library_id"],
        "slots": project["slots"],
        "native_slots": build["native_slots"],
        "native_selected": build["native_selected"],
        "reference_firmware_sha256": build["reference_firmware_sha256"],
        "rtos_sha256": build["rtos_sha256"],
        "object_sha256": build["object_sha256"],
        "menu_sha256": build["menu_sha256"],
        "icon_tail_sha256": sha256(icon_tail),
        "icon_overrides": build["icon_overrides"],
        "sources": sources,
    }
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".grslot-build-") as temporary:
        staging = Path(temporary) / "verified"
        staging.mkdir()
        candidate = staging / OFFLINE_FILENAME
        candidate.write_bytes(package)
        require(sha256(candidate.read_bytes()) == digest, "Written image failed readback")
        (staging / "SHA256.txt").write_text(f"{digest}  {OFFLINE_FILENAME}\n", encoding="ascii")
        (staging / "studio-project.json").write_bytes(project_bytes)
        (staging / "verification.json").write_bytes(json_bytes(receipt))
        require(not output.exists(), f"Output directory appeared during build: {output}")
        staging.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    project = parser.add_mutually_exclusive_group(required=True)
    project.add_argument("--project", type=Path)
    project.add_argument("--bundled", action="store_true", help="Use all bundled public presets")
    parser.add_argument("--firmware", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    firmware, output = args.firmware.resolve(), args.output.resolve()
    try:
        if args.bundled:
            with tempfile.TemporaryDirectory(prefix="grslot-bundled-project-") as temporary:
                studio = Studio(DEFAULT_LIBRARY, Path(temporary))
                studio.save(studio.read())
                receipt = build_firmware(studio.project_path, firmware, output)
        else:
            receipt = build_firmware(args.project.resolve(), firmware, output)
    except ImportError as error:
        parser.exit(2, f"Install Unicorn in the Python environment used for this build: {error}\n")
    except (OSError, ValueError, KeyError, AssertionError, subprocess.SubprocessError, zlib.error) as error:
        parser.exit(2, f"GRSlot build stopped before producing an offline candidate: {error}\n")
    sys.stdout.buffer.write(json_bytes(receipt))


if __name__ == "__main__":
    main()
