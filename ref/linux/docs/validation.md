# Local validation — 2026-10-18

At the time of this initial local validation, hardware boot had not been
performed. Subsequent user-confirmed device results are recorded in
[hardware-baseline.md](hardware-baseline.md). No phone commands were executed
by the agent.

- Kernel: clean Git export of `58161ead29e50d70a317ea26b472e0c7508e69da`.
- Cross compiler: `aarch64-linux-gnu-gcc (GCC) 16.2.0`.
- Python: 3.14.8. DTC: 1.8.1.
- Loader compiled with `-Wall -Wextra -Werror`; no GOT or runtime relocations.
- Minimal kernel Image, static AArch64 BusyBox, board DTB and boot image v3 built.
- Shell syntax check and 7 archive/packer tests passed, including rejection of
  a kernel footprint reaching the DTB, reserved destination, incompatible
  text_offset, malformed input headers and dynamic ELF userspace.
- Repeated build/pack produced identical loader, kernel, BusyBox, initramfs,
  payload and Android boot image hashes. This was an incremental rebuild and
  repack, not a second full build in a different path/toolchain environment.

Boot image SHA-256:

```text
4356501254d33d6824209a65618f9834cb1344f5eed0088c8f0d651cb7971f99
```

Generated files and full successful logs are in `out/`, outside Git.
`out/payload.json` contains input/output hashes and destination records.

Known build warnings were retained:

- BusyBox 1.37.0: const qualifier diagnostics with GCC 16 and one unused variable.
  No upstream code was patched to hide them.
- DTC: duplicate unit-address warnings for alternative QUP protocols inherited
  from sm8250.dtsi. No warning suppression or forced DTB generation is used.

Still unverified: real bootloader load address and entry state, DMA handoff,
QHEE timer/GIC accessibility, eight-CPU startup with untouched CPU domains,
physical RAM provenance, framebuffer lifetime and shell prompt on hardware.
The runtime loader refuses source/destination overlap instead of guessing a
relocation address. A silent early stop can mean unsupported EL/MMU/cache state.
