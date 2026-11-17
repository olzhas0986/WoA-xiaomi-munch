# Qualcomm PEP (qcpep8250) bring-up on POCO F4 (SM8250): state and open problem

This document is self-contained. It describes an attempt to get the Qualcomm
Power Engine Plug-in (PEP) driver of the SM8250 ("Kona") Windows BSP running on
a phone whose firmware was made for Android, the method used to debug it without
a kernel debugger, every gate passed so far, and the problem it is stuck on now.
It ends with concrete questions.

## 1. Target and goal

| Item | Value |
|:--|:--|
| Device | Xiaomi POCO F4, codename `munch` |
| SoC | Qualcomm SM8250-AC (Snapdragon 870, "Kona") |
| PMICs | PM8150 (`a`), PM8150B (`b`), PM8150L (`c`), PM8009 (`f`, camera) |
| Firmware | Stock Xiaomi Android firmware (XBL, TrustZone, AOP, hypervisor) — **not** a Windows firmware |
| OS | Windows 11 IoT Enterprise LTSC 2024, arm64 |
| UEFI | Project Mu / Mu-Silicium based port, booted tethered with `fastboot boot` |
| Goal | Run Qualcomm's `qcpep8250.sys` so Windows gets SoC power management, and later the Adreno GPU driver, which depends on PEP |

Windows already boots to the desktop. USB host (keyboard, mouse, flash drive) and
UFS storage work. The Kona BSP drivers `qcscm`, `qcrpen`, `qcspmi` and `qcpmic`
start with code 0. PEP is the blocker.

## 2. Software involved

- **Driver.** `qcpep8250.sys` 1.0.2140.0 from a public Kona Windows BSP
  repository (`windows_silicon_qcom_kona`), SHA-256
  `39fafcd60536c7d36dd95187dc9f51bfc4af661b614bce4a5e9ec0729fe24e01`.
  - **Origin:** its PDB path says it was built from the SM8150 tree
    (`Z:\b\WP\PEP\rel\10.5\...\qcpep8180.pdb`, sources under
    `Framework\PEP\8180\...`).
  - **Build:** image base 0x140000000. Sections `.text` (RVA 0x1000, file
    0x400), `.rdata` 0x16A000, `.data` 0x183000, `PAGE` 0x1DB000.
- **ACPI.** A DSDT with Kona BSP device numbering plus an SSDT for PEP/GPU,
  inherited from an earlier port attempt. PEP0 has `_HID QCOM2519` (Kona BSP
  numbering), `_CID PNP0D80`.
- **Test harness.** The driver is installed with `Start = 4` (disabled). A
  script signs a patched copy of the driver with a test certificate (test
  signing is on), points the service at it and enables the device once, with
  an ETW session running.
  - **Outcomes:** the driver either initialises or crashes the system; after a
    crash the next boot comes up with PEP disabled again.
  - **Turnaround:** each experiment is one boot.

## 3. Debugging method (no kernel debugger)

There is no kernel debugger and no serial console. Crash dumps worked at
first: the dump stays in `pagefile.sys` until the next boot and was read
from Android recovery with static `ntfscat`. Dumps **stop being written once
PEP's clock driver has initialised** (the "writing dump 0%" screen never
progresses), presumably because PEP has taken over the UFS clocks the crash
dump stack relies on.

Techniques that replaced the debugger:

1. **Breakpoint bisection.** One instruction at a chosen RVA is replaced
   with `brk #0xF000`.
   - **Reached:** the system stops with `SYSTEM_THREAD_EXCEPTION_NOT_HANDLED`
     (0x1000007E, exception 0x80000003).
   - **Not reached:** the original hang occurs (`CLOCK_WATCHDOG_TIMEOUT`
     0x101, or a silent freeze).
   - One boot answers "before or after this point".
2. **Tagged status codes.** Each of the 33 `orr wN, wzr, #0xC0000001` sites in
   RVA 0x100000–0x130000 got a distinct error value. The failing status saved
   in the dump then names the site.
3. **Site code in the stop code.** All `SOC_SUBSYSTEM_FAILURE` (0x14B) stops
   go through one helper, RVA 0x101E80, which has 350 callers, each passing a
   message string. The helper was patched to use
   `(return address − runtime address of RVA 0x101F20) mod 2^32` as the stop
   code, so the code on the blue screen identifies the caller without a dump:

   ```
   0x101F1C  ldr x10, [x29, #8]   ; saved LR
   0x101F20  adr x9, .
   0x101F24  sub w0, w10, w9
   0x101F28  add x1, sp, #0x10    ; unchanged
   0x101F2C  mov x2, x10
   ```
4. **Function stubbing.** A function's prologue is replaced with
   `mov w0, #0; ret`, or a branch is flipped, to skip a step and see what
   happens next.

## 4. Gates passed so far (chronological)

| # | Symptom | Cause | Fix |
|:--|:--|:--|:--|
| 1 | Code 31 / 0xC000000E | Missing ACPI `PEPH` | Added (earlier port) |
| 2 | Assertion `Idle_CoreTopology.c:169` | Missing CPU topology | Added `CTPM` package `CORE_TOPOLOGY` (8 cores) |
| 3 | Bugcheck 0x14B at RPMh init (RVA 0x111238) | The driver's controller table (RVA 0x19FF10, 0x50-byte records) demands 4 TCS for the display RSC; hardware DRV CONFIG at 0x0AF2000C reads 0x80000002 (2 TCS) | Patched the display record's TCS field (file offset 0x19DD84) from 4 to 2. Apps RSC CONFIG 0x1822000C = 0x800C8104 passes |
| 4 | 0x14E `'qpe0'`, status 0xC0000034 in `InitializePppFramework` (RVA 0x115288) | ACPI method `PPPM` missing | Added PPPM (resource list) |
| 5 | Same, 0xC014000F | `PPRR` empty | Added PPRR (9 range triples), taken from the Xiaomi pipa (SM8250) DSDT of Project Silicium |
| 6 | Same, 0xC0000001 | Command DB lookup failure (RVA 0x11F1B8): every non-GPIO PPPM resource is looked up in the RPMh Command DB and must exist with slave version 1.x and 4-byte aux data | Dumped the real Command DB (reserved memory 0x80860000, 128 KiB) from UEFI; 8 resources of the pipa list do not exist on munch (`smpa1`, `smpa2`, `smpc2`, `smpc5`, `ldoa8`, `rfclka2`, `divclka1`, `divclka2`). Removed them from PPPM |
| 7 | Init passes, then `CLOCK_WATCHDOG_TIMEOUT` | Earlier port had a CPU6 hang inside the LMh helper (RVA 0x5C50), writing 0x3A to an LMh block mapped at 0x18350800 (SM8150 address; munch's DT has no LMh there) | All four LMh MMIO functions (RVA 0x5520, 0x5B20, 0x5B88, 0x5C50) stubbed to `ret`. Did not fix the hang (a different one) |
| 8 | Hang persists with processor idle disabled (`powercfg IDLEDISABLE=1`) | — | Ruled out idle states |
| 9 | Bisection → hang inside PEP's embedded clock driver `Clock_DriverInit` (RVA 0xF5A78) | see §5 | in progress |

Bisection path for the current hang, breakpoint by breakpoint:

```
0x214C18 PEP start routine
  └ 0x1DB000 core init
      ├ 0x115288 InitializePppFramework          OK
      ├ 0x072848 RPMh clients: vdd_arc_hlos (apps RSC),
      │          vdd_arc_display (display RSC); cx/mx/xo/mmcx.lvl   OK
      └ 0x0F2490
          └ 0x0F5A78 Clock_DriverInit
              ├ attach (0x101258, id 0x10)                         OK
              ├ 0x0F5D60                                           OK
              ├ 0x0FD198                                           OK
              ├ 0x0F6A40 read back every clock domain's config     OK
              ├ 0x0FBC00 rail setup                                HANG
              │    ├ loop over 9 rails:
              │    │    0x0F49A0 read rail level table (MMIO)      HANG (see §5)
              │    │    0x0F4CD8 table processing (no MMIO)
              │    │    0x0FC820 registry read
              │    ├ register availability callbacks for
              │    │    /clk/hmss_ahb and /clk/mmnoc_ahb
              │    ├ 0x0FB118 define node /node/clk/hmss_ahb       HANG (second, independent)
              │    │    (its only clock: gcc_sys_noc_cpuss_ahb_clk;
              │    │     defining the node fires the callback that
              │    │     enables it)
              │    ├ 0x0F3C60 × 8 (set rail levels 12 / 11)
              │    └ 0x0F5618
              └ 0x0F9768
```

## 5. Current blocker: the clock driver's rail level tables

With the `hmss_ahb` node skipped (branch at RVA 0xFB14C turned into an
unconditional `b`), the remaining hang is in RVA **0xF49A0** and its helper
**0xFE8A0**, called once per rail (index 0–8) from 0xFBC00.

### What the code reads

- **Base pointer:** a global at RVA **0x1D5BC8** holds a mapped virtual
  address (`base`). Reads go through a trivial 32-bit MMIO read helper (RVA
  0xFE678, `ldr w0, [x0]`).
- **Address groups:** chosen by a jump table on the rail index.

| Rails | Registers read (per level entry `n`, `n` = 0..39, stride 0x20) |
|:--|:--|
| 0–3 | `base + 0xB23000 + n*0x20 + {0x110, 0x114, 0x118, 0x11C}` |
| 4–7 | `base + 0xB25000 + n*0x20 + {0x910, 0x914, 0x918, 0x91C}` |
| 8 | `base + 0xB21000 + n*0x20 + {0x118, 0x11C, …}` |

Rails 0–3 read the same addresses (the offset does not include the rail
index), so there are three distinct tables of 40 entries.

- **Fields extracted by 0xFE8A0 from `+0x110`:** bits 8–13, 30–31, 28–29,
  19–25, 16–18, 0–7. They go to output pointers in a table at RVA
  0x1C0F40 + rail*0x780 (0x30 bytes per level).
- **Fields extracted by 0xF49A0 from `+0x114`:** bits 24–27 and 16–21.
- **Loop:** 0xF49A0 runs 40 levels (`x14` from 0 to 0x500 step 0x20).

The pattern (a 40-entry table per resource manager, voltage-level-like
fields) looks like the AOSS/RPMh **ARC** (rail) hardware level tables that AOP
programs, but this is an inference.

Other functions that touch the same `base` (not reached yet, runtime paths):

| RVA | Access |
|:--|:--|
| 0xFEB38 | read-modify-write `base + 0xB23920 / 0xB23924` (+ rail offset) |
| 0xFEDD0 | read bit 0 of `base + 0xB230BC` |
| 0xFEE70 | read-modify-write `base + 0xAA0018` |

### Experiments on this blocker

| Variant | Result |
|:--|:--|
| Original 0xF49A0 | hang (0x101) |
| 0xF49A0 stubbed (`return 0`, nothing read) | no hang there; 0xFBC00 later returns −3 → `Clock_DriverInit` fatal 0x14B (identified via the site code). The rail table stays empty and a later check fails |
| Rail 8 skipped (jump-table entries redirected to the success exits) | hang |
| Rails 4–8 skipped, only 0–3 read | hang |

So reading group A alone already hangs, and the driver cannot proceed without
the data.

### What could not be established

- **Physical address behind `base`.** The global at 0x1D5BC8 is written
  indirectly (not found by static search for stores via `adrp/add`). The
  driver does not import `MmGetPhysicalAddress`. Its constant
  `MmMapIoSpaceEx` mappings are 0x0AEB0000, 0x17A00000, 0x090B0000,
  0x0C300000 (AOP message RAM, used to find the Command DB), LMh 0x18350800 /
  0x18358800, cpufreq-like 0x18323704 / 0x18325F04, GIC 0x17A00108/188. None
  is an obvious match. Candidates by layout: inside the AOSS region
  (0x0B000000–0x0EFFFFFF), e.g. `0x0B000000 + 0xB2xxxx`, but unverified.
- **Configuration source.** No public documentation describes these
  registers. The munch Android device tree has no node for them; Linux takes
  ARC levels from the Command DB aux data instead of reading hardware. PEP0 in
  the pipa DSDT has no `_CRS`. The qcpep INF writes PEP resource/DRIPS
  registry values but no clock driver parameters.

### Working hypothesis

The same pattern as LMh: the driver assumes a Windows-on-Snapdragon firmware
in which TrustZone grants the non-secure world access to AOSS/ARC (and LMh)
registers. On munch's Android firmware these regions are protected (XPU) or
not present at the SM8150 address the driver uses, so the first load stalls
the bus and freezes every core.

## 6. Data available

- **Command DB dump (`cmddb.bin`).** 128 KiB from 0x80860000. All ARC
  entries (`cx.lvl`, `mx.lvl`, `xo.lvl`, `mmcx.lvl`, …) with aux data (the
  vlvl lists Linux uses), VRM and BCM entries.
- **Hardware register values:** RPMh DRV CONFIG for apps and display RSC
  (above).
- **Earlier dumps:** triage dumps of the earlier 0x14E stops. A full
  MEMORY.DMP of an older 0x101 (earlier port) with CPU6 stuck in the LMh
  helper and the LMh blocks mapped at 0x18350800/0x18358800.
- **Disassembly:** of the whole driver (llvm-objdump).
- **Tooling:** a patcher that applies any combination of: display TCS fix,
  LMh stubs, `--ret0-at RVA`, `--brk-at RVA`, `--insn RVA=OLD:NEW`, tagged
  statuses, site code; and a packager for the test harness.

## 7. Constraints

- No JTAG, no kernel debugger, no serial. Crash dumps unusable after the
  clock driver starts. Each experiment costs one tethered boot plus manual
  steps in Windows.
- Firmware (XBL/TZ/AOP/hyp) is stock Android firmware; it cannot be replaced,
  only the UEFI and ACPI.
- The driver binary is signed by Qualcomm; any patched copy runs under test
  signing.

## 8. Questions

1. **What hardware block is it?** On SM8250 (or SM8150, where the driver was
   developed), what sits at `base + 0xB21000 / 0xB23000 / 0xB25000` with
   40 × 0x20-byte level entries (fields at +0x110..0x11C / +0x910..0x91C), plus
   `base + 0xB230BC`, `base + 0xB23920` and `base + 0xAA0018`? Is it the AOSS
   RPMh ARC/RM level table, CPR/CPRh, or something else, and what is its
   physical address?
2. **Is it reachable?** Are those registers readable from EL1 non-secure on
   production Android firmware for SM8250? If not, is there a known way
   (SCM call, different mapping) to obtain the same data?
3. **What do other ports do?** How do other Windows-on-SM8250-phone efforts
   (e.g. the Renegade Project or Project Silicium ports for Xiaomi
   alioth/pipa/elish, OnePlus 8 series) handle `qcpep8250`: do they run
   Qualcomm's PEP at all, a different build, a minimal custom PEP, or no PEP?
   Is there a known set of patches?
4. **Can the table be emulated?** Is there a reasonable way to supply the
   rail level table to the driver (redirect `base` to a RAM buffer filled from
   the Command DB ARC aux data) without understanding the full register
   format? What would the 40-entry fields most likely be (HLVL→VLVL mapping,
   sequence levels, voltage corners)?
5. **Why does the hmss_ahb node hang?** The definition of
   `/node/clk/hmss_ahb` (only clock `gcc_sys_noc_cpuss_ahb_clk`, always on in
   Linux) also hangs. Is that clock controlled by a different master on Kona
   (e.g. not writable from HLOS), and is skipping the node the right
   approach?
6. **Is this the right path at all?** Given that PEP's clock driver expects
   register access the Android firmware does not grant, is patching
   `qcpep8250` realistic, or is a minimal PEP (processor idle + device power
   via RPMh only) the better path towards running the Adreno driver?

## 9. Follow-up: the clock part is SC8180X (8cx)

An external review pointed out that the "rail" tables match the SC8180X OSM
(cpufreq-hw) LUT layout with base = 0x17800000, and that "8180" in the PDB
path is SC8180X rather than SM8150. Both checks it proposed confirm this.

- **Region table.** At RVA 0x19E3E0 in `.data` the driver keeps
  `{physical address, size, &global}` triples that the clock driver maps:

  | Physical | Size | Global (RVA) | On SC8180X |
  |:--|:--|:--|:--|
  | 0x17800000 | 0xC32000 | 0x1D5BC8 | APSS: OSM at 0x18321000/0x18323000/0x18325800, LMh |
  | 0x00100000 | 0x200000 | 0x1D5BD8 | GCC |
  | 0x02C00000 | 0x0D4000 | 0x1D5BC0 | GPU (on SM8250 the GPU is at 0x03D00000) |
  | 0x0AE00000 | 0x200000 | 0x1D5BE0 | display |
  | 0x09800000 | 0x800000 | 0x1D5BB8 | NPU |
  | 0x0AC00000 | 0x110000 | 0x1D5BB0 | camera / video |
  | 0x0AA00000 | 0x200000 | 0x1D5BD0 | video |

  The rail read-back therefore reads the OSM frequency/voltage LUT at
  0x18323110 (cluster 0), 0x18325910 (cluster 1) and 0x18321118 (L3). SM8250
  has EPSS at 0x18590000–0x18593000 instead of OSM, so nothing answers at
  0x1832xxxx and the first load stalls.
- **GCC clock names.** Of the 240 GCC clock names in the driver, 112 exist on
  both chips (per Linux `gcc-sm8250.c` / `gcc-sc8180x.c`), 35 only on SC8180X
  (UFS card 2, EMAC, USB3 MP, PCIe 3, QSPI 1, GP4/5) and 11 only on SM8250.
  The embedded clock driver describes the SC8180X GCC.

Consequence: the clock part of this qcpep8250 build programs SC8180X
registers. Every further step would hit another 8cx block, and the GPU power
path (clocks at the SC8180X GPU address) cannot work on Kona.
