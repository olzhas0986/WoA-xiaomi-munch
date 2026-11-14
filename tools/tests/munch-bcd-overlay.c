// Run the actual read-only firmware overlay on original and corrupted sectors.
#include "../../firmware/munch/BootManager/WinpeDisk.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <zlib.h>
static EFI_BOOT_SERVICES Services;
EFI_BOOT_SERVICES *gBS=&Services;
UINTN EFIAPI Print(CONST CHAR16 *F,...){(void)F;return 0;}
static EFI_STATUS EFIAPI Crc(VOID *Data,UINTN Size,UINT32 *Value){*Value=crc32(0,Data,Size);return EFI_SUCCESS;}
int main(int argc,char **argv){
 assert(argc==3);UINT8 Original[16384],Expected[16384],Buffer[16384];
 FILE *F=fopen(argv[1],"rb");assert(F && fread(Original,1,sizeof Original,F)==sizeof Original);fclose(F);
 F=fopen(argv[2],"rb");assert(F && fread(Expected,1,sizeof Expected,F)==sizeof Expected);fclose(F);
 Services.CalculateCrc32=Crc;
 for(UINTN View=0;View<2;View++){
  memcpy(Buffer,Original,sizeof Buffer);BcdDiagnostic=FALSE;
  assert(BcdOverlay(View,BcdSector[View]-2,sizeof Buffer,Buffer)==EFI_SUCCESS);
  assert(!memcmp(Buffer,Original,sizeof Buffer));BcdDiagnostic=TRUE;
  assert(BcdOverlay(View,BcdSector[View]-2,sizeof Buffer,Buffer)==EFI_SUCCESS);
  assert(!memcmp(Buffer,Expected,sizeof Buffer));
  memcpy(Buffer,Original,sizeof Buffer);Buffer[8192]^=1;
  UINT8 Copy[16384];memcpy(Copy,Buffer,sizeof Copy);
  assert(BcdOverlay(View,BcdSector[View]-2,sizeof Buffer,Buffer)==EFI_COMPROMISED_DATA);
  assert(!memcmp(Buffer,Copy,sizeof Copy));
  assert(BcdOverlay(View,BcdSector[View]+1,4096,Buffer)==EFI_SUCCESS);
 }
 puts("PASS actual BCD RAM overlay: both views, optional flag, multi-block read, corruption rejection and exact expected bytes");
}
