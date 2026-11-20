# SPDX-License-Identifier: GPL-2.0-only
"""Generate the six-slot parameter dispatchers from native 2.10 call sites."""

import struct

from container_codec import need
from native_registry import ROM_BASE


FIELDS = (0, 1, 2, 3, 4, 5, 6, 13, 14, 15)
ALLOCATION_SITES = ((0x53240730, 0x5324073C), (0x5324B338, 0x5324B34C), (0x5324B400, 0x5324B404),
                    (0x5324B4A4, 0x5324B4B4), (0x5324B5B8, 0x5324B5C8), (0x5324B6E0, 0x5324B6E8))


def compile_routes(rtos, symbols):
    """Return ARM assembly and guarded patch records for the actual factory ABI."""

    def word(address):
        offset = address - ROM_BASE
        need(0 <= offset <= len(rtos) - 4, "Parameter address outside the factory RTOS")
        return struct.unpack_from("<I", rtos, offset)[0]

    def branch_target(address):
        imm = word(address) & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        return address + 8 + imm * 4

    output = [".syntax unified", ".arm", ".text"]
    patches = []

    def emit(site, expected, label, instructions):
        need(word(site) == expected, f"Factory parameter instruction changed at {site:#x}")
        output.extend((f".global {label}", f".type {label},%function", f"{label}:", instructions,
                       f".size {label},.-{label}", ".ltorg"))
        patches.append((site, expected, label, False))

    seed = symbols["grs_parameter_seed"]
    for size, call in ALLOCATION_SITES:
        emit(size, 0xE3001B28, f"grs_userdata_size_{size:x}", f"movw r1,#0xc90\nldr pc,={size + 4:#x}")
        emit(call, 0xE12FFF3C, f"grs_userdata_alloc_{call:x}", f"""
push {{r4,lr}}
blx r12
push {{r0-r3,r12,lr}}
ldr r12,={seed:#x}
blx r12
pop {{r0-r3,r12,lr}}
pop {{r4,lr}}
ldr lr,={call + 4:#x}
ldr pc,={call + 4:#x}
""")

    get = symbols["grs_parameter_get"]
    put = symbols["grs_parameter_set"]
    handled = {"get": set(), "set": set()}
    for kind, low, high in (("set", 0x532BD784, 0x532C1780), ("get", 0x532C34E8, 0x532C9A00)):
        for site in range(low, high, 4):
            original = word(site)
            reg, normal = (original >> 12) & 15, original & 255
            if (normal not in (11, 13) or reg >= 12 or original != (0xE2400000 | normal | (reg << 16) | (reg << 12))
                    or word(site + 4) != (0xE3500000 | (22 - normal) | (reg << 16))
                    or word(site + 8) != (0x979FF100 | reg)):
                continue
            case = word(site + 16 + (22 - normal) * 4)
            if not ROM_BASE <= case < 0x54000000 or word(case + 12) >> 24 != 0xEA:
                continue
            leaf = branch_target(case + 12)
            if kind == "set":
                offsets = [word(a) & 4095 for a in range(leaf, leaf + 60, 4)
                           if word(a) & 0x0FF00000 == 0x05C00000 and 0xA42 <= word(a) & 4095 <= 0xA7C]
                if not offsets:
                    continue
                offset = offsets[0]
            else:
                load = word(case + 8)
                if load & 0x0FF00000 != 0x05D00000 or not 0xA42 <= load & 4095 <= 0xA7C:
                    continue
                offset = load & 4095
            group, index = divmod(offset - 0xA42, 20)
            need(group < 3 and index % 2 == 0, "Unrecognized native parameter offset")
            field = FIELDS[index // 2]
            need((group, field) not in handled[kind], "Duplicate native parameter dispatch")
            handled[kind].add((group, field))
            label = f"grs_parameter_{kind}_{site:x}"
            body = f"""
cmp r{reg},#30
blo 1f
cmp r{reg},#35
bhi 1f
sub r12,r{reg},#30
"""
            first = word(case)
            if kind == "get":
                need(first & 0xFFFFFFF0 == 0xE1A00000, "Factory getter root carrier changed")
                body += f"""
.word {first:#x}
push {{r4,lr}}
mov r1,#{group}
mov r2,#{field}
mov r3,r12
ldr r12,={get:#x}
blx r12
pop {{r4,lr}}
ldr pc,={leaf:#x}
"""
            else:
                need(first & 0xFFFFFFF0 == 0xE1A01000, "Factory setter value carrier changed")
                calls = [branch_target(a) for a in range(leaf, leaf + 60, 4) if word(a) >> 24 == 0xEB]
                need(calls and 0x53540000 <= calls[-1] < 0x53550000, "Factory setter notification changed")
                body += f"""
.word {first:#x},{word(case + 4):#x},{word(case + 8):#x}
push {{r4-r8,lr}}
mov r4,r0
mov r5,r1
mov r8,r12
movw r1,#{(field << 8) | group}
mov r2,r5
mov r3,r8
ldr r12,={put:#x}
blx r12
cmp r0,#0
beq 2f
ldr r6,[r4,#4]
ldrb r2,[r6,#0x44]
cmp r2,#0
bne 2f
ldrb r2,[r6,#0x1c0]
cmp r2,#{group}
bne 2f
ldrb r2,[r6,#{0x1c2 + 2*group}]
add r7,r8,#30
cmp r2,r7
bne 2f
ldr r12,=0x53525d5c
blx r12
ldr r0,[r0]
mov r1,r5
ldr r12,={calls[-1]:#x}
blx r12
mov r0,#1
2:
pop {{r4-r8,pc}}
"""
            body += f"1:\n.word {original:#x}\nldr pc,={site + 4:#x}\n"
            emit(site, original, label, body)
    need(handled["get"] == {(group, field) for group in range(3) for field in FIELDS}
         and handled["set"] == {(group, field) for group in range(3) for field in FIELDS[:-1]},
         "Factory parameter dispatches are incomplete")
    current = (0x53551568, 0x53551574, 0x53551580, 0x5355158C, 0x53551598, 0x535515A4,
               0x535515B0, 0x5355161C, 0x53551628, 0x53551634)
    for field, site in zip(FIELDS, current):
        emit(site, 0xE5903000, f"grs_current_parameter_{field}", f"""
ldr r3,[r0]
ldrb r12,[r3,#0x77c]
sub r12,r12,#30
cmp r12,#5
bhi 1f
push {{r4,lr}}
ldr r0,=0x55063f30
ldr r3,[r0,#4]
cmp r3,#0
mvneq r0,#0
popeq {{r4,pc}}
ldrb r1,[r3,#0x1c0]
mov r2,#{field}
mov r3,r12
ldr r12,={get:#x}
blx r12
pop {{r4,pc}}
1:
ldr pc,={site + 4:#x}
""")

    emit(0x532C17D0, 0xE3570001, "grs_user_grain_set", f"""
sub r3,r5,#30
cmp r3,#5
bhi 1f
orr r1,r7,#0xf00
mov r2,r6
ldr r12,={put:#x}
blx r12
sub sp,r11,#28
ldm sp,{{r4,r5,r6,r7,r11,sp,pc}}
1:
cmp r7,#1
ldr pc,=0x532c17d4
""")
    emit(0x532C1B0C, 0xE3560001, "grs_user_grain_get", f"""
sub r3,r5,#30
cmp r3,#5
bhi 1f
mov r1,r6
mov r2,#15
ldr r12,={get:#x}
blx r12
sub sp,r11,#24
ldm sp,{{r4,r5,r6,r11,sp,pc}}
1:
cmp r6,#1
ldr pc,=0x532c1b10
""")
    restore = symbols["grs_restore_parameter_record"]
    emit(0x53279A08, 0xE1A01006, "grs_restore_before_submit", f"""
push {{r0-r3,r12,lr}}
mov r0,r4
mov r1,r6
ldr r12,={restore:#x}
blx r12
pop {{r0-r3,r12,lr}}
mov r1,r6
ldr pc,=0x53279a0c
""")

    # Reuse the nine factory parameter row types and append Grain's selector.
    list_ptr = word(0x53B3488C)
    need(word(0x53B34890) == 9, "Factory colour parameter table size changed")
    start = list_ptr - ROM_BASE
    need(0 <= start <= len(rtos) - 18, "Factory parameter table is outside the RTOS")
    items = bytes(rtos[start:start + 18])
    need(tuple(items[1::2]) == FIELDS[:-1], "Factory colour parameter field order changed")
    output.extend((".balign 4", "grs_parameter_descriptor:", ".word grs_parameter_items", ".hword 10,0",
                   "grs_parameter_items:", ".byte " + ",".join(map(str, items + bytes([0, 15])))))
    for site, expected, role, index, group, out, table in (
        (0x531AFA2C, 0xE022219E, "type", 2, 1, 2, 12),
        (0x531AFAD0, 0xE0228192, "list", 8, 1, 2, 3),
        (0x531AFFB0, 0xE023239E, "draw", 2, 3, 3, 12),
        (0x531B01FC, 0xE022219C, "id", 2, 1, 2, 3),
    ):
        validate_row = "cmp r3,#9\nbhi 2f\n" if role == "type" else ""
        rejected = "2:\nmov r0,#0\nsub sp,r11,#12\nldm sp,{r11,sp,pc}\n" if role == "type" else ""
        emit(site, expected, f"grs_parameter_menu_{role}", f"""
cmp r{index},#12
blo 1f
cmp r{index},#17
bhi 1f
cmp r{group},#2
bhi 1f
{validate_row}mov r{out},#0
ldr r{table},=grs_parameter_descriptor
ldr pc,={site + 4:#x}
1:
.word {expected:#x}
ldr pc,={site + 4:#x}
{rejected}""")
    return "\n".join(output) + "\n", patches
