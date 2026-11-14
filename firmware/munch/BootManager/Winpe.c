// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Protocol/BlockIo.h>
#include <Protocol/SimpleFileSystem.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DevicePathLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/MemoryAllocationLib.h>
STATIC UINT8 *Ram;
STATIC UINTN RamSize;
STATIC EFI_BLOCK_IO_MEDIA Media;
STATIC EFI_STATUS EFIAPI Reset(EFI_BLOCK_IO_PROTOCOL *This, BOOLEAN Extended) { return EFI_SUCCESS; }
STATIC EFI_STATUS EFIAPI Read(EFI_BLOCK_IO_PROTOCOL *This, UINT32 Id, EFI_LBA Lba, UINTN Size, VOID *Buffer) {
  if (Id!=Media.MediaId) return EFI_MEDIA_CHANGED;
  if (!Buffer || Size%512 || Lba>=RamSize/512 || Size>RamSize-(UINTN)Lba*512) return EFI_INVALID_PARAMETER;
  CopyMem(Buffer,Ram+(UINTN)Lba*512,Size); return EFI_SUCCESS;
}
STATIC EFI_STATUS EFIAPI Write(EFI_BLOCK_IO_PROTOCOL *This, UINT32 Id, EFI_LBA Lba, UINTN Size, VOID *Buffer) { return EFI_WRITE_PROTECTED; }
STATIC EFI_STATUS EFIAPI Flush(EFI_BLOCK_IO_PROTOCOL *This) { return EFI_SUCCESS; }
STATIC EFI_BLOCK_IO_PROTOCOL Io={EFI_BLOCK_IO_PROTOCOL_REVISION, &Media, Reset, Read, Write, Flush};
STATIC struct { VENDOR_DEVICE_PATH Vendor; EFI_DEVICE_PATH_PROTOCOL End; } Path={
  {{HARDWARE_DEVICE_PATH,HW_VENDOR_DP,{sizeof(VENDOR_DEVICE_PATH),0}}, {0x45a20110,0x4c83,0x44bb,{0xb0,0x81,0xf4,0x11,0x57,0x3a,0x90,0x01}}},
  {END_DEVICE_PATH_TYPE,END_ENTIRE_DEVICE_PATH_SUBTYPE,{4,0}}
};
VOID MunchWinpeBoot(VOID *Data, UINTN Size) {
  EFI_HANDLE Handle=NULL, Image=NULL;
  EFI_DEVICE_PATH_PROTOCOL *File;
  EFI_STATUS Status;
  if (!Data || Size<64*1024*1024 || Size%512 || CompareMem((UINT8 *)Data+82,"FAT32   ",8)!=0 || ((UINT8 *)Data)[510]!=0x55 || ((UINT8 *)Data)[511]!=0xaa) {
    Print(L"WinPE: expected raw FAT32 image\n"); return;
  }
  if (Ram!=NULL) { Print(L"WinPE RAM disk already registered; reboot to replace\n"); return; }
  Ram=Data; RamSize=Size;
  ZeroMem(&Media,sizeof(Media)); Media.MediaId=1; Media.MediaPresent=TRUE; Media.ReadOnly=TRUE;
  Media.BlockSize=512; Media.LastBlock=Size/512-1; Media.IoAlign=1;
  Status=gBS->InstallMultipleProtocolInterfaces(&Handle,&gEfiDevicePathProtocolGuid,&Path,&gEfiBlockIoProtocolGuid,&Io,NULL);
  Print(L"WinPE RAM disk install: %r\n",Status);
  if (EFI_ERROR(Status)) { Ram=NULL; return; }
  Status=gBS->ConnectController(Handle,NULL,NULL,TRUE);
  Print(L"WinPE FAT connect: %r\n",Status);
  if (EFI_ERROR(Status)) return;
  File=FileDevicePath(Handle,L"\\EFI\\BOOT\\BOOTAA64.EFI");
  if (!File) return;
  Status=gBS->LoadImage(FALSE,gImageHandle,File,NULL,0,&Image);
  FreePool(File);
  Print(L"Windows ARM64 LoadImage: %r\n",Status);
  if (EFI_ERROR(Status)) return;
  Print(L"Starting Windows Boot Manager from RAM...\n");
  Status=gBS->StartImage(Image,NULL,NULL);
  Print(L"Windows Boot Manager returned: %r\n",Status);
  gBS->UnloadImage(Image);
}
