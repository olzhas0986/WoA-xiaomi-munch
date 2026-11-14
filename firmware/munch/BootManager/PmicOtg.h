// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef MUNCH_PMIC_OTG_H
#define MUNCH_PMIC_OTG_H
#include <Uefi.h>
typedef EFI_STATUS (EFIAPI *MUNCH_OTG_ENABLE)(BOOLEAN);
typedef EFI_STATUS (EFIAPI *MUNCH_OTG_READ)(BOOLEAN *);
EFI_STATUS MunchPmicOtgEnsureDisabled (MUNCH_OTG_ENABLE Enable, MUNCH_OTG_READ Read);
EFI_STATUS MunchPmicWaitUnpowered (MUNCH_OTG_READ Input, UINTN Attempts);
#endif
