SHELL := /bin/sh
.DEFAULT_GOAL := help
.DELETE_ON_ERROR:
ROOT := $(abspath .)
OUT ?= $(ROOT)/out
OUT := $(abspath $(OUT))
SOURCE_OUT ?= $(OUT)
SOURCE_OUT := $(abspath $(SOURCE_OUT))
KERNEL_REPO ?= $(HOME)/linux
BUSYBOX_TAR ?= $(ROOT)/../busybox-1.37.0.tar.bz2
JOBS ?= 8
KERNEL_PATCHES ?=
EXTRA_KERNEL_FRAGMENT ?=
BUSYBOX_FRAGMENT ?= $(ROOT)/configs/busybox.fragment
BOARD_DTS_DEPS ?=
BOARD_DTS ?= $(ROOT)/dts/sm8250-xiaomi-munch.dts
GPU_ZAP ?=
PHONE_TOOLS ?=
NATIVE_OUTPUT ?= $(OUT)/pmos-native
NATIVE_KERNEL_IMAGE ?= $(OUT)/pmos-touch/kernel/arch/arm64/boot/Image
NATIVE_DTB ?= $(OUT)/pmos-touch/sm8250-xiaomi-munch.dtb
NATIVE_MODULES ?=
INIT_SCRIPT ?= $(ROOT)/initramfs/init
CROSS_COMPILE ?= aarch64-linux-gnu-
export CROSS_COMPILE
CC := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy
KSRC := $(SOURCE_OUT)/linux-src
KOUT := $(OUT)/kernel
BSRC := $(SOURCE_OUT)/busybox-1.37.0
BOUT := $(OUT)/busybox
export LC_ALL := C
export SOURCE_DATE_EPOCH := 1792195200
export KBUILD_BUILD_TIMESTAMP := 2026-10-17 00:00:00 UTC
export KBUILD_BUILD_USER := pmos-munch
export KBUILD_BUILD_HOST := build
export KBUILD_BUILD_VERSION := 1
export KCONFIG_NOTIMESTAMP := 1
ARCH_ROOTFS ?= $(HOME)/Загрузки/ArchLinuxARM-aarch64-latest.tar.gz
.PHONY: arch-ram
arch-ram:
	mkdir -p "$(OUT)/arch-ram"
	cat configs/kernel-pmos-preflight.fragment configs/kernel-arch-systemd.fragment > "$(OUT)/arch-ram/kernel.fragment"
	cat configs/busybox-pmos-usb.fragment configs/busybox-arch.fragment > "$(OUT)/arch-ram/busybox.fragment"
	python3 tools/build-arch-init.py --archive "$(ARCH_ROOTFS)" --output "$(OUT)/arch-ram/init"
	$(MAKE) OUT="$(OUT)/arch-ram" SOURCE_OUT="$(OUT)/arch-ram" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(OUT)/arch-ram/kernel.fragment" \
	 BUSYBOX_FRAGMENT="$(OUT)/arch-ram/busybox.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-otg-keyboard.dts" \
	 BOARD_DTS_DEPS="$(wildcard $(ROOT)/dts/sm8250-xiaomi-munch-usb-*.dts)" \
	 INIT_SCRIPT="$(OUT)/arch-ram/init" image
	fdtput -t s "$(OUT)/arch-ram/sm8250-xiaomi-munch.dtb" /chosen bootargs 'console=tty0 rdinit=/init loglevel=6 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/arch-ram/loader.bin" --image "$(OUT)/arch-ram/kernel/arch/arm64/boot/Image" --dtb "$(OUT)/arch-ram/sm8250-xiaomi-munch.dtb" --initramfs "$(OUT)/arch-ram/initramfs.cpio.gz" --output "$(OUT)/arch-ram/payload.bin" --boot-image "$(OUT)/arch-ram/munch-boot.img"
CFLAGS := -O2 -Wall -Wextra -Werror -ffreestanding -fno-builtin -nostdlib \
 -mstrict-align -mcmodel=tiny -fno-pic -fno-pie -mgeneral-regs-only -fno-stack-protector \
 -fno-asynchronous-unwind-tables -fno-unwind-tables -static -no-pie
.PHONY: help sources loader kernel-config kernel busybox-config busybox dtb initramfs image check
help:
	@echo 'make sources kernel-config kernel busybox-config busybox dtb image'
	@echo 'make check; fastboot boot out/munch-boot.img (manual only)'
sources:
	python3 tools/sources.py --kernel-repo "$(KERNEL_REPO)" $(if $(KERNEL_TAR),--kernel-tar "$(KERNEL_TAR)" --kernel-sha256 "$(KERNEL_SHA256)") --busybox-tar "$(BUSYBOX_TAR)" --out "$(SOURCE_OUT)" $(foreach p,$(KERNEL_PATCHES),--patch "$(p)")
$(OUT):
	mkdir -p "$@"
loader: $(OUT)/loader.bin
$(OUT)/loader.elf: loader/start.S loader/main.c loader/fb.c loader/fb.h loader/link.ld Makefile | $(OUT)
	$(CC) $(CFLAGS) -Wl,--build-id=none,-T,loader/link.ld loader/start.S loader/main.c loader/fb.c -o "$@"
$(OUT)/loader.bin: $(OUT)/loader.elf
	$(OBJCOPY) -O binary "$<" "$@"
kernel-config: | sources
	python3 tools/configure.py --source "$(KSRC)" --out "$(KOUT)" --fragment "$(ROOT)/configs/kernel.fragment" $(if $(EXTRA_KERNEL_FRAGMENT),--extra-fragment "$(EXTRA_KERNEL_FRAGMENT)")
$(KOUT)/.config: configs/kernel.fragment tools/configure.py $(EXTRA_KERNEL_FRAGMENT) | sources
	python3 tools/configure.py --source "$(KSRC)" --out "$(KOUT)" --fragment "$(ROOT)/configs/kernel.fragment" $(if $(EXTRA_KERNEL_FRAGMENT),--extra-fragment "$(EXTRA_KERNEL_FRAGMENT)")
kernel: $(KOUT)/.config
	$(MAKE) -C "$(KSRC)" O="$(KOUT)" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS) Image
busybox-config: | sources
	python3 tools/configure.py --busybox --source "$(BSRC)" --out "$(BOUT)" --fragment "$(BUSYBOX_FRAGMENT)"
$(BOUT)/.config: $(BUSYBOX_FRAGMENT) tools/configure.py | sources
	python3 tools/configure.py --busybox --source "$(BSRC)" --out "$(BOUT)" --fragment "$(BUSYBOX_FRAGMENT)"
busybox: $(BOUT)/.config
	$(MAKE) -C "$(BSRC)" O="$(BOUT)" CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS)
dtb: $(OUT)/sm8250-xiaomi-munch.dtb
$(OUT)/sm8250-xiaomi-munch.dtb: $(BOARD_DTS) $(BOARD_DTS_DEPS) dts/sm8250-xiaomi-munch.dts tools/sources.py | sources $(OUT)
	$(CC) -E -P -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
	 -I"$(KSRC)/include" -I"$(KSRC)/arch/arm64/boot/dts/qcom" "$<" -o "$(OUT)/munch.preprocessed.dts"
	dtc -I dts -O dtb -o "$@" "$(OUT)/munch.preprocessed.dts"
initramfs: busybox | $(OUT)
	python3 tools/mkinitramfs.py --busybox "$(BOUT)/busybox" --init "$(INIT_SCRIPT)" $(if $(GPU_ZAP),--gpu-zap "$(GPU_ZAP)") $(if $(PHONE_TOOLS),--phone-tools "$(PHONE_TOOLS)") --output "$(OUT)/initramfs.cpio.gz"
image: kernel loader dtb initramfs
	python3 tools/pack.py --loader "$(OUT)/loader.bin" --image "$(KOUT)/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/sm8250-xiaomi-munch.dtb" --initramfs "$(OUT)/initramfs.cpio.gz" \
	 --output "$(OUT)/payload.bin" --boot-image "$(OUT)/munch-boot.img"
check: loader dtb
	sh -n initramfs/init
	sh -n initramfs/init-usb-preflight
	sh -n initramfs/init-usb-ipcc
	sh -n initramfs/init-usb-clocks
	sh -n initramfs/init-usb-gcc
	sh -n initramfs/init-usb-pdc
	sh -n initramfs/init-usb-icc
	sh -n initramfs/init-usb-smmu
	sh -n initramfs/init-usb-rails
	sh -n initramfs/init-usb-phy
	sh -n initramfs/init-usb-udc
	sh -n initramfs/init-usb-acm
	PMOS_MUNCH_OUT="$(OUT)" python3 -m unittest discover -s tests -v

.PHONY: usb-preflight
usb-preflight:
	$(MAKE) OUT="$(OUT)/usb-preflight" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-preflight.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-preflight" image

.PHONY: usb-ipcc
usb-ipcc:
	$(MAKE) OUT="$(OUT)/usb-ipcc" SOURCE_OUT="$(OUT)/usb-preflight" \
	 BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-ipcc.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-ipcc" image

.PHONY: usb-clocks
usb-clocks:
	$(MAKE) OUT="$(OUT)/usb-clocks" SOURCE_OUT="$(OUT)/usb-preflight" \
	 BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-clocks.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-clocks" image

.PHONY: usb-gcc
usb-gcc:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-clocks/kernel" --output "$(OUT)/usb-gcc/kernel"
	$(MAKE) OUT="$(OUT)/usb-gcc" SOURCE_OUT="$(OUT)/usb-preflight" \
	 BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-gcc.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-gcc" image

.PHONY: usb-gcc-trace
usb-gcc-trace: usb-gcc
	mkdir -p "$(OUT)/usb-gcc-trace"
	cp "$(OUT)/usb-gcc/sm8250-xiaomi-munch.dtb" "$(OUT)/usb-gcc-trace/sm8250-xiaomi-munch.dtb"
	fdtput -t s "$(OUT)/usb-gcc-trace/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8'
	python3 tools/pack.py --loader "$(OUT)/usb-gcc/loader.bin" \
	 --image "$(OUT)/usb-gcc/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-gcc-trace/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-gcc/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-gcc-trace/payload.bin" --boot-image "$(OUT)/usb-gcc-trace/munch-boot.img"

.PHONY: usb-cacheinfo-trace
usb-cacheinfo-trace:
	$(MAKE) OUT="$(OUT)/usb-preflight" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch" sources
	$(MAKE) OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-gcc.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-gcc" kernel loader dtb initramfs
	fdtput -t s "$(OUT)/usb-cacheinfo-trace/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8'
	python3 tools/pack.py --loader "$(OUT)/usb-cacheinfo-trace/loader.bin" \
	 --image "$(OUT)/usb-cacheinfo-trace/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-cacheinfo-trace/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-cacheinfo-trace/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-cacheinfo-trace/payload.bin" --boot-image "$(OUT)/usb-cacheinfo-trace/munch-boot.img"

.PHONY: usb-clock-cleanup-test
usb-clock-cleanup-test: usb-cacheinfo-trace
	mkdir -p "$(OUT)/usb-clock-cleanup-test"
	cp "$(OUT)/usb-cacheinfo-trace/sm8250-xiaomi-munch.dtb" "$(OUT)/usb-clock-cleanup-test/sm8250-xiaomi-munch.dtb"
	# TEMPORARY WORKAROUND: A/B test of unused-clock cleanup only.
	fdtput -t s "$(OUT)/usb-clock-cleanup-test/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-cacheinfo-trace/loader.bin" \
	 --image "$(OUT)/usb-cacheinfo-trace/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-clock-cleanup-test/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-cacheinfo-trace/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-clock-cleanup-test/payload.bin" --boot-image "$(OUT)/usb-clock-cleanup-test/munch-boot.img"

.PHONY: usb-pdc
usb-pdc:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-cacheinfo-trace/kernel" --output "$(OUT)/usb-pdc/kernel"
	$(MAKE) OUT="$(OUT)/usb-pdc" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-pdc.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-pdc" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-pdc/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-pdc/loader.bin" \
	 --image "$(OUT)/usb-pdc/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-pdc/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-pdc/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-pdc/payload.bin" --boot-image "$(OUT)/usb-pdc/munch-boot.img"

.PHONY: usb-icc
usb-icc:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-pdc/kernel" --output "$(OUT)/usb-icc/kernel"
	$(MAKE) OUT="$(OUT)/usb-icc" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-icc.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-icc" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-icc/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-icc/loader.bin" \
	 --image "$(OUT)/usb-icc/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-icc/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-icc/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-icc/payload.bin" --boot-image "$(OUT)/usb-icc/munch-boot.img"

.PHONY: usb-smmu
usb-smmu:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-icc/kernel" --output "$(OUT)/usb-smmu/kernel"
	$(MAKE) OUT="$(OUT)/usb-smmu" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-smmu.fragment" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-smmu" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-smmu/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-smmu/loader.bin" \
	 --image "$(OUT)/usb-smmu/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-smmu/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-smmu/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-smmu/payload.bin" --boot-image "$(OUT)/usb-smmu/munch-boot.img"

.PHONY: usb-rails
usb-rails:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-smmu/kernel" --output "$(OUT)/usb-rails/kernel"
	$(MAKE) OUT="$(OUT)/usb-rails" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-rails.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-rails" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-rails/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-rails/loader.bin" \
	 --image "$(OUT)/usb-rails/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-rails/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-rails/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-rails/payload.bin" --boot-image "$(OUT)/usb-rails/munch-boot.img"

.PHONY: usb-phy
usb-phy:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-rails/kernel" --output "$(OUT)/usb-phy/kernel"
	$(MAKE) OUT="$(OUT)/usb-phy" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-phy.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-phy.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-phy" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-phy/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-phy/loader.bin" \
	 --image "$(OUT)/usb-phy/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-phy/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-phy/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-phy/payload.bin" --boot-image "$(OUT)/usb-phy/munch-boot.img"

.PHONY: usb-udc
usb-udc:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-phy/kernel" --output "$(OUT)/usb-udc/kernel"
	$(MAKE) OUT="$(OUT)/usb-udc" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-preflight/busybox" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-udc.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-udc.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-phy.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-udc" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-udc/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-udc/loader.bin" \
	 --image "$(OUT)/usb-udc/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-udc/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-udc/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-udc/payload.bin" --boot-image "$(OUT)/usb-udc/munch-boot.img"

.PHONY: usb-acm
usb-acm:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-udc/kernel" --output "$(OUT)/usb-acm/kernel"
	$(MAKE) OUT="$(OUT)/usb-acm" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-acm/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-acm.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-acm.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-udc.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-phy.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-acm" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-acm/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-acm/loader.bin" \
	 --image "$(OUT)/usb-acm/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-acm/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-acm/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-acm/payload.bin" --boot-image "$(OUT)/usb-acm/munch-boot.img"

# Initramfs-only follow-up: reuse existing K artifacts without rebuilding them.
.PHONY: usb-acm-termios
usb-acm-termios:
	mkdir -p "$(OUT)/usb-acm-termios"
	python3 tools/mkinitramfs.py --busybox "$(OUT)/usb-acm/busybox/busybox" \
	 --init "$(ROOT)/initramfs/init-usb-acm" --output "$(OUT)/usb-acm-termios/initramfs.cpio.gz"
	python3 tools/pack.py --loader "$(OUT)/usb-acm/loader.bin" \
	 --image "$(OUT)/usb-acm/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-acm/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-acm-termios/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-acm-termios/payload.bin" --boot-image "$(OUT)/usb-acm-termios/munch-boot.img"

.PHONY: usb-host-ready
usb-host-ready:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-acm/kernel" --output "$(OUT)/usb-host-ready/kernel"
	$(MAKE) OUT="$(OUT)/usb-host-ready" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-acm/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-acm.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-host-ready.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-udc.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-phy.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-acm" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-host-ready/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-host-ready/loader.bin" \
	 --image "$(OUT)/usb-host-ready/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-host-ready/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-host-ready/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-host-ready/payload.bin" --boot-image "$(OUT)/usb-host-ready/munch-boot.img"

.PHONY: usb-otg-keyboard
usb-otg-keyboard:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-host-ready/kernel" --output "$(OUT)/usb-otg-keyboard/kernel"
	$(MAKE) OUT="$(OUT)/usb-otg-keyboard" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/usb-acm/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-acm.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-usb-otg-keyboard.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-otg-keyboard.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-udc.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-phy.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-usb-otg-keyboard" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/usb-otg-keyboard/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/usb-otg-keyboard/loader.bin" \
	 --image "$(OUT)/usb-otg-keyboard/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-otg-keyboard/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-otg-keyboard/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-otg-keyboard/payload.bin" --boot-image "$(OUT)/usb-otg-keyboard/munch-boot.img"

# Cosmetic loader follow-up: reuse the hardware-confirmed M kernel/DT/initramfs.
.PHONY: usb-otg-keyboard-ui
usb-otg-keyboard-ui:
	$(MAKE) OUT="$(OUT)/usb-otg-keyboard-ui" loader
	python3 tools/pack.py --loader "$(OUT)/usb-otg-keyboard-ui/loader.bin" \
	 --image "$(OUT)/usb-otg-keyboard/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/usb-otg-keyboard/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/usb-otg-keyboard/initramfs.cpio.gz" \
	 --output "$(OUT)/usb-otg-keyboard-ui/payload.bin" \
	 --boot-image "$(OUT)/usb-otg-keyboard-ui/munch-boot.img"

.PHONY: pmos-preflight
pmos-preflight:
	python3 tools/seed-kernel-build.py --source "$(OUT)/usb-otg-keyboard/kernel" --output "$(OUT)/pmos-preflight/kernel"
	$(MAKE) OUT="$(OUT)/pmos-preflight" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/pmos-usb/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-pmos-usb.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-pmos-preflight.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-otg-keyboard.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-usb-udc.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-rails.dts $(ROOT)/dts/sm8250-xiaomi-munch-usb-phy.dts" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-pmos-preflight" kernel loader dtb initramfs
	# TEMPORARY WORKAROUND: retain the confirmed clock-cleanup A/B baseline.
	fdtput -t s "$(OUT)/pmos-preflight/sm8250-xiaomi-munch.dtb" /chosen bootargs \
	 'console=tty0 rdinit=/init initcall_debug loglevel=8 clk_ignore_unused'
	python3 tools/pack.py --loader "$(OUT)/pmos-preflight/loader.bin" \
	 --image "$(OUT)/pmos-preflight/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/pmos-preflight/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/pmos-preflight/initramfs.cpio.gz" \
	 --output "$(OUT)/pmos-preflight/payload.bin" --boot-image "$(OUT)/pmos-preflight/munch-boot.img"


# Rootfs-only follow-up; reuse the hardware-confirmed P kernel and board DT.
.PHONY: pmos-ram
pmos-ram:
	$(MAKE) OUT="$(OUT)/pmos-ram" loader
	python3 tools/mkinitramfs.py --busybox "$(OUT)/pmos-usb/busybox/busybox" \
	 --init "$(ROOT)/initramfs/init-pmos-ram" \
	 --rootfs "$(OUT)/pmos-rootfs/postmarketos-aarch64-console.tar.gz" \
	 --output "$(OUT)/pmos-ram/initramfs.cpio.gz"
	python3 tools/pack.py --loader "$(OUT)/pmos-ram/loader.bin" \
	 --image "$(OUT)/pmos-preflight/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/pmos-preflight/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/pmos-ram/initramfs.cpio.gz" \
	 --output "$(OUT)/pmos-ram/payload.bin" \
	 --boot-image "$(OUT)/pmos-ram/munch-boot.img"

# Small USB-to-RAM follow-up; no rootfs in this boot image.
.PHONY: pmos-usb
pmos-usb:
	$(MAKE) OUT="$(OUT)/pmos-usb" loader
	$(MAKE) OUT="$(OUT)/pmos-usb" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/pmos-usb/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-pmos-usb.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" busybox
	python3 tools/mkinitramfs.py --busybox "$(OUT)/pmos-usb/busybox/busybox" \
	 --init "$(ROOT)/initramfs/init-pmos-usb" \
	 --output "$(OUT)/pmos-usb/initramfs.cpio.gz"
	python3 tools/pack.py --loader "$(OUT)/pmos-usb/loader.bin" \
	 --image "$(OUT)/pmos-preflight/kernel/arch/arm64/boot/Image" \
	 --dtb "$(OUT)/pmos-preflight/sm8250-xiaomi-munch.dtb" \
	 --initramfs "$(OUT)/pmos-usb/initramfs.cpio.gz" \
	 --output "$(OUT)/pmos-usb/payload.bin" \
	 --boot-image "$(OUT)/pmos-usb/munch-boot.img"

# Experimental native Wi-Fi; separate output preserves confirmed USB baseline.
.PHONY: pmos-wifi
pmos-wifi:
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-preflight/kernel" --output "$(OUT)/pmos-wifi/kernel"
	$(MAKE) OUT="$(OUT)/pmos-wifi" SOURCE_OUT="$(OUT)/usb-cacheinfo-trace" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/pmos-usb/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-pmos-usb.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-pmos-wifi.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-wifi.dts" \
	 BOARD_DTS_DEPS="$(wildcard $(ROOT)/dts/sm8250-xiaomi-munch-usb-*.dts)" \
	 INIT_SCRIPT="$(ROOT)/initramfs/init-pmos-wifi" image

.PHONY: pmos-gpu
pmos-gpu:
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-wifi/kernel" --output "$(OUT)/pmos-gpu/kernel"
	$(MAKE) OUT="$(OUT)/pmos-gpu" SOURCE_OUT="$(OUT)/pmos-gpu" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/pmos-usb/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-pmos-usb.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch $(ROOT)/patches/0003-drm-aux-hpd-bridge-select-KMS-helper.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-pmos-gpu.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-gpu.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-wifi.dts $(wildcard $(ROOT)/dts/sm8250-xiaomi-munch-usb-*.dts)" \
	 GPU_ZAP="$(OUT)/munch-zap-staged" INIT_SCRIPT="$(ROOT)/initramfs/init-pmos-gpu" image

.PHONY: pmos-display
pmos-display:
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-gpu/kernel" --output "$(OUT)/pmos-display/kernel"
	$(MAKE) OUT="$(OUT)/pmos-display" SOURCE_OUT="$(OUT)/pmos-display" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/pmos-usb/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-pmos-usb.fragment" \
 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch $(ROOT)/patches/0003-drm-aux-hpd-bridge-select-KMS-helper.patch $(ROOT)/patches/0004-drm-panel-xiaomi-munch-l11r.patch $(ROOT)/patches/0005-drm-panel-munch-use-refcounted-allocation.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-pmos-display.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-display.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-gpu.dts $(ROOT)/dts/sm8250-xiaomi-munch-wifi.dts $(wildcard $(ROOT)/dts/sm8250-xiaomi-munch-usb-*.dts)" \
	 PHONE_TOOLS="$(ROOT)/phone" GPU_ZAP="$(OUT)/munch-zap-staged" INIT_SCRIPT="$(ROOT)/initramfs/init-pmos-display" image

.PHONY: pmos-touch
pmos-touch:
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-display/kernel" --output "$(OUT)/pmos-touch/kernel"
	$(MAKE) OUT="$(OUT)/pmos-touch" SOURCE_OUT="$(OUT)/pmos-touch" \
	 BSRC="$(OUT)/usb-preflight/busybox-1.37.0" BOUT="$(OUT)/pmos-usb/busybox" \
	 BUSYBOX_FRAGMENT="$(ROOT)/configs/busybox-pmos-usb.fragment" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch $(ROOT)/patches/0003-drm-aux-hpd-bridge-select-KMS-helper.patch $(ROOT)/patches/0004-drm-panel-xiaomi-munch-l11r.patch $(ROOT)/patches/0005-drm-panel-munch-use-refcounted-allocation.patch $(ROOT)/patches/0006-input-munch-ft3658u.patch" \
	 EXTRA_KERNEL_FRAGMENT="$(ROOT)/configs/kernel-pmos-touch.fragment" \
	 BOARD_DTS="$(ROOT)/dts/sm8250-xiaomi-munch-touch.dts" \
	 BOARD_DTS_DEPS="$(ROOT)/dts/sm8250-xiaomi-munch-display.dts $(ROOT)/dts/sm8250-xiaomi-munch-gpu.dts $(ROOT)/dts/sm8250-xiaomi-munch-wifi.dts $(wildcard $(ROOT)/dts/sm8250-xiaomi-munch-usb-*.dts)" \
	 PHONE_TOOLS="$(ROOT)/phone" GPU_ZAP="$(OUT)/munch-zap-staged" INIT_SCRIPT="$(ROOT)/initramfs/init-pmos-display" image

# Isolated Wi-Fi diagnostics; retain the touch kernel source, DT and chroot init.
.PHONY: pmos-wifi-debug
pmos-wifi-debug:
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-touch/kernel" --output "$(OUT)/pmos-wifi-debug/kernel"
	cat configs/kernel-pmos-touch.fragment configs/kernel-wifi-debug.fragment > "$(OUT)/pmos-wifi-debug/kernel.fragment"
	python3 tools/configure.py --source "$(OUT)/pmos-touch/linux-src" --out "$(OUT)/pmos-wifi-debug/kernel" --fragment configs/kernel.fragment --extra-fragment "$(OUT)/pmos-wifi-debug/kernel.fragment"
	$(MAKE) -C "$(OUT)/pmos-touch/linux-src" O="$(OUT)/pmos-wifi-debug/kernel" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS) Image
	$(MAKE) OUT="$(OUT)/pmos-wifi-debug" loader
	cp "$(OUT)/pmos-touch/sm8250-xiaomi-munch.dtb" "$(OUT)/pmos-wifi-debug/sm8250-xiaomi-munch.dtb"
	python3 tools/mkinitramfs.py --busybox "$(OUT)/pmos-usb/busybox/busybox" --init initramfs/init-pmos-display --gpu-zap "$(OUT)/munch-zap-staged" --phone-tools phone --output "$(OUT)/pmos-wifi-debug/initramfs.cpio.gz"
	python3 tools/pack.py --loader "$(OUT)/pmos-wifi-debug/loader.bin" --image "$(OUT)/pmos-wifi-debug/kernel/arch/arm64/boot/Image" --dtb "$(OUT)/pmos-wifi-debug/sm8250-xiaomi-munch.dtb" --initramfs "$(OUT)/pmos-wifi-debug/initramfs.cpio.gz" --output "$(OUT)/pmos-wifi-debug/payload.bin" --boot-image "$(OUT)/pmos-wifi-debug/munch-boot.img"

# RX/EAPOL counters use an independent patched source export and build tree.
.PHONY: pmos-wifi-rx
pmos-wifi-rx:
	$(MAKE) OUT="$(OUT)/pmos-wifi-rx" SOURCE_OUT="$(OUT)/pmos-wifi-rx" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch $(ROOT)/patches/0003-drm-aux-hpd-bridge-select-KMS-helper.patch $(ROOT)/patches/0004-drm-panel-xiaomi-munch-l11r.patch $(ROOT)/patches/0005-drm-panel-munch-use-refcounted-allocation.patch $(ROOT)/patches/0006-input-munch-ft3658u.patch $(ROOT)/patches/0007-debug-count-ath11k-mac80211-rx.patch" sources
	cp diagnostics/wifi-rx/pmos_munch_rx_*.h "$(OUT)/pmos-wifi-rx/linux-src/include/net/"
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-wifi-debug/kernel" --output "$(OUT)/pmos-wifi-rx/kernel"
	cat configs/kernel-pmos-touch.fragment configs/kernel-wifi-debug.fragment > "$(OUT)/pmos-wifi-rx/kernel.fragment"
	python3 tools/configure.py --source "$(OUT)/pmos-wifi-rx/linux-src" --out "$(OUT)/pmos-wifi-rx/kernel" --fragment configs/kernel.fragment --extra-fragment "$(OUT)/pmos-wifi-rx/kernel.fragment"
	$(MAKE) -C "$(OUT)/pmos-wifi-rx/linux-src" O="$(OUT)/pmos-wifi-rx/kernel" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS) Image
	$(MAKE) OUT="$(OUT)/pmos-wifi-rx" loader
	cp "$(OUT)/pmos-touch/sm8250-xiaomi-munch.dtb" "$(OUT)/pmos-wifi-rx/sm8250-xiaomi-munch.dtb"
	python3 tools/mkinitramfs.py --busybox "$(OUT)/pmos-usb/busybox/busybox" --init initramfs/init-pmos-display --gpu-zap "$(OUT)/munch-zap-staged" --phone-tools phone --output "$(OUT)/pmos-wifi-rx/initramfs.cpio.gz"
	python3 tools/pack.py --loader "$(OUT)/pmos-wifi-rx/loader.bin" --image "$(OUT)/pmos-wifi-rx/kernel/arch/arm64/boot/Image" --dtb "$(OUT)/pmos-wifi-rx/sm8250-xiaomi-munch.dtb" --initramfs "$(OUT)/pmos-wifi-rx/initramfs.cpio.gz" --output "$(OUT)/pmos-wifi-rx/payload.bin" --boot-image "$(OUT)/pmos-wifi-rx/munch-boot.img"

# Native test reuses the tested kernel/DT without rebuilding or replacing the
# working chroot image. Build pmos-touch first when starting from a clean tree.
.PHONY: pmos-native
pmos-native:
	test -s "$(NATIVE_KERNEL_IMAGE)"
	test -s "$(NATIVE_DTB)"
	mkdir -p "$(NATIVE_OUTPUT)"
	cat configs/busybox-pmos-usb.fragment > "$(NATIVE_OUTPUT)/busybox.fragment"
	printf '\nCONFIG_SWITCH_ROOT=y\nCONFIG_CP=y\nCONFIG_FEATURE_PRESERVE_HARDLINKS=y\nCONFIG_READLINK=y\nCONFIG_FEATURE_READLINK_FOLLOW=y\n' >> "$(NATIVE_OUTPUT)/busybox.fragment"
	python3 tools/configure.py --busybox --source "$(OUT)/usb-preflight/busybox-1.37.0" --out "$(NATIVE_OUTPUT)/busybox" --fragment "$(NATIVE_OUTPUT)/busybox.fragment"
	$(MAKE) -C "$(OUT)/usb-preflight/busybox-1.37.0" O="$(NATIVE_OUTPUT)/busybox" CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS)
	$(MAKE) OUT="$(NATIVE_OUTPUT)" loader
	python3 tools/build-native-init.py --output "$(NATIVE_OUTPUT)/init"
	if [ "$(NATIVE_DTB)" != "$(NATIVE_OUTPUT)/sm8250-xiaomi-munch.dtb" ]; then cp "$(NATIVE_DTB)" "$(NATIVE_OUTPUT)/sm8250-xiaomi-munch.dtb"; fi
	python3 tools/mkinitramfs.py --busybox "$(NATIVE_OUTPUT)/busybox/busybox" --init "$(NATIVE_OUTPUT)/init" --gpu-zap "$(OUT)/munch-zap-staged" --phone-tools phone --native-tools native $(if $(NATIVE_MODULES),--kernel-modules "$(NATIVE_MODULES)") --output "$(NATIVE_OUTPUT)/initramfs.cpio.gz"
	python3 tools/pack.py --loader "$(NATIVE_OUTPUT)/loader.bin" --image "$(NATIVE_KERNEL_IMAGE)" --dtb "$(NATIVE_OUTPUT)/sm8250-xiaomi-munch.dtb" --initramfs "$(NATIVE_OUTPUT)/initramfs.cpio.gz" --output "$(NATIVE_OUTPUT)/payload.bin" --boot-image "$(NATIVE_OUTPUT)/munch-boot.img"

# Compare native services against the exact kernel used by the RX chroot test.
.PHONY: pmos-native-rx
pmos-native-rx:
	$(MAKE) NATIVE_OUTPUT="$(OUT)/pmos-native-rx" NATIVE_KERNEL_IMAGE="$(OUT)/pmos-wifi-rx/kernel/arch/arm64/boot/Image" pmos-native

# F3-style Wi-Fi modules are installed only after the RAM rootfs is available.
.PHONY: pmos-native-modular
pmos-native-modular:
	test -s "$(OUT)/pmos-wifi-rx/linux-src/include/net/pmos_munch_rx_probe.h"
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-wifi-rx/kernel" --output "$(OUT)/pmos-native-modular/kernel"
	sed -E '/^CONFIG_(CFG80211|MAC80211|ATH11K|ATH11K_PCI|PCI_PWRCTRL_PWRSEQ)=/d' configs/kernel-pmos-touch.fragment > "$(OUT)/pmos-native-modular/kernel.fragment"
	cat configs/kernel-wifi-debug.fragment configs/kernel-wifi-modular.fragment >> "$(OUT)/pmos-native-modular/kernel.fragment"
	python3 tools/configure.py --source "$(OUT)/pmos-wifi-rx/linux-src" --out "$(OUT)/pmos-native-modular/kernel" --fragment configs/kernel.fragment --extra-fragment "$(OUT)/pmos-native-modular/kernel.fragment"
	$(MAKE) -C "$(OUT)/pmos-wifi-rx/linux-src" O="$(OUT)/pmos-native-modular/kernel" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS) Image modules
	$(MAKE) -C "$(OUT)/pmos-wifi-rx/linux-src" O="$(OUT)/pmos-native-modular/kernel" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) INSTALL_MOD_PATH="$(OUT)/pmos-native-modular/modules-root" INSTALL_MOD_STRIP=1 DEPMOD=true modules_install
	depmod -b "$(OUT)/pmos-native-modular/modules-root" "$$(cat "$(OUT)/pmos-native-modular/kernel/include/config/kernel.release")"
	$(MAKE) NATIVE_OUTPUT="$(OUT)/pmos-native-modular" NATIVE_KERNEL_IMAGE="$(OUT)/pmos-native-modular/kernel/arch/arm64/boot/Image" NATIVE_MODULES="$(OUT)/pmos-native-modular/modules-root/lib/modules/$$(cat "$(OUT)/pmos-native-modular/kernel/include/config/kernel.release")" pmos-native

# Fixed stock 120 Hz plus battery telemetry, preserving modular Wi-Fi.
.PHONY: pmos-native-120-battery
pmos-native-120-battery:
	$(MAKE) OUT="$(OUT)/pmos-native-120-battery" SOURCE_OUT="$(OUT)/pmos-native-120-battery" \
	 KERNEL_PATCHES="$(ROOT)/patches/0001-pmdomain-qcom-rpmhpd-select-PM_OPP.patch $(ROOT)/patches/0002-debug-trace-cacheinfo-cpu-hotplug.patch $(ROOT)/patches/0003-drm-aux-hpd-bridge-select-KMS-helper.patch $(ROOT)/patches/0004-drm-panel-xiaomi-munch-l11r.patch $(ROOT)/patches/0005-drm-panel-munch-use-refcounted-allocation.patch $(ROOT)/patches/0006-input-munch-ft3658u.patch $(ROOT)/patches/0007-debug-count-ath11k-mac80211-rx.patch $(ROOT)/patches/0008-drm-panel-munch-stock-120hz.patch" sources
	cp diagnostics/wifi-rx/pmos_munch_rx_*.h "$(OUT)/pmos-native-120-battery/linux-src/include/net/"
	python3 tools/seed-kernel-build.py --source "$(OUT)/pmos-native-modular/kernel" --output "$(OUT)/pmos-native-120-battery/kernel"
	sed -E '/^CONFIG_(CFG80211|MAC80211|ATH11K|ATH11K_PCI|PCI_PWRCTRL_PWRSEQ)=/d' configs/kernel-pmos-touch.fragment > "$(OUT)/pmos-native-120-battery/kernel.fragment"
	cat configs/kernel-wifi-debug.fragment >> "$(OUT)/pmos-native-120-battery/kernel.fragment"
	sed 's/-pmos-munch-modular/-pmos-munch-120-battery/' configs/kernel-wifi-modular.fragment >> "$(OUT)/pmos-native-120-battery/kernel.fragment"
	cat configs/kernel-120-battery.fragment >> "$(OUT)/pmos-native-120-battery/kernel.fragment"
	python3 tools/configure.py --source "$(OUT)/pmos-native-120-battery/linux-src" --out "$(OUT)/pmos-native-120-battery/kernel" --fragment configs/kernel.fragment --extra-fragment "$(OUT)/pmos-native-120-battery/kernel.fragment"
	$(MAKE) -C "$(OUT)/pmos-native-120-battery/linux-src" O="$(OUT)/pmos-native-120-battery/kernel" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) -j$(JOBS) Image modules
	$(MAKE) -C "$(OUT)/pmos-native-120-battery/linux-src" O="$(OUT)/pmos-native-120-battery/kernel" ARCH=arm64 CROSS_COMPILE=$(CROSS_COMPILE) INSTALL_MOD_PATH="$(OUT)/pmos-native-120-battery/modules-root" INSTALL_MOD_STRIP=1 DEPMOD=true modules_install
	depmod -b "$(OUT)/pmos-native-120-battery/modules-root" "$$(cat "$(OUT)/pmos-native-120-battery/kernel/include/config/kernel.release")"
	$(CC) -E -P -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I"$(OUT)/pmos-native-120-battery/linux-src/include" -I"$(OUT)/pmos-native-120-battery/linux-src/arch/arm64/boot/dts/qcom" dts/sm8250-xiaomi-munch-120-battery.dts -o "$(OUT)/pmos-native-120-battery/munch.preprocessed.dts"
	dtc -I dts -O dtb -o "$(OUT)/pmos-native-120-battery/board.dtb" "$(OUT)/pmos-native-120-battery/munch.preprocessed.dts"
	$(MAKE) NATIVE_OUTPUT="$(OUT)/pmos-native-120-battery" NATIVE_DTB="$(OUT)/pmos-native-120-battery/board.dtb" NATIVE_KERNEL_IMAGE="$(OUT)/pmos-native-120-battery/kernel/arch/arm64/boot/Image" NATIVE_MODULES="$(OUT)/pmos-native-120-battery/modules-root/lib/modules/$$(cat "$(OUT)/pmos-native-120-battery/kernel/include/config/kernel.release")" pmos-native
