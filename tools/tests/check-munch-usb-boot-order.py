#!/usr/bin/env python3
"""Execute the production Windows USB entry with observable handoff callbacks."""
from pathlib import Path
import subprocess,tempfile
R=Path(__file__).resolve().parents[2];s=(R/'firmware/munch/BootManager/Diagnostics.c').read_text()
start=s.index('EFI_STATUS MunchUsbWindowsBegin (VOID) {');end=s.index('\nSTATIC VOID CountHandles',start);body=s[start:end]
prefix=r'''
#include <Uefi.h>
#include "UsbRole.h"
#include <assert.h>
#include <stdio.h>
EFI_BOOT_SERVICES *gBS;
static MUNCH_USB_ROLE WindowsRole;
static MUNCH_USB_CONFIG *WindowsConfig,Config;
static EFI_LOADED_IMAGE_PROTOCOL *UsbLoaded[8];
static EFI_HANDLE Host=(VOID*)1;
static BOOLEAN AutomaticWindowsBoot=TRUE,HostPowerReady,PowerOk;
static EFI_STATUS FacsStatus,StartStatus,ArmStatus;
static unsigned Step,Starts,Ends,Arms,Waits;
UINTN EFIAPI Print(CONST CHAR16 *F,...){(void)F;return 0;}
EFI_STATUS MunchAcpiPowerPrepare(void){return FacsStatus;}
static void UsbDriverSummary(void){}
static void PmicUsbTryHost(void){assert(Step==2);Step=3;HostPowerReady=PowerOk;}
void MunchUsbWindowsEnd(void){assert(WindowsConfig==&Config);Ends++;WindowsConfig=NULL;}
EFI_STATUS MunchUsbRoleOpen(EFI_LOADED_IMAGE_PROTOCOL *I,MUNCH_USB_CONFIG *C,MUNCH_USB_ROLE *Role){(void)I;assert(C==&Config);Role->Port=C;Role->HostHandle=&Host;return EFI_SUCCESS;}
EFI_STATUS MunchUsbRoleHost(MUNCH_USB_ROLE *Role){assert(Role==&WindowsRole && Step==1);Step=2;return EFI_SUCCESS;}
EFI_STATUS MunchUsbHandoffArm(MUNCH_USB_ROLE *Role){assert(Role==&WindowsRole && Step==5);Arms++;Step=6;return ArmStatus;}
static EFI_STATUS EFIAPI Start(MUNCH_USB_CONFIG *C,UINT32 Core,UINT32 Mode){assert(C==&Config && Core==0 && Mode==8 && Step==3 && HostPowerReady);Step=4;Starts++;C->Mode=1;return StartStatus;}
static EFI_STATUS EFIAPI Stop(MUNCH_USB_CONFIG *C,UINT32 Core,UINT32 Mode){assert(C==&Config && Core==0 && Mode==16 && Step==0);Step=1;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Locate(EFI_GUID *G,VOID *R,VOID **Out){(void)G;(void)R;*Out=&Config;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Connect(EFI_HANDLE H,EFI_HANDLE *D,EFI_DEVICE_PATH_PROTOCOL *P,BOOLEAN Recursive){assert(H==Host && !D && !P && Recursive && Step==4);Step=5;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Stall(UINTN Us){assert(Us==1000000);Waits++;return EFI_SUCCESS;}
static void reset(void){Step=Starts=Ends=Arms=Waits=0;HostPowerReady=FALSE;PowerOk=TRUE;FacsStatus=StartStatus=ArmStatus=EFI_SUCCESS;WindowsConfig=NULL;Config.Mode=0;AutomaticWindowsBoot=TRUE;}
'''
suffix=r'''
int main(void){
 EFI_BOOT_SERVICES Bs={0};Bs.LocateProtocol=Locate;Bs.ConnectController=Connect;Bs.Stall=Stall;gBS=&Bs;Config.Start=Start;Config.Stop=Stop;
 reset();assert(MunchUsbWindowsBegin()==EFI_SUCCESS && Step==6 && Starts==1 && Arms==1 && Ends==0 && Waits==0);
 reset();PowerOk=FALSE;assert(MunchUsbWindowsBegin()==EFI_NOT_READY && Starts==0 && Arms==0 && Ends==1);
 reset();FacsStatus=EFI_NOT_FOUND;assert(MunchUsbWindowsBegin()==EFI_NOT_FOUND && Step==0 && Starts==0 && Ends==0);
 reset();StartStatus=EFI_DEVICE_ERROR;assert(MunchUsbWindowsBegin()==EFI_DEVICE_ERROR && Ends==1 && Arms==0);
 reset();ArmStatus=EFI_DEVICE_ERROR;assert(MunchUsbWindowsBegin()==EFI_DEVICE_ERROR && Ends==1 && Arms==1);
 reset();AutomaticWindowsBoot=FALSE;assert(MunchUsbWindowsBegin()==EFI_SUCCESS && Waits==10 && Step==6);
 puts("PASS actual Windows USB entry: PMIC before host start, no auto mouse wait, FACS/power/controller/EBS errors stop handoff");return 0;
}
'''
with tempfile.TemporaryDirectory() as t:
 c=Path(t)/'test.c';exe=Path(t)/'test';c.write_text(prefix+body+suffix);inc=R/'Mu-Silicium/Mu_Basecore/MdePkg/Include'
 subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fshort-wchar','-I'+str(inc),'-I'+str(inc/'X64'),'-I'+str(R/'firmware/munch/BootManager'),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
