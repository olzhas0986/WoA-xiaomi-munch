// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Uefi/UefiGpt.h>
#include <Protocol/BlockIo.h>
#include <Protocol/SimpleFileSystem.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/DevicePathLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include "WinpeLayout.h"
EFI_STATUS MunchUsbWindowsBegin (VOID);
VOID MunchUsbWindowsEnd (VOID);
typedef struct {
 EFI_BLOCK_IO_PROTOCOL Io;
 EFI_BLOCK_IO_MEDIA Media;
 EFI_BLOCK_IO_PROTOCOL *Parent;
 EFI_LBA First;
 EFI_HANDLE Handle;
 VOID *Bounce;
 BOOLEAN Reading;
} VIEW;
#define VIEW_READ_CHUNK 65536
STATIC VIEW Views[2];
#include "BcdOverlay.h"
STATIC BOOLEAN BcdDiagnostic;
STATIC EFI_STATUS BcdOverlay (UINTN View, EFI_LBA Lba, UINTN Size, UINT8 *Buffer) {
 UINTN Offset,I;
 UINT32 Crc;
 EFI_STATUS S;
 if (!BcdDiagnostic || BcdSector[View]<Lba || BcdSector[View]-Lba>=Size/4096) return EFI_SUCCESS;
 Offset=(UINTN)(BcdSector[View]-Lba)*4096;
 S=gBS->CalculateCrc32(Buffer+Offset,4096,&Crc);
 if (EFI_ERROR(S) || Crc!=BCD_ORIGINAL_CRC) return EFI_COMPROMISED_DATA;
 for (I=0;I<ARRAY_SIZE(BcdChanges);I++) {
  if(Buffer[Offset+BcdChanges[I].Offset]!=BcdChanges[I].Before) return EFI_COMPROMISED_DATA;
 }
 for (I=0;I<ARRAY_SIZE(BcdChanges);I++) Buffer[Offset+BcdChanges[I].Offset]=BcdChanges[I].After;
 Print(L"BCD diagnostic: crash auto-reboot disabled in RAM (view %u)\n",View);
 return EFI_SUCCESS;
}
STATIC EFI_STATUS EFIAPI Reset(EFI_BLOCK_IO_PROTOCOL *This, BOOLEAN Extended) { return EFI_SUCCESS; }
STATIC EFI_STATUS EFIAPI Read(EFI_BLOCK_IO_PROTOCOL *This,UINT32 Id,EFI_LBA Lba,UINTN Size,VOID *Buffer) {
 VIEW *V=BASE_CR(This,VIEW,Io);
 EFI_STATUS S;
 UINTN Done=0,Chunk;
 if (Id!=V->Media.MediaId) return EFI_MEDIA_CHANGED;
 if (!Size) return EFI_SUCCESS;
 if (!Buffer || Size%V->Media.BlockSize || Lba>V->Media.LastBlock || Size/V->Media.BlockSize>V->Media.LastBlock-Lba+1) {
  Print(L"Windows BlockIo invalid read: LBA=%lx bytes=%lu\n",Lba,(UINT64)Size);
  return EFI_INVALID_PARAMETER;
 }
 if(!V->Bounce || V->Reading) return EFI_NOT_READY;
 V->Reading=TRUE;
 // Vendor DMA receives a page-aligned BootServices buffer and a bounded
 // transfer, regardless of the loader buffer's alignment/memory type.
 while(Done<Size) {
  Chunk=MIN(Size-Done,VIEW_READ_CHUNK);
  S=V->Parent->ReadBlocks(V->Parent,V->Parent->Media->MediaId,V->First+Lba+Done/V->Media.BlockSize,Chunk,V->Bounce);
  if(EFI_ERROR(S)) {
   V->Reading=FALSE;
   Print(L"Windows UFS read failed: LBA=%lx bytes=%lu status=%r\n",V->First+Lba+Done/V->Media.BlockSize,(UINT64)Chunk,S);
   return S;
  }
  CopyMem((UINT8 *)Buffer+Done,V->Bounce,Chunk);
  Done+=Chunk;
 }
 V->Reading=FALSE;
 return BcdOverlay(V==&Views[0]?0:1,Lba,Size,Buffer);
}
STATIC EFI_STATUS EFIAPI Write(EFI_BLOCK_IO_PROTOCOL *This,UINT32 Id,EFI_LBA Lba,UINTN Size,VOID *Buffer) { return EFI_WRITE_PROTECTED; }
STATIC EFI_STATUS EFIAPI Flush(EFI_BLOCK_IO_PROTOCOL *This) { return EFI_SUCCESS; }
STATIC EFI_STATUS Install(VIEW *V,EFI_HANDLE Parent,EFI_BLOCK_IO_PROTOCOL *Io,EFI_PARTITION_ENTRY *Entry,UINT32 Number) {
 HARDDRIVE_DEVICE_PATH Hd;
 EFI_DEVICE_PATH_PROTOCOL *Path;
 EFI_STATUS S;
 ZeroMem(&Hd,sizeof(Hd));Hd.Header.Type=MEDIA_DEVICE_PATH;Hd.Header.SubType=MEDIA_HARDDRIVE_DP;
 SetDevicePathNodeLength(&Hd.Header,sizeof(Hd));Hd.PartitionNumber=Number;
 Hd.PartitionStart=Entry->StartingLBA;Hd.PartitionSize=Entry->EndingLBA-Entry->StartingLBA+1;
 CopyMem(Hd.Signature,&Entry->UniquePartitionGUID,sizeof(EFI_GUID));
 Hd.MBRType=MBR_TYPE_EFI_PARTITION_TABLE_HEADER;Hd.SignatureType=SIGNATURE_TYPE_GUID;
 Path=AppendDevicePathNode(DevicePathFromHandle(Parent),&Hd.Header);
 if (!Path) return EFI_OUT_OF_RESOURCES;
 V->Parent=Io;V->First=Entry->StartingLBA;V->Media=*Io->Media;
 V->Media.LogicalPartition=TRUE;V->Media.ReadOnly=TRUE;V->Media.LastBlock=Hd.PartitionSize-1;
 V->Media.IoAlign=1;
 V->Bounce=AllocateAlignedPages(EFI_SIZE_TO_PAGES(VIEW_READ_CHUNK),EFI_PAGE_SIZE);
 if(!V->Bounce) { FreePool(Path);return EFI_OUT_OF_RESOURCES; }
 V->Io.Revision=EFI_BLOCK_IO_PROTOCOL_REVISION;V->Io.Media=&V->Media;
 V->Io.Reset=Reset;V->Io.ReadBlocks=Read;V->Io.WriteBlocks=Write;V->Io.FlushBlocks=Flush;
 S=gBS->InstallMultipleProtocolInterfaces(&V->Handle,&gEfiDevicePathProtocolGuid,Path,&gEfiBlockIoProtocolGuid,&V->Io,NULL);
 if (EFI_ERROR(S)) { FreeAlignedPages(V->Bounce,EFI_SIZE_TO_PAGES(VIEW_READ_CHUNK));V->Bounce=NULL;FreePool(Path);return S; }
 S=gBS->ConnectController(V->Handle,NULL,NULL,TRUE);
 Print(L"Windows partition %u filesystem connect: %r\n",Number,S);
 // Native Windows Boot Manager reads NTFS through BlockIo. A firmware FAT
 // binding is optional; retain the successfully installed read-only view.
 return EFI_SUCCESS;
}
STATIC VOID DiskBoot(BOOLEAN WithUsb, BOOLEAN InstalledWindows) {
 EFI_HANDLE *Handles=NULL,Image=NULL;
 EFI_BLOCK_IO_PROTOCOL *Io;
 EFI_PARTITION_TABLE_HEADER H;
 EFI_PARTITION_ENTRY Esp,Win;
 EFI_STATUS S;
 EFI_DEVICE_PATH_PROTOCOL *File;
 UINTN Count=0,I;
 UINT32 Saved,Crc;
 VOID *Buffer=NULL;
 BOOLEAN Found=FALSE;
 if (Views[1].Handle==NULL) {
  S=gBS->LocateHandleBuffer(ByProtocol,&gEfiBlockIoProtocolGuid,NULL,&Count,&Handles);
  if (EFI_ERROR(S)) { Print(L"WinPE: no UFS Block IO\n");return; }
  Buffer=AllocateAlignedPages(2,EFI_PAGE_SIZE);
  if (!Buffer) { FreePool(Handles);return; }
  for (I=0;I<Count;I++) {
   S=gBS->HandleProtocol(Handles[I],&gEfiBlockIoProtocolGuid,(VOID **)&Io);
   if (EFI_ERROR(S) || !Io->Media || !Io->Media->MediaPresent || Io->Media->LogicalPartition || Io->Media->RemovableMedia || Io->Media->BlockSize!=4096 || Io->Media->LastBlock!=30650367 || Io->Media->IoAlign>EFI_PAGE_SIZE) continue;
   S=Io->ReadBlocks(Io,Io->Media->MediaId,1,4096,Buffer);if (EFI_ERROR(S)) continue;
   CopyMem(&H,Buffer,sizeof(H));
   if (H.Header.Signature!=EFI_PTAB_HEADER_ID || H.Header.HeaderSize!=92 || H.MyLBA!=1 || H.AlternateLBA!=30650367 || H.PartitionEntryLBA!=2 || H.NumberOfPartitionEntries!=64 || H.SizeOfPartitionEntry!=128) continue;
   Saved=H.Header.CRC32;((EFI_PARTITION_TABLE_HEADER *)Buffer)->Header.CRC32=0;
   S=gBS->CalculateCrc32(Buffer,92,&Crc);if (EFI_ERROR(S) || Crc!=Saved) continue;
   S=Io->ReadBlocks(Io,Io->Media->MediaId,2,8192,Buffer);if (EFI_ERROR(S)) continue;
   S=gBS->CalculateCrc32(Buffer,8192,&Crc);if (EFI_ERROR(S) || Crc!=H.PartitionEntryArrayCRC32) continue;
   CopyMem(&Esp,(UINT8 *)Buffer+34*128,sizeof(Esp));CopyMem(&Win,(UINT8 *)Buffer+36*128,sizeof(Win));
   if (CompareMem(&Esp.UniquePartitionGUID,&ExpectedEspGuid,16) || CompareMem(&Win.UniquePartitionGUID,&ExpectedWinGuid,16) || Esp.StartingLBA!=22261504 || Esp.EndingLBA!=22392575 || Win.StartingLBA!=22396672 || Win.EndingLBA!=30650111) continue;
   Print(L"WinPE: GPT CRC and new partition identities verified\n");
   if (Views[0].Handle==NULL) Install(&Views[0],Handles[I],Io,&Esp,35);
   S=Install(&Views[1],Handles[I],Io,&Win,37);Found=!EFI_ERROR(S);break;
  }
  FreeAlignedPages(Buffer,2);FreePool(Handles);
  if (!Found) { Print(L"WinPE: verified win FAT partition unavailable\n");return; }
 }
 {
  UINT8 *Boot=AllocateAlignedPages(1,EFI_PAGE_SIZE);
  BOOLEAN Ntfs;
  if(!Boot) return;
  S=Views[1].Io.ReadBlocks(&Views[1].Io,Views[1].Media.MediaId,0,4096,Boot);
  Ntfs=!EFI_ERROR(S) && !CompareMem(Boot+3,"NTFS    ",8) && Boot[11]==0 && Boot[12]==0x10;
  Print(L"Windows win volume: read=%r 4Kn NTFS=%u\n",S,Ntfs);
  if(InstalledWindows && !Ntfs) {
   Print(L"Installed Windows requires the prepared 4Kn NTFS volume: %r\n",S);
   FreeAlignedPages(Boot,1);return;
  }
  if(Ntfs) { InstalledWindows=TRUE;BcdDiagnostic=FALSE; }
  FreeAlignedPages(Boot,1);
 }
 {
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs;
  EFI_FILE_PROTOCOL *Root=NULL,*Loader=NULL;
  EFI_HANDLE BootHandle=Views[InstalledWindows?0:1].Handle;
  Print(L"Windows boot source: %s handle=%p file=\\EFI\\BOOT\\BOOTAA64.EFI\n",InstalledWindows?L"ESP":L"WinPE win",BootHandle);
  if(BootHandle==NULL) { Print(L"Boot partition view was not installed\n");return; }
  S=gBS->HandleProtocol(BootHandle,&gEfiSimpleFileSystemProtocolGuid,(VOID **)&Fs);
  Print(L"Boot source filesystem lookup: %r\n",S);
  if(EFI_ERROR(S)) return;
  S=Fs->OpenVolume(Fs,&Root);
  Print(L"Boot source OpenVolume: %r\n",S);
  if(EFI_ERROR(S)) return;
  S=Root->Open(Root,&Loader,L"\\EFI\\BOOT\\BOOTAA64.EFI",EFI_FILE_MODE_READ,0);
  Print(L"Boot source loader Open: %r\n",S);
  if(Loader) Loader->Close(Loader);
  Root->Close(Root);
  if(EFI_ERROR(S)) return;
 }
 File=FileDevicePath(Views[InstalledWindows?0:1].Handle,L"\\EFI\\BOOT\\BOOTAA64.EFI");if (!File) return;
 S=gBS->LoadImage(FALSE,gImageHandle,File,NULL,0,&Image);FreePool(File);
 Print(L"Windows ARM64 LoadImage from %s: %r\n",InstalledWindows?L"ESP":L"win",S);if (EFI_ERROR(S)) return;
 if (WithUsb) {
  S=MunchUsbWindowsBegin();
  if (EFI_ERROR(S)) { Print(L"Windows USB preparation failed: %r\n",S);gBS->UnloadImage(Image);return; }
 }
 Print(L"Starting Windows Boot Manager from %s partition...\n",InstalledWindows?L"esp":L"win");
 S=gBS->StartImage(Image,NULL,NULL);
 Print(L"Windows Boot Manager returned: %r\n",S);
 if (WithUsb) MunchUsbWindowsEnd();
 gBS->UnloadImage(Image);
}

VOID MunchWinpeDiskBoot(VOID) { DiskBoot(FALSE,FALSE); }
VOID MunchWinpeUsbDiskBoot(VOID) { DiskBoot(TRUE,FALSE); }
VOID MunchWindowsDiskBoot(VOID) { DiskBoot(TRUE,TRUE); }
VOID MunchWinpeUsbDiagDiskBoot(VOID) {
 BcdDiagnostic=TRUE;
 DiskBoot(TRUE,FALSE);
 BcdDiagnostic=FALSE;
}
