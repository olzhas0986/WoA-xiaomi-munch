// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef MUNCH_RAM_LOG_H
#define MUNCH_RAM_LOG_H
#include <Uefi.h>
#define LOG_CAPACITY (0x100000 - 16)
#define LOG_MAGIC 0x4D554E43484C4F47ULL
typedef struct { UINT64 Magic; UINT64 Total; UINT8 Data[LOG_CAPACITY]; } MUNCH_LOG;
#define RAM_LOG ((volatile MUNCH_LOG *)(UINTN)0xF0000000)
STATIC VOID RamLogAppend (CONST UINT8 *Data, UINTN Size) {
  UINTN Index;
  if (RAM_LOG->Magic != LOG_MAGIC) { RAM_LOG->Total = 0; RAM_LOG->Magic = LOG_MAGIC; }
  for (Index = 0; Index < Size; Index++) {
    RAM_LOG->Data[RAM_LOG->Total % LOG_CAPACITY] = Data[Index];
    RAM_LOG->Total++;
  }
}
#endif
