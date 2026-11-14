// SPDX-License-Identifier: BSD-2-Clause-Patent
// Windows26: retain SCM/RPEN/SPMI and enumerate the core PMIC interface.
DefinitionBlock ("SSDT-GPU-PMIC.aml", "SSDT", 2, "MUNCH ", "COREPMIC", 1)
{
    Scope (\_SB)
    {
        Device (SCM0)
        {
            Name (_HID, "QCOM250B")
            Name (_UID, Zero)
            Name (_STA, 0x0F)
        }
        Device (RPEN)
        {
            Name (_HID, "QCOM2533")
            Name (_UID, Zero)
            Name (_STA, 0x0F)
        }
        Device (SPMI)
        {
            // Kona qcspmi8250.inf: this is not the older alioth SPMI ID.
            Name (_HID, "QCOM250C")
            Name (_CID, "PNP0CA2")
            Name (_UID, One)
            Name (_CCA, Zero)
            Name (_STA, 0x0F)
            Name (_CRS, ResourceTemplate ()
            {
                Memory32Fixed (ReadWrite, 0x0C400000, 0x02800000)
            })
            // Native Kona bus configuration, byte-identical in alioth/nabu.
            // It is a vendor ABI buffer; do not reinterpret its unknown fields.
            Method (CONF, 0, NotSerialized)
            {
                Return (Buffer (0x1A)
                {
                    0x00, 0x01, 0x01, 0x01, 0xFF, 0x00, 0x02, 0x00,
                    0x0A, 0x07, 0x04, 0x07, 0x01, 0xFF, 0x10, 0x01,
                    0x00, 0x01, 0x0C, 0x40, 0x00, 0x00, 0x02, 0x80,
                    0x00, 0x00
                })
            }
        }
        Device (PMIC)
        {
            Name (_HID, "QCOM252E")
            Name (_CID, "PNP0CA3")
            Name (_STA, 0x0F)
            Name (_DEP, Package () { \_SB.SPMI })
            // Core PM8150 / PM8150B / PM8150L, present in the captured DT.
            // Native three-pair ABI as used by the nabu Kona reference.
            // Camera/modem PMICs are outside this initial core-driver test.
            Method (PMCF, 0, NotSerialized)
            {
                Return (Package ()
                {
                    3,
                    Package () { 0, 1 },
                    Package () { 2, 3 },
                    Package () { 4, 5 }
                })
            }
        }
    }
}
