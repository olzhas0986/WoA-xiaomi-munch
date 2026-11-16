# RPMh DRV CONFIG on munch

`qcpep8250.sys` 1.0.2140.0 (Kona BSP) checks the hardware size of two RPMh
controllers during initialisation. A failed check ends in bugcheck 0x14B
(SOC_SUBSYSTEM_FAILURE) without an assertion string.

## Measurement

Read on the phone with `port/munchPkg/Application/RpmhPeek` (UEFI, read-only,
one register at a time, each value saved before the next read):

```
apps CONFIG=0x800C8104      (0x1822000C, apps RSC)
display CONFIG=0x80000002   (0x0AF2000C, display RSC)
```

Reading the display RSC page works once it is mapped as MMIO from the
application. Mapping it in the platform memory map instead made the UEFI
reset before BDS.

## Decoding

CONFIG holds a 6-bit TCS count per DRV (DRV n at bits 6n..6n+5) and the
commands per TCS in bits 27..31, as in Linux `rpmh-rsc`.

| Controller | Field checked by qcpep | Value | Required by qcpep | Result |
|:--|:--|:--:|:--:|:--|
| apps DRV2 | bits 12..17 | 8 | >= 8 | pass |
| apps | commands, bits 27..31 | 16 | >= 16 | pass |
| display DRV0 | bits 0..5 | **2** | >= 4 | **fail** |
| display | commands, bits 27..31 | 16 | >= 16 | pass |

The display RSC has two TCS, which matches the Linux device tree for SM8250
(`qcom,tcs-config` for `disp_rsc`: one sleep and one wake TCS). The value is
fixed by the silicon, so the check cannot be satisfied by configuration; the
driver's controller table asks for more TCS than this SoC provides for that
controller.

This is the first hardware-size gate in the failing function. It explains a
fatal exit there, but other gates (allocation, runtime state) have not been
measured.

## Driver record and patch

The controller records start at RVA 0x19FF10 in `.data`, 0x50 bytes each
(record count at RVA 0x18A6A8):

| Field | apps | display |
|:--|:--|:--|
| +0x00 controller ID | 2 | 9 |
| +0x24 TCS required | 8 | **4** |
| +0x28 commands per TCS | 16 | 16 |
| +0x30 base | 0x18220000 | 0x0AF20000 |
| +0x48 descriptor; its first dword is the sleep/wake base | 2 | 2 |

Gates in RVA 0x111238, per record `e`, with `hw` = TCS count from CONFIG:

1. `hw < e+0x24` → fatal (display: 2 < 4, the observed 0x14B);
2. commands < `e+0x28`, or `hw < base` → fatal;
3. `e+0x28 != 16` → fatal;
4. if `hw > base`, then `hw >= base + 2` is required; `hw == base` is
   accepted, i.e. a controller without dedicated active TCSs.

With `e+0x24 = 2` the display record passes all four. The init routine
(RVA 0x111450) then programs two slots below the base (sleep/wake) and no
active slot, the same split as Linux uses for `disp_rsc`. How the driver
handles active requests to the display controller in that mode is not
visible from these functions and needs a hardware test.

`tools/patch_qcpep_display_tcs.py` makes the change on a copy of the pinned
driver (SHA-256 `39fafcd6…`), verifying both records first, recomputing the
PE checksum and dropping the embedded signature. `--with-lmh` also applies
the previous port's LMH diagnostic (BL 0x5c50 at RVA 0x1DF358 and 0x21555C
replaced by NOP), on which the 0x14B crash was observed.
