// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Guid/Acpi.h>
#include <IndustryStandard/Acpi60.h>
#include <Protocol/AcpiTable.h>
#include <Protocol/EFISmem.h>
#include <Library/BaseMemoryLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>

// Windows 26100 PopGetHwConfigurationSignature reads the 32-bit FACS
// address even on our HW_REDUCED_ACPI platform. Never leave it at zero.
STATIC EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE *FindFadt (VOID) {
  UINTN I, J, Count;
  EFI_ACPI_6_0_ROOT_SYSTEM_DESCRIPTION_POINTER *Rsdp;
  EFI_ACPI_DESCRIPTION_HEADER *Xsdt, *Table;
  UINT64 Address;
  for (I = 0; I < gST->NumberOfTableEntries; I++) {
    if (!CompareGuid (&gST->ConfigurationTable[I].VendorGuid, &gEfiAcpi20TableGuid)) { continue; }
    Rsdp = gST->ConfigurationTable[I].VendorTable;
    if (Rsdp == NULL || Rsdp->Revision < 2 || Rsdp->XsdtAddress == 0) { return NULL; }
    Xsdt = (VOID *)(UINTN)Rsdp->XsdtAddress;
    if (Xsdt->Signature != SIGNATURE_32 ('X','S','D','T') ||
        Xsdt->Length < sizeof (*Xsdt) || Xsdt->Length > 65536 ||
        (Xsdt->Length - sizeof (*Xsdt)) % sizeof (Address) != 0) { return NULL; }
    Count = (Xsdt->Length - sizeof (*Xsdt)) / sizeof (Address);
    for (J = 0; J < Count; J++) {
      CopyMem (&Address, (UINT8 *)Xsdt + sizeof (*Xsdt) + J * sizeof (Address), sizeof (Address));
      if (Address == 0) { continue; }
      Table = (VOID *)(UINTN)Address;
      if (Table->Signature == SIGNATURE_32 ('F','A','C','P') &&
          Table->Length >= sizeof (EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE)) { return (VOID *)Table; }
    }
  }
  return NULL;
}

STATIC BOOLEAN ValidFacs (EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE *Fadt) {
  EFI_ACPI_6_0_FIRMWARE_ACPI_CONTROL_STRUCTURE *Facs;
  if (Fadt == NULL || Fadt->FirmwareCtrl == 0 || Fadt->FirmwareCtrl % 64 != 0) { return FALSE; }
  Facs = (VOID *)(UINTN)Fadt->FirmwareCtrl;
  return Facs->Signature == SIGNATURE_32 ('F','A','C','S') &&
         Facs->Length == sizeof (*Facs) && Facs->Version == 2;
}

STATIC EFI_STATUS PrepareSocInfo (EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE *Fadt) {
  EFI_ACPI_DESCRIPTION_HEADER *Dsdt;
  EFI_SMEM_PROTOCOL *Smem;
  EFI_STATUS Status;
  VOID *Info;
  UINT32 Size;
  UINTN I, Found;
  UINT64 Address;
  UINT8 *Bytes;
  UINT8 Sum;
  Dsdt = (VOID *)(UINTN)(Fadt->XDsdt != 0 ? Fadt->XDsdt : Fadt->Dsdt);
  if (Dsdt == NULL || Dsdt->Signature != SIGNATURE_32 ('D','S','D','T') ||
      Dsdt->Length < sizeof (*Dsdt) || Dsdt->Length > 65536) { return EFI_COMPROMISED_DATA; }
  Bytes = (VOID *)Dsdt;
  Found = 0;
  for (I = sizeof (*Dsdt); I + 14 <= Dsdt->Length; I++) {
    if (Bytes[I] == 0x08 && CompareMem (Bytes + I + 1, "SOSI", 4) == 0 && Bytes[I + 5] == 0x0E) {
      if (Found != 0) { return EFI_COMPROMISED_DATA; }
      Found = I + 6;
    }
  }
  // Earlier profiles have no PEP/SOSI contract.
  if (Found == 0) { return EFI_SUCCESS; }
  Status = gBS->LocateProtocol (&gEfiSMEMProtocolGuid, NULL, (VOID **)&Smem);
  if (EFI_ERROR (Status)) { return Status; }
  Size = 0;
  Info = NULL;
  Status = Smem->GetFunc (137, &Size, &Info);
  if (EFI_ERROR (Status)) { return Status; }
  Address = (UINTN)Info;
  // Captured munch DT reserves SMEM at 0x80900000..0x80afffff.
  // The native reader first maps 0xb0 bytes of the real socinfo structure.
  if (Size < 0xB0 || Size > 0x200000 || Address < 0x80900000 ||
      Address >= 0x80B00000 || Size > 0x80B00000 - Address) { return EFI_COMPROMISED_DATA; }
  CopyMem (Bytes + Found, &Address, sizeof (Address));
  Dsdt->Checksum = 0;
  Sum = 0;
  for (I = 0; I < Dsdt->Length; I++) { Sum = (UINT8)(Sum + Bytes[I]); }
  Dsdt->Checksum = (UINT8)(0 - Sum);
  Print (L"ACPI SOSI: SMEM137=%lx size=%u\n", Address, Size);
  return EFI_SUCCESS;
}

EFI_STATUS MunchAcpiPowerPrepare (VOID) {
  EFI_ACPI_TABLE_PROTOCOL *Protocol;
  EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE *Fadt;
  EFI_ACPI_6_0_FIRMWARE_ACPI_CONTROL_STRUCTURE Facs;
  EFI_STATUS Status;
  UINTN Key;
  Fadt = FindFadt ();
  if (Fadt == NULL) { return EFI_NOT_FOUND; }
  Status = PrepareSocInfo (Fadt);
  if (EFI_ERROR (Status)) { return Status; }
  if (ValidFacs (Fadt)) { return EFI_SUCCESS; }
  // Refuse an unexpected existing table instead of installing a duplicate.
  if (Fadt->FirmwareCtrl != 0 || Fadt->XFirmwareCtrl != 0) { return EFI_COMPROMISED_DATA; }
  Status = gBS->LocateProtocol (&gEfiAcpiTableProtocolGuid, NULL, (VOID **)&Protocol);
  if (EFI_ERROR (Status)) { return Status; }
  ZeroMem (&Facs, sizeof (Facs));
  Facs.Signature = SIGNATURE_32 ('F','A','C','S');
  Facs.Length = sizeof (Facs);
  Facs.HardwareSignature = SIGNATURE_32 ('M','U','N','C');
  Facs.Version = 2;
  // AcpiTableDxe special-cases FACS: AllocateMaxAddress below 4GiB,
  // EfiACPIMemoryNVS pages, 64-byte alignment, no ACPI header/checksum.
  // It also updates FADT FirmwareCtrl and recalculates its checksum.
  Status = Protocol->InstallAcpiTable (Protocol, &Facs, sizeof (Facs), &Key);
  if (EFI_ERROR (Status)) { return Status; }
  Fadt = FindFadt ();
  if (!ValidFacs (Fadt)) { return EFI_COMPROMISED_DATA; }
  Print (L"ACPI FACS: %08x length=64 NVS via AcpiTableDxe\n", Fadt->FirmwareCtrl);
  return EFI_SUCCESS;
}
