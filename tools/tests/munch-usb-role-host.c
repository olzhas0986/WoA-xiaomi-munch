// SPDX-License-Identifier: BSD-2-Clause-Patent
// Host execution of the actual compatibility adapter with fake boot services.
#include "UsbRole.h"
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

static EFI_BOOT_SERVICES Services;
EFI_BOOT_SERVICES *gBS = &Services;
static UINT32 *Core;
static UINT32 MemoryType = EfiBootServicesData;
static UINTN Tpl;

VOID *EFIAPI AllocatePool (UINTN Size) { return malloc (Size); }
VOID EFIAPI FreePool (VOID *P) { free (P); }
VOID *EFIAPI CopyMem (VOID *D, CONST VOID *S, UINTN N) { return memcpy (D, S, N); }
INTN EFIAPI CompareMem (CONST VOID *A, CONST VOID *B, UINTN N) { return memcmp(A,B,N); }
VOID *EFIAPI ZeroMem (VOID *D, UINTN N) { return memset (D, 0, N); }
UINTN EFIAPI Print (CONST CHAR16 *Format, ...) { (void)Format; return 0; }
static EFI_TPL EFIAPI Raise (EFI_TPL New) { UINTN Old = Tpl; Tpl = New; return Old; }
static EFI_STATUS EventStatus;
static EFI_EVENT_NOTIFY ExpectedNotify;
static UINTN Closed;
static EFI_STATUS EFIAPI Close (EFI_EVENT Event) {
  assert(Event==(EFI_EVENT)(UINTN)1);Closed++;return EventStatus;
}
static EFI_STATUS EFIAPI Create (UINT32 Type, EFI_TPL Level, EFI_EVENT_NOTIFY Notify,
                                CONST VOID *Context, CONST EFI_GUID *Guid, EFI_EVENT *Event) {
  assert(Type==EVT_NOTIFY_SIGNAL && Level==TPL_NOTIFY && Notify==ExpectedNotify);
  assert(Context==NULL && Guid->Data1==0x27abf055);
  if(!EFI_ERROR(EventStatus)) *Event=(EFI_EVENT)(UINTN)2;
  return EventStatus;
}
static VOID EFIAPI Restore (EFI_TPL Old) { Tpl = Old; }
static EFI_STATUS EFIAPI Crc (VOID *P, UINTN N, UINT32 *Value) {
  *Value = (UINT32)crc32 (0, P, N); return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI Map (UINTN *Size, EFI_MEMORY_DESCRIPTOR *M,
  UINTN *Key, UINTN *Stride, UINT32 *Version) {
  *Stride = sizeof (*M); *Key = 1; *Version = 1;
  if (M == NULL || *Size < sizeof (*M)) { *Size = sizeof (*M); return EFI_BUFFER_TOO_SMALL; }
  *Size = sizeof (*M); memset (M, 0, *Size);
  M->PhysicalStart = (UINTN)Core & ~0xfffULL;
  M->NumberOfPages = 1; M->Type = MemoryType;
  return EFI_SUCCESS;
}
int main (int Argc, char **Argv) {
  EFI_LOADED_IMAGE_PROTOCOL Image = {0};
  MUNCH_USB_CONFIG *Root, *Port;
  MUNCH_USB_ROLE Role;
  UINT8 *Base, Before[0x17000];
  FILE *File;
  assert (Argc == 3);
  File = fopen (Argv[1], "rb"); assert (File != NULL);
  Base = malloc (sizeof (Before)); assert (Base != NULL);
  assert (fread (Base, 1, sizeof (Before), File) == sizeof (Before)); fclose (File);
  Core = aligned_alloc (4096, 4096); assert (Core != NULL); *Core = 0x10;
  Services.CalculateCrc32 = Crc; Services.GetMemoryMap = Map;
  Services.RaiseTPL = Raise; Services.RestoreTPL = Restore;
  Image.ImageBase = Base; Image.ImageSize = sizeof (Before);
  // The fixture and installed-root RVA come from executing vendor Init in
  // Unicorn, rather than duplicating the adapter's assumed memory layout.
  Root = (VOID *)(Base + strtoul (Argv[2], NULL, 0)); Port = (VOID *)(Base + 0x15388);
  assert (Root->Revision == 0x10005 && Root->Core == 2 && Root->Mode == 0x10000);
  assert (Port->Core == 0 && Port->Mode == 0x10000);
  Root->Start = (MUNCH_USB_MODE_FN)(Base + (UINTN)Root->Start);
  Root->Stop = (MUNCH_USB_MODE_FN)(Base + (UINTN)Root->Stop);
  Port->Start = (MUNCH_USB_MODE_FN)(Base + (UINTN)Port->Start);
  Port->Stop = (MUNCH_USB_MODE_FN)(Base + (UINTN)Port->Stop);
  memcpy (Base + 0x15378, &Core, sizeof (Core));
  assert (Base[0x15440] == 1 && *(UINT32 *)(Base + 0x15444) == 4 && Base[0x15bdd] == 0);
  memcpy (Before, Base, sizeof (Before));

  assert (MunchUsbRoleOpen (&Image, Root, &Role) == EFI_SUCCESS);
  assert (MunchUsbRoleHost (&Role) == EFI_SUCCESS && Role.Active);
  assert (*Role.StaticMode == 1 && *Core == 8 && Tpl == 0);
  assert (MunchUsbRoleHost (&Role) == EFI_NOT_READY);
  MunchUsbRoleRestore (&Role);
  MunchUsbRoleRestore (&Role); // restoration is idempotent
  assert (*Core == 0x10 && !Role.Active && Tpl == 0);
  assert (memcmp (Before, Base, sizeof (Before)) == 0);
  puts ("PASS actual adapter switches and restores only the intended RAM data");

  Services.CloseEvent=Close;Services.CreateEventEx=Create;
  assert(MunchUsbRoleOpen(&Image,Root,&Role)==EFI_SUCCESS);
  assert(MunchUsbRoleHost(&Role)==EFI_SUCCESS);Port->Mode=1;
  EFI_EVENT *ExitSlot=(VOID *)(Base+0x15850);*ExitSlot=(EFI_EVENT)(UINTN)1;
  ExpectedNotify=(EFI_EVENT_NOTIFY)(UINTN)(Base+0x16ec);
  Base[0x5400]^=1;
  assert(MunchUsbHandoffArm(&Role)==EFI_COMPROMISED_DATA && Closed==0);
  Base[0x5400]^=1;
  EventStatus=EFI_DEVICE_ERROR;
  assert(MunchUsbHandoffArm(&Role)==EFI_DEVICE_ERROR && Role.ExitSlot==NULL && *ExitSlot==(EFI_EVENT)(UINTN)1);
  EventStatus=EFI_SUCCESS;
  assert(MunchUsbHandoffArm(&Role)==EFI_SUCCESS && *ExitSlot==NULL && Role.ExitSlot==ExitSlot);
  assert(MunchUsbHandoffArm(&Role)==EFI_NOT_READY);
  EventStatus=EFI_DEVICE_ERROR;
  assert(MunchUsbHandoffRestore(&Role)==EFI_DEVICE_ERROR && Role.ExitSlot==ExitSlot);
  EventStatus=EFI_SUCCESS;
  assert(MunchUsbHandoffRestore(&Role)==EFI_SUCCESS && Role.ExitSlot==NULL && *ExitSlot==(EFI_EVENT)(UINTN)2);
  MunchUsbRoleRestore(&Role);memcpy(Base,Before,sizeof(Before));*Core=0x10;
  puts("PASS actual PHY handoff event guards, close failure and event recreation");

  // Regression: host9 confused the template with the installed copy. Even a
  // template whose prefix looks valid is not an acceptable root instance.
  MUNCH_USB_CONFIG *Template = (VOID *)(Base + 0x15188);
  *Template = *Root;
  assert (MunchUsbRoleOpen (&Image, Template, &Role) == EFI_UNSUPPORTED);
  memcpy (Base, Before, sizeof (Before));
  puts ("PASS installed root accepted and source template rejected");

  // A running controller or changed policy must not be overwritten.
  for (unsigned Case = 0; Case < 5; Case++) {
    assert (MunchUsbRoleOpen (&Image, Root, &Role) == EFI_SUCCESS);
    if (Case == 0) Port->Mode = 4;
    if (Case == 1) *Role.Enabled = 0;
    if (Case == 2) *Role.StaticMode = 1;
    if (Case == 3) *Core = 0x20;
    if (Case == 4) *Role.LatchPending = 1;
    UINT8 Snapshot[sizeof (Before)]; memcpy (Snapshot, Base, sizeof (Before));
    UINT32 CoreBefore = *Core;
    assert (MunchUsbRoleHost (&Role) == EFI_UNSUPPORTED && !Role.Active && Tpl == 0);
    MunchUsbRoleRestore (&Role);
    assert (memcmp (Snapshot, Base, sizeof (Before)) == 0 && *Core == CoreBefore);
    memcpy (Base, Before, sizeof (Before)); *Core = 0x10;
  }
  puts ("PASS unexpected controller/policy state rejected without writes");

  for (unsigned Case = 0; Case < 9; Case++) {
    if (Case == 0) Image.ImageSize--;
    if (Case == 1) Root->Revision++;
    if (Case == 2) Base[0x4ca0] ^= 1;
    if (Case == 3) Base[0x15360] ^= 1;
    if (Case == 4) Port->Core = 1;
    if (Case == 5) MemoryType = EfiMemoryMappedIO;
    if (Case == 6) *(UINTN *)(Base + 0x15378) = 1;
    if (Case == 7) Root->Core = 0;
    if (Case == 8) Root->Mode = 4;
    assert (EFI_ERROR (MunchUsbRoleOpen (&Image, Root, &Role)));
    memcpy (Base, Before, sizeof (Before));
    Image.ImageSize = sizeof (Before); MemoryType = EfiBootServicesData;
  }
  puts ("PASS wrong image, instructions, structure and unsafe pointers rejected");
  free (Core); free (Base);
  return 0;
}
