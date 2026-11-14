#!/usr/bin/env python3
"""Reproduce stale UsbfnIo dispatch in the exact supplied vendor StartEx."""
from pathlib import Path
import hashlib, struct, zlib
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC
p = (Path(__file__).resolve().parents[1] / 'inputs/munch/extracted-xbl/QcomPkg/Drivers/UsbDeviceDxe/UsbDeviceDxe.efi').read_bytes()
assert hashlib.sha256(p).hexdigest() == '75560d994975db36a8d24e11105388e327aefb4fc7ea7b24b4f50ae2b0d900e6'
assert zlib.crc32(p[0x1ef8:0x1f74]) == 0x4bcdbf11
assert zlib.crc32(p[0x1c1c:0x1d28]) == 0x0f0bad3c
for refresh in (False, True):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    u.mem_map(0, 0x20000)
    u.mem_map(0x100000, 0x10000)
    u.mem_write(0, p)
    old, current, target = 0x103000, 0x104000, 0x105000
    u.mem_write(old, b'\xaf' * 0x100)
    u.mem_write(current + 0x78, struct.pack('<Q', target))
    u.mem_write(0xa3d0, struct.pack('<Q', current if refresh else old))
    calls = []
    def observe(cpu, address, size, data):
        if address == target:
            calls.append(cpu.reg_read(UC_ARM64_REG_X0))
            cpu.emu_stop()
    u.hook_add(UC_HOOK_CODE, observe)
    u.reg_write(UC_ARM64_REG_X0, 0x106000)
    u.reg_write(UC_ARM64_REG_SP, 0x10fff0)
    u.reg_write(UC_ARM64_REG_X30, 0x107000)
    try:
        u.emu_start(0x1c1c, 0x107000, count=200)
    except Exception:
        if refresh: raise
        assert u.reg_read(UC_ARM64_REG_PC) == 0xafafafafafafafaf
        assert u.reg_read(UC_ARM64_REG_X30) == 0x1c50
    else:
        assert refresh and calls == [current]
    print('PASS', 'refreshed interface dispatch' if refresh else 'reproduced photo ELR and LR offset')
