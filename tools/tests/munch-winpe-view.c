// SPDX-License-Identifier: BSD-2-Clause-Patent
#include "../../firmware/munch/BootManager/WinpeDisk.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>
EFI_BOOT_SERVICES *gBS;
UINTN EFIAPI Print(CONST CHAR16 *Format,...) { (void)Format;return 0; }
VOID *EFIAPI CopyMem(VOID *D,CONST VOID *S,UINTN N) { return memcpy(D,S,N); }
static EFI_LBA LastLba;
static UINTN LastSize,Calls;
static EFI_STATUS EFIAPI ParentRead(EFI_BLOCK_IO_PROTOCOL *This,UINT32 Id,EFI_LBA Lba,UINTN Size,VOID *Buffer) {
 assert(Id==77 && ((UINTN)Buffer%4096)==0 && Size<=65536);
 LastLba=Lba;LastSize=Size;Calls++;
 for(UINTN I=0;I<Size;I++) ((UINT8 *)Buffer)[I]=(UINT8)(Lba+I/4096);
 return EFI_SUCCESS;
}
int main(void) {
 VIEW V={0};EFI_BLOCK_IO_MEDIA M={0};EFI_BLOCK_IO_PROTOCOL Parent={0};UINT8 Buffer[8192];
 _Alignas(4096) UINT8 Bounce[65536];V.Bounce=Bounce;
 M.MediaId=77;Parent.Media=&M;Parent.ReadBlocks=ParentRead;
 V.Parent=&Parent;V.First=22396672;V.Media.MediaId=12;V.Media.BlockSize=4096;V.Media.LastBlock=127;
 assert(Read(&V.Io,12,0,4096,Buffer)==EFI_SUCCESS && LastLba==22396672 && LastSize==4096);
 assert(Read(&V.Io,12,126,8192,Buffer)==EFI_SUCCESS && LastLba==22396798 && LastSize==8192);
 UINTN Before=Calls;
 assert(Read(&V.Io,11,0,4096,Buffer)==EFI_MEDIA_CHANGED);
 assert(Read(&V.Io,12,128,4096,Buffer)==EFI_INVALID_PARAMETER);
 assert(Read(&V.Io,12,127,8192,Buffer)==EFI_INVALID_PARAMETER);
 assert(Read(&V.Io,12,MAX_UINT64,4096,Buffer)==EFI_INVALID_PARAMETER);
 assert(Read(&V.Io,12,0,512,Buffer)==EFI_INVALID_PARAMETER);
 assert(Read(&V.Io,12,0,4096,NULL)==EFI_INVALID_PARAMETER);
 assert(Read(&V.Io,12,0,0,NULL)==EFI_SUCCESS);
 assert(Write(&V.Io,12,0,4096,Buffer)==EFI_WRITE_PROTECTED);
 assert(Calls==Before);
 UINT8 Large[131073];Before=Calls;
 assert(Read(&V.Io,12,1,131072,Large+1)==EFI_SUCCESS && Calls==Before+2);
 for(UINTN I=0;I<131072;I++) assert(Large[I+1]==(UINT8)(V.First+1+I/4096));
 V.Reading=TRUE;
 assert(Read(&V.Io,12,0,4096,Buffer)==EFI_NOT_READY);
 V.Reading=FALSE;
 puts("PASS actual UFS partition view: offset translation, end bounds, overflow, alignment size, media ID and writes rejected");
 puts("PASS unaligned loader buffer, aligned bounded DMA, multi-chunk data and reentry rejection");
 return 0;
}
