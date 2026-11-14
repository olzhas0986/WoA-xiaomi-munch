# EL1 boot contract

The implementation follows the pinned kernel's
`Documentation/arch/arm64/booting.rst` and the
[ARM64 boot protocol](https://docs.kernel.org/arch/arm64/booting.html).

## Firmware to loader

An Android boot image v3 carries a small ARM64 Image-shaped loader followed by
its payload. The firmware enters the loader through the existing Android boot
path; EFI Boot Services and a PE entry point are not used.

The expected state is non-secure, little-endian AArch64 EL1 with the MMU and
data cache disabled, coherent RAM, and firmware-configured timers/GIC. QHEE
retains EL2. The loader does not access EL2 registers. Entry masks DAIF and checks
CurrentEL/SCTLR before C code. An unsupported entry state stops before framebuffer
access, rather than attempting an unverified cache or translation change.

The loader uses no libc, heap, floating point, SIMD or MMU. It has a 16 KiB stack,
clears BSS and uses PC-relative references; the linker rejects a GOT. Exceptions
report ESR_EL1, ELR_EL1 and FAR_EL1 before stopping.

Firmware remains responsible for stopping unrelated DMA masters. Display scanout
continues using the reserved splash buffer. The packer's checks cannot establish
that the firmware has fulfilled its DMA contract.

## Payload container

The header starts at offset `0x100000` from `_start`. Integers are little-endian
u64; item records contain four u64 values.

```text
+0     magic[8] = "PMUNCH01"
+8     version = 1
+16    item_count = 2 or 3
+24    payload size, including header page
+32    kernel entry
+40    DTB address
+48    items: { destination, file_size, memory_size, payload_offset }
+4096  payload data; each source starts on a 4096-byte boundary
```

The maximum payload size is 256 MiB. Item order is Linux Image, DTB and optional
initramfs. The initrd's exclusive end is its actual size, without container
padding. Its bounds are passed through `/chosen/linux,initrd-start` and
`linux,initrd-end`, not CPU registers. Stale initrd properties are rejected when
no initramfs is supplied. Use a loader and packer from the same source revision.

All records are validated before writing destination RAM. Destinations must not
overlap one another, reserved memory, or the full running loader/header/source
range, including stack and BSS. The loader stops on overlap; it does not relocate
itself. Availability of the claimed source RAM depends on the firmware loading
the complete Android image.

## Memory destinations

All right-hand bounds are exclusive.

| Component | Start | Window limit |
| --- | --- | --- |
| Kernel | `0xc0200000` | `0xc8000000` |
| DTB | `0xc8000000` | `0xc8200000` |
| Initramfs | `0xc8400000` | `0xffc00000` |

Kernel bounds use `Image.image_size`, not the file length. Checks include Image
magic, endianness, placement flag bit 3, and
`(entry - text_offset) % 2 MiB == 0`. Change addresses together in the packer,
loader and DT, with a separate review of the resulting layout.

The inherited RAM ranges are `0x80000000–0xbcc00000` and
`0xc0000000–0x200000000`. Fixed reservations are read from the final DTB,
including its FDT reserve map, even for disabled devices. The dynamic ADSP heap
retains its mainline size/range constraints. The kernel reserves Image, initrd
and DTB before allocating that heap; the packer does not invent a heap address.

Board reservations include xbl_aop, slpi, adsp, spss, secure CDSP heap, firmware
logs, splash, dfps and display dumps. Historical DT copies are supporting
evidence, not independent proof of the physical RAM map. The extra
`0xffc00000+0x20000` reservation is retained conservatively.

The loader's inherited framebuffer is `0x9c000000`, 1080×2400, stride 4320,
ARGB8888. Its `0x9e3400` visible bytes fit inside the `0x2300000` splash
reservation. The loader writes that memory without taking ownership of display
clocks, rails or pipeline state. Native DSI ownership is a later kernel stage.
The normal boot message is `Booting linux...`; error diagnostics remain visible.

The region at `0xb0000000+1 MiB` remains reserved without an enabled ramoops
backend. Historical DTs disagree on its console/record layout, so cross-OS
persistent-log access is not assumed.

## Loader to Linux

Copied data is cleaned to PoC with `dc cvac`; the cache-line size comes from
CTR_EL0. Barriers, I-cache invalidation and masked DAIF precede the final branch.
MMU and data cache remain disabled. The register handoff is:

```text
x0 = physical DTB address
x1 = x2 = x3 = 0
```

EL1 timer/GIC/PAUTH access controlled by EL2 remains a firmware responsibility.
Linux starts secondary CPUs through PSCI; the loader does not start them.

## Error codes

The loader reports hexadecimal codes with its error diagnostics.

| Code | Meaning |
| --- | --- |
| 1 | Invalid magic, version or item count |
| 2 | Payload size or address overflow |
| 3 | Loader runtime footprint reaches the header |
| 4 | Unexpected kernel or DTB destination |
| 5 | Invalid item bounds, window or alignment |
| 6 | Destination overlaps the loader or source payload |
| 7 | Source items overlap |
| 8 | Invalid Linux Image header, footprint or placement |
| 9 | Invalid DTB header or size |
| A | Copy verification failed |
| EE | Exception; preceding values contain ESR, ELR and FAR |
