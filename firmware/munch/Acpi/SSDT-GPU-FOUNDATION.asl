// SPDX-License-Identifier: BSD-2-Clause-Patent
// Kona BSP foundation stage: enumerate the real SCM interface only.
// This does not enable the graphics miniport, DMA or board power resources.
DefinitionBlock ("SSDT-GPU-FOUNDATION.aml", "SSDT", 2, "MUNCH ", "SCMBOOT ", 1)
{
    Scope (\_SB)
    {
        Device (SCM0)
        {
            Name (_HID, "QCOM250B")
            Name (_UID, Zero)
            Name (_STA, 0x0F)
        }
    }
}
