# Hardware baseline: minimal loader → Linux → initramfs → shell

User-confirmed on the POCO F4/munch: two successful temporary boots.
Baseline source commit/tag: `05a50f1` / `baseline-minimal-shell`.

Boot image SHA-256:

```text
4356501254d33d6824209a65618f9834cb1344f5eed0088c8f0d651cb7971f99
```

Preserved locally at `out/baseline/munch-boot.img`, with the original payload
manifest and full kernel config. This generated backup is not stored in Git.
It can be rebuilt from the baseline tag with the pinned sources/toolchain.

Visible on the supplied photograph:

- Linux 7.3.0-rc7, ARM64, framebuffer console.
- `online CPUs: 0-7`, `CPU count: 8`.
- `init: userspace alive`.
- `/run/dmesg.boot` saved, BusyBox 1.37.0 ash and a shell prompt.
- RPMh genpd OPP registration failure, error -95.
- AOSS `failed to acquire ipc mailbox`.

No claim of prolonged display stability or interactive input is made.

The photograph was untracked in this checkout. Its observations have been
recorded here; the local photo and Windows Zone.Identifier sidecar were removed
as requested. Photo SHA-256 for provenance:
`c055a083557147c6985eaab29c2365e9194cd9edce666c54ae91bea230ee5ba8`.
