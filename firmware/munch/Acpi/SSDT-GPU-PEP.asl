// SPDX-License-Identifier: BSD-2-Clause-Patent
// Windows28: core PEP bring-up; CPU/system low power is disabled by the installer.
DefinitionBlock ("SSDT-GPU-PEP.aml", "SSDT", 2, "MUNCH ", "PEPCORE ", 1)
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
        Device (PEP0)
        {
            Name (_HID, "QCOM2519")
            Name (_CID, "PNP0D80")
            Name (_UID, Zero)
            Name (_STA, 0x0F)
            // Driver validates its full PnP hardware ID using this method.
            // The reference adds PEPH in a separate Scope (\_SB.PEP0).
            Method (PEPH, 0, NotSerialized)
            {
                Return (Package () { "ACPI\\VEN_QCOM&DEV_2519" })
            }
            // No old IPCC HID or invented placeholder dependency is exposed.
            Method (_CRS, 0, NotSerialized)  // _CRS: Current Resource Settings
            {
                Return (ResourceTemplate ()
                {
                    Interrupt (ResourceConsumer, Level, ActiveHigh, ExclusiveAndWake, ,, )
                    {
                        0x0000021A,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, ExclusiveAndWake, ,, )
                    {
                        0x0000021C,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, ExclusiveAndWake, ,, )
                    {
                        0x0000021B,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, ExclusiveAndWake, ,, )
                    {
                        0x0000021D,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, Exclusive, ,, )
                    {
                        0x00000025,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, Exclusive, ,, )
                    {
                        0x0000003E,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, Exclusive, ,, )
                    {
                        0x0000003F,
                    }
                    Interrupt (ResourceConsumer, Level, ActiveHigh, Exclusive, ,, )
                    {
                        0x00000033,
                    }
                    Interrupt (ResourceConsumer, Edge, ActiveHigh, Exclusive, ,, )
                    {
                        0x00000265,
                    }
                    Interrupt (ResourceConsumer, Edge, ActiveHigh, Exclusive, ,, )
                    {
                        0x0000010D,
                    }
                    Interrupt (ResourceConsumer, Edge, ActiveHigh, Exclusive, ,, )
                    {
                        0x00000113,
                    }
                })
            }
            Method (INTR, 0, NotSerialized)
            {
                Name (RBUF, Package (0x18)
                {
                    0x02, 
                    One, 
                    0x03, 
                    One, 
                    0x06, 
                    0x17911008, 
                    One, 
                    Zero, 
                    0x86000000, 
                    0x00200000, 
                    Zero, 
                    Zero, 
                    0x0C300000, 
                    0x1000, 
                    Zero, 
                    Zero, 
                    0x01FD4000, 
                    0x08, 
                    Zero, 
                    Zero, 
                    0x17C0000C, 
                    Zero, 
                    Zero, 
                    Zero
                })
                Return (RBUF) /* \_SB_.PEP0.INTR.RBUF */
            }
            Method (GEPT, 0, NotSerialized)
            {
                Name (BUFF, Buffer (0x04){})
                CreateByteField (BUFF, Zero, STAT)
                CreateWordField (BUFF, 0x02, DATA)
                DATA = One
                Return (DATA) /* \_SB_.PEP0.GEPT.DATA */
            }
            // Native Idle_CoreTopology loader requires this typed package.
            // Eight physical cores match the captured DT and MADT CPU UIDs.
            Method (CTPM, 0, NotSerialized)
            {
                Return (Package () { "CORE_TOPOLOGY", 0x08 })
            }
            // Native reference defaults for optional initial queries.
            Method (PGDS, 0, NotSerialized) { Return (Zero) }
            Method (FPMD, 0, NotSerialized) { Return (Zero) }
            Method (PPRR, 0, NotSerialized) { Return (Package () {}) }
        }
    }
}
