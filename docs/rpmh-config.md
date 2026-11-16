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
