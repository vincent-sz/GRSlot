# SPDX-License-Identifier: GPL-2.0-only
"""Rebuild the verified RAW colour row layout from an official 2.10 RTOS."""

from collections import Counter
import struct

from container_codec import need
from native_registry import ROM_BASE


RAW_ROWS = 20
RAW_STRIDE = 340
RAW_OFFSET = 0x400
RAW_SIZE = 0x800
RAW_MODEL_ADDRESS = 0x55804440
RAW_MODEL_END = RAW_MODEL_ADDRESS + RAW_SIZE


def mov16(instruction, value):
    return instruction & ~0xF0FFF | ((value & 0xF000) << 4) | (value & 0xFFF)


def prepare_playback_tables(rtos, origin):
    """Extend the native per-photo tone table while retaining factory entries."""
    entries = (
        (0x535C2514, 0xE350000B, 0xE3500011),
        (0x535C2518, 0x930D3D64, mov16(0x930D3D64, origin & 0xFFFF)),
        (0x535C2520, 0x934533D2, mov16(0x934533D2, origin >> 16)),
        (0x532B44DC, 0xE350000B, 0xE3500011),
        (0x532B44E4, 0xE30C3BC4, mov16(0xE30C3BC4, (origin + 20) & 0xFFFF)),
        (0x532B44EC, 0xE34533B5, mov16(0xE34533B5, (origin + 20) >> 16)),
        (0x535CA2A4, 0xE2812008, 0xE1A02001),
    )
    ordinal_offset = 0x53D2DD64 - ROM_BASE
    display_offset = 0x53B5CBC4 - ROM_BASE
    ordinals = bytes(rtos[ordinal_offset:ordinal_offset + 12])
    display = bytes(rtos[display_offset:display_offset + 12])
    need(ordinals == bytes(range(1, 13)) and len(display) == 12 and origin % 4 == 0,
         "Factory Playback tone tables changed")
    data = ordinals + bytes(range(13, 19)) + bytes(2) + display + bytes(range(30, 36))
    return data + bytes(-len(data) % 32), entries


def prepare_raw_layout(rtos, origin):
    data = bytearray()
    patches = {}

    def read(address, size=4):
        index = address - ROM_BASE
        need(0 <= index <= len(rtos) - size, f"RAW address outside factory RTOS: {address:#x}")
        return rtos[index:index + size]

    def word(address):
        return struct.unpack("<I", read(address))[0]

    def add(raw):
        data.extend(bytes(-(origin + len(data)) % 4))
        address = origin + len(data)
        data.extend(raw)
        return address

    def patch(address, value):
        need(address not in patches, f"Duplicate RAW patch at {address:#x}")
        patches[address] = (word(address), value)

    def immediate(address, value):
        for rotation in range(16):
            rotated = ((value << (rotation * 2)) | (value >> (32 - rotation * 2))) & 0xFFFFFFFF
            if rotated <= 255:
                patch(address, word(address) & ~0xFFF | (rotation << 8) | rotated)
                return
        raise ValueError(f"RAW immediate is out of range: {value:#x}")

    def change_field(address):
        old = word(address)
        offset = old & 0xFFF
        need(0x86 <= offset <= 0x96, f"Unexpected factory RAW byte field {address:#x}")
        patch(address, old & ~0xFFF | (RAW_OFFSET + offset - 0x86))

    factory_capability = read(0x53B5A750, 13 * 17)
    custom_capability = bytearray(factory_capability[17:34])
    custom_capability[15] = 1
    capability = add(bytes(factory_capability) + bytes(17) + bytes(custom_capability) * 6)
    selection = add(bytes((*range(1, 13), *range(14, 20))))
    groups = add(bytes(19) + bytes([1, 2]))
    need((word(0x53283360), word(0x53283364)) == (0x13A0000F, 0x03A0000E),
         "RAW selector count does not match the factory")
    immediate(0x53283360, 21)
    immediate(0x53283364, 20)
    for site in (0x532834D8, 0x532834F4):
        patch(site, mov16(word(site), groups & 0xFFFF))
    for site in (0x532834DC, 0x53283510, 0x53283564):
        patch(site, mov16(word(site), groups >> 16))
    for site in (0x532835C8, 0x532835DC):
        patch(site, mov16(word(site), selection & 0xFFFF))
    for site in (0x532835CC, 0x532835E4):
        patch(site, mov16(word(site), selection >> 16))

    counts = Counter()
    for low, high in ((0x53283D18, 0x5328452C), (0x532846DC, 0x53284918), (0x53286E94, 0x532885D8)):
        for site in range(low, high, 4):
            old = word(site)
            if old & 0x0FF00FFF == 0x0350000D:
                immediate(site, RAW_ROWS)
                counts['bounds'] += 1
            elif old & 0x0FFF0FFF == 0x03A000DD:
                patch(site, mov16(old & 0xF000F000 | 0x03000000, RAW_STRIDE))
                counts['stride'] += 1
            elif old & 0x0E000000 == 0x04000000 and not old & (1 << 25) and 0x86 <= old & 0xFFF <= 0x96:
                change_field(site)
                counts['field'] += 1
            elif old == 0x53B5A758:
                patch(site, capability + 8)
                counts['literal'] += 1
        for site in range(low, high, 4):
            old = word(site)
            if old & 0x0FF00000 != 0x03000000 or mov16(old, 0xA750) != old:
                continue
            for upper in range(site + 4, min(site + 36, high), 4):
                top = word(upper)
                if top & 0x0FF00000 == 0x03400000 and (top >> 12) & 15 == (old >> 12) & 15 and mov16(top, 0x53B5) == top:
                    patch(site, mov16(old, capability & 0xFFFF))
                    patch(upper, mov16(top, capability >> 16))
                    counts['pointer'] += 1
                    break
    need(counts == {'bounds': 80, 'stride': 63, 'field': 63, 'literal': 17, 'pointer': 28},
         f"Factory RAW consumer coverage changed: {counts}")

    for address, value in ((0x5327BA0C, RAW_OFFSET), (0x53288F6C, RAW_STRIDE), (0x53283C08, 18),
                           (0x53289A30, RAW_ROWS), (0x53289A5C, RAW_OFFSET)):
        immediate(address, value)
    patch(0x5327BA14, mov16(word(0x5327BA14), 3 * RAW_STRIDE))
    for address in (0x53288FB0, 0x53288FB4, 0x53288FB8, 0x53288FBC, 0x53288FC4,
                    0x53289A78, 0x53289A80, 0x53289A84, 0x53289A88):
        change_field(address)
    # The getter, constructor and destructor keep the factory's static
    # lifetime. All three refer to the same boot-zeroed expanded object.
    for address in (0x5320AC20, 0x5320B39C, 0x5320B3B8):
        low, high = word(address), word(address + 4)
        need((low, high) == (0xE30606E0, 0xE3450506),
             f"Factory RAW object address changed at {address:#x}")
        patch(address, mov16(low, RAW_MODEL_ADDRESS & 0xFFFF))
        patch(address + 4, mov16(high, RAW_MODEL_ADDRESS >> 16))
    data.extend(bytes(-(origin + len(data)) % 32))
    need(RAW_OFFSET + 3 * RAW_STRIDE <= RAW_SIZE, "RAW parameter model is too small")
    return bytes(data), [(address, before, after) for address, (before, after) in sorted(patches.items())]
