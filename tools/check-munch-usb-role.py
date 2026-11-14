#!/usr/bin/env python3
"""Check the runtime adapter and execute the supplied vendor role logic on ARM64.

Protocol initialization, role selection and Stop are emulated with service stubs.
This does not emulate the PHY, Type-C electrical role, VBUS or xHCI hardware.
"""
import hashlib
import os
import re
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (
    UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X30,
    UC_ARM64_REG_SP, UC_ARM64_REG_PC,
)

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'inputs/munch/extracted-xbl/QcomPkg/Drivers/UsbConfigDxe/UsbConfigDxe.efi'
CODE = VENDOR.read_bytes()
assert hashlib.sha256(CODE).hexdigest() == '09b54b03ab45797c7b8aabc15bcb5a5bc91796b290ae3e1e5e17748ba10aed87'

# Check the exact ranges used by the runtime adapter, including relocation safety.
relocations = []
offset = 0x16000
while offset + 8 <= len(CODE):
    page, size = struct.unpack_from('<II', CODE, offset)
    if size == 0:
        break
    assert size >= 8 and offset + size <= len(CODE)
    for pos in range(offset + 8, offset + size, 2):
        value, = struct.unpack_from('<H', CODE, pos)
        if value >> 12:
            assert value >> 12 == 10  # IMAGE_REL_BASED_DIR64
            relocations.append(page + (value & 0xfff))
    offset += size
source = (ROOT / 'firmware/munch/BootManager/UsbRole.c').read_text()
ranges = re.findall(r'\{ (0x[0-9a-f]+), (0x[0-9a-f]+), (0x[0-9a-f]+) \}', source)
assert len(ranges) == 4
for row in ranges:
    offset, size, crc = map(lambda x: int(x, 16), row)
    assert zlib.crc32(CODE[offset:offset + size]) == crc
    assert not any(addr < offset + size and addr + 8 > offset for addr in relocations)
print('PASS runtime fingerprints match the pinned binary and contain no relocations', flush=True)

def word(uc, addr, value):
    uc.mem_write(addr, struct.pack('<I', value))

def readword(uc, addr):
    return struct.unpack('<I', uc.mem_read(addr, 4))[0]

def machine():
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(0, 0x20000)
    uc.mem_map(0x100000, 0x10000)
    uc.mem_write(0, CODE)
    uc.mem_write(0x15440, b'\x01')
    word(uc, 0x15444, 4)  # latched device mode
    word(uc, 0x15414, 0x10000)  # controller stopped
    # Fake boot services and a successful DisconnectController function.
    uc.mem_write(0x15880, struct.pack('<Q', 0x100000))
    uc.mem_write(0x100110, struct.pack('<Q', 0x101000))
    uc.mem_write(0x101000, bytes.fromhex('000080d2c0035fd6'))  # mov x0,0; ret
    return uc

def run(uc, start, end, mode):
    uc.reg_write(UC_ARM64_REG_SP, 0x10fff0)
    uc.reg_write(UC_ARM64_REG_X0, 0)
    uc.reg_write(UC_ARM64_REG_X1, mode)
    uc.reg_write(UC_ARM64_REG_X30, end)
    uc.emu_start(start, end, count=5000)
    assert uc.reg_read(UC_ARM64_REG_PC) == end

def initialized_fixture():
    """Obtain the installed root address from actual vendor Init instructions.

    Stop after creation of the root and two per-core protocol copies, before
    power/PHY initialization. Then execute the first-attach role-latch branch.
    """
    uc = machine()
    uc.mem_write(0x15868, struct.pack('<Q', 0x100300))  # runtime service table
    uc.mem_write(0x100348, struct.pack('<Q', 0x101100))  # GetVariable
    uc.mem_write(0x100148, struct.pack('<Q', 0x101200))  # InstallMultiple...
    installed, cores = [], []

    def service(emulator, addr, size, user):
        result = 0
        if addr == 0x101100:
            result = 0x800000000000000e  # GetVariable: EFI_NOT_FOUND
        elif addr == 0x101200:
            installed.append(emulator.reg_read(UC_ARM64_REG_X2))
            out = emulator.reg_read(UC_ARM64_REG_X0)
            emulator.mem_write(out, struct.pack('<Q', 0x1234))
        elif addr in (0x8834, 0xc21c):  # hardware core and port constructors
            core = emulator.reg_read(UC_ARM64_REG_X0)
            assert core in (0, 1)
            out = emulator.reg_read(UC_ARM64_REG_X1)
            pointer = (0x104000 if addr == 0x8834 else 0x106000) + core * 0x1000
            emulator.mem_write(out, struct.pack('<Q', pointer))
            if addr == 0x8834:
                cores.append(core)
        else:
            return
        emulator.reg_write(UC_ARM64_REG_X0, result)
        emulator.reg_write(UC_ARM64_REG_PC, emulator.reg_read(UC_ARM64_REG_X30))

    for addr in (0x101100, 0x101200, 0x8834, 0xc21c):
        uc.hook_add(UC_HOOK_CODE, service, begin=addr, end=addr)
    run(uc, 0x3ad4, 0x3f70, 0)
    assert cores == [0, 1] and len(installed) == 1
    root = installed[0]
    assert root == 0x15558  # also measured in the host9 device transcript
    assert root != 0x15188  # source template must not be used as installed root
    assert readword(uc, root) == 0x10005
    assert readword(uc, root + 0x88) == 2
    assert readword(uc, root + 0x8c) == 0x10000
    for core in (0, 1):
        port = 0x15388 + core * 0xe8
        assert readword(uc, port) == 0x10005
        assert readword(uc, port + 0x88) == core
        assert readword(uc, port + 0x8c) == 0x10000
    # Default policy 3 arms the first-attachment latch. Emulate a PC/UFP attach,
    # stopping just before the callback touches the PHY.
    uc.mem_write(0x15bdd, b'\x01')
    word(uc, 0x15828, 50)  # actual munch platform type from the device transcript
    uc.reg_write(UC_ARM64_REG_X2, 1)  # UFP
    run(uc, 0x765c, 0x7958, 2)  # core0, partner attach, UFP
    assert uc.mem_read(0x15440, 1) == b'\x01'
    assert readword(uc, 0x15444) == 4
    assert readword(uc, 0x104000) == 16
    assert uc.mem_read(0x15bdd, 1) == b'\0'
    print('PASS actual vendor Init installs root at 0x15558; PC attach latches device policy', flush=True)
    return bytes(uc.mem_read(0, len(CODE))), root

fixture, installed_root = initialized_fixture()

uc = machine()
run(uc, 0x4a3c, 0x4e68, 8)  # stop before any hardware/library calls
assert readword(uc, 0x15414) == 4
print('PASS actual vendor Start reproduces host8: HOST request selects DEVICE', flush=True)

for requested, policy, expected in [(8, 1, 1), (1, 1, 1), (16, 4, 4)]:
    uc = machine()
    word(uc, 0x15444, policy)
    run(uc, 0x4a3c, 0x4e68, requested)
    assert readword(uc, 0x15414) == expected
    # Stop the selected controller. Give it a synthetic non-null owned handle.
    handle = 0x15368 if expected == 1 else 0x15370
    uc.mem_write(handle, struct.pack('<Q', 0x1234))
    run(uc, 0x5788, 0x102000, requested)
    assert uc.reg_read(UC_ARM64_REG_X0) == 0
    assert readword(uc, 0x15414) == 0x10000
    assert bytes(uc.mem_read(handle, 8)) == bytes(8)
    # Restore device policy, then select the device path for fastboot.
    word(uc, 0x15444, 4)
    run(uc, 0x4a3c, 0x4e68, 16)
    assert readword(uc, 0x15414) == 4
print('PASS actual vendor selection/Stop/restoration with HOST and DEVICE policies', flush=True)

# Compile the actual adapter against EDK headers, running guards and restoration
# on the host. Sanitizers catch out-of-range accesses in the compatibility code.
with tempfile.TemporaryDirectory(prefix='munch-usb-role-') as temp:
    output = str(Path(temp) / 'check')
    fixture_path = Path(temp) / 'initialized-vendor.bin'
    fixture_path.write_bytes(fixture)
    include = ROOT / 'Mu-Silicium/Mu_Basecore/MdePkg/Include'
    subprocess.run([
        'clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fshort-wchar',
        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
        '-I' + str(include), '-I' + str(include / 'X64'),
        '-I' + str(ROOT / 'firmware/munch/BootManager'),
        str(ROOT / 'tools/tests/munch-usb-role-host.c'),
        str(ROOT / 'firmware/munch/BootManager/UsbRole.c'), '-lz', '-o', output,
    ], check=True)
    # LeakSanitizer cannot enumerate threads under this sandbox's ptrace policy.
    # AddressSanitizer and UndefinedBehaviorSanitizer stay enabled.
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
    subprocess.run([output, str(fixture_path), hex(installed_root)], check=True, env=env)
