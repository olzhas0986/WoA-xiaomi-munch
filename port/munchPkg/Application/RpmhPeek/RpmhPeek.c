/** @file
  Read the two RPMh DRV CONFIG registers checked by qcpep8250 (TCS and command
  counts) one at a time, saving each result to \rpmh.txt on the volume this
  application was loaded from before attempting the next read. If a read
  hangs the bus, the values read before it are already on disk.

  Before that, the RPMh Command DB (AOP reserved memory 0x80860000, 128 KiB,
  in the platform memory map) is copied to \cmddb.bin; qcpep8250 looks up
  every PEP resource there.

  Afterwards the Windows boot manager is started from the same volume, so the
  application can sit at \EFI\Boot\bootaa64.efi without breaking boot.

  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#include <PiDxe.h>
#include <Library/UefiLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/IoLib.h>
#include <Library/PrintLib.h>
#include <Library/DevicePathLib.h>
#include <Library/DxeServicesTableLib.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
#include <Guid/FileInfo.h>

#define APPS_RSC_CONFIG     0x1822000CULL   // apps RSC DRV2 CONFIG
#define DISPLAY_RSC_CONFIG  0x0AF2000CULL   // display RSC DRV CONFIG
#define CMD_DB_BASE         0x80860000ULL   // reserved-memory "qcom,cmd-db"
#define CMD_DB_SIZE         0x20000

STATIC EFI_FILE_PROTOCOL  *mRoot;

/**
  The display RSC page is not in the platform memory map. Map it here, after
  the apps value is safely on disk, so a fault cannot hide that result.
**/
STATIC
EFI_STATUS
MapMmioPage (
  IN UINT64  Address
  )
{
  EFI_PHYSICAL_ADDRESS  Base = Address & ~(EFI_PHYSICAL_ADDRESS)0xFFF;
  EFI_STATUS            Status;

  Status = gDS->AddMemorySpace (EfiGcdMemoryTypeMemoryMappedIo, Base, SIZE_4KB,
                                EFI_MEMORY_UC | EFI_MEMORY_RUNTIME);
  if (EFI_ERROR (Status) && (Status != EFI_ACCESS_DENIED)) {
    return Status;
  }
  return gDS->SetMemorySpaceAttributes (Base, SIZE_4KB, EFI_MEMORY_UC);
}

STATIC
VOID
Save (
  IN CONST CHAR8  *Line
  )
{
  EFI_FILE_PROTOCOL  *File;
  UINTN              Size;
  EFI_FILE_INFO      *Info;
  UINTN              InfoSize;
  UINT8              InfoBuffer[SIZE_OF_EFI_FILE_INFO + 64];

  if (mRoot == NULL) {
    return;
  }
  if (EFI_ERROR (mRoot->Open (mRoot, &File, L"\\rpmh.txt",
                              EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0))) {
    Print (L"cannot open \\rpmh.txt\n");
    return;
  }
  // append
  InfoSize = sizeof (InfoBuffer);
  Info     = (EFI_FILE_INFO *)InfoBuffer;
  if (!EFI_ERROR (File->GetInfo (File, &gEfiFileInfoGuid, &InfoSize, Info))) {
    File->SetPosition (File, Info->FileSize);
  }
  Size = AsciiStrLen (Line);
  File->Write (File, &Size, (VOID *)Line);
  File->Flush (File);
  File->Close (File);
}

STATIC
EFI_STATUS
DumpCmdDb (
  VOID
  )
{
  EFI_FILE_PROTOCOL  *File;
  UINTN              Size;
  EFI_STATUS         Status;

  if (mRoot == NULL) {
    return EFI_NOT_READY;
  }
  Status = mRoot->Open (mRoot, &File, L"\\cmddb.bin",
                        EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  File->SetPosition (File, 0);
  Size   = CMD_DB_SIZE;
  Status = File->Write (File, &Size, (VOID *)(UINTN)CMD_DB_BASE);
  File->Flush (File);
  File->Close (File);
  return Status;
}

STATIC
VOID
ReadAndSave (
  IN CONST CHAR8  *Name,
  IN UINT64       Address
  )
{
  CHAR8   Line[96];
  UINT32  Value;

  AsciiSPrint (Line, sizeof (Line), "reading %a 0x%lx\n", Name, Address);
  Save (Line);
  Print (L"%a", Line);

  Value = MmioRead32 ((UINTN)Address);

  AsciiSPrint (Line, sizeof (Line), "%a CONFIG=0x%08x\n", Name, Value);
  Save (Line);
  Print (L"%a", Line);
}

EFI_STATUS
EFIAPI
UefiMain (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS                       Status;
  EFI_LOADED_IMAGE_PROTOCOL        *Loaded;
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL  *Fs;
  EFI_DEVICE_PATH_PROTOCOL         *Path;
  EFI_HANDLE                       Next;

  Print (L"RpmhPeek: RPMh DRV CONFIG read (no writes)\n");
  Status = gBS->HandleProtocol (ImageHandle, &gEfiLoadedImageProtocolGuid, (VOID **)&Loaded);
  if (!EFI_ERROR (Status)) {
    Status = gBS->HandleProtocol (Loaded->DeviceHandle, &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
  }
  if (!EFI_ERROR (Status)) {
    Status = Fs->OpenVolume (Fs, &mRoot);
  }
  if (EFI_ERROR (Status)) {
    Print (L"no writable boot volume: %r\n", Status);
  }

  Save ("--- boot\n");
  Status = DumpCmdDb ();
  {
    CHAR8  Line[64];
    AsciiSPrint (Line, sizeof (Line), "cmd-db dump: %r\n", Status);
    Save (Line);
    Print (L"%a", Line);
  }
  ReadAndSave ("apps", APPS_RSC_CONFIG);

  Status = MapMmioPage (DISPLAY_RSC_CONFIG);
  {
    CHAR8  Line[64];
    AsciiSPrint (Line, sizeof (Line), "map display page: %r\n", Status);
    Save (Line);
    Print (L"%a", Line);
  }
  if (!EFI_ERROR (Status)) {
    ReadAndSave ("display", DISPLAY_RSC_CONFIG);
  }
  Save ("done\n");

  Print (L"Starting Windows Boot Manager in 5 s\n");
  gBS->Stall (5 * 1000 * 1000);
  Path   = FileDevicePath (Loaded->DeviceHandle, L"\\EFI\\Microsoft\\Boot\\bootmgfw.efi");
  Status = gBS->LoadImage (FALSE, ImageHandle, Path, NULL, 0, &Next);
  if (!EFI_ERROR (Status)) {
    Status = gBS->StartImage (Next, NULL, NULL);
  }
  Print (L"bootmgfw.efi: %r\n", Status);
  gBS->Stall (30 * 1000 * 1000);
  return Status;
}
