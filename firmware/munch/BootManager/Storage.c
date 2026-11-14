// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/DevicePathLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Protocol/BlockIo.h>

VOID MunchGptProbe(EFI_BLOCK_IO_PROTOCOL *Io);

VOID MunchStorageProbe (VOID) {
  EFI_HANDLE *Handles = NULL;
  EFI_BLOCK_IO_PROTOCOL *Io;
  EFI_BLOCK_IO_MEDIA *Media;
  EFI_DEVICE_PATH_PROTOCOL *Path;
  CHAR16 *Text;
  VOID *Buffer;
  UINTN Count = 0, Index, Alignment, Pages;
  EFI_LBA Lba;
  UINT32 Crc;
  EFI_STATUS Status;
  Print (L"UFS READ PROBE: raw media, LBA0 and LBA1 only\n");
  Status = gBS->LocateHandleBuffer (ByProtocol, &gEfiBlockIoProtocolGuid, NULL, &Count, &Handles);
  Print (L"Storage Block IO handles: %u (%r)\n", Count, Status);
  if (EFI_ERROR (Status)) { return; }
  for (Index = 0; Index < Count; Index++) {
    Status = gBS->HandleProtocol (Handles[Index], &gEfiBlockIoProtocolGuid, (VOID **)&Io);
    if (EFI_ERROR (Status) || Io->Media == NULL) { continue; }
    Media = Io->Media;
    Print (L"Disk[%u] present=%u removable=%u partition=%u readonly=%u\n",
      Index, Media->MediaPresent, Media->RemovableMedia, Media->LogicalPartition, Media->ReadOnly);
    Print (L" block=%u align=%u last-LBA=%lx\n", Media->BlockSize, Media->IoAlign, Media->LastBlock);
    Path = DevicePathFromHandle (Handles[Index]);
    if (Path != NULL) {
      Text = ConvertDevicePathToText (Path, FALSE, FALSE);
      if (Text != NULL) { Print (L" path=%s\n", Text); FreePool (Text); }
    }
    if (!Media->MediaPresent || Media->RemovableMedia || Media->LogicalPartition) { continue; }
    if (Media->BlockSize < 512 || Media->BlockSize > 65536 ||
        (Media->BlockSize & (Media->BlockSize - 1)) != 0 || Media->IoAlign > 65536 ||
        (Media->IoAlign > 1 && (Media->IoAlign & (Media->IoAlign - 1)) != 0)) {
      Print (L" Unsupported block size/alignment: skipped\n"); continue;
    }
    Alignment = Media->IoAlign > EFI_PAGE_SIZE ? Media->IoAlign : EFI_PAGE_SIZE;
    Pages = EFI_SIZE_TO_PAGES (Media->BlockSize);
    Buffer = AllocateAlignedPages (Pages, Alignment);
    if (Buffer == NULL) { Print (L" Read buffer allocation failed\n"); continue; }
    for (Lba = 0; Lba < 2 && Lba <= Media->LastBlock; Lba++) {
      ZeroMem (Buffer, Media->BlockSize);
      Status = Io->ReadBlocks (Io, Media->MediaId, Lba, Media->BlockSize, Buffer);
      Print (L" Disk[%u] LBA%lu read: %r\n", Index, Lba, Status);
      if (EFI_ERROR (Status)) { break; }
      Status = gBS->CalculateCrc32 (Buffer, Media->BlockSize, &Crc);
      if (!EFI_ERROR (Status)) { Print (L"  CRC32=%08x\n", Crc); }
      if (Lba == 0) {
        Print (L"  MBR signature=%u\n", ((UINT8 *)Buffer)[510] == 0x55 && ((UINT8 *)Buffer)[511] == 0xaa);
      } else {
        Print (L"  GPT signature=%u\n", CompareMem (Buffer, "EFI PART", 8) == 0);
      }
    }
    MunchGptProbe (Io);
    FreeAlignedPages (Buffer, Pages);
  }
  FreePool (Handles);
  Print (L"UFS READ PROBE DONE\n");
}
