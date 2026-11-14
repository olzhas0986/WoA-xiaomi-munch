.PHONY: deps inputs stable pep verify clean

IMAGE := out/munch-fresh/munch-uefi.img

deps:
	bash tools/bootstrap-deps.sh

inputs:
	@test -n "$(XBL)" -a -n "$(DTB)" || (echo 'usage: make inputs XBL=/path/xbl.img DTB=/path/munch.dtb' >&2; exit 2)
	bash tools/import-inputs.sh "$(XBL)" "$(DTB)"

# Tested desktop profile: USB, UFS and the non-PEP Qualcomm foundation.
stable:
	MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 MUNCH_GPU_FOUNDATION=5 bash tools/build-munch.sh
	python3 tools/pack-munch.py --output $(IMAGE)

# Research profile. Installing/enabling qcpep can crash Windows; read docs/PEP.md.
pep:
	MUNCH_USB_ACPI=1 MUNCH_UFS_ACPI=1 MUNCH_GPU_FOUNDATION=6 bash tools/build-munch.sh
	python3 tools/pack-munch.py --output out/munch-fresh/munch-uefi-pep.img

verify:
	.venv/bin/python tools/verify-munch.py --image $(IMAGE) --winpe --usb-acpi --ufs-acpi --gpu-pmic --pep-prep --no-preboot-kbd
	.venv/bin/python tools/check-munch-shim.py

clean:
	rm -rf out/munch-fresh Mu-Silicium/Build/munchFreshPkg Mu-Silicium/Platforms/Xiaomi/munchFreshPkg
