// Exercise actual firmware write/readback/restore helpers with a fake bus.
#include "../../firmware/munch/BootManager/SpmiUsb.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>
EFI_BOOT_SERVICES *gBS;
VOID *EFIAPI CopyMem(VOID *D,CONST VOID *S,UINTN N){return memcpy(D,S,N);}
UINTN EFIAPI Print(CONST CHAR16 *F,...){(void)F;return 0;}
static UINT8 Register;
static UINT8 ProtocolBytes[16];
static UINT8 OtgCommand;
static BOOLEAN BadCrc;
static EFI_STATUS EFIAPI Locate(EFI_GUID *G,VOID *R,VOID **Out){(void)G;(void)R;*Out=ProtocolBytes;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Stall(UINTN Us){assert(Us==10000);return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Crc(VOID *D,UINTN N,UINT32 *Value){(void)D;assert(N==0xb8);*Value=BadCrc?0:0xe72b1d9a;return EFI_SUCCESS;}
static int WriteError,ReadError,Mismatch,Writes;
static UINT32 EFIAPI Read(VOID *P,UINT32 Sid,UINT32 Priority,UINT32 Reg,UINT8 *D,UINT32 N,UINT32 *Count){
 assert(Sid==2 && Priority==0 && N==1);
 if(P==ProtocolBytes){assert(Reg==0x1140);*D=OtgCommand;*Count=ReadError?0:1;return ReadError;}
 assert(P==(VOID *)0x1234 && Reg==0x1544);
 *D=Mismatch ? 0xff:Register;*Count=ReadError?0:1;return ReadError;
}
static UINT32 EFIAPI Write(VOID *P,UINT32 Sid,UINT32 Priority,UINT32 Reg,UINT8 *D,UINT32 N){
 assert(P==(VOID *)0x1234 && Sid==2 && Priority==0 && Reg==0x1544 && N==1);
 Writes++;Register=*D;return WriteError;
}
int main(void){
 EFI_BOOT_SERVICES Bs={0};Bs.LocateProtocol=Locate;Bs.CalculateCrc32=Crc;Bs.Stall=Stall;gBS=&Bs;
 EFI_LOADED_IMAGE_PROTOCOL Image={0};Image.ImageBase=(VOID *)((UINTN)Read-0x13dc);Image.ImageSize=0xb000;
 UINT64 Revision=0x10001;MODE_READ Fn=Read;memcpy(ProtocolBytes,&Revision,8);memcpy(ProtocolBytes+8,&Fn,8);
 BOOLEAN Enabled=TRUE;
 OtgCommand=0;assert(MunchSpmiUsbOtgCommand(&Image,&Enabled)==EFI_SUCCESS && !Enabled);
 OtgCommand=1;assert(MunchSpmiUsbOtgCommand(&Image,&Enabled)==EFI_SUCCESS && Enabled);
 OtgCommand=0x80;assert(MunchSpmiUsbOtgCommand(&Image,&Enabled)==EFI_SUCCESS && !Enabled);
 ReadError=9;assert(MunchSpmiUsbOtgCommand(&Image,&Enabled)==EFI_DEVICE_ERROR && Enabled);ReadError=0;
 BadCrc=TRUE;assert(MunchSpmiUsbOtgCommand(&Image,&Enabled)==EFI_COMPROMISED_DATA && Enabled);BadCrc=FALSE;
 ProtocolBytes[0]=0;assert(MunchSpmiUsbOtgCommand(&Image,&Enabled)==EFI_UNSUPPORTED && Enabled);ProtocolBytes[0]=1;
 assert(MunchSpmiUsbOtgCommand(NULL,&Enabled)==EFI_UNSUPPORTED && Enabled);
 assert(MunchSpmiUsbOtgCommand(&Image,NULL)==EFI_INVALID_PARAMETER);
 assert(Writes==0);
 puts("PASS actual OTG command reader: read-only sid2/1140, bit0 semantics, fail-closed bus/ABI/CRC validation");
 ModeProtocol=(VOID *)0x1234;ModeRead=Read;ModeWrite=Write;
 assert(MunchSpmiUsbSource(NULL)==EFI_UNSUPPORTED && Writes==0);
 UINT8 Policies[]={0x00,0x01,0x02,0x04,0x08,0x10,0x12};
 for(UINTN I=0;I<sizeof(Policies);I++){
  Register=Policies[I];int Before=Writes;
  assert(BeginSourceMode()==EFI_SUCCESS && Register==4 && SavedMode==Policies[I] && Writes==Before+2);
  assert(BeginSourceMode()==EFI_ALREADY_STARTED && Writes==Before+2);
  assert(MunchSpmiUsbRestore()==EFI_SUCCESS && Register==Policies[I] && !RestoreMode);
 }
 Register=0x06;int Before=Writes;assert(BeginSourceMode()==EFI_UNSUPPORTED && Writes==Before && !RestoreMode);
 Register=0x80;assert(BeginSourceMode()==EFI_UNSUPPORTED && Writes==Before && !RestoreMode);
 ReadError=9;assert(BeginSourceMode()==EFI_DEVICE_ERROR && Writes==Before && !RestoreMode);ReadError=0;
 Register=0x10;WriteError=9;assert(BeginSourceMode()==EFI_DEVICE_ERROR && RestoreMode);
 WriteError=0;assert(MunchSpmiUsbRestore()==EFI_SUCCESS && Register==0x10 && !RestoreMode);
 puts("PASS actual source transition: DRP/disabled/source/sink/try policies, exact restoration, reserved/conflicting bits rejected before writes");
 assert(WriteMode(1)==EFI_SUCCESS && Register==1);
 assert(WriteMode(4)==EFI_SUCCESS && Register==4);
 SavedMode=0x12;RestoreMode=TRUE;
 // A write can change the register yet report failure: cleanup must persist.
 WriteError=9;assert(MunchSpmiUsbRestore()==EFI_DEVICE_ERROR && RestoreMode);
 WriteError=0;ReadError=9;assert(MunchSpmiUsbRestore()==EFI_DEVICE_ERROR && RestoreMode);
 ReadError=0;Mismatch=1;assert(MunchSpmiUsbRestore()==EFI_DEVICE_ERROR && RestoreMode);
 Mismatch=0;assert(MunchSpmiUsbRestore()==EFI_SUCCESS && !RestoreMode && Register==0x12);
 int Previous=Writes;assert(MunchSpmiUsbRestore()==EFI_SUCCESS && Writes==Previous);
 puts("PASS actual mode helper: address restriction, readback, partial failure and restoration retry");
}
