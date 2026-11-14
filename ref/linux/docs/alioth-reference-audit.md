# Alioth reference audit for munch / postmarketOS

User-provided branch: https://github.com/mainlining/linux/commits/nikroks/alioth/
Reviewed board source via web:
https://raw.githubusercontent.com/mainlining/linux/nikroks/alioth/arch/arm64/boot/dts/qcom/sm8250-xiaomi-alioth.dts

The user has now supplied a local shallow checkout pinned to
`022f7f866a9377c34301e60ba131121c624d2e56`. Its Makefile identifies Linux
6.15.1, whereas our known boot baseline is 7.3-rc7. `sm8250.config` is a fragment
on top of defconfig, not a complete standalone kernel config. The shallow clone
contains only the tip commit, so full per-commit history was not audited.
Key source hashes are recorded in out/alioth-source-audit.json.

Local toolchain snapshots received from user:
- pmbootstrap: `7d23010a125ca7386fec4e390d14128b6c24d266`
- pmaports: `f3f926903c1be144b0f92e1a8f3b88383911ad80`

pmbootstrap CLI/help runs locally (3.12.1 release commit). Local pmaports contains
linux-postmarketos-qcom-sm8250, version 7.2.0_git20261010, pointing at
https://gitlab.postmarketos.org/soc/qualcomm-sm8250/linux, not the supplied GitHub
branch. No alioth or munch device package references were found under device/
or main/ in this pinned checkout. This does not establish their absence elsewhere.

## Reuse findings

- USB: Alioth uses USB2-only UTMI-as-PIPE, DWC3 OTG role switch and high-speed
  limit. HS PHY rails L5A=880000, L12A=1800000, L2A=3072000 match our stock munch
  evidence. These are already implemented in our tested M profile. The viewed
  USB node has no extra PHY tuning that immediately explains the speed problem.
- Power: upstream supply topology is valuable for comparing against munch stock
  regulator parents. It is not proof that every rail/consumer matches munch.
  Alioth source advertises 3 A / additional sink PDOs; do not transplant these
  into our conservative 500 mA setup as a performance fix.
- UFS: controller/PHY supply references provide candidates for a later stock
  munch comparison and read-only bring-up, not authorization to enable writes.
- Display/touch/audio/Wi-Fi: bindings and driver names identify candidates for
  investigation. Panel commands, pin assignments, firmware names and voltages
  require munch-specific verification before use.
- Identity/memory: Alioth board-id is 44 (0x2c); our stock munch overlay evidence
  is 0x32. Do not substitute its DTB, identity or reserved-memory map.
- Kernel configuration: local pmOS SM8250 config is a better distro feature
  reference than copying the whole alioth tree. Our kernel remains pinned to
  its working 7.3-rc7 source/patches. Kernel API/version differences must be
  checked for every imported patch.

## Selected configuration comparison

Values are literal Kconfig states in the built NTFS image versus the local
pmOS SM8250 seed. They are not a declaration that every reference option is
required for a console chroot. Hardware drivers stay a separate bring-up task.

| Symbol | Current image | pmOS SM8250 reference |
|---|---|---|
| NET | n | y |
| UNIX | absent | y |
| CGROUPS | n | y |
| SECCOMP | n | y |
| SECCOMP_FILTER | absent | y |
| INOTIFY_USER | n | y |
| NAMESPACES | y | y |
| FHANDLE | y | y |
| EPOLL | y | y |
| SIGNALFD | y | y |
| TIMERFD | y | y |
| TMPFS_POSIX_ACL | y | y |
| TMPFS_XATTR | y | y |
| DEVTMPFS | y | y |
| DRM_MSM | absent | y |
| TYPEC_QCOM_PMIC | y | y |
| USB_DWC3_DUAL_ROLE | y | y |
| PHY_QCOM_QMP_USB | absent | y |

The next userspace-enablement change should review NET/UNIX, CGROUPS, inotify
and seccomp against the actual selected init/release. Do not enable GPU, UFS,
remote processors or all PMIC consumers merely to match the broad reference.

## Local source findings after clone

- Additional driver sources include `drivers/input/touchscreen/ft8756.c` and
  `drivers/gpu/drm/panel/panel-samsung-ams667xx01.c`.
- The fragment enables battery QCOM_FG, charger QCOM_SMB5, FSA4480, CS35L41,
  PM8008, GENI SPI, GPU/display clock controllers and DRM/MSM. A fragment line
  is evidence of intended configuration, not proof of working hardware.
- Stock munch's SPI FocalTech node uses IRQ GPIO39, reset GPIO33 and 6 MHz,
  matching those particular alioth board parameters. Stock compatible is generic
  focaltech,fts, so this does not prove the chip is FT8756. Supply phandles,
  chip identity, controller firmware state and driver API differences remain to be checked before
  enabling a touchscreen experiment.
- The next built image is a separate pmOS userspace kernel preflight, retaining
  the verified board DT and adding generic userspace facilities. It does not
  transplant alioth DTS or drivers. See postmarketos.md.

FT8756 detail: this snapshot defines ROM/PRAM firmware command constants but
contains no request_firmware or implemented upload path. Probe checks chip ID
and acquires vio/lab/ibb unless following a DRM panel. Its required supplies and
IRQ setup must be reconciled with munch stock evidence before a driver test.
