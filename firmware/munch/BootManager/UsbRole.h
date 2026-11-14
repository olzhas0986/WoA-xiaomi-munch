// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef MUNCH_USB_ROLE_H
#define MUNCH_USB_ROLE_H

#include <Uefi.h>
#include <Protocol/LoadedImage.h>

// Prefix of this XBL's revision 0x10005. Do not use the unverified tail.
typedef struct MUNCH_USB_CONFIG MUNCH_USB_CONFIG;
typedef EFI_STATUS (EFIAPI *MUNCH_USB_MODE_FN)(MUNCH_USB_CONFIG *, UINT32, UINT32);
struct MUNCH_USB_CONFIG {
  UINT32 Revision, Padding;
  VOID *Early[9];
  MUNCH_USB_MODE_FN Start, Stop;
  VOID *Tail[5];
  UINT32 Core, Mode;
};
STATIC_ASSERT (OFFSET_OF (MUNCH_USB_CONFIG, Start) == 0x50, "USB ABI Start");
STATIC_ASSERT (OFFSET_OF (MUNCH_USB_CONFIG, Mode) == 0x8c, "USB ABI Mode");

typedef struct {
  MUNCH_USB_CONFIG *Port;
  EFI_HANDLE *HostHandle;
  volatile UINT8 *Enabled, *LatchPending;
  volatile UINT32 *StaticMode, *CoreMode;
  UINT32 SavedStaticMode, SavedCoreMode;
  BOOLEAN Active;
  EFI_EVENT *ExitSlot;
  EFI_EVENT_NOTIFY ExitNotify;
} MUNCH_USB_ROLE;

EFI_STATUS MunchUsbRoleOpen (EFI_LOADED_IMAGE_PROTOCOL *Image,
                            MUNCH_USB_CONFIG *Root, MUNCH_USB_ROLE *Role);
EFI_STATUS MunchUsbRoleHost (MUNCH_USB_ROLE *Role);
VOID MunchUsbRoleRestore (MUNCH_USB_ROLE *Role);
EFI_STATUS MunchUsbHandoffArm (MUNCH_USB_ROLE *Role);
EFI_STATUS MunchUsbHandoffRestore (MUNCH_USB_ROLE *Role);
#endif
