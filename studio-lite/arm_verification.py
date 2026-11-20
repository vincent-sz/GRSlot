# SPDX-License-Identifier: GPL-2.0-only
"""Existing GRSlot ARM checks, executed on the decoded build output."""

import struct
import unittest

from native_registry import ROM_BASE
from raw_platform import RAW_MODEL_ADDRESS, RAW_MODEL_END, RAW_SIZE
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
    UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R11, UC_ARM_REG_R12, UC_ARM_REG_SP,
)

CONFIRM = 6
RESTORE_CURRENT = 10
RESTORE_ALL = 11


class ArmPublicMenuChecks(unittest.TestCase):
    def verify_file_identity(self, stock_image, image):
        scratch = 0x56000000
        tag, photo, model = scratch + 0x100, scratch + 0x1000, scratch + 0x3000
        stack, stop = scratch + 0xE000, scratch + 0xF000

        def machine(program):
            arm = Uc(UC_ARCH_ARM, UC_MODE_ARM)
            arm.mem_map(ROM_BASE, (len(program) + 4095) & ~4095)
            arm.mem_write(ROM_BASE, program)
            arm.mem_map(0x5534A000, 0x1000)
            arm.mem_map(scratch, 0x10000)
            return arm

        def run(arm, write, value, external, empty=False):
            arm.mem_write(tag, bytes(128))
            payload = tag + (64 if external else 12)
            arm.mem_write(tag + 16, struct.pack("<I", payload if external else 0))
            arm.mem_write(model + 0x18, struct.pack("<I", photo))
            start = 0x53D2B6F4
            arm.mem_write(0x5534AD6C, struct.pack("<II", start, start if empty else start + 48))
            arm.mem_write(payload, struct.pack("<H", 0xA5A5 if write else value))
            arm.mem_write(photo + 0x77C, bytes((value if write else 0xA5,)))
            arm.reg_write(UC_ARM_REG_CPSR, 0x60000013)
            for register, argument in (
                (UC_ARM_REG_SP, stack), (UC_ARM_REG_LR, stop),
                (UC_ARM_REG_R0, tag), (UC_ARM_REG_R1, tag), (UC_ARM_REG_R2, photo),
                (UC_ARM_REG_R4, tag), (UC_ARM_REG_R5, model),
            ):
                arm.reg_write(register, argument)
            end = 0x53608084 if write else stop
            arm.emu_start(0x53608074 if write else 0x535BF7A8, end, count=50000)
            self.assertEqual(arm.reg_read(UC_ARM_REG_PC), end)
            self.assertEqual(arm.reg_read(UC_ARM_REG_SP), stack)
            return (struct.unpack("<H", arm.mem_read(payload, 2))[0] if write
                    else arm.mem_read(photo + 0x77C, 1)[0])

        factory, candidate = machine(stock_image), machine(image)
        for external in (False, True):
            for empty in (False, True):
                for public in range(256):
                    value = run(candidate, True, public, external, empty)
                    if 30 <= public <= 35:
                        self.assertEqual(value, 0x10C + public - 30)
                        self.assertEqual(run(candidate, False, value, external), public)
                    else:
                        self.assertEqual(value, run(factory, True, public, external, empty))
            for tag_value in (0, 1, *range(0x100, 0x120), 0xFFFF):
                actual = run(candidate, False, tag_value, external)
                if 0x10C <= tag_value <= 0x111:
                    self.assertEqual(actual, 30 + tag_value - 0x10C)
                else:
                    self.assertEqual(actual, run(factory, False, tag_value, external))

        properties, display = photo + 0x18C, scratch + 0x6000

        def playback_call(arm, address, first=0, second=0, third=0):
            arm.reg_write(UC_ARM_REG_SP, stack)
            arm.reg_write(UC_ARM_REG_LR, stop)
            arm.reg_write(UC_ARM_REG_R0, first)
            arm.reg_write(UC_ARM_REG_R1, second)
            arm.reg_write(UC_ARM_REG_R2, third)
            arm.emu_start(address, stop, count=200000)
            self.assertEqual(arm.reg_read(UC_ARM_REG_PC), stop)
            self.assertEqual(arm.reg_read(UC_ARM_REG_SP), stack)
            return arm.reg_read(UC_ARM_REG_R0)

        def import_photo(arm, value):
            arm.mem_write(photo, bytes(0x1000))
            arm.mem_write(photo, b"\x01")
            arm.mem_write(photo + 18, b"\x08")
            arm.mem_write(tag, bytes(128))
            arm.mem_write(tag + 6, struct.pack("<HI", 3, 2))
            arm.mem_write(tag + 16, struct.pack("<I", tag + 64))
            arm.mem_write(tag + 64, struct.pack("<H", value))
            playback_call(arm, 0x535C24EC, photo, properties, tag)
            return struct.unpack("<I", arm.mem_read(properties + 37 * 4, 4))[0]

        def playback_context(arm, address, size, data):
            arm.reg_write(UC_ARM_REG_R0, photo)
            arm.reg_write(UC_ARM_REG_PC, arm.reg_read(UC_ARM_REG_LR))

        for arm in (factory, candidate):
            for address in (0x5320AD88, 0x5320B97C):
                arm.hook_add(UC_HOOK_CODE, playback_context, begin=address, end=address)

        for value in (0, *range(0x100, 0x120), 0xFFFF):
            actual = import_photo(candidate, value)
            if 0x10C <= value <= 0x111:
                self.assertEqual(actual, value - 0x100 + 1)
                self.assertEqual(playback_call(candidate, 0x532B44BC, photo, display), 1)
                self.assertEqual(candidate.mem_read(display, 1), bytes((value - 0x10C + 30,)))
                self.assertEqual(playback_call(candidate, 0x532B6EEC), value - 0x10C + 677)
            else:
                self.assertEqual(actual, import_photo(factory, value))
                if actual:
                    self.assertEqual(playback_call(candidate, 0x532B6EEC), playback_call(factory, 0x532B6EEC))

        # The recorded Grain value must drive DISP even if the live setting
        # has changed. Exercise the native encoder, importer and row builder.
        candidate.mem_map(0x55357000, 0x1000)
        candidate.mem_write(0x5534AD18, struct.pack("<II", 0x53D2B624, 0x53D2B634))
        allocated = scratch + 0x9000

        def playback_service(arm, address, size, data):
            nonlocal allocated
            r0, r1, r2, r3 = (
                arm.reg_read(register) for register in
                (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
            )
            result = r0
            if address == 0x536AF2A8:
                self.assertIn(r0, (8, 12, 16))
                result = allocated
                allocated += 32
            elif address in (0x5313FD80, 0x53140280, 0x531403A8):
                source = bytes((r1 & 255,)) * r2 if address == 0x531403A8 else bytes(arm.mem_read(r1, r2))
                arm.mem_write(r0, source)
            elif address == 0x53141100:
                fmt = bytes(arm.mem_read(r2, 4)).split(b"\0", 1)[0]
                if fmt == b"%s":
                    output = bytes(arm.mem_read(r3, 16)).split(b"\0", 1)[0]
                else:
                    self.assertIn(fmt, (b"%d", b"%+d"))
                    number, = struct.unpack("<i", struct.pack("<I", r3))
                    output = fmt % number
                arm.mem_write(r0, output[:r1 - 1] + b"\0")
                result = len(output)
            arm.reg_write(UC_ARM_REG_R0, result)
            arm.reg_write(UC_ARM_REG_PC, arm.reg_read(UC_ARM_REG_LR))

        for address in (
            0x536AF2A8, 0x536AF2E4, 0x5313FD80, 0x53140280, 0x531403A8, 0x536B5EC4, 0x53141100,
        ):
            candidate.hook_add(UC_HOOK_CODE, playback_service, begin=address, end=address)

        candidate.reg_write(UC_ARM_REG_SP, stack)
        candidate.reg_write(UC_ARM_REG_R4, 0)
        candidate.emu_start(0x535CA290, 0x535CA2B8, count=50000)
        self.assertEqual(candidate.reg_read(UC_ARM_REG_PC), 0x535CA2B8)
        for public, ordinal in ((11, 1), (30, 13), (35, 18)):
            for grain, label in ((0, b"--"), (1, b"3"), (2, b"2"), (3, b"1")):
                allocated = scratch + 0x9000
                candidate.mem_write(photo, bytes(0x1000))
                candidate.mem_write(photo, b"\x01")
                candidate.mem_write(photo + 18, b"\x08")
                candidate.mem_write(photo + 0x77C, bytes((public,)))
                candidate.mem_write(photo + 0x795, bytes((grain,)))
                playback_call(candidate, 0x535C67D4, 0, photo, display)
                encoded = bytes(candidate.mem_read(display, 2))
                candidate.mem_write(tag, bytes(128))
                candidate.mem_write(tag + 6, struct.pack("<HI", 3, 44))
                candidate.mem_write(tag + 16, struct.pack("<I", tag + 64))
                candidate.mem_write(tag + 64 + 19 * 2, encoded)
                playback_call(candidate, 0x535C3C3C, photo, properties, tag)
                candidate.mem_write(properties + 37 * 4, struct.pack("<I", ordinal))
                candidate.mem_write(photo + 0x795, b"\0")
                candidate.mem_write(display, bytes(128))
                playback_call(candidate, 0x532B7C90, 0, display, display + 64)
                self.assertEqual(bytes(candidate.mem_read(display + 64 + 27, 3)).split(b"\0", 1)[0],
                                 label, (public, grain))

    def verify_raw_lifetime(self, image):
        arm = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        arm.mem_map(ROM_BASE, (len(image) + 4095) & ~4095)
        arm.mem_write(ROM_BASE, image)
        arm.mem_map(0x55000000, 0x1000000)
        arm.reg_write(UC_ARM_REG_SP, 0x55FFF000)
        calls = []
        boundaries = {0x538C8444: 1, 0x5313FBB8: 0, 0x5327B940: 0, 0x5327EDD8: 0}

        def boundary(machine, address, size, data):
            calls.append((address, machine.reg_read(UC_ARM_REG_R0)))
            result = boundaries.get(address, 0)  # Force allocation failure if called.
            machine.reg_write(UC_ARM_REG_R0, result)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        for address in (*boundaries, 0x536AF2A8, 0x536AF358):
            arm.hook_add(UC_HOOK_CODE, boundary, begin=address, end=address)
        self.assertEqual(RAW_MODEL_END - RAW_MODEL_ADDRESS, RAW_SIZE)
        self.assertEqual(struct.unpack_from("<I", image, 0x460)[0], RAW_MODEL_END)

        # Use the original caller that dereferences the returned RAW model.
        for _ in range(2):
            arm.emu_start(0x531923C4, 0x531923D0, count=200000)
            self.assertEqual(arm.reg_read(UC_ARM_REG_PC), 0x531923D0)
            self.assertEqual(arm.reg_read(UC_ARM_REG_R0), RAW_MODEL_ADDRESS)
            self.assertEqual(arm.mem_read(RAW_MODEL_ADDRESS + 0x38, 1), b"\x01")
        arm.reg_write(UC_ARM_REG_LR, 0x531923D0)
        arm.emu_start(0x5320AC20, 0x531923D0, count=200000)
        self.assertEqual(arm.reg_read(UC_ARM_REG_PC), 0x531923D0)
        self.assertEqual([argument for address, argument in calls if address == 0x5327B940],
                         [RAW_MODEL_ADDRESS])
        self.assertEqual([argument for address, argument in calls if address == 0x5327EDD8],
                         [RAW_MODEL_ADDRESS])
        self.assertFalse(any(address in (0x536AF2A8, 0x536AF358) for address, _ in calls))

    def verify(self, image, symbols, receipt):
        vm = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        rom_size = (len(image) + 4095) & ~4095
        vm.mem_map(ROM_BASE, rom_size)
        vm.mem_write(ROM_BASE, image)

        def map_scratch(address, size):
            if not ROM_BASE <= address <= ROM_BASE + rom_size - size:
                vm.mem_map(address, size)

        map_scratch(0x53825000, 0x1000)
        map_scratch(0x53828000, 0x1000)
        map_scratch(0x55804000, 0x1000)
        map_scratch(0x55063000, 0x1000)
        scratch = 0x56000000
        map_scratch(scratch, 0x10000)
        state = scratch + 0x1000
        native_settings = scratch + 0x9000
        sentinel = scratch + 0xF000
        records = {}
        writes = []
        fail_write = [False]
        vm.mem_write(native_settings, bytes(range(180)) * 2)
        vm.mem_write(scratch + 8, struct.pack("<I", scratch + 0x10))
        vm.mem_write(scratch + 0x10, struct.pack("<I", scratch + 0x20))

        def domain_data(machine, address, _, __):
            if address == 0x53828014:
                result = scratch
            else:
                key = bytes(machine.mem_read(machine.reg_read(UC_ARM_REG_R1), 16)).split(b"\0")[0]
                self.assertIn(key, (b"GRS4A_ASG0", b"GRS4A_ASG1", b"GRS2P_PARAM0", b"GRS2P_PARAM1"))
                record_size = 192 if key.startswith(b"GRS2P_") else 32
                if address == 0x53825834:
                    result = len(records.get(key, b""))
                elif address == 0x53825648:
                    self.assertIn(key, records)
                    self.assertEqual(machine.reg_read(UC_ARM_REG_R2), record_size)
                    machine.mem_write(machine.reg_read(UC_ARM_REG_R3), records[key])
                    result = 1
                else:
                    self.assertEqual(machine.reg_read(UC_ARM_REG_R2), record_size)
                    result = int(not fail_write[0])
                    if result:
                        records[key] = bytes(machine.mem_read(machine.reg_read(UC_ARM_REG_R3), record_size))
                        writes.append(key)
            machine.reg_write(UC_ARM_REG_R0, result)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        for endpoint in (0x53828014, 0x53825834, 0x53825648, 0x53825FA8):
            vm.hook_add(UC_HOOK_CODE, domain_data, begin=endpoint, end=endpoint)

        def call(name, first=0, second=0, third=0, fourth=0, *, stop=sentinel, limit=50000):
            vm.reg_write(UC_ARM_REG_SP, scratch + 0xE000)
            vm.reg_write(UC_ARM_REG_LR, sentinel)
            vm.reg_write(UC_ARM_REG_R0, first)
            vm.reg_write(UC_ARM_REG_R1, second)
            vm.reg_write(UC_ARM_REG_R2, third)
            vm.reg_write(UC_ARM_REG_R3, fourth)
            vm.emu_start(symbols[name], stop, count=limit)
            self.assertEqual(vm.reg_read(UC_ARM_REG_PC), stop, name)
            return vm.reg_read(UC_ARM_REG_R0)

        def choose(view, slot=0, pending=0):
            vm.mem_write(state + 27504, struct.pack("<14I", 0x354C4942, view, 1, slot, 0, pending, *[0] * 8))

        def assignments():
            return [call("p4_assignment", slot) for slot in range(6)]

        film_ids = [film["uid"] for film in receipt["films"]]
        defaults = receipt["slots"]
        first = next((uid for uid in film_ids if uid != defaults[0]), defaults[0])
        second = next((uid for uid in film_ids if uid != defaults[1]), defaults[1])
        expected_writes = 2 * (int(first != defaults[0]) + int(second != defaults[1]))
        self.assertEqual(call("p4_count"), len(film_ids))
        self.assertTrue(call("p4_load"))
        self.assertEqual(assignments(), receipt["slots"])
        choose(CONFIRM, pending=first)
        self.assertTrue(call("grs_install", state))
        self.assertEqual(assignments(), [first, *defaults[1:]])
        choose(RESTORE_CURRENT)
        self.assertTrue(call("grs_restore", state))
        self.assertEqual(assignments(), receipt["slots"])
        self.assertTrue(call("p4_assign", 1, second))
        choose(RESTORE_ALL)
        self.assertTrue(call("grs_restore", state, 1))
        self.assertEqual(assignments(), receipt["slots"])
        self.assertEqual(len(writes), expected_writes)
        vm.mem_write(0x55804384, bytes(0xBC))
        boot_exit = 0x5324B430
        map_scratch(boot_exit & ~4095, 0x1000)
        boot_frame = scratch + 0xE800
        vm.reg_write(UC_ARM_REG_R11, boot_frame)
        self.assertEqual(call("grs_boot_assignments", 123, stop=boot_exit), 123)
        self.assertEqual(vm.reg_read(UC_ARM_REG_SP), boot_frame - 40)
        self.assertEqual(assignments(), receipt["slots"])
        self.assertEqual(len(writes), expected_writes)
        self.assertEqual(bytes(vm.mem_read(native_settings, 360)), bytes(range(180)) * 2)

        # Exercise the real linked adapters for the final preset and for a
        # factory context. Native continuation bodies remain outside this VM.
        gate_fallback = 0x536E8698
        getter_fallback = 0x536EEDF0
        map_scratch(gate_fallback & ~4095, 0x1000)
        map_scratch(getter_fallback & ~4095, 0x1000)
        last_curve = receipt["curve_table"] + (len(film_ids) - 1) * 16
        aux, red, green, blue = struct.unpack("<4I", vm.mem_read(last_curve, 16))
        context = scratch + 0xA000
        destinations = scratch + 0xB000
        vm.reg_write(UC_ARM_REG_R4, context)
        vm.mem_write(context + 24, struct.pack("<I", aux))
        vm.mem_write(context + 0x9B, b"\x09")
        call("grs_gamma_gate", stop=gate_fallback)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), 1)
        call("grs_gamma_getter", destinations, destinations + 4, destinations + 8, destinations + 12)
        self.assertEqual(struct.unpack("<3I", vm.mem_read(destinations + 4, 12)), (red, green, blue))
        vm.mem_write(context + 24, struct.pack("<I", 0x53DC555C))
        call("grs_gamma_gate", stop=gate_fallback)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), 9)
        call("grs_gamma_getter", destinations, destinations + 4, destinations + 8, destinations + 12,
             stop=getter_fallback)
        self.assertEqual(struct.unpack("<3I", vm.mem_read(destinations + 4, 12)), (red, green, blue))

        refresh_exit = 0x536DCB84
        map_scratch(refresh_exit & ~4095, 0x1000)
        native_frame = scratch + 0xC800
        vm.reg_write(UC_ARM_REG_R11, native_frame)
        vm.mem_write(native_frame - 52, struct.pack("<I", 30))
        for dirty, expected in ((0, 1), (0, 0), (2, 2)):
            call("grs_colour_refresh", fourth=dirty, stop=refresh_exit)
            self.assertEqual(struct.unpack("<I", vm.mem_read(native_frame - 0xCC, 4))[0], expected)
        self.assertTrue(call("p4_assign", 0, first))
        call("grs_colour_refresh", stop=refresh_exit)
        self.assertEqual(struct.unpack("<I", vm.mem_read(native_frame - 0xCC, 4))[0],
                         int(first != defaults[0]))

        source_exit = 0x536DC2CC
        native_mode = scratch + 0xD000
        vm.reg_write(UC_ARM_REG_R7, native_mode)
        vm.mem_write(native_mode + 0x77C, bytes([30]))
        default_film = call("p4_lookup", receipt["slots"][0])
        active_film = call("p4_film", 0)
        default_basis = struct.unpack("<I", vm.mem_read(default_film + 16, 4))[0]
        chosen_basis, chosen_aux = struct.unpack("<II", vm.mem_read(active_film + 16, 8))
        vm.mem_write(context + 8, struct.pack("<5I", default_basis, 6, 0, 0, 7))
        call("grs_colour_source", stop=source_exit)
        self.assertEqual(struct.unpack("<5I", vm.mem_read(context + 8, 20)),
                         (chosen_basis, 0x53DC2BA0, 0, 0, chosen_aux))
        factory_context = struct.pack("<5I", 0x550192F4, 6, 0, 0, 7)
        vm.mem_write(context + 8, factory_context)
        call("grs_colour_source", stop=source_exit)
        self.assertEqual(bytes(vm.mem_read(context + 8, 20)), factory_context)

        # Reach all six new processing indices and preserve the two displaced
        # instructions for the original table route.
        for slot in range(6):
            self.assertEqual(call("grs_processing_index", third=30 + slot, stop=0x536DC29C), receipt["processing_basis"])
            self.assertEqual(vm.reg_read(UC_ARM_REG_R1), 26 + slot)
            self.assertEqual(vm.reg_read(UC_ARM_REG_R12), receipt["processing_descriptors"])
            self.assertEqual(call("grs_processing_aux", third=30 + slot, stop=0x536DC2AC), receipt["processing_aux"])
        self.assertEqual(call("grs_processing_index", third=11, stop=0x536DC290), 0x8D94)
        self.assertEqual(call("grs_processing_aux", third=29, stop=0x536DC2A8), 0x8E4C)
        map_scratch(0x536DB000, 0x1000)
        for public in range(30, 36):
            call("grs_colour_converter", third=public, stop=0x536DBAA4)
            self.assertTrue(vm.reg_read(UC_ARM_REG_CPSR) & 0x40000000)
        call("grs_colour_converter", third=11, stop=0x536DB800)
        self.assertTrue(vm.reg_read(UC_ARM_REG_CPSR) & 0x40000000)
        call("grs_colour_converter", third=20, stop=0x536DB800)
        self.assertFalse(vm.reg_read(UC_ARM_REG_CPSR) & 0x40000000)

        native_table_model = scratch + 0xAC00
        map_scratch(0x532C2000, 0x1000)
        group_query = 0x532BD6D4
        map_scratch(group_query & ~4095, 0x1000)

        def native_group(machine, _, __, ___):
            self.assertEqual(machine.reg_read(UC_ARM_REG_R0), native_table_model)
            machine.reg_write(UC_ARM_REG_R0, 2)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        vm.hook_add(UC_HOOK_CODE, native_group, begin=group_query, end=group_query)
        for slot in range(6):
            self.assertEqual(call("grs_native_slot_forward", native_table_model, 12 + slot), 30 + slot)
            self.assertEqual(call("grs_native_slot_reverse", native_table_model, 30 + slot), 12 + slot)
        vm.mem_write(native_table_model + 0x1B, b"\x01")
        call("grs_native_slot_forward", native_table_model, 12, stop=0x532C2C84)
        call("grs_native_slot_reverse", native_table_model, 35, stop=0x532C2F0C)
        for menu_class, count in ((0, 18), (1, 12)):
            vm.reg_write(UC_ARM_REG_CPSR, vm.reg_read(UC_ARM_REG_CPSR) & ~0xF0000000)
            self.assertEqual(call("grs_native_slot_count", fourth=menu_class, stop=0x532C2AD4), count)

        # Native Select attachment owns a copy of the vtable, preserves the
        # original draw callback, and leaves events in other panels alone.
        model, view, panel = scratch + 0x200, scratch + 0x400, scratch + 0x800
        vtable = 0x5320C000
        map_scratch(vtable, 0x1000)
        native_table = [vtable + 0x400 + i * 4 for i in range(48)]
        vm.mem_write(vtable, struct.pack("<48I", *native_table))
        vm.mem_write(model + 0x18C, struct.pack("<I", view))
        vm.mem_write(model + 0x198, bytes([117]))
        vm.mem_write(view, struct.pack("<I", vtable + 8))
        vm.mem_write(state + 0x720, struct.pack("<I", 0x34415347))
        vm.mem_write(0x55804380, struct.pack("<I", state))
        self.assertEqual(call("grs_menu_count", model), 6)
        self.assertEqual(call("grs_menu_count", model), 6)
        self.assertEqual(struct.unpack("<I", vm.mem_read(view, 4))[0], state + 0x65C)
        self.assertEqual(struct.unpack("<I", vm.mem_read(state + 0x24, 4))[0], native_table[21])
        native_table[21] = symbols["grs_frame"]
        self.assertEqual(struct.unpack("<48I", vm.mem_read(state + 0x654, 192)), tuple(native_table))
        map_scratch(0x5320A000, 0x1000)

        def native_panel(machine, address, _, __):
            if address == 0x5320AEFC:
                self.assertEqual(machine.reg_read(UC_ARM_REG_R0), model)
            machine.reg_write(UC_ARM_REG_R0, model if address == 0x5320AD88 else panel)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        for endpoint in (0x5320AD88, 0x5320AEFC):
            vm.hook_add(UC_HOOK_CODE, native_panel, begin=endpoint, end=endpoint)
        def native_key(event):
            vm.reg_write(UC_ARM_REG_SP, scratch + 0xE000)
            vm.reg_write(UC_ARM_REG_R1, event)
            vm.emu_start(0x53221A38, 0x53221A3C, count=50000)
            self.assertEqual(vm.reg_read(UC_ARM_REG_PC), 0x53221A3C)
            result = vm.reg_read(UC_ARM_REG_R5)
            self.assertEqual(vm.reg_read(UC_ARM_REG_R1), result)
            return result

        self.assertEqual(native_key(28), 28)
        vm.mem_write(panel, struct.pack("<I", 0x02000141))
        self.assertEqual(native_key(28), 22)

        # Follow the existing menu sequence through the patched key entry and
        # owned view callback. Model only the native graphics and redraw APIs.
        graphics = []
        layer = scratch + 0xB800
        manager = scratch + 0xBA00
        parent_paint = native_table[21]
        original_paint = struct.unpack("<I", vm.mem_read(state + 0x24, 4))[0]
        self.assertEqual(parent_paint, symbols["grs_frame"])
        vm.mem_write(view + 0x30, struct.pack("<4I", 0, 0, 720, 360))
        vm.mem_write(view + 0x9E, b"\x01")
        vm.mem_write(state + 27504, bytes(56))

        def paint_service(machine, address, size, data):
            first = machine.reg_read(UC_ARM_REG_R0)
            second = machine.reg_read(UC_ARM_REG_R1)
            result = 0
            if address == original_paint:
                self.assertEqual((first, second), (view, layer))
                graphics.append(("underlay", None))
            elif address == 0x5320804C:
                result = manager
            elif address in (0x532081EC, 0x53208298, 0x53208224):
                self.assertEqual(first, manager)
                result = manager
            elif address == 0x53208A2C:
                command_layer, x, y, width, height = struct.unpack("<5I", machine.mem_read(second, 20))
                self.assertEqual(command_layer, layer)
                self.assertTrue(0 < width <= 720 - x and 0 < height <= 360 - y)
                graphics.append(("rectangle", None))
            elif address == 0x53208D7C:
                machine.mem_write(first, struct.pack("<2I", 64, 40))
            elif address == 0x532090C4:
                text = struct.unpack("<I", machine.mem_read(second + 48, 4))[0]
                chars = struct.unpack("<33H", machine.mem_read(text, 66))
                title = "".join(chr(char) for char in chars[:chars.index(0)])
                graphics.append(("text", title))
            elif address == 0x5320A020:
                graphics.append(("bitmap", None))
            elif address == 0x533AD308:
                self.assertEqual(first, view)
            machine.reg_write(UC_ARM_REG_R0, result)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        for endpoint in (
            original_paint, 0x5320804C, 0x532081EC, 0x53208298, 0x53208224,
            0x53208A2C, 0x53208D7C, 0x532090C4, 0x5320A020, 0x533963F8, 0x533AD308,
        ):
            vm.hook_add(UC_HOOK_CODE, paint_service, begin=endpoint, end=endpoint)

        def navigate(event, page, text=None):
            if event is not None:
                self.assertEqual(native_key(event), 22)
            self.assertEqual(call("p5_view"), page)
            graphics.clear()
            call("grs_frame", view, layer, limit=2000000)
            self.assertEqual(graphics[0], ("underlay", None))
            self.assertIn(("rectangle", None), graphics)
            self.assertTrue(any(kind == "text" for kind, _ in graphics))
            if text is not None:
                self.assertIn(("text", text), graphics)

        navigate(None, 1)
        navigate(14, 2, "Film Library")
        navigate(14, 3, "All Films")
        navigate(14, 4)
        navigate(14, 5, "Install to Slot")
        navigate(14, 6, "Install selected film?")
        navigate(57, 5, "Install to Slot")
        navigate(9, 5)
        navigate(14, 8, "Favorites are compile-time only.")
        navigate(57, 5)
        navigate(9, 5)
        navigate(14, 7)
        navigate(57, 5)
        navigate(57, 4)
        navigate(57, 3, "All Films")
        navigate(9, 3)
        navigate(9, 3)
        navigate(14, 12)
        navigate(57, 3)
        navigate(57, 2, "Restore Defaults")
        navigate(9, 2)
        navigate(14, 9, "Restore Current Slot Default")
        navigate(14, 10, "Restore current default film?")
        navigate(57, 9)
        navigate(9, 9)
        navigate(14, 11, "Restore all six default films?")
        navigate(57, 9)
        navigate(57, 2)
        navigate(57, 1)
        self.assertEqual(native_key(57), 57)

        # Perform Install and Restore through the native confirmation events.
        # This also works when a one-preset project makes Install a no-op.
        previous_slots = assignments()
        navigate(14, 2)
        navigate(14, 3)
        for _ in range(call("p5_focus")):
            navigate(10, 3)
        navigate(14, 4)
        chosen = call("p5_uid_at", 0)
        self.assertIn(chosen, film_ids)
        navigate(14, 5)
        navigate(14, 6)
        navigate(9, 6)
        navigate(14, 2)
        self.assertEqual(assignments(), [chosen, *previous_slots[1:]])
        navigate(9, 2)
        navigate(14, 9)
        navigate(14, 10)
        navigate(9, 10)
        navigate(14, 2)
        self.assertEqual(assignments(), [defaults[0], *previous_slots[1:]])
        vm.mem_write(panel, struct.pack("<I", 0x02000001))
        graphics.clear()
        call("grs_frame", view, layer)
        self.assertEqual(graphics, [("underlay", None)])

        # Start from the actual 21 factory language tables, using the original
        # RAM initializer. The heap allocator is the only modeled resource API.
        offset = 0x5407B540 - ROM_BASE
        map_scratch(0x55000000, 0x3B000)
        vm.mem_write(0x55000000, image[offset:offset + 0x3A080])
        roots = 0x55002BAC
        original_tables = struct.unpack("<21I", vm.mem_read(roots, 84))
        prefixes = [bytes(vm.mem_read(table, 786 * 4)) for table in original_tables]
        new_tables = 0x57000000
        map_scratch(new_tables, 0x12000)
        alloc = 0x536AF2A8
        map_scratch(alloc & ~4095, 0x1000)
        allocations = []

        def allocate(machine, _, __, ___):
            allocations.append(machine.reg_read(UC_ARM_REG_R0))
            machine.reg_write(UC_ARM_REG_R0, new_tables)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        vm.hook_add(UC_HOOK_CODE, allocate, begin=alloc, end=alloc)
        self.assertTrue(call("grs_resources", limit=200000))
        self.assertTrue(call("grs_resources"))
        self.assertEqual(allocations, [21 * 811 * 4])
        current = struct.unpack("<21I", vm.mem_read(roots, 84))
        owned_title = call("grs_common_text", 900, 0)
        for i, table in enumerate(current):
            self.assertEqual(table, new_tables + i * 811 * 4)
            self.assertEqual(bytes(vm.mem_read(table, 786 * 4)), prefixes[i])
            self.assertEqual(bytes(vm.mem_read(original_tables[i], 786 * 4)), prefixes[i])
            self.assertEqual(struct.unpack("<I", vm.mem_read(table + 786 * 4, 4))[0], owned_title)
        flags, text = struct.unpack("<II", vm.mem_read(owned_title, 8))
        self.assertEqual(flags, 0x107)
        self.assertEqual(bytes(vm.mem_read(text, 14)).decode("utf-16-le"), "GRSlot\0")
        self.assertEqual(call("grs_common_text", 900, 21), 0)

        map_scratch(0x53209000, 0x1000)
        for icon_id in range(677, 683):
            self.assertEqual(call("grs_icon_width", second=icon_id), 40)
            self.assertEqual(call("grs_icon_height", second=icon_id), 40)
        call("grs_icon_width", second=671, stop=0x53209FBC)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), 670)
        for icon_id, limit in ((670, 670), (672, 670), (682, 682), (683, 670)):
            call("grs_icon_draw_limit", fourth=icon_id, stop=0x5320A7D0)
            self.assertEqual(vm.reg_read(UC_ARM_REG_R1), limit)
        expected = call("p4_icon", 677)
        call("grs_icon_token", fourth=677, stop=0x5320A814)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), expected)
        self.assertEqual(struct.unpack("<II", vm.mem_read(expected, 8)), (0x00280028, 0))
        stock_descriptor = struct.unpack("<I", vm.mem_read(0x550020FC + 670 * 4, 4))[0]
        call("grs_icon_token", fourth=670, stop=0x5320A814)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), stock_descriptor)
        pixel_index = (expected - receipt["icon_descriptors"]) // 8
        expected_pixels = struct.unpack("<I", vm.mem_read(receipt["icon_pixels"] + pixel_index * 4, 4))[0]
        for descriptor, pixels in ((expected, expected_pixels), (expected + 4, 55), (stock_descriptor, 55)):
            arguments = scratch + 0xE000 + 16
            vm.mem_write(arguments, struct.pack("<II", descriptor, 55))
            call("grs_icon_blit", stop=0x5320A024)
            self.assertEqual(struct.unpack("<II", vm.mem_read(arguments, 8)), (descriptor, pixels))

        map_scratch(0x55068000, 0x1000)
        map_scratch(0x532A9000, 0x1000)
        for slot in range(6):
            self.assertEqual(call("grs_shoot_name", second=30 + slot), 925 + slot)
            self.assertEqual(call("grs_shoot_icon", second=30 + slot), 677 + slot)
            self.assertEqual(call("grs_list_name", second=30 + slot), 925 + slot)
            self.assertEqual(call("grs_list_icon", second=30 + slot), 677 + slot)
        self.assertEqual(call("grs_shoot_name", 123, 29, stop=0x532A9860), 123)
        vm.mem_write(0x55063DCC, struct.pack("<I", 1))
        vm.mem_write(0x5506821B, b"\x01")
        self.assertEqual(call("grs_shoot_icon", 123, 30, stop=0x532A998C), 123)
        map_scratch(0x53396000, 0x2000)
        film_text = call("p4_text", 925)
        vm.reg_write(UC_ARM_REG_R7, 925)
        call("grs_measure_name", 20, stop=0x53396700)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R7), film_text)
        vm.reg_write(UC_ARM_REG_R7, 900)
        call("grs_draw_name", 0, stop=0x5339710C)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), owned_title)
        vm.reg_write(UC_ARM_REG_R7, 400)
        call("grs_draw_name", 0, stop=0x533970F0)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R3), 785)

        current_owner, current_userdata = 0x55063F30, 0x57100000
        map_scratch(current_userdata, 0x1000)
        vm.mem_write(current_owner + 4, struct.pack("<I", current_userdata))
        factory_settings = bytes((i & 255) for i in range(0xB28))
        vm.mem_write(current_userdata, factory_settings)
        call("grs_parameter_seed", current_userdata)
        self.assertEqual(bytes(vm.mem_read(current_userdata, 0xB28)), factory_settings)
        self.assertEqual(call("grs_parameter_get", current_owner, 0, 15, 0), 0)
        self.assertEqual(call("grs_parameter_set", current_owner, (3 << 8) | 2, 7, 5), 1)
        self.assertEqual(call("grs_parameter_set", current_owner, (15 << 8) | 1, 3, 4), 1)
        self.assertEqual(call("grs_parameter_get", current_owner, 2, 3, 5), 7)
        self.assertEqual(call("grs_parameter_get", current_owner, 2, 3, 4), 4)
        tail = bytes(vm.mem_read(current_userdata + 0xB28, 360))
        fail_write[0] = True
        self.assertEqual(call("grs_parameter_set", current_owner, (3 << 8) | 2, 8, 5), 0)
        self.assertEqual(bytes(vm.mem_read(current_userdata + 0xB28, 360)), tail)
        fail_write[0] = False
        call("grs_parameter_seed", current_userdata)
        call("grs_boot_assignments", stop=boot_exit)
        self.assertEqual(bytes(vm.mem_read(current_userdata, 0xB28)), factory_settings)
        self.assertEqual(bytes(vm.mem_read(current_userdata + 0xB28, 360)), tail)
        self.assertEqual(len(receipt["parameter_routes"]), 86)

        vm.mem_write(current_userdata + 0x44, b"\x00")
        vm.mem_write(current_userdata + 0x1C0, b"\x02")
        vm.mem_write(current_userdata + 0x1C6, b"\x23")
        cache_owner, shooting_state = scratch + 0x800, scratch + 0x900
        vm.mem_write(cache_owner, struct.pack("<I", shooting_state))
        vm.mem_write(shooting_state + 0x77C, b"\x23")
        self.assertEqual(call("grs_current_parameter_3", cache_owner), 7)
        map_scratch(0x53279000, 0x1000)
        record = scratch + 0x8200
        vm.mem_write(record, bytes([88]) * 0x100)
        vm.reg_write(UC_ARM_REG_R4, current_owner)
        vm.reg_write(UC_ARM_REG_R6, record)
        call("grs_restore_before_submit", stop=0x53279A0C)
        self.assertEqual(bytes(vm.mem_read(record + 0xB8, 5)), bytes([35, 4, 4, 4, 7]))
        self.assertEqual(bytes(vm.mem_read(record + 0xB7, 1)), b"X")
        vm.mem_write(current_userdata + 0x1C6, b"\x0b")
        saved_record = bytes(vm.mem_read(record, 0x100))
        call("grs_restore_before_submit", stop=0x53279A0C)
        self.assertEqual(bytes(vm.mem_read(record, 0x100)), saved_record)
        map_scratch(0x531AF000, 0x1000)
        call("grs_parameter_menu_type", second=2, third=17, fourth=9, stop=0x531AFA30)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R2), 0)
        menu_descriptor = vm.reg_read(UC_ARM_REG_R12)
        field_list, field_count = struct.unpack("<II", vm.mem_read(menu_descriptor, 8))
        self.assertEqual(field_count, 10)
        self.assertEqual(bytes(vm.mem_read(field_list, 20))[1::2], bytes((0, 1, 2, 3, 4, 5, 6, 13, 14, 15)))

        map_scratch(0x53513000, 0x1000)
        call("grs_grain_enable", fourth=35, stop=0x53513240)
        call("grs_grain_enable", fourth=20, stop=0x535131F0)
        self.assertEqual(vm.reg_read(UC_ARM_REG_R2), 3)
        vm.reg_write(UC_ARM_REG_R6, 1)
        vm.mem_write(shooting_state + 0x795, b"\x03")
        call("grs_grain_prepare", fourth=shooting_state, stop=0x536DB9CC)
        self.assertEqual(bytes(vm.mem_read(shooting_state + 0x795, 1)), b"\x03")
        vm.mem_write(shooting_state + 0x77C, b"\x0b")
        vm.reg_write(UC_ARM_REG_R6, 1)
        call("grs_grain_prepare", fourth=shooting_state, stop=0x536DB9CC)
        self.assertEqual(bytes(vm.mem_read(shooting_state + 0x795, 1)), b"\x01")

        for slot in range(6):
            self.assertEqual(call("grs_public_to_raw", second=30 + slot), 14 + slot)
            self.assertEqual(call("grs_raw_to_public", second=14 + slot), 30 + slot)
        raw_model = 0x57101000
        map_scratch(raw_model, 0x1000)
        original_raw = bytes((i % 91) for i in range(0x800))
        vm.mem_write(raw_model, original_raw)
        call("grs_seed_raw_slots", raw_model, current_owner)
        result = bytes(vm.mem_read(raw_model, 0x800))
        self.assertEqual(result[:0x400], original_raw[:0x400])
        for group in range(3):
            base = 0x400 + 340 * group
            self.assertEqual(result[base:base + 14 * 17], original_raw[base:base + 14 * 17])
        self.assertEqual(result[0x400 + 340 * 2 + 17 * 19 + 3], 7)
        self.assertEqual(result[0x400 + 340 * 1 + 17 * 18 + 15], 3)
        self.assertEqual(bytes(vm.mem_read(current_userdata + 0xB28, 360)), tail)
        self.assertEqual(len(receipt["raw_patches"]), 311)

    def verify_menu_owner(self, image):
        for allow in (True, False):
            arm = Uc(UC_ARCH_ARM, UC_MODE_ARM)
            arm.mem_map(ROM_BASE, (len(image) + 4095) & ~4095)
            arm.mem_write(ROM_BASE, image)
            arm.mem_map(0x55000000, 0x1000000)
            offset = 0x5407B540 - ROM_BASE
            arm.mem_write(0x55000000, image[offset:offset + 0x3A080])
            arm.mem_map(0x56000000, 0x100000)
            arm.reg_write(UC_ARM_REG_CPSR, 0x60000013)
            arm.reg_write(UC_ARM_REG_SP, 0x55FFF000)
            allocations = iter((0x56000000, 0x56020000))
            stock_categories = bytes(arm.mem_read(0x55001EB8, 20))
            fail_owner = [not allow]

            def allocate(machine, address, size, user_data):
                requested = machine.reg_read(UC_ARM_REG_R0)
                address = 0 if fail_owner[0] and requested == 14208 else next(allocations)
                machine.reg_write(UC_ARM_REG_R0, address)
                machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

            arm.hook_add(UC_HOOK_CODE, allocate, begin=0x536AF2A8, end=0x536AF2A8)
            arm.emu_start(0x5316FCEC, 0x5316FCF0, count=3000000)
            self.assertEqual(arm.reg_read(UC_ARM_REG_PC), 0x5316FCF0)
            self.assertEqual(arm.reg_read(UC_ARM_REG_CPSR) & 0xF0000000, 0x60000000)
            flags, menu, submenu = struct.unpack("<3I", arm.mem_read(0x55804374, 12))
            if allow:
                self.assertTrue(flags & 0x80000000)
                self.assertEqual(submenu, menu + 0x1E80)
                self.assertEqual(arm.reg_read(UC_ARM_REG_R0), 0x1420)
                self.assertEqual(bytes(arm.mem_read(menu + 0x2613, 1)), b"\x27")
                self.assertEqual(struct.unpack("<I", arm.mem_read(menu + 0x27E4, 4))[0], 0x02000143)
            else:
                self.assertEqual((flags, menu, submenu), (0, 0, 0))
                self.assertEqual(arm.reg_read(UC_ARM_REG_R0), 0x13BC)
                self.assertEqual(bytes(arm.mem_read(0x55001EB8, 20)), stock_categories)
                fail_owner[0] = False
                arm.emu_start(0x5316FCEC, 0x5316FCF0, count=3000000)
                self.assertEqual(arm.reg_read(UC_ARM_REG_R0), 0x13BC)
                self.assertEqual(bytes(arm.mem_read(0x55001EB8, 20)), stock_categories)
