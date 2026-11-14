// SPDX-License-Identifier: BSD-2-Clause-Patent
// Windows24: retain the device-tested SCM node and add the BSP RPEN service.
// RPEN has no MMIO/interrupt resources in the Kona reference namespace.
// GPU/PEP/SMMU enumeration is deliberately deferred until their contracts exist.
DefinitionBlock ("SSDT-GPU-RPEN.aml", "SSDT", 2, "MUNCH ", "SCMRPEN ", 1)
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
    }
}
