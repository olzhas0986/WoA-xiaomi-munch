// SPDX-License-Identifier: BSD-2-Clause-Patent
// Temporary data-only compatibility adapter for the supplied munch XBL.
// See firmware/munch/usb-role-analysis.md for offsets and binary evidence.
#include "UsbRole.h"
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>

// The core interface is allocated by UsbConfigDxe. Reject pointers outside
// BootServicesData before reading/writing its ModeType member.
STATIC BOOLEAN IsBootData (UINTN Address, UINTN Length) {
  EFI_MEMORY_DESCRIPTOR *Map, *Entry;
  UINTN Size = 0, Key, Stride, Offset;
  UINT32 Version;
  EFI_STATUS Status;
  BOOLEAN Found = FALSE;
  Status = gBS->GetMemoryMap (&Size, NULL, &Key, &Stride, &Version);
  if (Status != EFI_BUFFER_TOO_SMALL || Stride < sizeof (*Map)) { return FALSE; }
  Size += 16 * Stride;
  Map = AllocatePool (Size);
  if (Map == NULL) { return FALSE; }
  Status = gBS->GetMemoryMap (&Size, Map, &Key, &Stride, &Version);
  if (!EFI_ERROR (Status)) {
    for (Offset = 0; Offset + Stride <= Size; Offset += Stride) {
      Entry = (VOID *)((UINT8 *)Map + Offset);
      if (Entry->Type == EfiBootServicesData && Address >= Entry->PhysicalStart &&
          Address - Entry->PhysicalStart < EFI_PAGES_TO_SIZE (Entry->NumberOfPages) &&
          Length <= EFI_PAGES_TO_SIZE (Entry->NumberOfPages) - (Address - Entry->PhysicalStart)) {
        Found = TRUE;
        break;
      }
    }
  }
  FreePool (Map);
  return Found;
}

EFI_STATUS MunchUsbRoleOpen (EFI_LOADED_IMAGE_PROTOCOL *Image,
                            MUNCH_USB_CONFIG *Root, MUNCH_USB_ROLE *Role) {
  UINT8 *Base;
  UINTN CoreInterface, Index;
  UINT32 Crc, Signature;
  EFI_STATUS Status;
  // These instruction ranges contain no PE base relocations. Their CRCs must
  // also match after the image has been relocated by DXE.
  STATIC CONST struct { UINT32 Offset, Size, Crc; } Ranges[] = {
    { 0x3c1c, 0x354, 0x01e54217 }, // initialization: copy/install root and per-core protocols
    { 0x4a3c, 0x85c, 0xd3dcf5cc }, // Start, including static-role override
    { 0x5788, 0x634, 0xfc90b16d }, // Stop, including static-role override
    { 0x765c, 0x88c, 0x143cf98c }, // Type-C callback, including first-role latch
  };
  ZeroMem (Role, sizeof (*Role));
  if (Image != NULL) { Print (L"USB Config image base=%p size=%lx\n", Image->ImageBase, Image->ImageSize); }
  if (Image == NULL || Image->ImageBase == NULL || Image->ImageSize != 0x17000) {
    return EFI_UNSUPPORTED;
  }
  Base = Image->ImageBase;
  // Init copies the template at 0x15188 into the sentinel core2 slot and
  // installs that copy (0x15360 + 2 * 0xe8 + 0x28), not the template itself.
  if ((UINT8 *)Root != Base + 0x15558 || Root->Revision != 0x10005 ||
      Root->Core != 2 || Root->Mode != 0x10000 ||
      (UINTN)Root->Start != (UINTN)Base + 0x14ec ||
      (UINTN)Root->Stop != (UINTN)Base + 0x1534) {
    Print (L"USB role: unexpected root interface %p\n", Root);
    return EFI_UNSUPPORTED;
  }
  for (Index = 0; Index < ARRAY_SIZE (Ranges); Index++) {
    Status = gBS->CalculateCrc32 (Base + Ranges[Index].Offset, Ranges[Index].Size, &Crc);
    if (EFI_ERROR (Status) || Crc != Ranges[Index].Crc) {
      Print (L"USB role: code check failed at RVA %x (%r)\n", Ranges[Index].Offset, Status);
      return EFI_COMPROMISED_DATA;
    }
  }
  CopyMem (&Signature, Base + 0x15360, sizeof (Signature));
  if (Signature != SIGNATURE_32 ('u', 's', 'b', 'c')) {
    Print (L"USB role: unexpected state signature %x\n", Signature);
    return EFI_COMPROMISED_DATA;
  }
  Role->Port = (VOID *)(Base + 0x15388);
  if (Role->Port->Revision != Root->Revision || Role->Port->Core != 0 ||
      Role->Port->Start != Root->Start || Role->Port->Stop != Root->Stop) {
    Print (L"USB role: unexpected port revision=%x core=%u\n", Role->Port->Revision, Role->Port->Core);
    return EFI_COMPROMISED_DATA;
  }
  CopyMem (&CoreInterface, Base + 0x15378, sizeof (CoreInterface));
  if ((CoreInterface & 7) != 0 || !IsBootData (CoreInterface, sizeof (UINT32))) {
    Print (L"USB role: core interface %p is not valid pool data\n", (VOID *)CoreInterface);
    return EFI_COMPROMISED_DATA;
  }
  Role->HostHandle = (VOID *)(Base + 0x15368);
  Role->Enabled = Base + 0x15440;
  Role->StaticMode = (VOID *)(Base + 0x15444);
  Role->LatchPending = Base + 0x15bdd;
  Role->CoreMode = (VOID *)CoreInterface;
  Print (L"USB policy: static=%u mode=%x core-mode=%x latch=%u\n",
    *Role->Enabled, *Role->StaticMode, *Role->CoreMode, *Role->LatchPending);
  return EFI_SUCCESS;
}

EFI_STATUS MunchUsbRoleHost (MUNCH_USB_ROLE *Role) {
  EFI_TPL OldTpl;
  EFI_STATUS Status = EFI_SUCCESS;
  if (Role->Port == NULL || Role->CoreMode == NULL || Role->Active) { return EFI_NOT_READY; }
  // The Type-C timer runs at TPL_CALLBACK. Change both policy fields as one
  // operation, but do not call controller APIs while TPL is raised.
  OldTpl = gBS->RaiseTPL (TPL_NOTIFY);
  if (Role->Port->Mode != 0x10000 || *Role->Enabled != 1 ||
      *Role->StaticMode != 4 || *Role->CoreMode != 0x10 || *Role->LatchPending != 0) {
    Status = EFI_UNSUPPORTED;
  } else {
    Role->SavedStaticMode = *Role->StaticMode;
    Role->SavedCoreMode = *Role->CoreMode;
    *Role->StaticMode = 1; // USB_HOST_MODE_XHCI
    *Role->CoreMode = 8;   // USB_HOST_MODE
    Role->Active = TRUE;
  }
  gBS->RestoreTPL (OldTpl);
  Print (L"USB RAM host policy: %r\n", Status);
  if (EFI_ERROR (Status)) {
    Print (L"USB role rejected: actual=%x static=%u/%x core-mode=%x latch=%u\n",
      Role->Port->Mode, *Role->Enabled, *Role->StaticMode, *Role->CoreMode, *Role->LatchPending);
  }
  return Status;
}

VOID MunchUsbRoleRestore (MUNCH_USB_ROLE *Role) {
  EFI_TPL OldTpl;
  if (!Role->Active) { return; }
  OldTpl = gBS->RaiseTPL (TPL_NOTIFY);
  *Role->StaticMode = Role->SavedStaticMode;
  *Role->CoreMode = Role->SavedCoreMode;
  Role->Active = FALSE;
  gBS->RestoreTPL (OldTpl);
  Print (L"USB RAM policy restored: mode=%x core-mode=%x\n",
    *Role->StaticMode, *Role->CoreMode);
}

// Android XBL has HostModeSupported=0. Its ExitBootServices callback then
// forces both PHYs into non-driving mode regardless of our host policy.
// Suppress that one verified vendor event for the Windows host handoff.
// The source xHCI driver's normal halt/ownership callback is left intact.
STATIC EFI_GUID UsbExitGuid={0x27abf055,0xb1b8,0x4c26,{0x80,0x48,0x74,0x8f,0x37,0xba,0xa2,0xdf}};
EFI_STATUS MunchUsbHandoffArm (MUNCH_USB_ROLE *Role) {
 UINT8 *Base;
 UINT32 Crc;
 EFI_EVENT *Slot;
 EFI_STATUS Status;
 if(!Role->Active || Role->Port==NULL || Role->Port->Mode!=1 || Role->ExitSlot!=NULL) return EFI_NOT_READY;
 Base=(UINT8 *)Role->Enabled-0x15440;
 if(Base[0x10098]!=0 || CompareMem(Base+0x15028,&UsbExitGuid,sizeof(UsbExitGuid))) return EFI_UNSUPPORTED;
 if(EFI_ERROR(gBS->CalculateCrc32(Base+0x16ec,0x60,&Crc)) || Crc!=0xff5914dd ||
    EFI_ERROR(gBS->CalculateCrc32(Base+0x5400,0x388,&Crc)) || Crc!=0x39872245 ||
    EFI_ERROR(gBS->CalculateCrc32(Base+0x1798,0x150,&Crc)) || Crc!=0xbf9cfae7) return EFI_COMPROMISED_DATA;
 Slot=(VOID *)(Base+0x15850);
 if(*Slot==NULL) return EFI_NOT_READY;
 Status=gBS->CloseEvent(*Slot);
 Print(L"USB handoff: disable vendor PHY teardown event=%p: %r\n",*Slot,Status);
 if(EFI_ERROR(Status)) return Status;
 *Slot=NULL;
 Role->ExitSlot=Slot;
 Role->ExitNotify=(EFI_EVENT_NOTIFY)(UINTN)(Base+0x16ec);
 return EFI_SUCCESS;
}
EFI_STATUS MunchUsbHandoffRestore (MUNCH_USB_ROLE *Role) {
 EFI_STATUS Status;
 if(Role->ExitSlot==NULL) return EFI_SUCCESS;
 Status=gBS->CreateEventEx(EVT_NOTIFY_SIGNAL,TPL_NOTIFY,Role->ExitNotify,NULL,&UsbExitGuid,Role->ExitSlot);
 Print(L"USB handoff: restore vendor exit event: %r\n",Status);
 if(!EFI_ERROR(Status)) { Role->ExitSlot=NULL;Role->ExitNotify=NULL; }
 return Status;
}
