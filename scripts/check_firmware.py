# SPDX-License-Identifier: GPL-2.0-only
"""Read-only identification of the exact supported official input."""
import argparse
import struct
from pathlib import Path

from container_codec import blocks, verify_package, DECODED
from native_profile import FACTORY_SHA256, NATIVE_B, json_bytes, require, sha256


def inspect_firmware(path):
    return inspect_firmware_bytes(Path(path).read_bytes())


def inspect_firmware_bytes(data):
    require(sha256(data) == FACTORY_SHA256,
            "Unsupported input. Require the exact official standard GR III 2.10 package, "
            "SHA-256 " + FACTORY_SHA256)
    decoded, frames = verify_package(data)
    require(sha256(decoded) == DECODED, "Decoded official input does not match")
    entries = blocks(decoded)
    _, start, end, _, _ = entries["RTOS"]
    matrix_at = start + 0x53dc1444 - 0x53000000
    require(struct.unpack_from("<9i", decoded, matrix_at) == tuple(sum(NATIVE_B, [])),
            "Native CSP basis differs from the verified ABI")
    return {"status": "PASS_OFFICIAL_INPUT_ONLY", "model": "GR III", "firmware": "2.10",
            "sha256": sha256(data), "bytes": len(data), "decoded_sha256": sha256(decoded),
            "rtos_bytes": end - start, "compressed_frames": len(frames),
            "camera_installed_firmware": "REQUIRES_USER_CONFIRMATION",
            "firmware_generated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path)
    args = parser.parse_args()
    try:
        print(json_bytes(inspect_firmware(args.firmware)).decode(), end="")
    except (OSError, ValueError, KeyError, struct.error) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
