# SPDX-License-Identifier: GPL-2.0-only
"""Check FilmInfo's real boot hook, assignment lookup and display aliases."""

import ctypes
import struct
import sys
import zlib

from native_profile import require
from native_registry import ROM_BASE
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc, UcError
from unicorn import arm_const as arm


BOOT_ENTRY = 0x5324B42C
BOOT_RESUME = 0x540C125C
DOMAIN_STORE_GET = 0x53828014
DOMAIN_SIZE = 0x53825834
DOMAIN_READ = 0x53825648


def verify_native_entry_points(image, build):
    if sys.platform == "darwin":
        cache_line = ctypes.c_long()
        size = ctypes.c_size_t(ctypes.sizeof(cache_line))
        query = ctypes.CDLL(None).sysctlbyname
        require(query(b"hw.cachelinesize", ctypes.byref(cache_line), ctypes.byref(size), None, 0) == 0,
                "Unicorn needs permission to read the macOS CPU cache line size")
    stack, stop = 0x5600E000, 0x5600F000
    engine, link, store = 0x56000000, 0x56000020, 0x56000040
    machine = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    machine.mem_map(ROM_BASE, (len(image) + 4095) & ~4095)
    machine.mem_write(ROM_BASE, image)
    machine.mem_map(0x55804000, 0x1000)
    machine.mem_map(0x56000000, 0x10000)
    machine.mem_write(engine + 8, struct.pack("<I", link))
    machine.mem_write(link, struct.pack("<I", store))
    registers = tuple(getattr(arm, f"UC_ARM_REG_R{index}") for index in range(13))
    calls = []
    expected = build["native_slots"]
    journal_ids = list(reversed(expected))
    header = struct.pack("<IHHI6HI", 0x31415347, 1, 32, 4, *journal_ids, 0)
    journal = header + struct.pack("<I", zlib.crc32(header))
    stored = {}

    def service(uc, address, _size, _context):
        calls.append(address)
        if address == DOMAIN_STORE_GET:
            result = engine
        else:
            require(uc.reg_read(arm.UC_ARM_REG_R0) == store, "FilmInfo journal used the wrong DomainData owner")
            key = bytes(uc.mem_read(uc.reg_read(arm.UC_ARM_REG_R1), 16)).split(b"\x00")[0]
            record = stored.get(key, b"")
            if address == DOMAIN_SIZE:
                result = len(record)
            else:
                require(len(record) == uc.reg_read(arm.UC_ARM_REG_R2) == 32, "Invalid FilmInfo journal read")
                uc.mem_write(uc.reg_read(arm.UC_ARM_REG_R3), record)
                result = 1
        uc.reg_write(arm.UC_ARM_REG_R0, result)
        uc.reg_write(arm.UC_ARM_REG_PC, uc.reg_read(arm.UC_ARM_REG_LR))

    for address in (DOMAIN_STORE_GET, DOMAIN_SIZE, DOMAIN_READ):
        machine.hook_add(UC_HOOK_CODE, service, begin=address, end=address)

    def call(name, value=0):
        machine.reg_write(arm.UC_ARM_REG_SP, stack)
        machine.reg_write(arm.UC_ARM_REG_LR, stop)
        machine.reg_write(arm.UC_ARM_REG_R0, value)
        machine.emu_start(build["symbols"][name], stop, count=200000)
        require(machine.reg_read(arm.UC_ARM_REG_PC) == stop, f"FilmInfo {name} did not return")
        return machine.reg_read(arm.UC_ARM_REG_R0)

    try:
        for expected_ids in (expected, journal_ids):
            if expected_ids is journal_ids:
                stored[b"GRS4A_ASG0"] = journal
            machine.mem_write(0x55804384, bytes(0xBC))
            calls.clear()
            flags = 0x60000013
            machine.reg_write(arm.UC_ARM_REG_CPSR, flags)
            machine.reg_write(arm.UC_ARM_REG_SP, stack)
            inputs = [0x12340000 + index for index in range(13)]
            for register, value in zip(registers, inputs):
                machine.reg_write(register, value)
            machine.emu_start(BOOT_ENTRY, BOOT_RESUME, count=200000)
            require(machine.reg_read(arm.UC_ARM_REG_PC) == BOOT_RESUME
                    and machine.reg_read(arm.UC_ARM_REG_CPSR) & 0xF8000000 == flags & 0xF8000000
                    and [machine.reg_read(reg) for reg in registers] == inputs
                    and machine.reg_read(arm.UC_ARM_REG_SP) == stack,
                    "FilmInfo boot did not resume with its native ABI")
            require(calls == ([DOMAIN_STORE_GET, DOMAIN_SIZE, DOMAIN_READ, DOMAIN_SIZE] if stored
                              else [DOMAIN_STORE_GET, DOMAIN_SIZE, DOMAIN_SIZE]),
                    "FilmInfo boot journal access differed from the reference")
            require([call("p4_assignment", slot) for slot in range(6)] == expected_ids,
                    "FilmInfo boot assignments differ")
        selected = build["native_selected"]
        require(call("p4_count") == len(selected), "FilmInfo registered count differs")
        require([uid for uid in range(1, 85) if call("p4_lookup", uid)] == selected,
                "FilmInfo ARM lookup contains an unselected or missing preset")
        for slot in range(6):
            require(call("p4_icon", 677 + slot) and call("p4_text", 925 + slot),
                    f"FilmInfo slot {slot + 1} lost its native display aliases")
    except UcError as error:
        raise ValueError(f"FilmInfo ARM verification failed: {error}") from error
