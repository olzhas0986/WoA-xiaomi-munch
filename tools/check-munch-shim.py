#!/usr/bin/env python3
"""Execute the actual built shim on ARM64 Unicorn, checking relocation/handoff."""
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_PC

ROOT = Path(__file__).resolve().parents[1]
SHIM = (ROOT / 'out/munch-fresh/shim.bin').read_bytes()
FD_BASE, FD_SIZE = 0x9FC00000, 0x300000
DATA = bytes(range(256)) * (FD_SIZE // 256)

def run(name, source, reject=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    start = min(source, FD_BASE) & ~0xFFF
    end = (max(source + len(SHIM) + FD_SIZE, FD_BASE + FD_SIZE) + 0xFFF) & ~0xFFF
    uc.mem_map(start, end - start)
    uc.mem_map(0xF0000000, 0x100000)
    uc.mem_write(source, SHIM + DATA)
    uc.reg_write(UC_ARM64_REG_X0, 0xAABBCCDD11223344)
    uc.reg_write(UC_ARM64_REG_X1, 0x8877665544332211)
    arrived = []
    def stop(emulator, address, size, state):
        if address == FD_BASE:
            arrived.append(True)
            emulator.emu_stop()
    uc.hook_add(UC_HOOK_CODE, stop, begin=FD_BASE, end=FD_BASE)
    # Hook only the destination; instruction loop count bounds rejected layouts.
    uc.emu_start(source, 0, count=1500000)
    if reject:
        assert not arrived, name + ': invalid layout entered firmware'
        assert bytes(uc.mem_read(source, len(SHIM))) == SHIM, name + ': executing shim corrupted'
    else:
        assert arrived, name + ': did not enter firmware'
        assert bytes(uc.mem_read(FD_BASE, FD_SIZE)) == DATA, name + ': bad FD copy'
    assert uc.reg_read(UC_ARM64_REG_X0) == 0xAABBCCDD11223344
    assert uc.reg_read(UC_ARM64_REG_X1) == 0x8877665544332211
    print('PASS', name)

run('source above FD, no overlap', 0xA4000000)
run('source at output end', FD_BASE + FD_SIZE)
run('FD already at destination', FD_BASE - len(SHIM))
run('source below FD, overlapping copy backward', FD_BASE - 0x200000)
run('source below FD, no overlap', FD_BASE - 0x400000)
run('reject copy over executing shim', FD_BASE + 0x1000, True)
