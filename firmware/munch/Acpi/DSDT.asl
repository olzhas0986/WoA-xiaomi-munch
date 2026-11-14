// SPDX-License-Identifier: BSD-2-Clause-Patent
// Stable WinPE CPU namespace; USB ACPI experiment is disabled.
DefinitionBlock ("DSDT.aml", "DSDT", 2, "MUNCH ", "MUNCHCPU", 1)
{
    Scope (\_SB)
    {
        Device (CPU0) { Name (_HID, "ACPI0007") Name (_UID, 0) }
        Device (CPU1) { Name (_HID, "ACPI0007") Name (_UID, 1) }
        Device (CPU2) { Name (_HID, "ACPI0007") Name (_UID, 2) }
        Device (CPU3) { Name (_HID, "ACPI0007") Name (_UID, 3) }
        Device (CPU4) { Name (_HID, "ACPI0007") Name (_UID, 4) }
        Device (CPU5) { Name (_HID, "ACPI0007") Name (_UID, 5) }
        Device (CPU6) { Name (_HID, "ACPI0007") Name (_UID, 6) }
        Device (CPU7) { Name (_HID, "ACPI0007") Name (_UID, 7) }
    }
}
