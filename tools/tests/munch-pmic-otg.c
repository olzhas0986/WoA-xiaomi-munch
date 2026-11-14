// SPDX-License-Identifier: BSD-2-Clause-Patent
#include "../../firmware/munch/BootManager/PmicOtg.c"
#include <assert.h>
#include <stdio.h>
EFI_BOOT_SERVICES *gBS;
static BOOLEAN State;static UINTN Writes,Reads,Waits;static EFI_STATUS ReadStatus,WriteStatus;static BOOLEAN Stuck;
static EFI_STATUS EFIAPI Read(BOOLEAN *Value){Reads++;*Value=State;return ReadStatus;}
static EFI_STATUS EFIAPI Enable(BOOLEAN On){assert(!On);Writes++;if(!Stuck && WriteStatus==EFI_SUCCESS)State=FALSE;return WriteStatus;}
static EFI_STATUS EFIAPI Stall(UINTN Us){assert(Us==100000);Waits++;return EFI_SUCCESS;}
static void reset(void){State=TRUE;Writes=Reads=Waits=0;ReadStatus=WriteStatus=EFI_SUCCESS;Stuck=FALSE;}
static UINTN InputReads, DetachAfter;
static EFI_STATUS EFIAPI Input(BOOLEAN *Powered){*Powered=InputReads++<DetachAfter;return ReadStatus;}
int main(void){
 EFI_BOOT_SERVICES Bs={0};Bs.Stall=Stall;gBS=&Bs;
 reset();State=FALSE;assert(MunchPmicOtgEnsureDisabled(Enable,Read)==EFI_SUCCESS && Writes==0);
 reset();assert(MunchPmicOtgEnsureDisabled(Enable,Read)==EFI_SUCCESS && Writes==1 && State==FALSE && Waits==1);
 reset();ReadStatus=EFI_DEVICE_ERROR;assert(MunchPmicOtgEnsureDisabled(Enable,Read)==EFI_DEVICE_ERROR && Writes==0);
 reset();WriteStatus=EFI_DEVICE_ERROR;assert(MunchPmicOtgEnsureDisabled(Enable,Read)==EFI_DEVICE_ERROR && Writes==1 && Waits==0);
 reset();Stuck=TRUE;assert(MunchPmicOtgEnsureDisabled(Enable,Read)==EFI_TIMEOUT && Writes==1 && Waits==10);
 assert(MunchPmicOtgEnsureDisabled(NULL,Read)==EFI_INVALID_PARAMETER);
 reset();InputReads=0;DetachAfter=0;assert(MunchPmicWaitUnpowered(Input,100)==EFI_SUCCESS && InputReads==1 && Waits==0 && Writes==0);
 reset();InputReads=0;DetachAfter=3;assert(MunchPmicWaitUnpowered(Input,100)==EFI_SUCCESS && InputReads==4 && Waits==3 && Writes==0);
 reset();InputReads=0;DetachAfter=1000;assert(MunchPmicWaitUnpowered(Input,100)==EFI_NOT_READY && InputReads==100 && Waits==99 && Writes==0);
 reset();InputReads=0;ReadStatus=EFI_DEVICE_ERROR;assert(MunchPmicWaitUnpowered(Input,100)==EFI_DEVICE_ERROR && InputReads==1 && Waits==0 && Writes==0);
 assert(MunchPmicWaitUnpowered(NULL,100)==EFI_INVALID_PARAMETER && MunchPmicWaitUnpowered(Input,101)==EFI_INVALID_PARAMETER);
 puts("PASS external-input wait: detach event, bounded timeout, no power writes, query errors stop preparation");
 puts("PASS actual PMIC OTG helper: already disabled, inherited enabled, read/write errors and bounded readback timeout");return 0;
}
