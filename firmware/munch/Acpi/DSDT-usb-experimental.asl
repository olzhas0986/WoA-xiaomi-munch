// SPDX-License-Identifier: BSD-2-Clause-Patent
// CPU namespace plus experimental DT-derived primary USB host description.
DefinitionBlock ("DSDT.aml", "DSDT", 2, "MUNCH ", "MUNCHCPU", 1)
{
    Scope (\_SB)
    {
        Device (XHC0)
        {
            Name (_HID, "PNP0D10")
            Name (_CID, "PNP0D10")
            Name (_UID, Zero)
            Name (_CCA, Zero) // DT does not advertise dma-coherent.
            Name (_STA, 0x0F)
            Name (_CRS, ResourceTemplate ()
            {
                Memory32Fixed (ReadWrite, 0x0A600000, 0x0000D93C)
                Interrupt (ResourceConsumer, Level, ActiveHigh, Exclusive) { 165 }
            })
            Device (RHUB)
            {
                Name (_ADR, Zero)
                Device (HS01)
                {
                    Name (_ADR, One)
                    Name (_UPC, Package () { 0xFF, 0x09, Zero, Zero })
                }
                Device (SS01)
                {
                    Name (_ADR, 2)
                    Name (_UPC, Package () { 0xFF, 0x09, Zero, Zero })
                }
            }
        }
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
