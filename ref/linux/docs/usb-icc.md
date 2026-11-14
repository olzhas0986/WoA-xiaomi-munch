# USB preflight F: SM8250 interconnect

Preflight E is confirmed: PDC=1 and the shell screen remained visible for one
minute. USB traffic and long-term stability remain untested.

## Change

Enable INTERCONNECT_QCOM and INTERCONNECT_QCOM_SM8250, with their selected
RPMh and BCM voter helpers. Keep all PDC profile requirements. No board DT,
command-line, USB controller, PHY, supply, IOMMU or gadget changes.

The inherited sm8250.dtsi USB wrapper declares these interconnect paths:

- aggre1_noc MASTER_USB3 -> mc_virt SLAVE_EBI_CH0
- gem_noc MASTER_AMPSS_M0 -> config_noc SLAVE_USB3

The mainline driver binds all enabled matching SM8250 NoC nodes, not just these
four endpoints. It registers the graph and uses BCM/RPMh bandwidth votes;
probe/sync_state may change shared resource votes and display behaviour.
clk_ignore_unused does not bypass interconnect voting. No additional workaround
is introduced. No storage/partition writes occur.

Source references in the pinned kernel: drivers/interconnect/qcom/sm8250.c
(match table and qnoc-sm8250 driver), icc-rpmh.c (probe), bcm-voter.c
(bcm_voter driver and vote aggregation), and arch/arm64/boot/dts/qcom/sm8250.dtsi.

The F init script checks actual bound sysfs devices for each USB path endpoint:
A1=16e0000, MC=163d000, GEM=9100000, CN=1500000, plus the BCM voter.
This confirms binding, not end-to-end USB path requests or traffic.

TEMPORARY WORKAROUND: retain clk_ignore_unused from the successful baseline.
Existing initcall/cacheinfo diagnostics also remain unchanged.

## Build and test

```sh
make usb-icc
fastboot boot out/usb-icc/munch-boot.img
```

Expected two summary lines followed by BusyBox:

```text
F CPU=8 RPMH=1 IPCC=1 AOSS=1 CLK=1 GCC=1 PDC=1
F BCM=1 A1=1 MC=1 GEM=1 CN=1
```

Report both F lines. If a field is zero, report preceding interconnect diagnostic
messages. If boot stalls or display stops updating, report the last 2–4 visible
lines. No camera or idle-duration wait is needed. USB enumeration is not expected.
Full dmesg stays in RAM at /run/dmesg.boot. The confirmed PDC image is preserved.

## Local validation

Build and repeat build succeeded; eight existing tests and shell syntax checks
passed. Config enables exactly five additional symbols: INTERCONNECT_QCOM,
INTERCONNECT_QCOM_SM8250, INTERCONNECT_QCOM_RPMH,
INTERCONNECT_QCOM_BCM_VOTER and the hidden RPMH_POSSIBLE dependency.
Other newly visible SoC choices stay unset. DTB decompilation matches E,
loader bytes match, and the confirmed E boot-image SHA remains unchanged.
User confirmed both expected F lines and successful boot. This verifies
provider binding, not USB traffic or requested bandwidth. Logs: out/usb-icc/logs/.

Boot image SHA-256:

```text
ad340f0e22086fd3bc63f2409bc070618bb7d9c40ff37f274f1158897391344b
```
