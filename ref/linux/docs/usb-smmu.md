# USB preflight G: ARM SMMU

User confirmed both expected F summary lines and successful userspace boot.
Interconnect provider binding is established; USB traffic is still untested.

## Scope and risk

DWC3 at a600000 has iommus = <&apps_smmu 0x0 0x0> in the inherited
sm8250.dtsi. Enable IOMMU_SUPPORT, ARM_SMMU and its QCOM implementation,
retaining translated strict DMA and the upstream unmatched-stream policy.
No passthrough or disable_bypass parameter is added. No DT properties change.
DWC3, PHY and USB gadget remain disabled.

This is hardware programming, not just a passive check: the mainline SMMU driver
probes/reset-configures translation and stream routing. Display scanout inherited
from the bootloader could stop or fault. The existing F image is preserved as a
fallback. Boot only via fastboot boot; no partition/storage writes occur.

Source references in the pinned kernel:

- arch/arm64/boot/dts/qcom/sm8250.dtsi: USB IOMMU link and apps_smmu@15000000.
- drivers/iommu/arm/Kconfig: ARM_SMMU/QCOM and default bypass policy.
- drivers/iommu/arm/arm-smmu/arm-smmu.c: arm-smmu driver and reset path.
- drivers/iommu/arm/arm-smmu/arm-smmu-qcom.c: SM8250 implementation,
  firmware-dependent S2CR probe and stream state handling.

The upstream QCOM implementation detects hypervisor register emulation quirks.
This uses normal EL1 MMIO/SCM interfaces; the loader still does not access EL2.
The profile explicitly enables the upstream MMU-500 CPRE errata option
(default y in mainline), disabling next-page prefetch in the reset path.
No new local SMMU patch is introduced.

TEMPORARY WORKAROUND: clk_ignore_unused stays as in F. Existing trace patches
and command line are retained. This does not guarantee preservation of DMA state.

## Build and hardware check

```sh
make usb-smmu
fastboot boot out/usb-smmu/munch-boot.img
```

Expected:

```text
G CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=1 PDC=1
G BCM=1 A1=1 MC=1 GEM=1 CN=1 SMMU=1
```

SMMU=1 checks the actual binding of 15000000.iommu to arm-smmu. It does not
prove DMA works; the USB DMA master is not enabled yet. Report both G lines.
For SMMU=0, copy the preceding SMMU diagnostic messages. If the screen freezes
or goes black, report the last visible lines and approximate timing. Do not
add a bypass parameter yourself; any such A/B test must remain separate.
No camera or prolonged idle check is required. Full dmesg stays in RAM.

## Local validation

Final build succeeded with CPRE errata enabled. All eight existing tests passed;
shell syntax and whitespace checks passed. Previous enabled kernel settings are
unchanged; fourteen symbols are newly enabled: IOMMU_SUPPORT/API/IOVA,
IOMMU_IO_PGTABLE/LPAE, IOMMU_DEFAULT_DMA_STRICT, IOMMU_DMA, OF_IOMMU,
DMA_OPS_HELPERS, NEED_SG_DMA_FLAGS, ARM_SMMU/QCOM,
ARM_SMMU_DISABLE_BYPASS_BY_DEFAULT and ARM_SMMU_MMU_500_CPRE_ERRATA.
Loader bytes and DTB semantics match F; the confirmed F boot-image SHA is
unchanged. User confirmed the expected test passed, SMMU enabled, and screen still
visible after about one minute. This does not verify USB DMA or long-term stability. Logs: out/usb-smmu/logs/.

Final boot image SHA-256:

```text
f3e1596b63bbc6bcf46ac4b093bf4246f10c97ae9c8063bc4f6ef016f1139c74
```
