# Preflight H: three verified USB2 RPMh LDOs

## Scope

Preserve G (SMMU/interconnect/PDC/GCC) and its temporary clk_ignore_unused.
Enable REGULATOR and REGULATOR_QCOM_RPMH. Use a separate board DTS including
the baseline and adding only PM8150 A ldo5/ldo12/ldo2 beneath apps_rsc.
No PHY, DWC3, gadget, PMIC/SPMI, DRM, UFS or additional regulator drivers.

The stock munch overlay evidence in stock-usb-evidence.json establishes:
ldoa5=880000, ldoa12=1800000, ldoa2=3072000 uV. Mainline maps PM8150 A
ldoN nodes to these command-db resources. Only those children are registered.
These are voltage/enable votes to real hardware and may affect shared users;
the test is not a passive DT inspection. Values match supplied stock constraints.

## Explicit temporary limitations

TEMPORARY WORKAROUND: input supply phandles are omitted because physical parent
wiring is not established by the stock extraction. The unmodified regulator core
resolves missing input supplies to its dummy regulator under full constraints.
No fabricated fixed input voltage/parent topology is added, and no input rail is
programmed here. Firmware must retain input power. This tests APPS output votes,
not a complete regulator graph or verified physical voltages. H prints
UPSTREAM=UNMODELED so this limitation is visible on the device.

TEMPORARY WORKAROUND: regulator-always-on holds exactly these three LDOs while
no USB PHY consumer is enabled. This prevents regulator cleanup switching them
off in the provider-only test. It is neither a permanent ownership solution nor
a global regulator_ignore_unused flag. Revisit when adding the PHY consumer.
No initial-mode property is invented; the upstream driver reads initial mode.
Driver read failures remain visible. No firmware mode errors are suppressed.

Sources: drivers/regulator/qcom-rpmh-regulator.c (pm8150_vreg_data and probe),
drivers/regulator/core.c (regulator_resolve_supply, registration constraints),
Documentation/devicetree/bindings/regulator/qcom,rpmh-regulator.yaml.

## Build and temporary boot

```sh
make usb-rails
fastboot boot out/usb-rails/munch-boot.img
```

Expected CPU=8 and all existing provider fields=1, plus:

```text
H L5=1 L12=1 L2=1 UPSTREAM=UNMODELED
```

Each LDO field requires a matching sysfs regulator name, the expected microvolts
and state=enabled. These values are the driver's reported state/vote, not an ADC
measurement or proof the PHY is powered. USB enumeration is not expected yet.

Report the H lines. On a zero, report preceding regulator messages. If boot
stalls or the display goes black, report last visible lines and timing. Do not
add new command-line flags. G remains unchanged as a fallback. No partition
writes occur. Full dmesg and, if available, regulator debugfs summary stay in RAM
at /run/dmesg.boot and /run/regulator-summary.boot for future transport.

## Local validation

Build succeeded. User confirmed all expected H fields on hardware.
This confirms reported output votes/state, not measured voltages or input wiring. All ten existing tests passed, plus
shell syntax and whitespace checks. Kernel config adds exactly REGULATOR,
REGULATOR_QCOM_RPMH and selected LINEAR_RANGES, with every previous enabled
setting unchanged. Removing the new regulator subtree from H produces the exact
same sorted DT decompilation as G: command line, memory, display, SMMU and other
properties are unchanged. Loader bytes and confirmed G image hash are unchanged.
Packer checks passed. Build log: out/usb-rails/logs/build.log.

Image SHA-256:

```text
2c5cc61b3e78f84ba2aa8e2d825fc2553ddf733d6827092236ebfb54e1b76ca5
```
