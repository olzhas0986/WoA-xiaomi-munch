# Stock munch USB2 supply evidence

The user supplied vendor_boot.img and dtbo.img from what they identify as the
latest HyperOS. Exact release/build provenance is not independently established.
These files are retained locally and ignored by Git; only evidence is tracked.
No Android root is needed. No phone command or partition access is involved.

## Reproduce offline

```sh
python3 tools/extract-stock-dt.py
```

Requires host fdtget and fdtoverlay. Output is out/stock-usb-evidence/;
choose --out for a new directory on subsequent runs. Header/table/FDT ranges
are checked. vendor_boot v3 includes three Kona SoC bases and an RTIC metadata
FDT. The DTBO table includes 27 entries. Overlay 21 uniquely identifies
`Qualcomm Technologies, Inc. xiaomi munch`, qcom,board-id = <0x32 0>.
It is applied separately to each actual SoC base; RTIC is not treated as a SoC.
Overlay root identification properties are selection metadata; fdtoverlay does
not copy them into the merged root unless a fragment explicitly targets it.

## Resolved USB2 rails

The vendor PHY symbol usb2_phy0 resolves to /soc/hsphy@88e3000.
Supply references are resolved by phandle, not by similar node names:

| Vendor PHY property | RPMh resource | Regulator | Fixed constraint (uV) | Mainline PHY property |
|---|---|---|---:|---|
| vdd-supply | ldoa5 | pm8150_l5 | 880000 | vdda-pll-supply |
| vdda18-supply | ldoa12 | pm8150_l12 | 1800000 | vdda18-supply |
| vdda33-supply | ldoa2 | pm8150_l2 | 3072000 | vdda33-supply |

The vendor vdd-voltage-level also requests 880000 for the first rail. The old
local MTP-derived include constrained L5A to 875000; do not reuse that value.
Mainline SM8250 FEMTO PHY uses vdda-pll/vdda33/vdda18 supply names; use its
binding and driver, not the vendor compatible or raw register sequences.
Vendor USB3 PHY is disabled in the merged munch tree, supporting a USB2-only
initial scope. It does not prove the hardware cannot support USB3.

The supplied stock tree identifies LDO resource consumers but does not establish
all physical upstream supply wiring required for a complete mainline regulator
topology. Do not manufacture parent rails from MTP or mask missing supplies with
silent dummy regulators. Audit parent requirements before programming resources.
Do not copy vendor GPIO reservations, display, clocks, memory map or PHY tuning.

Actual bootloader base/overlay selection is not captured. Matching rail evidence
across all three SoC bases removes that particular ambiguity for these supplies;
it does not validate every property of a selected base or replace the current DTS.

Next hardware stage should bind the minimal real regulator/USB2 PHY providers
before DWC3/configfs ACM, retaining the confirmed G fallback. Binding a PHY alone
does not prove it has been powered or the USB link works. No new boot image is
produced by the extraction tool.

## Validation

Offline extraction completed successfully for Kona v2.1 (356/0x20001),
v2 (356/0x20000) and v1 (356/0x10000). All three produced identical resolved
supply names/resources and min/max values. Machine-readable evidence and input
SHA-256 values are in stock-usb-evidence.json. Python compilation, whitespace
checks and rejection of a truncated vendor header before output creation passed.
Source images are unchanged; no kernel/loader/initramfs/boot artifacts were rebuilt.
The merged DTB is evidence only and must never be substituted for the boot DTS.
