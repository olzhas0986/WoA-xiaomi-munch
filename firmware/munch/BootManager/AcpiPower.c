// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Guid/Acpi.h>
#include <IndustryStandard/Acpi60.h>
#include <Protocol/AcpiTable.h>
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

EFI_STATUS MunchAcpiPowerPrepare (VOID) {
  EFI_ACPI_TABLE_PROTOCOL *Protocol;
  EFI_ACPI_6_0_FIXED_ACPI_DESCRIPTION_TABLE *Fadt;
  EFI_ACPI_6_0_FIRMWARE_ACPI_CONTROL_STRUCTURE Facs;
  EFI_STATUS Status;
  UINTN Key;
  Fadt = FindFadt ();
  if (Fadt == NULL) { return EFI_NOT_FOUND; }
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
