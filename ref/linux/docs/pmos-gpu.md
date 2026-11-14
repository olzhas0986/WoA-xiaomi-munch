# Adreno 650 experiment T

GPU rendering test for munch. Image built: 16080896 bytes; 40 host tests passed.
Hardware validation is pending. This retains
simplefb and the P/R clock workaround; native DSI/DPU is still disabled.
The confirmed Wi-Fi image is preserved in `out/baseline-pmos-wifi/`.

The pinned SM8250 DT already describes Adreno 650.2, GMU, GPUCC, its SMMU,
OPPs, speed-bin efuse and the 8192-byte gpu_mem reservation. T enables these
existing nodes plus MSM DRM, QFPROM, LLCC and SM8250 GPUCC. It does not
increase GPU clocks or carve out new memory. DRM_MSM_DPU/MDP4/MDP5 stay off.
The HPD bridge Kconfig fix is isolated in `out/pmos-gpu/linux-src`, because
the existing Type-C driver selects that bridge once DRM is enabled. The
bridge calls KMS helper functions even in a render-only configuration.

## Supplied ZAP

The user supplied `a650zap.zip` (SHA256
f9c73b7222c9c924ebe7093585a9577855d9c8cf0eb04ead202b8b1e851264f2).
It contains MDT, b00/b01/b02, an ELF and SQE/GMU files. The MDT/split
set passed layout checks: 4096 load bytes fit the unchanged 8192-byte
reservation. `out/munch-zap-staged/manifest.json` records hashes. Hardware
signature authentication remains pending. The normalized ZAP files are
embedded under `/lib/firmware/qcom/sm8250/xiaomi/munch/` in T only; the
provided SQE/GMU files are retained as evidence, not embedded.

## Obtaining another dump if needed

Ordinary SQE/GMU firmware comes from `firmware-qcom-adreno-a650`. Signed
ZAP must come from munch Android. Do not substitute alioth/elish ZAP or
remove the zap-shader node to bypass authentication.

Boot Android normally and use an authorized ADB connection. These commands
only list/read files, and do not flash or write Android partitions:

```sh
adb shell 'ls -l /vendor/firmware/a650* /vendor/firmware_mnt/image/a650*'
```

Some Android versions use `/vendor/firmware_mnt/image/`, others
`/vendor/firmware/`. From the directory that actually contains the files,
copy `a650_zap.mdt` and every `a650_zap.bNN` shown by that listing, or a
single `a650_zap.mbn`. For example (adjust directory and segment list):

```sh
mkdir -p out/munch-zap-android
adb pull /vendor/firmware/a650_zap.mdt out/munch-zap-android/
adb pull /vendor/firmware/a650_zap.b00 out/munch-zap-android/
# Repeat only for all a650_zap.bNN files shown by ls.
```

If Android denies reading, stop and provide the error; do not change
permissions or write partitions. Extraction from a matching stock firmware
archive is another option. Provide the exact firmware/device provenance.

Validate/stage the dump on the PC:

```sh
python3 tools/stage-adreno-firmware.py --source out/munch-zap-android --output out/munch-zap-staged
```

The tool checks ELF32 header/segment bounds, required split files, hash
segment presence and the existing GPU reservation size. It preserves image
bytes, normalizing the header filename to `a650_zap.mbn` (the Linux loader
handles both split and monolithic ELF containers). This is not signature
verification; TrustZone performs authentication on the phone. A JSON
manifest records hashes. Existing output directories are never overwritten.

## Quick test with the existing Wi-Fi rootfs

T embeds the supplied ZAP, so the existing NTFS rootfs is sufficient.
After booting T and running pmos-load/wifi-start, connect Wi-Fi as before,
enter pmos-enter, then install into RAM:

```sh
apk add firmware-qcom-adreno-a650 mesa-dri-gallium mesa-egl mesa-gbm mesa-utils
exit
gpu-prepare
pmos-enter
EGL_PLATFORM=surfaceless eglinfo -B
```

For a persistent archive containing these packages, use the optional host
rootfs recipe below. Manual `fastboot boot` remains the only boot action.

## Prepare rootfs and image on the PC

```sh
python3 tools/pmos-rootfs.py gpu-build
```

Export the userspace; the validated ZAP is already embedded in the GPU image:

```sh
python3 tools/pmos-rootfs.py gpu-export
make pmos-gpu
```

This adds the A650 package, Mesa Gallium/EGL/GBM, mesa-utils and libdrm-tests
alongside Wi-Fi packages. The previous exports stay intact. Copy the archive
and `.sha256` from `out/pmos-rootfs/gpu/` to the NTFS stick, replacing its
older copies. The boot image contains only the small signed ZAP bootstrap, not the rootfs.
SQE/GMU firmware stays in the external rootfs.

## Manual hardware test

```sh
fastboot boot out/pmos-gpu/munch-boot.img
```

On the phone, start with enumeration and logs:

```sh
ls /dev/dri
dmesg | grep -iE 'adreno|msm|gmu|gpu|smmu|drm|qfprom'
pmos-load
# Wait for PMOS READY
gpu-prepare
```

Do not interpret renderD128 alone as successful GPU execution. After
`gpu-prepare` has verified firmware paths, enter userspace and test EGL:

```sh
pmos-enter
EGL_PLATFORM=surfaceless eglinfo -B
```

Mesa supports surfaceless EGL, so native display modesetting is not needed
for this initialization test. Inspect the renderer: Adreno/Freedreno is the
hardware path; llvmpipe/softpipe is software fallback and does not prove GPU
support. See [Mesa EGL](https://docs.mesa3d.org/egl.html) and
[Mesa environment variables](https://docs.mesa3d.org/envvars.html).
An EGL renderer report establishes initialization, not sustained rendering
stability or accelerated screen output. Do not force software rendering,
spoof a GPU model or disable firmware authentication to make this pass.

If startup fails, exit the chroot and collect `dmesg | tail -n 150` and
`cat /sys/kernel/debug/devices_deferred`. Return to the saved Wi-Fi image
if boot fails; no flashing command is part of this experiment.

## T follow-up: separate GPU DRM device

The first hardware report has GPUCC and Adreno SMMU initialized, adreno
probe returns 0, but no /dev/dri. The render-only profile omitted
`msm.separate_gpu_kms=1`: this kernel defaults to a shared display/GPU
component DRM device, while our display master is disabled. The GPU DTS
now explicitly selects the independent GPU DRM device. Further GMU probe
errors still require devices_deferred and the full relevant dmesg.

## T follow-up: UBWC/SMEM and devfreq

With separate_gpu_kms=1 the hardware log reaches a6xx initialization but
returns -95 and logs `Couldn't initialize GPU devfreq`. These are two
separate missing dependencies in the minimal configuration:

- PM_DEVFREQ was disabled; msm_devfreq_init's devfreq call used its stub.
  That function logs the failure and returns void, so it is not itself
  the fatal -95. Enable PM_DEVFREQ and DEVFREQ_GOV_SIMPLE_ONDEMAND.
- a6xx_gpu_init later calls qcom_ubwc_config_get_data(). With
  QCOM_UBWC_CONFIG disabled its stub returns -EOPNOTSUPP (-95), aborting
  GPU binding. Enable HWSPINLOCK/HWSPINLOCK_QCOM, QCOM_SMEM and
  QCOM_UBWC_CONFIG. The existing SM8250 SMEM node uses the retained
  0x80900000/0x200000 reservation and TCSR hardware lock 3.

No regulator supplies are invented from the dummy vdd/vddcx warnings.
The native GMU/GPUCC power-domain path remains unchanged. SMEM availability
and UBWC initialization still require confirmation on hardware.
