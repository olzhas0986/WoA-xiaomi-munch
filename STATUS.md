# Hardware status

Results below refer to POCO F4 (`munch`), Snapdragon 870, 6 GB RAM, with the
tested input hashes in `BUILDING.md`.

| Component | Result | Evidence / limitation |
|---|---|---|
| Firmware UI and framebuffer | Pass | GOP reports 1080×2400; framebuffer console and Windows output work |
| CPU topology | Pass | Windows sees 8 logical processors |
| RAM | Pass | Windows sees 6.00 GB installed / about 5.34 GB usable |
| ACPI core tables | Pass | FACP, APIC and GTDT are generated and checksum-verified |
| UFS | Pass | Installer and installed Windows access internal storage |
| USB mouse | Pass | Pointer and clicks work in Setup and desktop |
| USB keyboard | Unconfirmed on final profile | It failed in earlier trials and was not revalidated after the final USB changes |
| USB mass storage | Pass | Files can be read/written from Windows |
| Windows installation/desktop | Pass | Windows 11 IoT Enterprise LTSC 24H2 reached desktop |
| SCM (`QCOM250B`) | Pass | Qualcomm driver reached PnP status OK / code 0 |
| RPEN, SPMI, core PMIC | Pass as foundation | Staged drivers reached code 0 in isolation |
| GPU | Fail | No Adreno WDDM device; Basic Display framebuffer only |
| Touch | Fail | No Windows touch driver; Linux implementation is reference material |
| PEP (`QCOM2519`) | Experimental/fail | Driver reached code 31/ProblemStatus `0xC000000E`; later tests crashed |
| Suspend/shutdown | Fail | `INTERNAL_POWER_ERROR` and `CLOCK_WATCHDOG_TIMEOUT` observed |
| PC detach before boot | Required | Unplug immediately after `fastboot boot` finishes so VBUS is absent for host hand-off |
| OTG hot detach in Windows | Unstable | Some later detach sequences reboot or crash firmware/Windows |
| Audio/camera/modem/radios | Unknown | Not implemented or validated |

## Known PEP failure modes

The diagnostic work produced `PAGE_FAULT_IN_NONPAGED_AREA`,
`SOC_SUBSYSTEM_FAILURE`, `CLOCK_WATCHDOG_TIMEOUT` and
`INTERNAL_POWER_ERROR`. The LMH/SOSI binary-patch experiments are retained only
for analysis and are not part of `make stable`. Do not install a boot-start
`qcpep` service on a daily-use Windows installation without a recovery path.

## What “GPU foundation” means

Names such as GPU28 in historical logs referred to staged dependencies needed
before a Kona display/GPU driver can bind: SCM, RPEN, SPMI, PMIC and PEP. Code 0
for those foundation devices did not mean GPU acceleration was working. No GPU
driver is installed by the default build.
