// Replay actual fastboot loop: a disconnect after OKAY must preserve boot intent.
#define _GNU_SOURCE
#include "../../firmware/munch/BootManager/FastbootLog.c"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
EFI_GUID gEfiUsbDeviceProtocolGuid={1},gEfiLoadedImageProtocolGuid={2};
static EFI_BOOT_SERVICES Bs;static EFI_RUNTIME_SERVICES Rt;static EFI_SYSTEM_TABLE St;
static EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL Con;
EFI_BOOT_SERVICES *gBS=&Bs;EFI_RUNTIME_SERVICES *gRT=&Rt;EFI_SYSTEM_TABLE *gST=&St;
static EFI_LOADED_IMAGE_PROTOCOL Img;static EFI_USB_DEVICE_PROTOCOL Device;
static int Step,Starts,WindowsCalls,PeCalls,Case;static UINT8 *Receive;
VOID *EFIAPI CopyMem(VOID *D,CONST VOID *S,UINTN N){return memcpy(D,S,N);}
INTN EFIAPI CompareMem(CONST VOID *A,CONST VOID *B,UINTN N){return memcmp(A,B,N);}
UINTN EFIAPI AsciiStrLen(CONST CHAR8 *S){return strlen(S);}
INTN EFIAPI AsciiStrCmp(CONST CHAR8 *A,CONST CHAR8 *B){return strcmp(A,B);}
INTN EFIAPI AsciiStrnCmp(CONST CHAR8 *A,CONST CHAR8 *B,UINTN N){return strncmp(A,B,N);}
RETURN_STATUS EFIAPI AsciiStrCpyS(CHAR8 *D,UINTN N,CONST CHAR8 *S){assert(strlen(S)<N);strcpy(D,S);return 0;}
VOID *EFIAPI AllocatePool(UINTN N){return malloc(N);}
VOID EFIAPI FreePool(VOID *P){free(P);}
UINTN EFIAPI Print(CONST CHAR16 *F,...){(void)F;return 0;}
static EFI_STATUS EFIAPI Output(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *T,CHAR16 *S){(void)T;(void)S;return 0;}
static EFI_STATUS EFIAPI Locate(EFI_GUID *G,VOID *Reg,VOID **Out){(void)Reg;*Out=G==&gEfiUsbDeviceProtocolGuid?(VOID *)&Device:(VOID *)0x1234;return 0;}
static EFI_STATUS EFIAPI Handles(EFI_LOCATE_SEARCH_TYPE T,EFI_GUID *G,VOID *K,UINTN *N,EFI_HANDLE **H){(void)T;(void)G;(void)K;*N=1;*H=malloc(sizeof **H);(*H)[0]=(VOID *)1;return 0;}
static EFI_STATUS EFIAPI Protocol(EFI_HANDLE H,EFI_GUID *G,VOID **Out){(void)H;(void)G;*Out=&Img;return 0;}
static EFI_STATUS EFIAPI Crc(VOID *D,UINTN N,UINT32 *V){(void)D;*V=N==0x7c?0x4bcdbf11:0x0f0bad3c;return 0;}
static EFI_STATUS EFIAPI Stall(UINTN N){(void)N;return 0;}
static EFI_STATUS Start(USB_DEVICE_DESCRIPTOR_SET *D){(void)D;return ++Starts==1?EFI_SUCCESS:EFI_ABORTED;}
static EFI_STATUS EFIAPI Buffer(UINTN N,VOID **P){*P=malloc(N);if(N==65536)Receive=*P;return 0;}
static EFI_STATUS EFIAPI Release(VOID *P){free(P);return 0;}
static EFI_STATUS Send(UINT8 Ep,UINTN N,VOID *P){(void)Ep;(void)N;(void)P;return 0;}
static EFI_STATUS Abort(UINT8 Ep){(void)Ep;return 0;}
static EFI_STATUS Stop(void){return 0;}
static EFI_STATUS EFIAPI Event(USB_DEVICE_EVENT *E,UINTN *N,USB_DEVICE_EVENT_DATA *D){
 (void)N;memset(D,0,sizeof *D);
 if(Step++==0){*E=UsbDeviceEventDeviceStateChange;D->DeviceState=UsbDeviceStateConnected;return 0;}
 if(Case==2)return EFI_DEVICE_ERROR; // Cable/transport failure with no command.
 if(Step==2){
  strcpy((char *)Receive,"oem windows");*E=UsbDeviceEventTransferNotification;
  D->TransferOutcome.EndpointIndex=1;D->TransferOutcome.Status=UsbDeviceTransferStatusCompleteOK;
  D->TransferOutcome.BytesCompleted=strlen((char *)Receive);return 0;
 }
 if(Case==0){*E=UsbDeviceEventDeviceStateChange;D->DeviceState=UsbDeviceStateDisconnected;return 0;}
 *E=UsbDeviceEventTransferNotification;D->TransferOutcome.EndpointIndex=0x81;
 D->TransferOutcome.Status=UsbDeviceTransferStatusCompleteOK;return 0;
}
VOID MunchWindowsDiskBoot(VOID){WindowsCalls++;}
VOID MunchWinpeDiskBoot(VOID){PeCalls++;}
VOID MunchWinpeUsbDiskBoot(VOID){PeCalls++;}
VOID MunchWinpeUsbDiagDiskBoot(VOID){PeCalls++;}
VOID MunchHostTest(VOID){assert(0);}
VOID MunchWinpeBoot(VOID *P,UINTN N){(void)P;(void)N;assert(0);}
int main(void){
 UINT8 *Base=mmap(NULL,0xc000,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(Base!=MAP_FAILED);
 // x86 host trampoline emulates the pinned image's StartEx entry address.
 UINT8 Jump[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};UINTN Address=(UINTN)Start;
 memcpy(Jump+2,&Address,8);memcpy(Base+0x1c1c,Jump,sizeof Jump);
 EFI_GUID Usbfn={0x32d2963a,0xfe5d,0x4f30,{0xb6,0x33,0x6e,0x5d,0xc5,0x58,0x03,0xcc}};
 memcpy(Base+0xa088,&Usbfn,sizeof Usbfn);Img.ImageBase=Base;Img.ImageSize=0xc000;
 Bs.LocateProtocol=Locate;Bs.LocateHandleBuffer=Handles;Bs.HandleProtocol=Protocol;Bs.CalculateCrc32=Crc;Bs.Stall=Stall;
 Device.StartEx=(USB_DEVICE_START_EX)(UINTN)(Base+0x1c1c);Device.AllocateTransferBuffer=Buffer;Device.FreeTransferBuffer=Release;
 Device.Send=Send;Device.AbortXfer=Abort;Device.Stop=Stop;Device.HandleEvent=Event;
 Con.OutputString=Output;St.ConOut=&Con;MunchInstallConsoleLog();
 for(Case=0;Case<3;Case++){
  Step=Starts=WindowsCalls=PeCalls=0;MunchFastbootLog();
  assert(Starts==2 && PeCalls==0 && WindowsCalls==(Case==2?0:1));
  printf("PASS actual fastboot loop: %s\n",Case==0?"disconnect before ACK completion preserves Windows boot":Case==1?"normal ACK selects installed Windows":"transport failure restarts without reset");
 }
 munmap(Base,0xc000);
}
