# SPDX-License-Identifier: GPL-2.0-only
"""Link one freestanding ARM object using the GRSlot P4 relocation subset."""

import struct

from container_codec import need


def link_arm_object(obj, origin):
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", obj)
    identity, kind, machine, _, _, _, table, _, _, _, _, stride, count, names_index = header
    need(identity[:7] == b"\x7fELF\x01\x01\x01" and (kind, machine, stride) == (1, 40, 40),
         "Expected a little-endian ARM relocatable ELF object")
    need(0 < names_index < count and table + count * stride <= len(obj), "Invalid ELF section table")
    sections = [struct.unpack_from("<10I", obj, table + i * stride) for i in range(count)]

    def content(section):
        start, size = section[4:6]
        need(start + size <= len(obj), "Truncated ELF section")
        return obj[start:start + size]

    def name(strings, index):
        end = strings.find(b"\0", index)
        need(end >= index, "Unterminated ELF symbol or section name")
        return strings[index:end].decode("ascii")

    section_names = content(sections[names_index])
    placements = {}
    output = bytearray()
    for i, section in enumerate(sections):
        if section[1] not in (1, 8) or not section[2] & 2 or name(section_names, section[0]).startswith(".ARM"):
            continue
        alignment = max(4, section[8])
        need(alignment & (alignment - 1) == 0, "Invalid ELF section alignment")
        output.extend(bytes(-(origin + len(output)) % alignment))
        placements[i] = origin + len(output)
        output.extend(bytes(section[5]) if section[1] == 8 else content(section))
    need(output and origin + len(output) <= 0x55000000, "ARM module exceeds the ROM window")

    symbols = {}
    symbol_tables = {}
    for i, section in enumerate(sections):
        if section[1] != 2:
            continue
        strings = content(sections[section[6]])
        rows = []
        for index, value, _, info, _, owner in struct.iter_unpack("<IIIBBH", content(section)):
            label = name(strings, index)
            address = placements[owner] + value if owner in placements else None
            rows.append((label, address))
            if label and address is not None and info & 0xF == 2:
                symbols[label] = address
        symbol_tables[i] = rows

    for section in sections:
        if section[7] not in placements or section[1] not in (4, 9):
            continue
        need(section[1] == 9, "Unsupported explicit-addend ARM relocation")
        for offset, info in struct.iter_unpack("<II", content(section)):
            label, target = symbol_tables[section[6]][info >> 8]
            need(target is not None, "Unresolved ARM symbol: " + label)
            address = placements[section[7]] + offset
            pos = address - origin
            need(offset % 4 == 0 and offset + 4 <= sections[section[7]][5], "ARM relocation leaves its section")
            word = struct.unpack_from("<I", output, pos)[0]
            relocation = info & 255
            if relocation == 2:  # R_ARM_ABS32
                value = target + word
                need(value <= 0xFFFFFFFF, "ARM absolute relocation overflows")
            elif relocation in (28, 29):  # R_ARM_CALL, R_ARM_JUMP24
                immediate = word & 0xFFFFFF
                if immediate & 0x800000:
                    immediate -= 0x1000000
                delta = target + immediate * 4 - address
                need((word >> 25) & 7 == 5 and delta % 4 == 0 and -(1 << 25) <= delta < 1 << 25,
                     "Invalid ARM branch relocation")
                value = (word & 0xFF000000) | ((delta // 4) & 0xFFFFFF)
            elif relocation in (43, 44):  # R_ARM_MOVW_ABS_NC, R_ARM_MOVT_ABS
                immediate = ((word >> 4) & 0xF000) | (word & 0xFFF)
                if immediate & 0x8000:
                    immediate -= 0x10000
                adjusted = target + immediate
                half = adjusted & 0xFFFF if relocation == 43 else (adjusted >> 16) & 0xFFFF
                value = (word & ~0xF0FFF) | ((half & 0xF000) << 4) | (half & 0xFFF)
            else:
                raise ValueError(f"Unsupported ARM relocation {relocation}: {label}")
            struct.pack_into("<I", output, pos, value)
    return bytes(output), symbols
