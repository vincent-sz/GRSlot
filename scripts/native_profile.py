# SPDX-License-Identifier: GPL-2.0-only
# Darkslide-derived validation/parser portions: Copyright (C) 2026 LiorMoment.
"""Validate and encode the existing GRSlot V3 native parameter ABI.

The rational CSP conversion is reused from the verified V3 P2 encoder.
Profile validation follows Darkslide GR's GPL-2.0-only validation contract.
"""
import hashlib
import json
import math
import struct
from fractions import Fraction
from pathlib import Path

FACTORY_SHA256 = "d6a3c9c288d784080e7b283222ecdd8752adfeed6faa36dab44f73115354bfd4"
BASE_MODEL = "gr3-210-upstream-neutral-stubbed-v2"
ENVELOPE_MODEL = "gr3-210-stored-look-and-curve-bounds-v1"
NATIVE_B = [[77, 150, 29], [-43, -85, 128], [128, -107, -21]]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field: " + key)
        result[key] = value
    return result


def _finite(value):
    number = float(value)
    require(math.isfinite(number), "Non-finite JSON number")
    return number


def _invalid(value):
    raise ValueError("Non-finite JSON constant: " + value)


def parse_json(text):
    return json.loads(text, object_pairs_hook=_pairs, parse_float=_finite,
                      parse_constant=_invalid)


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8"))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def validate_profile(profile):
    require(type(profile) is dict and type(profile.get("schema")) is int
            and profile["schema"] == 1, "Require profile schema 1")
    require(profile.get("model") == "GR III" and profile.get("firmware") == "2.10",
            "Only standard GR III 2.10 profiles are supported")
    require(type(profile.get("id")) is str and bool(profile["id"]), "Missing profile ID")
    for key, width, lower, upper in (
        ("look_matrix_q13", 3, -32768, 32767),
        ("curves_u14", 256, 0, 16383),
        ("post_matrix_q512", 3, -32768, 32767),
    ):
        matrix = profile.get(key)
        require(type(matrix) is list and len(matrix) == 3, "Invalid " + key)
        for row in matrix:
            require(type(row) is list and len(row) == width
                    and all(type(v) is int and lower <= v <= upper for v in row),
                    "Invalid integer storage in " + key)
    require(all(sum(row) == 8192 for row in profile["look_matrix_q13"]),
            "M1 must preserve white in Q13")
    require(all(sum(row) == 512 for row in profile["post_matrix_q512"]),
            "Post matrix must preserve white in Q512")
    require(all(sum(abs(profile["post_matrix_q512"][r][c]) for r in range(3)) <= 8191
                for c in range(3)), "Post matrix exceeds signed ARM accumulation bound")
    json.dumps(profile, allow_nan=False)
    return profile


def _inverse3(matrix):
    augmented = [[Fraction(x) for x in row] + [Fraction(int(i == j)) for j in range(3)]
                 for i, row in enumerate(matrix)]
    for i in range(3):
        pivot = next(k for k in range(i, 3) if augmented[k][i])
        augmented[i], augmented[pivot] = augmented[pivot], augmented[i]
        scale = augmented[i][i]
        augmented[i] = [v / scale for v in augmented[i]]
        for k in range(3):
            if k != i:
                scale = augmented[k][i]
                augmented[k] = [v - scale * w for v, w in zip(augmented[k], augmented[i])]
    return [row[3:] for row in augmented]


def _multiply(left, right):
    return [[sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def encode_profile(profile):
    validate_profile(profile)
    post = profile["post_matrix_q512"]
    desired = [[(v + 256) // 512 for v in row] for row in _multiply(NATIVE_B, post)]
    require(all(-256 <= v <= 255 for row in desired for v in row),
            "Native CSP signed9 coefficient range exceeded")
    source = _multiply(desired, _inverse3(NATIVE_B))
    q13 = [[round(v * 8192) for v in row] for row in source]
    require(all(-(1 << 31) <= v < (1 << 31) for row in q13 for v in row),
            "Native CSP signed32 storage exceeded")
    require(all(sum(abs(v) for v in row) * 150 + 4096 < (1 << 31) for row in q13),
            "Native CSP accumulation bound exceeded")
    actual = [[((v + 4096) & 0xffffffff) >> 13 for v in row]
              for row in _multiply(q13, NATIVE_B)]
    signed = [[v - (1 << 19) if v & (1 << 18) else v for v in row] for row in actual]
    require(signed == desired, "Native CSP integer result differs from Darkslide")
    files = {
        "M1_Q13_s16.bin": struct.pack("<9h", *sum(profile["look_matrix_q13"], [])),
        "RGB_GAMMA_u16.bin": struct.pack("<768H", *sum(profile["curves_u14"], [])),
        "M2_NATIVE_CSP_Q13_s32.bin": struct.pack("<9i", *sum(q13, [])),
    }
    receipt = {"status": "PASS_NATIVE_ENCODING", "native_B": NATIVE_B,
               "expected_coefficients": desired, "actual_coefficients": signed,
               "native_source_q13": q13, "runtime_math_added": False,
               "files": {name: sha256(data) for name, data in files.items()}}
    files["CSP_ENCODING.json"] = json_bytes(receipt)
    return files
