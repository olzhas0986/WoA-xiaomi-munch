// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Uefi/UefiGpt.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Protocol/BlockIo.h>
VOID MunchGptProbe(EFI_BLOCK_IO_PROTOCOL *Io) {
  EFI_PARTITION_TABLE_HEADER H[2];
  EFI_PARTITION_ENTRY E;
  VOID *Block, *Tables[2] = {NULL,NULL};
  UINTN Align, Pages[2] = {0,0}, Bytes[2] = {0,0}, I, J;
  UINT32 Saved, Crc;
  EFI_STATUS S;
  BOOLEAN Valid[2] = {FALSE,FALSE};
  EFI_GUID Zero = {0};
  CHAR16 Name[37];
  Align = Io->Media->IoAlign > EFI_PAGE_SIZE ? Io->Media->IoAlign : EFI_PAGE_SIZE;
  Block = AllocateAlignedPages(EFI_SIZE_TO_PAGES(Io->Media->BlockSize),Align);
  if (!Block) return;
  for (I=0; I<2; I++) {
    EFI_LBA Lba = I ? Io->Media->LastBlock : 1;
    S=Io->ReadBlocks(Io,Io->Media->MediaId,Lba,Io->Media->BlockSize,Block);
    Print(L"GPT copy=%u header read: %r\n",I,S);
    if (EFI_ERROR(S)) continue;
    CopyMem(&H[I],Block,sizeof(H[I]));
    if (H[I].Header.Signature!=EFI_PTAB_HEADER_ID || H[I].Header.HeaderSize<sizeof(H[I]) || H[I].Header.HeaderSize>Io->Media->BlockSize || H[I].Header.Revision!=0x10000 || H[I].Header.Reserved || H[I].MyLBA!=Lba || H[I].AlternateLBA!=(I ? 1 : Io->Media->LastBlock)) continue;
    Saved=((EFI_PARTITION_TABLE_HEADER *)Block)->Header.CRC32;
    ((EFI_PARTITION_TABLE_HEADER *)Block)->Header.CRC32=0;
    S=gBS->CalculateCrc32(Block,H[I].Header.HeaderSize,&Crc);
    if (EFI_ERROR(S) || Crc!=Saved) { Print(L"GPT header CRC failed\n"); continue; }
    if (H[I].FirstUsableLBA<2 || H[I].FirstUsableLBA>H[I].LastUsableLBA || H[I].LastUsableLBA>=Io->Media->LastBlock || !H[I].NumberOfPartitionEntries || H[I].NumberOfPartitionEntries>1024 || H[I].SizeOfPartitionEntry<128 || H[I].SizeOfPartitionEntry>4096 || (H[I].SizeOfPartitionEntry & (H[I].SizeOfPartitionEntry-1))) continue;
    Bytes[I]=(UINTN)H[I].NumberOfPartitionEntries*H[I].SizeOfPartitionEntry;
    if (Bytes[I]>1024*1024) continue;
    UINTN Blocks=(Bytes[I]+Io->Media->BlockSize-1)/Io->Media->BlockSize;
    if (H[I].PartitionEntryLBA<2 || H[I].PartitionEntryLBA>Io->Media->LastBlock || Blocks>Io->Media->LastBlock-H[I].PartitionEntryLBA) continue;
    if ((!I && H[I].PartitionEntryLBA+Blocks>H[I].FirstUsableLBA) || (I && H[I].PartitionEntryLBA<=H[I].LastUsableLBA)) continue;
    Pages[I]=EFI_SIZE_TO_PAGES(Blocks*Io->Media->BlockSize);
    Tables[I]=AllocateAlignedPages(Pages[I],Align);
    if (!Tables[I]) continue;
    S=Io->ReadBlocks(Io,Io->Media->MediaId,H[I].PartitionEntryLBA,Blocks*Io->Media->BlockSize,Tables[I]);
    if (EFI_ERROR(S)) { Print(L"GPT entries read: %r\n",S); continue; }
    S=gBS->CalculateCrc32(Tables[I],Bytes[I],&Crc);
    Valid[I]=!EFI_ERROR(S) && Crc==H[I].PartitionEntryArrayCRC32;
    Print(L"GPT copy=%u header CRC=OK entries CRC=%u count=%u\n",I,Valid[I],H[I].NumberOfPartitionEntries);
  }
  if (Valid[0] && Valid[1]) Print(L"GPT copies agree=%u\n",Bytes[0]==Bytes[1] && CompareMem(&H[0].DiskGUID,&H[1].DiskGUID,sizeof(EFI_GUID))==0 && H[0].FirstUsableLBA==H[1].FirstUsableLBA && H[0].LastUsableLBA==H[1].LastUsableLBA && H[0].SizeOfPartitionEntry==H[1].SizeOfPartitionEntry && CompareMem(Tables[0],Tables[1],Bytes[0])==0);
  I=Valid[0] ? 0 : 1;
  if (Valid[I]) for (J=0; J<H[I].NumberOfPartitionEntries; J++) {
    CopyMem(&E,(UINT8 *)Tables[I]+J*H[I].SizeOfPartitionEntry,sizeof(E));
    if (CompareMem(&E.PartitionTypeGUID,&Zero,sizeof(Zero))==0) continue;
    for (UINTN K=0; K<36; K++) Name[K]=E.PartitionName[K]>=32 && E.PartitionName[K]<127 ? E.PartitionName[K] : (E.PartitionName[K] ? '?' : 0);
    Name[36]=0;
    Print(L"PART %u name=%s first=%lu last=%lu bounds=%u\n",J,Name,E.StartingLBA,E.EndingLBA,E.StartingLBA>=H[I].FirstUsableLBA && E.StartingLBA<=E.EndingLBA && E.EndingLBA<=H[I].LastUsableLBA);
    Print(L" type=%g unique=%g attrs=%lx\n",&E.PartitionTypeGUID,&E.UniquePartitionGUID,E.Attributes);
  }
  for (I=0; I<2; I++) if (Tables[I]) FreeAlignedPages(Tables[I],Pages[I]);
  FreeAlignedPages(Block,EFI_SIZE_TO_PAGES(Io->Media->BlockSize));
}
