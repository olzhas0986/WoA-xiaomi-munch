#!/usr/bin/env python3
"""Compile the production automatic BDS entry with observable host callbacks."""
from pathlib import Path
import subprocess,tempfile
R=Path(__file__).resolve().parents[2]
s=(R/'firmware/munch/BootManager/Diagnostics.c').read_text();start=s.index('VOID MunchDiagnostics (VOID) {');body=s[start:]
# This is the final function in the file; compile it unchanged.
assert body.count('{')==body.count('}')
prefix=r'''
#include <Uefi.h>
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
static BOOLEAN AutomaticWindowsBoot;
static int Step;
static jmp_buf Done;
EFI_BOOT_SERVICES *gBS;
EFI_SYSTEM_TABLE *gST;
UINTN EFIAPI Print(CONST CHAR16 *F,...){(void)F;return 0;}
static EFI_STATUS EFIAPI Watchdog(UINTN T,UINT64 C,UINTN N,CHAR16 *D){assert(T==0);(void)C;(void)N;(void)D;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI Clear(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *P){(void)P;return EFI_SUCCESS;}
static void MunchInstallConsoleLog(void){}
static void MunchConsoleStatus(CHAR16 *S){(void)S;}
static void DeviceBootManagerOnDemandConInConnect(void){}
static void EfiBootManagerConnectAll(void){assert(Step==0);Step=1;}
static void UsbDriverSummary(void){assert(Step==1);Step=2;}
static void MunchWindowsDiskBoot(void){assert(Step==2 && AutomaticWindowsBoot);Step=3;}
static void MunchStorageProbe(void){assert(Step==3 && !AutomaticWindowsBoot);Step=4;}
static void MunchFastbootLog(void){assert(Step==4 && !AutomaticWindowsBoot);Step=5;longjmp(Done,1);}
'''
suffix=r'''
int main(void){
 EFI_BOOT_SERVICES Bs={0};EFI_SYSTEM_TABLE St={0};EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL Console={0};
 Bs.SetWatchdogTimer=Watchdog;Console.ClearScreen=Clear;St.ConOut=&Console;gBS=&Bs;gST=&St;
 if(!setjmp(Done))MunchDiagnostics();
 assert(Step==5);puts("PASS actual BDS entry: automatic Windows before fastboot, auto flag lifetime and diagnostic fallback");return 0;
}
'''
with tempfile.TemporaryDirectory() as temp:
 c=Path(temp)/'check.c';exe=Path(temp)/'check';c.write_text(prefix+body+suffix)
 inc=R/'Mu-Silicium/Mu_Basecore/MdePkg/Include'
 subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fshort-wchar','-I'+str(inc),'-I'+str(inc/'X64'),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
