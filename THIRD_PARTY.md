# Third-party code and provenance

This repository combines original project code with files derived from Project
Mu, EDK II, Linux and device bring-up projects. File-level SPDX identifiers and
copyright notices are authoritative and override the root BSD-2-Clause license.

## UEFI base

The UEFI platform and boot-manager sources derive from Project Silicium /
Mu-Silicium, Microsoft Project Mu and TianoCore EDK II. Their retained notices
primarily use `BSD-2-Clause-Patent`; a few imported compatibility and font files
contain their complete upstream license notices.

## Linux reference tree

`ref/linux/` is supporting hardware bring-up material, not an input to the
normal UEFI build. Its Linux drivers and patches use `GPL-2.0-only`, while its
device-tree sources use their marked BSD or dual licenses. Moving this material
under `ref/` does not change those licenses.

## USB probe descriptors

`firmware/munch/BootManager/UsbDescriptors.h` is marked `APSL-2.0` and records
that its descriptor sequence was adapted from an UMI loader at commit
`6b6fb2b0c5a1720496ec71e88c95d2a45a0046a4`. The original repository URL was
not preserved in the available development record and could not be verified
from the commit alone. Keep the APSL marker and this disclosure. Do not present
that file as original BSD-licensed work or redistribute it independently until
the original source location and notices have been recovered.

## XBL metadata templates

`vendor-templates/` contains text-only EDK II INF metadata used to locate
modules inside an XBL supplied by the user. It contains no extracted PE/COFF
module. The names, GUIDs and dependency expressions describe the supported XBL
layout and do not grant permission to redistribute the corresponding Qualcomm
or Xiaomi binaries.

## Generated images

The build imports an XBL and live DTB supplied by the user, verifies an exact
supported revision and produces an image locally. Generated images can embed
proprietary modules from that XBL. They are deliberately ignored by Git and are
not project release artifacts. Anyone redistributing one is responsible for
obtaining permission for every embedded component.
