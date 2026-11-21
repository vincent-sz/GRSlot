# SPDX-License-Identifier: GPL-2.0-only
"""Build and verify a local GRSlot candidate from original GR III 2.10."""

import argparse
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from build_menu import ROOT, prepare_menu_image
from app import DEFAULT_LIBRARY, Studio
from container_codec import blocks, repack_official_rtos, verify_package
from native_profile import json_bytes, require, sha256
from native_registry import ROM_BASE


def verify_container(stock, package, receipt):
    original, _ = verify_package(stock)
    decoded, _ = verify_package(package)
    stock_blocks = blocks(original)
    output_blocks = blocks(decoded)
    require(tuple(stock_blocks) == tuple(output_blocks), "Firmware block list changed")
    for name, (header, _, end, _, _) in stock_blocks.items():
        if name != "RTOS":
            new_header, _, new_end, _, _ = output_blocks[name]
            require(original[header:end] == decoded[new_header:new_end],
                    f"Original {name} changed when the container was rebuilt")
    _, start, end, _, _ = output_blocks["RTOS"]
    image = decoded[start:end]
    require(sha256(image) == receipt["rtos_sha256"], "Rebuilt RTOS failed readback")

    for name, component in receipt["components"].items():
        offset = component["address"] - ROM_BASE
        component_end = offset + component["size"]
        require(0 <= offset < component_end <= len(image)
                and sha256(image[offset:component_end]) == component["sha256"],
                f"Rebuilt {name} failed readback")
    for name, route in {"paint_callback": receipt["callback"], **receipt["routes"]}.items():
        require(struct.unpack_from("<I", image, route["address"] - ROM_BASE)[0] == route["after"],
                f"Rebuilt {name} entry failed readback")
    for address, _, after in (*receipt["bindings"]["raw_patches"], *receipt["bindings"]["playback_patches"]):
        require(struct.unpack_from("<I", image, address - ROM_BASE)[0] == after,
                f"Rebuilt RAW or Playback entry {address:#x} failed readback")
    _, stock_start, stock_end, _, _ = stock_blocks["RTOS"]
    return image, original[stock_start:stock_end]


def source_hashes():
    files = [*ROOT.glob("source/p5/*"), *ROOT.glob("scripts/*.py"), *ROOT.glob("studio-lite/*.py")]
    return {str(path.relative_to(ROOT)): sha256(path.read_bytes()) for path in sorted(files) if path.is_file()}


def build_firmware(project, firmware, output):
    from arm_verification import ArmPublicMenuChecks
    from unicorn import UcError

    require(not output.exists(), f"Choose a fresh output directory: {output}")
    require(output.parent.is_dir(), f"Output parent does not exist: {output.parent}")
    if firmware.is_dir():
        firmware = firmware / "fwdc239b.bin"
    sources = source_hashes()
    stock = firmware.read_bytes()
    image, build = prepare_menu_image(project, firmware)
    require(sha256(stock) == build["factory_sha256"], "Original firmware changed during build")
    package = repack_official_rtos(stock, image)
    verified_image, stock_image = verify_container(stock, package, build)
    checks = ArmPublicMenuChecks()
    try:
        checks.verify_file_identity(stock_image, verified_image)
        checks.verify_raw_lifetime(verified_image)
        checks.verify_menu_owner(verified_image)
        checks.verify(verified_image, build["symbols"], build["bindings"])
    except UcError as error:
        raise ValueError(f"ARM verification failed: {error}") from error
    require(repack_official_rtos(stock, verified_image) == package,
            "Repacking the verified RTOS did not reproduce the same container")
    require(source_hashes() == sources, "Build source changed during verification")
    project_bytes = project.read_bytes()
    require(sha256(project_bytes) == build["project_sha256"], "Studio project changed during build")

    name = "fwdc239b.bin"
    digest = sha256(package)
    receipt = {
        "status": "PASS_DESKTOP_ARM_CONTAINER",
        "camera_status": "NOT_TESTED",
        "firmware_generated": True,
        "firmware_path": str(output / name),
        "firmware_sha256": digest,
        "firmware_size": len(package),
        "stock_sha256": build["factory_sha256"],
        "studio_project_sha256": build["project_sha256"],
        "library_sha256": build["bindings"]["library_sha256"],
        "slots": build["bindings"]["slots"],
        "rtos_sha256": build["rtos_sha256"],
        "object_sha256": build["bindings"]["object_sha256"],
        "components": build["components"],
        "sources": sources,
    }
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".grslot-build-") as temporary:
        staging = Path(temporary) / "verified"
        staging.mkdir()
        candidate = staging / name
        candidate.write_bytes(package)
        require(sha256(candidate.read_bytes()) == digest, "Written firmware candidate failed readback")
        (staging / "SHA256.txt").write_text(f"{digest}  {name}\n", encoding="ascii")
        (staging / "studio-project.json").write_bytes(project_bytes)
        (staging / "verification.json").write_bytes(json_bytes(receipt))
        require(not output.exists(), f"Output directory appeared during build: {output}")
        staging.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    project = parser.add_mutually_exclusive_group(required=True)
    project.add_argument("--project", type=Path)
    project.add_argument("--bundled", action="store_true", help="Create a Studio project with the bundled presets")
    parser.add_argument("--firmware", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        firmware = args.firmware.resolve()
        output = args.output.resolve()
        if args.bundled:
            with tempfile.TemporaryDirectory(prefix="grslot-bundled-project-") as temporary:
                studio = Studio(DEFAULT_LIBRARY, Path(temporary))
                studio.save(studio.read())
                receipt = build_firmware(studio.project_path, firmware, output)
        else:
            receipt = build_firmware(args.project.resolve(), firmware, output)
    except ImportError as error:
        parser.exit(2, f"Install Unicorn in the Python environment used for this build: {error}\n")
    except (OSError, ValueError, KeyError, AssertionError, subprocess.SubprocessError) as error:
        parser.exit(2, f"GRSlot build stopped before producing a candidate: {error}\n")
    sys.stdout.buffer.write(json_bytes(receipt))


if __name__ == "__main__":
    main()
