// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Guid/Acpi.h>
#include <IndustryStandard/Acpi60.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Library/BaseLib.h>
#include <Library/UefiBootManagerLib.h>
#include <Library/DeviceBootManagerLib.h>
#include <Protocol/GraphicsOutput.h>
#include <Protocol/BlockIo.h>
#include <Protocol/SimpleFileSystem.h>
#include <Protocol/UsbIo.h>
#include <Protocol/Usb2HostController.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/DriverBinding.h>
#include <Protocol/PciIo.h>
#include <Library/DevicePathLib.h>
#include "UsbImages.h"
#include "UsbRole.h"
#include "PmicOtg.h"
EFI_STATUS MunchAcpiPowerPrepare (VOID);
VOID MunchInstallConsoleLog (VOID);
VOID MunchConsoleStatus (CHAR16 *Text);
VOID MunchFastbootLog (VOID);
VOID MunchStorageProbe (VOID);
VOID MunchSpmiUsbSnapshot (EFI_LOADED_IMAGE_PROTOCOL *Image);
EFI_STATUS MunchSpmiUsbSource (EFI_LOADED_IMAGE_PROTOCOL *Image);
EFI_STATUS MunchSpmiUsbRestore (VOID);
STATIC VOID CountHandles (CHAR16 *Name, EFI_GUID *Guid);

STATIC EFI_DRIVER_BINDING_PROTOCOL *UsbBindings[ARRAY_SIZE (UsbImages)];
STATIC EFI_LOADED_IMAGE_PROTOCOL *UsbLoaded[ARRAY_SIZE (UsbImages)];

STATIC VOID UsbDriverSummary (VOID) {
  EFI_HANDLE *Handles = NULL;
  UINTN Count = 0, Index, Driver;
  EFI_LOADED_IMAGE_PROTOCOL *Image;
  EFI_DEVICE_PATH_PROTOCOL *Node;
  EFI_GUID Guid;
  VOID *Binding;
  BOOLEAN Loaded[ARRAY_SIZE (UsbImages)] = { FALSE };
  BOOLEAN Bound[ARRAY_SIZE (UsbImages)] = { FALSE };
  if (!EFI_ERROR (gBS->LocateHandleBuffer (ByProtocol, &gEfiLoadedImageProtocolGuid, NULL, &Count, &Handles))) {
    for (Index = 0; Index < Count; Index++) {
      if (EFI_ERROR (gBS->HandleProtocol (Handles[Index], &gEfiLoadedImageProtocolGuid, (VOID **)&Image))) { continue; }
      for (Node = Image->FilePath; Node != NULL && !IsDevicePathEnd (Node); Node = NextDevicePathNode (Node)) {
        if (DevicePathType (Node) != MEDIA_DEVICE_PATH || DevicePathSubType (Node) != MEDIA_PIWG_FW_FILE_DP ||
            DevicePathNodeLength (Node) < sizeof (MEDIA_FW_VOL_FILEPATH_DEVICE_PATH)) { continue; }
        CopyMem (&Guid, &((MEDIA_FW_VOL_FILEPATH_DEVICE_PATH *)Node)->FvFileName, sizeof (Guid));
        for (Driver = 0; Driver < ARRAY_SIZE (UsbImages); Driver++) {
          if (CompareGuid (&Guid, &UsbImages[Driver].Guid)) {
            UsbLoaded[Driver] = Image;
            Loaded[Driver] = TRUE;
            Bound[Driver] = !EFI_ERROR (gBS->HandleProtocol (Handles[Index], &gEfiDriverBindingProtocolGuid, &Binding));
            if (Bound[Driver]) { UsbBindings[Driver] = Binding; }
          }
        }
      }
    }
    FreePool (Handles);
  }
  for (Driver = 0; Driver < ARRAY_SIZE (UsbImages); Driver++) {
    Print (L"%s image=%u binding=%u\n", UsbImages[Driver].Name, Loaded[Driver], Bound[Driver]);
  }
}



STATIC VOID UsbRootPorts (BOOLEAN RequestPower) {
  EFI_HANDLE *Handles = NULL;
  EFI_USB2_HC_PROTOCOL *Hc;
  EFI_USB_PORT_STATUS PortStatus;
  EFI_USB_HC_STATE State;
  EFI_STATUS Status;
  UINTN Count = 0, Index;
  UINT8 Speed, Ports, Bits64, Port;
  Status = gBS->LocateHandleBuffer (ByProtocol, &gEfiUsb2HcProtocolGuid, NULL, &Count, &Handles);
  if (EFI_ERROR (Status)) { return; }
  for (Index = 0; Index < Count; Index++) {
    if (EFI_ERROR (gBS->HandleProtocol (Handles[Index], &gEfiUsb2HcProtocolGuid, (VOID **)&Hc))) { continue; }
    Status = Hc->GetState (Hc, &State);
    if (!EFI_ERROR (Status)) { Print (L" HC[%u] state=%u\n", Index, State); }
    Status = Hc->GetCapability (Hc, &Speed, &Ports, &Bits64);
    if (EFI_ERROR (Status)) { Print (L" HC capabilities: %r\n", Status); continue; }
    Print (L" HC[%u] speed=%u ports=%u dma64=%u\n", Index, Speed, Ports, Bits64);
    for (Port = 0; Port < Ports && Port < 16; Port++) {
      if (RequestPower) {
        Status = Hc->SetRootHubPortFeature (Hc, Port, EfiUsbPortPower);
        Print (L" Port[%u] request power: %r\n", Port, Status);
        gBS->Stall (200000);
      }
      Status = Hc->GetRootHubPortStatus (Hc, Port, &PortStatus);
      if (EFI_ERROR (Status)) { Print (L" Port[%u]: %r\n", Port, Status); continue; }
      Print (L" Port[%u] status=%04x change=%04x\n", Port, PortStatus.PortStatus, PortStatus.PortChangeStatus);
    }
  }
  FreePool (Handles);
}

STATIC VOID PmicUsbSummary (VOID) {
  typedef EFI_STATUS (EFIAPI *READ_WORD)(UINT32 *);
  typedef EFI_STATUS (EFIAPI *READ_BOOL)(BOOLEAN *);
  EFI_GUID Guid = {0x6adb9972,0x083d,0x4be4,{0xbb,0x74,0xc7,0x25,0xa7,0x30,0x61,0x56}};
  UINT8 *Protocol, *Base;
  UINT64 Revision;
  UINT32 Crc, Otg = MAX_UINT32, Connection = MAX_UINT32, DeviceIndex;
  BOOLEAN Valid = FALSE;
  READ_WORD GetOtg, GetConnection;
  READ_BOOL GetUsbin;
  EFI_STATUS Status;
  if (UsbLoaded[5] == NULL || UsbLoaded[5]->ImageSize != 0x2f000) {
    Print (L"PMIC USB: expected module unavailable\n"); return;
  }
  Base = UsbLoaded[5]->ImageBase;
  Status = gBS->LocateProtocol (&Guid, NULL, (VOID **)&Protocol);
  if (EFI_ERROR (Status)) { Print (L"PMIC USB lookup: %r\n", Status); return; }
  CopyMem (&Revision, Protocol, 8);
  CopyMem (&GetUsbin, Protocol+8, 8);
  CopyMem (&GetOtg, Protocol+0x28, 8);
  CopyMem (&GetConnection, Protocol+0x38, 8);
  if (Revision != 0x10009 || (UINTN)GetUsbin != (UINTN)Base+0x2a34 ||
      (UINTN)GetOtg != (UINTN)Base+0x2b88 || (UINTN)GetConnection != (UINTN)Base+0x2c4c) {
    Print (L"PMIC USB read ABI mismatch revision=%lx\n", Revision); return;
  }
  Status = gBS->CalculateCrc32 (Base+0x29b8, 0x2ec, &Crc);
  if (EFI_ERROR (Status) || Crc != 0x0b187554) { Print (L"PMIC USB code mismatch\n"); return; }
  Status = GetConnection (&Connection);
  Print (L"PMIC TypeC connection: status=%lx raw=%x\n", Status, Connection);
  Status = GetOtg (&Otg);
  Print (L"PMIC OTG status: status=%lx raw=%x\n", Status, Otg);
  Status = GetUsbin (&Valid);
  Print (L"PMIC USBIN valid: status=%lx raw=%u\n", Status, Valid);
  CopyMem (&DeviceIndex, Base+0x2b5b0, 4);
  Print (L"PMIC USB cached device index=%u\n", DeviceIndex);
  MunchSpmiUsbSnapshot (UsbLoaded[7]);
}

typedef EFI_STATUS (EFIAPI *PMIC_OTG_ENABLE)(BOOLEAN);
STATIC PMIC_OTG_ENABLE OtgRestore;
STATIC BOOLEAN HostPowerReady;
STATIC BOOLEAN AutomaticWindowsBoot;
EFI_STATUS MunchSpmiUsbOtgCommand (EFI_LOADED_IMAGE_PROTOCOL *Image, BOOLEAN *Enabled);
STATIC EFI_STATUS EFIAPI PmicOtgCommand (BOOLEAN *Enabled) {
  return MunchSpmiUsbOtgCommand (UsbLoaded[7], Enabled);
}
STATIC VOID PmicUsbTryHost (VOID) {
  typedef EFI_STATUS (EFIAPI *READ_WORD)(UINT32 *);
  typedef EFI_STATUS (EFIAPI *READ_BOOL)(BOOLEAN *);
  typedef EFI_STATUS (EFIAPI *SET_ROLE)(UINT32);
  EFI_GUID Guid = {0x6adb9972,0x083d,0x4be4,{0xbb,0x74,0xc7,0x25,0xa7,0x30,0x61,0x56}};
  UINT8 *Protocol, *Base;
  READ_WORD Connection, GetOtg;
  READ_BOOL Input;
  SET_ROLE Role;
  PMIC_OTG_ENABLE Enable;
  EFI_STATUS Status;
  UINT64 Revision;
  UINT32 Crc, State, Otg;
  BOOLEAN InputValid, CommandEnabled;
  UINTN Attempt;
  OtgRestore = NULL;
  HostPowerReady = FALSE;
  if (UsbLoaded[5] == NULL || UsbLoaded[5]->ImageSize != 0x2f000) { return; }
  Base = UsbLoaded[5]->ImageBase;
  Status = gBS->LocateProtocol (&Guid, NULL, (VOID **)&Protocol);
  if (Status != EFI_SUCCESS) { return; }
  CopyMem (&Revision, Protocol, 8);
  CopyMem (&Input, Protocol+8, 8);
  CopyMem (&Enable, Protocol+0x20, 8);
  CopyMem (&GetOtg, Protocol+0x28, 8);
  CopyMem (&Connection, Protocol+0x38, 8);
  CopyMem (&Role, Protocol+0x48, 8);
  if (Revision != 0x10009 || (UINTN)Input != (UINTN)Base+0x2a34 ||
      (UINTN)Enable != (UINTN)Base+0x2b3c || (UINTN)GetOtg != (UINTN)Base+0x2b88 ||
      (UINTN)Connection != (UINTN)Base+0x2c4c || (UINTN)Role != (UINTN)Base+0x2cd0) {
    Print (L"PMIC host request: ABI mismatch\n"); return;
  }
  Status = gBS->CalculateCrc32 (Base+0x29b8, 0x454, &Crc);
  if (Status != EFI_SUCCESS || Crc != 0xb5cf6d7a) { Print (L"PMIC host request: code mismatch\n"); return; }
  if (AutomaticWindowsBoot) {
    Print (L"Auto Windows: disconnect PC cable; preparing USB power before OS\n");
    Status = MunchPmicWaitUnpowered (Input, 100);
    if (Status != EFI_SUCCESS) { Print (L"Auto Windows: PC power present or unknown: %r\n", Status); return; }
  }
  InputValid = TRUE;
  Status = Input (&InputValid);
  if (Status != EFI_SUCCESS || InputValid) { Print (L"PMIC host request skipped: input power present or unknown\n"); return; }
  Otg = MAX_UINT32;
  Status = GetOtg (&Otg);
  Print (L"PMIC initial OTG: status=%lx raw=%x\n", Status, Otg);
  if (Status != EFI_SUCCESS || (Otg != 0 && Otg != 1)) {
    Print (L"PMIC host request skipped: unknown OTG state\n"); return;
  }
  // The protocol value above is an FSM state. Check the command register
  // instead of waiting for an FSM transition that may remain latched.
  OtgRestore = Enable;
  Status = MunchPmicOtgEnsureDisabled (Enable, PmicOtgCommand);
  Print (L"PMIC OTG command disabled: %r\n", Status);
  if (Status != EFI_SUCCESS) { return; }
  // The vendor Role(0) only clears TRY_SNK and leaves EN_SNK_ONLY set.
  // Use the verified SPMI wrapper for a temporary source-only policy.
  Status = MunchSpmiUsbSource (UsbLoaded[7]);
  Print (L"PMIC temporary source request: %r\n", Status);
  if (Status != EFI_SUCCESS) { return; }
  for (Attempt=0; Attempt<(AutomaticWindowsBoot ? 1 : 40); Attempt++) {
    State = MAX_UINT32;
    Status = Connection (&State);
    if (Status != EFI_SUCCESS) { Print (L"PMIC role query failed: %lx\n", Status); return; }
    if (State == 1) { break; } // PMIC protocol revision0x10009 DFP/source.
    if (!AutomaticWindowsBoot) { gBS->Stall (250000); }
  }
  Print (L"PMIC role after request: raw=%x\n", State);
  if (!AutomaticWindowsBoot && State != 1) { Print (L"No PMIC DFP attachment: VBUS enable skipped\n"); return; }
  if (AutomaticWindowsBoot && State != 1) {
    Print (L"Auto Windows: source-only port armed for attachment after OS boot\n");
  }
  InputValid = TRUE;
  Status = Input (&InputValid);
  if (Status != EFI_SUCCESS || InputValid) { Print (L"VBUS enable skipped: input power present or unknown\n"); return; }
  // Register cleanup before the call so a partially failing enable is undone.
  OtgRestore = Enable;
  Status = Enable (TRUE);
  Print (L"PMIC OTG enable request: raw-status=%lx\n", Status);
  gBS->Stall (500000);
  if (Status == EFI_SUCCESS) {
    Otg = MAX_UINT32;
    Status = GetOtg (&Otg);
    if (AutomaticWindowsBoot) {
      Status = PmicOtgCommand (&CommandEnabled);
      HostPowerReady = Status == EFI_SUCCESS && CommandEnabled;
      Print (L"Auto Windows: VBUS command readback %r armed=%u\n", Status, HostPowerReady);
    } else {
      HostPowerReady = Status == EFI_SUCCESS && Otg == 0;
    }
  }
  PmicUsbSummary ();
}
STATIC VOID PmicUsbRestoreHost (VOID) {
  EFI_STATUS Status;
  HostPowerReady = FALSE;
  if (OtgRestore != NULL) {
    Status = OtgRestore (FALSE);
    Print (L"PMIC OTG disable on exit: raw-status=%lx\n", Status);
    if (Status != EFI_SUCCESS) {
      gRT->ResetSystem (EfiResetCold, EFI_DEVICE_ERROR, 0, NULL);
      CpuDeadLoop ();
    }
    OtgRestore = NULL;
    gBS->Stall (500000);
  }
  Status = MunchSpmiUsbRestore ();
  if (EFI_ERROR (Status)) {
    Print (L"TypeC restore failed; rebooting before returning to PC\n");
    gRT->ResetSystem (EfiResetCold, EFI_DEVICE_ERROR, 0, NULL);
    CpuDeadLoop ();
  }
}


VOID MunchHostTest (VOID) {
  EFI_GUID Guid = { 0xe722b03f, 0xb250, 0x42ce, {0x8e,0xbd,0x5b,0xd5,0x18,0x12,0xd0,0x37} };
  MUNCH_USB_CONFIG *Config = NULL;
  MUNCH_USB_ROLE Role;
  EFI_STATUS Status;
  UINTN Second;
  MunchConsoleStatus (L"Connect OTG mouse within 10 seconds.\r\n");
  for (Second = 0; Second < 10; Second++) { gBS->Stall (1000000); }
  Status = gBS->LocateProtocol (&Guid, NULL, (VOID **)&Config);
  Print (L"USB Config lookup: %r\n", Status);
  if (EFI_ERROR (Status)) { return; }
  Print (L"USB Config revision=%x core=%u mode=%x\n", Config->Revision, Config->Core, Config->Mode);
  if (Config->Revision != 0x10005 || Config->Start == NULL || Config->Stop == NULL) {
    Print (L"USB ABI mismatch: host test skipped\n"); return;
  }
  UsbDriverSummary ();
  Status = MunchUsbRoleOpen (UsbLoaded[2], Config, &Role);
  Print (L"USB role adapter validation: %r\n", Status);
  if (EFI_ERROR (Status)) { return; }
  PmicUsbSummary ();
  Status = Config->Stop (Config, 0, 0x10);
  Print (L"Stop peripheral core0: %r\n", Status);
  if (EFI_ERROR (Status)) { goto Restore; }
  Status = MunchUsbRoleHost (&Role);
  if (EFI_ERROR (Status)) { goto Restore; }
  Status = Config->Start (Config, 0, 8);
  Print (L"Start HOST core0: %r actual-mode=%x\n", Status, Role.Port->Mode);
  PmicUsbSummary ();
  if (EFI_ERROR (Status) || Role.Port->Mode != 1) { goto StopHost; }
  PmicUsbTryHost ();
  PmicUsbSummary ();
  UsbRootPorts (TRUE);
  for (Second = 0; Second < 60; Second++) {
    if (Second % 10 == 0) {
      Print (L"HOST TEST elapsed=%u\n", Second);
      PmicUsbSummary ();
      // Stop() leaves stale UsbConfig handles sharing the same interface.
      // Connect only the current host handle, not every old alias of core0.
      if (*Role.HostHandle != NULL) {
        Status = gBS->ConnectController (*Role.HostHandle, NULL, NULL, TRUE);
        Print (L"Current host connect: %r\n", Status);
      }
      UsbRootPorts (FALSE);
      CountHandles (L"USB IO handles", &gEfiUsbIoProtocolGuid);
    }
    gBS->Stall (1000000);
  }
StopHost:
  if (Role.Port->Mode == 1) {
    Status = Config->Stop (Config, 0, 8);
    Print (L"Stop HOST core0: %r\n", Status);
  }
Restore:
  PmicUsbRestoreHost ();
  MunchUsbRoleRestore (&Role);
  Status = Config->Start (Config, 0, 0x10);
  Print (L"Restore peripheral core0: %r\n", Status);
  Print (L"HOST TEST DONE: reconnect PC to fetch log\n");
  MunchConsoleStatus (L"USB test complete. Reconnect PC for log.\r\n");
}

STATIC MUNCH_USB_ROLE WindowsRole;
STATIC MUNCH_USB_CONFIG *WindowsConfig;
VOID MunchUsbWindowsEnd (VOID) {
  EFI_STATUS Status;
  if (WindowsConfig == NULL) { return; }
  Status = MunchUsbHandoffRestore (&WindowsRole);
  if (EFI_ERROR (Status)) {
    gRT->ResetSystem (EfiResetCold, Status, 0, NULL);
    CpuDeadLoop ();
  }
  if (WindowsRole.Port != NULL && WindowsRole.Port->Mode == 1) {
    Status = WindowsConfig->Stop (WindowsConfig, 0, 8);
    Print (L"Windows USB host stop: %r\n", Status);
  }
  PmicUsbRestoreHost ();
  MunchUsbRoleRestore (&WindowsRole);
  Status = WindowsConfig->Start (WindowsConfig, 0, 16);
  Print (L"Windows USB peripheral restore: %r\n", Status);
  WindowsConfig = NULL;
}
EFI_STATUS MunchUsbWindowsBegin (VOID) {
  EFI_GUID Guid = { 0xe722b03f, 0xb250, 0x42ce, {0x8e,0xbd,0x5b,0xd5,0x18,0x12,0xd0,0x37} };
  MUNCH_USB_CONFIG *Config;
  EFI_STATUS Status;
  UINTN Second;
  Status = MunchAcpiPowerPrepare ();
  Print (L"Windows ACPI FACS check: %r\n", Status);
  if (EFI_ERROR (Status)) { return Status; }
  if (AutomaticWindowsBoot) {
    Print (L"AUTO WINDOWS: no mouse wait; disconnect PC and attach mouse in Windows\n");
  } else {
    Print (L"WINDOWS USB: unplug PC, attach OTG mouse within 10s\n");
    for (Second=0; Second<10; Second++) { gBS->Stall (1000000); }
  }
  UsbDriverSummary ();
  Status = gBS->LocateProtocol (&Guid, NULL, (VOID **)&Config);
  if (EFI_ERROR (Status)) { return Status; }
  Status = MunchUsbRoleOpen (UsbLoaded[2], Config, &WindowsRole);
  if (EFI_ERROR (Status)) { return Status; }
  WindowsConfig = Config;
  Status = Config->Stop (Config, 0, 16);
  Print (L"Windows USB peripheral stop: %r\n", Status);
  if (!EFI_ERROR (Status)) { Status = MunchUsbRoleHost (&WindowsRole); }
  if (!EFI_ERROR (Status)) {
    // Prepare PMIC while the native host callbacks are not running yet.
    PmicUsbTryHost ();
    if (!HostPowerReady) { MunchUsbWindowsEnd (); return EFI_NOT_READY; }
    Status = Config->Start (Config, 0, 8);
    Print (L"Windows USB host start: %r actual=%x\n", Status, WindowsRole.Port->Mode);
    if (!EFI_ERROR (Status) && WindowsRole.Port->Mode != 1) { Status = EFI_DEVICE_ERROR; }
  }
  if (EFI_ERROR (Status)) { MunchUsbWindowsEnd (); return Status; }
  if (*WindowsRole.HostHandle != NULL) {
    gBS->ConnectController (*WindowsRole.HostHandle, NULL, NULL, TRUE);
  }
  Status = MunchUsbHandoffArm (&WindowsRole);
  if (EFI_ERROR (Status)) { MunchUsbWindowsEnd (); return Status; }
  Print (L"USB host policy and PHY retained for Windows handoff\n");
  return EFI_SUCCESS;
}

STATIC VOID CountHandles (CHAR16 *Name, EFI_GUID *Guid) {
  EFI_HANDLE *Handles = NULL;
  UINTN Count = 0;
  EFI_STATUS Status = gBS->LocateHandleBuffer (ByProtocol, Guid, NULL, &Count, &Handles);
  Print (L"%s: %u (%r)\n", Name, Count, Status);
  if (Handles != NULL) { FreePool (Handles); }
}



VOID MunchWindowsDiskBoot (VOID);

VOID MunchDiagnostics (VOID) {
  gBS->SetWatchdogTimer (0, 0, 0, NULL);
  MunchInstallConsoleLog ();
  gST->ConOut->ClearScreen (gST->ConOut);
  MunchConsoleStatus (L"POCO F4 UEFI - WINDOWS 31 - CORE TOPOLOGY\r\nStarting...\r\n");
  DeviceBootManagerOnDemandConInConnect ();
  Print (L"Connecting controllers...\n");
  EfiBootManagerConnectAll ();
  UsbDriverSummary ();
  Print (L"Automatic Windows boot from existing ESP...\n");
  AutomaticWindowsBoot = TRUE;
  MunchWindowsDiskBoot ();
  AutomaticWindowsBoot = FALSE;
  Print (L"Windows boot returned; entering diagnostic fastboot...\n");
  MunchStorageProbe ();
  MunchFastbootLog ();
  Print (L"Fastboot initialization failed. Firmware stays here for diagnosis.\n");
  for (;;) { gBS->Stall (1000000); }
}
