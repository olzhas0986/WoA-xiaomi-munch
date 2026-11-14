// SPDX-License-Identifier: BSD-2-Clause-Patent
#define _GNU_SOURCE
#include "../../firmware/munch/BootManager/AcpiPower.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
EFI_BOOT_SERVICES *gBS;
EFI_SYSTEM_TABLE *gST;
EFI_GUID gEfiAcpiTableProtocolGuid={1,0,0,{0}};
EFI_GUID gEfiAcpi20TableGuid={2,0,0,{0}};
VOID *EFIAPI CopyMem(VOID *D,CONST VOID *S,UINTN N){return memcpy(D,S,N);}
VOID *EFIAPI ZeroMem(VOID *D,UINTN N){return memset(D,0,N);}
BOOLEAN EFIAPI CompareGuid(CONST GUID *A,CONST GUID *B){return memcmp(A,B,sizeof(*A))==0;}
UINTN EFIAPI Print(CONST CHAR16 *Format,...){(void)Format;return 0;}
static EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE Fadt;
static EFI_ACPI_TABLE_PROTOCOL Protocol;
static EFI_STATUS InstallResult;
static unsigned Installs;
static void *Nvs;
static EFI_STATUS EFIAPI Install(EFI_ACPI_TABLE_PROTOCOL *This,VOID *Source,UINTN Size,UINTN *Key){
 assert(This==&Protocol && Size==64);Installs++;
 if(EFI_ERROR(InstallResult))return InstallResult;
 const EFI_ACPI_6_0_FIRMWARE_ACPI_CONTROL_STRUCTURE *F=Source;
 assert(F->Signature==SIGNATURE_32('F','A','C','S') && F->Length==64 && F->Version==2);
 assert(F->FirmwareWakingVector==0 && F->GlobalLock==0 && F->Flags==0 && F->XFirmwareWakingVector==0 && F->OspmFlags==0);
 memcpy(Nvs,Source,Size);Fadt.FirmwareCtrl=(UINT32)(UINTN)Nvs;Fadt.XFirmwareCtrl=0;*Key=1;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI Locate(EFI_GUID *Guid,VOID *Registration,VOID **Output){assert(CompareGuid(Guid,&gEfiAcpiTableProtocolGuid));(void)Registration;*Output=&Protocol;return EFI_SUCCESS;}
int main(void){
 EFI_BOOT_SERVICES Bs={0};EFI_SYSTEM_TABLE St={0};EFI_CONFIGURATION_TABLE Config={0};EFI_ACPI_6_0_ROOT_SYSTEM_DESCRIPTION_POINTER Rsdp={0};
 struct {EFI_ACPI_DESCRIPTION_HEADER H;UINT8 Entry[8];} Xsdt={0};
 Bs.LocateProtocol=Locate;gBS=&Bs;gST=&St;Protocol.InstallAcpiTable=Install;
 St.NumberOfTableEntries=1;St.ConfigurationTable=&Config;Config.VendorGuid=gEfiAcpi20TableGuid;Config.VendorTable=&Rsdp;
 assert(MunchAcpiPowerPrepare()==EFI_NOT_FOUND);
 Rsdp.Revision=2;Rsdp.XsdtAddress=(UINTN)&Xsdt;Xsdt.H.Signature=SIGNATURE_32('X','S','D','T');Xsdt.H.Length=sizeof(EFI_ACPI_DESCRIPTION_HEADER)+8;
 UINT64 Address=(UINTN)&Fadt;memcpy(Xsdt.Entry,&Address,8);Fadt.Header.Signature=SIGNATURE_32('F','A','C','P');Fadt.Header.Length=sizeof(Fadt);
 Fadt.XFirmwareCtrl=0x100000000;assert(MunchAcpiPowerPrepare()==EFI_COMPROMISED_DATA && Installs==0);Fadt.XFirmwareCtrl=0;
 InstallResult=EFI_OUT_OF_RESOURCES;assert(MunchAcpiPowerPrepare()==EFI_OUT_OF_RESOURCES && Fadt.FirmwareCtrl==0);
 Nvs=mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);assert(Nvs!=MAP_FAILED && (UINTN)Nvs<0x100000000ULL && (UINTN)Nvs%64==0);
 InstallResult=EFI_SUCCESS;assert(MunchAcpiPowerPrepare()==EFI_SUCCESS && Fadt.FirmwareCtrl==(UINTN)Nvs);
 unsigned Before=Installs;assert(MunchAcpiPowerPrepare()==EFI_SUCCESS && Installs==Before);
 ((EFI_ACPI_6_0_FIRMWARE_ACPI_CONTROL_STRUCTURE*)Nvs)->Version=0;assert(MunchAcpiPowerPrepare()==EFI_COMPROMISED_DATA && Installs==Before);
 Xsdt.H.Length=37;assert(MunchAcpiPowerPrepare()==EFI_NOT_FOUND && Installs==Before);
 munmap(Nvs,4096);puts("PASS actual FACS adapter: missing ACPI, unexpected pointers, allocation failure, valid low FACS, idempotence, malformed table rejected");return 0;
}
