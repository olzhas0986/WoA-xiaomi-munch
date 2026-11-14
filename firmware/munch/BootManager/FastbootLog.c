// SPDX-License-Identifier: BSD-2-Clause-Patent
// Descriptor data in UsbDescriptors.h retains its upstream APSL-2.0 notice.
#include <Uefi.h>
#include <Library/UefiLib.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Protocol/LoadedImage.h>
#include "CompatUsbDevice.h"
#include "RamLog.h"
#include "UsbDescriptors.h"

STATIC EFI_TEXT_STRING OriginalOutput;
STATIC BOOLEAN ConsoleQuiet = FALSE;
VOID MunchConsoleStatus (CHAR16 *Text) { OriginalOutput (gST->ConOut, Text); }
VOID MunchHostTest (VOID);
VOID MunchWinpeBoot (VOID *, UINTN);
VOID MunchWinpeDiskBoot (VOID);
VOID MunchWinpeUsbDiskBoot (VOID);
VOID MunchWinpeUsbDiagDiskBoot (VOID);
VOID MunchWindowsDiskBoot (VOID);
STATIC EFI_PHYSICAL_ADDRESS DownloadAddress;
STATIC UINTN DownloadLength, DownloadOffset;
STATIC BOOLEAN DownloadReady, DownloadLocked;
// This XBL's UsbDeviceDxe caches UsbfnIo at RVA a3d0. UsbConfig's
// peripheral Stop uninstalls/frees that interface. StartEx's lazy lookup
// skips LocateProtocol when the cache is non-NULL, even after Stop.
// Refresh only the verified vendor image's data slot; never dereference
// the previous (possibly freed) interface or change executable bytes.
STATIC EFI_STATUS RefreshUsbDevice (EFI_USB_DEVICE_PROTOCOL *Usb) {
  EFI_HANDLE *Handles;
  EFI_LOADED_IMAGE_PROTOCOL *Image;
  UINTN Count, Index;
  UINT8 *Base;
  UINT32 Crc;
  VOID *Current;
  EFI_STATUS Status;
  EFI_GUID UsbfnGuid = {0x32d2963a,0xfe5d,0x4f30,{0xb6,0x33,0x6e,0x5d,0xc5,0x58,0x03,0xcc}};
  Status = gBS->LocateProtocol (&UsbfnGuid, NULL, &Current);
  if (EFI_ERROR (Status)) { return Status; }
  Status = gBS->LocateHandleBuffer (ByProtocol, &gEfiLoadedImageProtocolGuid, NULL, &Count, &Handles);
  if (EFI_ERROR (Status)) { return Status; }
  Status = EFI_UNSUPPORTED;
  for (Index = 0; Index < Count; Index++) {
    if (EFI_ERROR (gBS->HandleProtocol (Handles[Index], &gEfiLoadedImageProtocolGuid, (VOID **)&Image)) ||
        Image->ImageSize != 0xc000 || Image->ImageBase == NULL) { continue; }
    Base = Image->ImageBase;
    if ((UINTN)Usb->StartEx != (UINTN)Base + 0x1c1c) { continue; }
    if (EFI_ERROR (gBS->CalculateCrc32 (Base + 0x1ef8, 0x7c, &Crc)) || Crc != 0x4bcdbf11 ||
        EFI_ERROR (gBS->CalculateCrc32 (Base + 0x1c1c, 0x10c, &Crc)) || Crc != 0x0f0bad3c ||
        CompareMem (Base + 0xa088, &UsbfnGuid, sizeof (UsbfnGuid)) != 0) { break; }
    Print (L"USB device cache refresh: image=%p current=%p\n", Base, Current);
    CopyMem (Base + 0xa3d0, &Current, sizeof (Current));
    Status = EFI_SUCCESS;
    break;
  }
  FreePool (Handles);
  return Status;
}
STATIC EFI_STATUS EFIAPI LogOutput (EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This, CHAR16 *Text) {
  CHAR16 *Cursor;
  for (Cursor = Text; *Cursor; Cursor++) { UINT8 Byte = *Cursor < 128 ? (UINT8)*Cursor : '?'; RamLogAppend (&Byte, 1); }
  return ConsoleQuiet ? EFI_SUCCESS : OriginalOutput (This, Text);
}
VOID MunchInstallConsoleLog (VOID) {
  OriginalOutput = gST->ConOut->OutputString;
  gST->ConOut->OutputString = LogOutput;
}

VOID MunchFastbootLog (VOID) {
  EFI_USB_DEVICE_PROTOCOL *Usb = NULL;
  EFI_STATUS Status;
  VOID *Config = (VOID *)probe_config, *SsConfig = (VOID *)probe_ss_config;
  EFI_USB_STRING_DESCRIPTOR *Strings[] = { (VOID *)probe_language, (VOID *)probe_manufacturer,
    (VOID *)probe_product, (VOID *)probe_serial, (VOID *)probe_interface };
  USB_DEVICE_DESCRIPTOR_SET Descriptors = { (VOID *)probe_device, &Config, (VOID *)probe_ss_device,
    &SsConfig, (VOID *)probe_qualifier, (VOID *)probe_bos, 5, Strings };
  UINT8 *Rx = NULL, *Tx = NULL, *Snapshot = NULL;
  UINTN Offset = 0, Length = 0, Size, Index, Packet;
  UINT64 Total, Start;
  BOOLEAN Downloading = FALSE, Armed = FALSE, BootPe = FALSE, BootDisk = FALSE, BootUsb = FALSE, BootDiag = FALSE, BootWindows = FALSE;
  BOOLEAN Connected = FALSE, Receiving = FALSE, Sending = FALSE, Dumping = FALSE, Reboot = FALSE, HostTest = FALSE;
  USB_DEVICE_EVENT Event;
  USB_DEVICE_EVENT_DATA Data;
Restart:
  Connected = Receiving = Sending = Dumping = Reboot = HostTest = FALSE;
  Downloading = Armed = BootPe = BootDisk = BootUsb = BootDiag = BootWindows = FALSE;
  Rx = Tx = Snapshot = NULL;
  Status = gBS->LocateProtocol (&gEfiUsbDeviceProtocolGuid, NULL, (VOID **)&Usb);
  Print (L"Fastboot USB protocol: %r\n", Status);
  if (EFI_ERROR (Status)) { return; }
  Status = RefreshUsbDevice (Usb);
  Print (L"Fastboot USB cache validation: %r\n", Status);
  if (EFI_ERROR (Status)) { return; }
  Status = Usb->StartEx (&Descriptors);
  Print (L"Fastboot USB StartEx: %r\n", Status);
  if (EFI_ERROR (Status)) { return; }
  Status = Usb->AllocateTransferBuffer (65536, (VOID **)&Rx);
  if (EFI_ERROR (Status)) { goto Exit; }
  Status = Usb->AllocateTransferBuffer (1024, (VOID **)&Tx);
  if (EFI_ERROR (Status)) { goto Exit; }
  Snapshot = AllocatePool (LOG_CAPACITY);
  if (Snapshot == NULL) { goto Exit; }
  Print (L"FASTBOOT LOG READY - connect PC\nfastboot oem log\n");
  MunchConsoleStatus (L"Fastboot ready.\r\n");
  // Download accepts only a RAM image; no flash/erase commands exist.
  for (;;) {
    if (Connected && !Sending && Dumping) {
      Packet = 4;
      CopyMem (Tx, "INFO", 4);
      // A short packet also terminates transfers at USB full-speed (64-byte MPS).
      while (Offset < Length && Packet < 63) {
        UINT8 Byte = Snapshot[Offset++];
        if (Byte == '\r') { continue; }
        if (Byte == '\n') { break; }
        Tx[Packet++] = Byte >= 32 && Byte < 127 ? Byte : '.';
      }
      if (Packet == 4 && Offset == Length) { CopyMem (Tx, "OKAY", 4); Dumping = FALSE; }
      Status = Usb->Send (0x81, Packet, Tx);
      if (EFI_ERROR (Status)) { break; }
      Sending = TRUE;
    }
    if (Connected && !Receiving && !Sending && !Dumping) {
      Status = Usb->Send (1, Downloading ? MIN (65536, DownloadLength - DownloadOffset) : 511, Rx);
      if (EFI_ERROR (Status)) { break; }
      Receiving = TRUE;
    }
    Size = sizeof (Data);
    Status = Usb->HandleEvent (&Event, &Size, &Data);
    if (EFI_ERROR (Status)) { break; }
    if (Event == UsbDeviceEventDeviceStateChange) {
      Connected = Data.DeviceState == UsbDeviceStateConnected;
      // The PC can unplug as soon as it receives OKAY, before our event loop
      // consumes the IN completion. Keep the already authorized boot action.
      if (!Connected && (HostTest || BootDisk || BootPe)) {
        Print (L"USB disconnected with pending boot action; continuing\n");
        goto Exit;
      }
      if (!Connected) { Downloading = Armed = FALSE; }
      Receiving = Sending = Dumping = Reboot = HostTest = FALSE;
    } else if (Event == UsbDeviceEventTransferNotification) {
      if (Data.TransferOutcome.EndpointIndex == 0x81) {
        Sending = FALSE;
        if (Data.TransferOutcome.Status != UsbDeviceTransferStatusCompleteOK) { Dumping = Reboot = HostTest = FALSE; }
        else if (Reboot) { gRT->ResetSystem (EfiResetCold, EFI_SUCCESS, 0, NULL); }
        else if (HostTest || BootPe || BootDisk) { goto Exit; }
        else if (Armed) { Downloading = TRUE; Armed = FALSE; }
      } else if (Data.TransferOutcome.EndpointIndex == 1) {
        Receiving = FALSE;
        if (Downloading) {
          UINTN Received = Data.TransferOutcome.BytesCompleted;
          if (Data.TransferOutcome.Status != UsbDeviceTransferStatusCompleteOK || Received == 0 || Received > 65536 || Received > DownloadLength - DownloadOffset) { break; }
          CopyMem ((UINT8 *)(UINTN)DownloadAddress + DownloadOffset, Rx, Received);
          DownloadOffset += Received;
          if (DownloadOffset == DownloadLength) {
            Downloading = FALSE; DownloadReady = TRUE;
            CopyMem (Tx, "OKAY", 4);
            Status = Usb->Send (0x81, 4, Tx);
            if (EFI_ERROR (Status)) { break; }
            Sending = TRUE;
          }
          continue;
        }
        if (Data.TransferOutcome.Status != UsbDeviceTransferStatusCompleteOK || Data.TransferOutcome.BytesCompleted == 0 || Data.TransferOutcome.BytesCompleted > 511) { continue; }
        Rx[Data.TransferOutcome.BytesCompleted] = 0;
        if (AsciiStrCmp ((CHAR8 *)Rx, "oem log") == 0) {
          Total = RAM_LOG->Magic == LOG_MAGIC ? RAM_LOG->Total : 0;
          Length = (UINTN)(Total < LOG_CAPACITY ? Total : LOG_CAPACITY);
          Start = Total - Length;
          for (Index = 0; Index < Length; Index++) { Snapshot[Index] = RAM_LOG->Data[(Start + Index) % LOG_CAPACITY]; }
          Offset = 0; Dumping = TRUE; continue;
        }
        if (AsciiStrnCmp ((CHAR8 *)Rx, "download:", 9) == 0) {
          UINTN Value = 0, Digit, Position;
          BOOLEAN Valid = AsciiStrLen ((CHAR8 *)Rx) == 17;
          for (Position = 9; Valid && Position < 17; Position++) {
            UINT8 C = Rx[Position];
            if (C >= '0' && C <= '9') Digit = C - '0';
            else if (C >= 'a' && C <= 'f') Digit = C - 'a' + 10;
            else if (C >= 'A' && C <= 'F') Digit = C - 'A' + 10;
            else { Valid = FALSE; break; }
            Value = (Value << 4) | Digit;
          }
          if (!Valid || Value < 64*1024*1024 || Value > 0x30000000 || Value % 512 || DownloadLocked) {
            AsciiStrCpyS ((CHAR8 *)Tx, 1024, "FAILinvalid RAM image size or disk already registered");
          } else {
            if (DownloadAddress) { gBS->FreePages (DownloadAddress, EFI_SIZE_TO_PAGES (DownloadLength)); DownloadAddress = 0; }
            DownloadReady = FALSE; DownloadLength = Value; DownloadOffset = 0;
            Status = gBS->AllocatePages (AllocateAnyPages, EfiBootServicesData, EFI_SIZE_TO_PAGES (Value), &DownloadAddress);
            if (EFI_ERROR (Status)) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "FAILRAM allocation failed"); }
            else { CopyMem (Tx, "DATA", 4); CopyMem (Tx + 4, Rx + 9, 8); Tx[12] = 0; Armed = TRUE; }
          }
        }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "getvar:max-download-size") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAY0x30000000"); }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem windows") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYattach OTG within 10s; boot installed Windows"); BootDisk = BootUsb = BootWindows = TRUE; }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem winpe-usb-diag") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYattach OTG within 10s; diagnostic WinPE"); BootDisk = BootUsb = BootDiag = TRUE; }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem winpe-usb") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYattach OTG within 10s; starting WinPE with USB"); BootDisk = BootUsb = TRUE; }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem winpe-disk") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYstarting WinPE from verified UFS partition"); BootDisk = TRUE; }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem winpe") == 0) {
          if (DownloadReady && !DownloadLocked) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYstarting ARM64 boot manager"); BootPe = TRUE; }
          else { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "FAILstage a FAT32 RAM image first"); }
        }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "getvar:product") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYmunch-uefi-log"); }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "getvar:version") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAY0.31-core-topology"); }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem ping") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYpong"); }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "reboot") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAY"); Reboot = TRUE; }
        else if (AsciiStrCmp ((CHAR8 *)Rx, "oem host-test") == 0) { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "OKAYunplug PC, attach OTG within 10s"); HostTest = TRUE; }
        else { AsciiStrCpyS ((CHAR8 *)Tx, 1024, "FAILunsupported diagnostic command"); }
        Status = Usb->Send (0x81, AsciiStrLen ((CHAR8 *)Tx), Tx);
        if (EFI_ERROR (Status)) { break; }
        Sending = TRUE;
      }
    }
    gBS->Stall (100);
  }
  Print (L"Fastboot transfer failed: %r\n", Status);
Exit:
  // Stop outstanding transfers before releasing their DMA buffers.
  Usb->AbortXfer (1);
  Usb->AbortXfer (0x81);
  if (Rx != NULL) { Usb->FreeTransferBuffer (Rx); }
  if (Tx != NULL) { Usb->FreeTransferBuffer (Tx); }
  if (Snapshot != NULL) { FreePool (Snapshot); }
  Usb->Stop ();
  if (HostTest) { MunchHostTest (); goto Restart; }
  if (BootDisk) { ConsoleQuiet = FALSE; if (BootWindows) { MunchWindowsDiskBoot (); } else if (BootDiag) { MunchWinpeUsbDiagDiskBoot (); } else if (BootUsb) { MunchWinpeUsbDiskBoot (); } else { MunchWinpeDiskBoot (); } ConsoleQuiet = FALSE; goto Restart; }
  if (BootPe) { DownloadLocked = TRUE; ConsoleQuiet = FALSE; MunchWinpeBoot ((VOID *)(UINTN)DownloadAddress, DownloadLength); ConsoleQuiet = FALSE; goto Restart; }
  // A transport failure/cable removal is not a request to reboot Android.
  Print (L"USB transport stopped; restarting fastboot without reboot\n");
  gBS->Stall (1000000);
  goto Restart;
}
