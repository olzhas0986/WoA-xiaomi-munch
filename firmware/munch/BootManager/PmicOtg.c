// SPDX-License-Identifier: BSD-2-Clause-Patent
#include "PmicOtg.h"
#include <Library/UefiBootServicesTableLib.h>

// Call only after the PMIC ABI/code and absence of USB input power have
// been verified. Read reports the hardware OTG command bit, NOT the FSM.
EFI_STATUS MunchPmicOtgEnsureDisabled (MUNCH_OTG_ENABLE Enable, MUNCH_OTG_READ Read) {
  EFI_STATUS Status;
  BOOLEAN Enabled;
  UINTN Attempt;
  if (Enable == NULL || Read == NULL) { return EFI_INVALID_PARAMETER; }
  Enabled = TRUE;
  Status = Read (&Enabled);
  if (Status != EFI_SUCCESS) { return Status; }
  if (!Enabled) { return EFI_SUCCESS; }
  Status = Enable (FALSE);
  if (Status != EFI_SUCCESS) { return Status; }
  for (Attempt = 0; Attempt < 10; Attempt++) {
    gBS->Stall (100000);
    Enabled = TRUE;
    Status = Read (&Enabled);
    if (Status != EFI_SUCCESS) { return Status; }
    if (!Enabled) { return EFI_SUCCESS; }
  }
  return EFI_TIMEOUT;
}

// Wait only for removal of external USB power, never for a mouse/keyboard.
EFI_STATUS MunchPmicWaitUnpowered (MUNCH_OTG_READ Input, UINTN Attempts) {
  EFI_STATUS Status;
  BOOLEAN Powered;
  UINTN Attempt;
  if (Input == NULL || Attempts == 0 || Attempts > 100) { return EFI_INVALID_PARAMETER; }
  for (Attempt = 0; Attempt < Attempts; Attempt++) {
    Powered = TRUE;
    Status = Input (&Powered);
    if (Status != EFI_SUCCESS) { return Status; }
    if (!Powered) { return EFI_SUCCESS; }
    if (Attempt + 1 < Attempts) { gBS->Stall (100000); }
  }
  return EFI_NOT_READY;
}
