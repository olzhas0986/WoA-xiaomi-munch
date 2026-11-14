# Stock 120 Hz and battery telemetry

Build `make pmos-native-120-battery` after the modular Wi-Fi build. Output:

```sh
fastboot boot out/pmos-native-120-battery/munch-boot.img
```

Use the existing saved USB rootfs. This image keeps the modular Wi-Fi lifecycle
verified by the user on two native boots. The new display and battery paths
still require hardware verification. The working modular image is preserved.

## Panel

The Android-selected L11R 38:08:0a panel has a stock `timing@2` at 120 Hz.
Its horizontal front/sync/back porch is 16/8/8 pixels and its vertical porch
is 4/4/8 lines, with a 1080x2400 active area. DSC stays at two 540x8 slices,
8 bits per component and 8 compressed bits per pixel. This is a different
timing and command stream from the existing 60 Hz mode, not a doubled clock
using the old porches. The computed DRM pixel clock is 322391 kHz.

Patch 0008 includes the exact stock 120 Hz on/off packets and their delays,
including the final `60 10` refresh selection. It can be reproduced against
the existing RX source export:

```sh
python3 tools/generate-display-patch.py --extension \
  --dtb out/stock-dt/munch-v21.dtb --cmdline cmdline.txt \
  --kernel-source out/pmos-wifi-rx/linux-src --output /tmp/panel-120.patch
cmp /tmp/panel-120.patch patches/0008-drm-panel-munch-stock-120hz.patch
```

The experimental panel property `xiaomi,refresh-rate` selects a fixed 60 or
120 Hz profile at probe. Omitted means 60 Hz. Other values fail probe rather
than silently selecting a mode. Only the selected mode is advertised: runtime
60/120 switching has not been implemented. The test DT selects 120 Hz; Phoc
uses that single preferred mode. Driver logs confirm the selected profile,
and DRM debugfs state can confirm the actual scanout timing.

## Battery

Stock munch overlay 21 contains `/soc/i2c@888000/bq27z561@55`, compatible
`ti,bq27z561`. Its active pin group is GPIO48/49, function `qup16`, 2 mA,
with bias disabled. The upstream SM8250 I2C16 pin group matches it exactly.
The test enables only that GENI controller, its wrapper/GPI DMA, and the
existing upstream BQ27XXX I2C driver. The module is loaded by native udev
after the matching module bundle has been installed into the RAM rootfs.

The gauge reports capacity, status, voltage, current, temperature and charge
through `/sys/class/power_supply/bq27z561-*`; UPower can expose it to Phosh.
No replacement capacity calibration or `monitored-battery` data is supplied.
`CONFIG_BATTERY_BQ27XXX_DT_UPDATES_NVM` is explicitly disabled. Neither the
PMIC charger nor the stock external charge pumps are enabled by this change.
Battery reporting does not establish working charge control or fast charging.

The stock PM8150B fuel-gauge node is disabled, so the F3 PMIC gauge setup was
not copied. Relevant upstream sources are the kernel's
`Documentation/devicetree/bindings/power/supply/bq27xxx.yaml` and
`drivers/power/supply/bq27xxx_battery{,_i2c}.c`.

## Device checks

```sh
uname -r
dmesg | grep -iE 'l11r|bq27|geni.*i2c|i2c.*geni'
grep -H . /sys/class/power_supply/bq27z561-*/uevent
```

The release should be `7.3.0-rc7-pmos-munch-120-battery`, and the panel log
should say `120 Hz`. Check scrolling, brightness, Wi-Fi and battery percentage
in Phosh. If sysfs has valid battery readings but the shade has no indicator,
check `upower -d` and whether the saved rootfs includes UPower. Collect logs
before changing the rootfs or assuming a gauge failure.
