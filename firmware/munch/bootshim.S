/* SPDX-License-Identifier: BSD-2-Clause-Patent
 * RAM boot shim: overlap-safe FD relocation, preserving ABL's x0/x1.
 * No disk operations or OS payload. FD is appended at the firmware label.
 */
.text
.global _start
_start:
  adr x20, firmware
  b relocate
  .quad FD_BASE
  .quad FD_SIZE + (firmware - _start)
  .quad 0
  .quad 0
  .quad 0
  .quad 0
  .ascii "ARM\x64"
  .long 0
relocate:
  ldr x21, =FD_BASE
  ldr x22, =FD_SIZE
  cmp x20, x21
  b.eq enter
  /* Refuse an output range that intersects the executing shim. */
  adr x23, _start
  add x24, x21, x22
  cmp x21, x20
  b.hs safe
  cmp x24, x23
  b.hi reject
safe:
  cmp x21, x20
  b.lo forward
  add x23, x20, x22
  cmp x21, x23
  b.hs forward
  add x20, x20, x22
  add x21, x21, x22
backward:
  ldp x23, x24, [x20, #-16]!
  stp x23, x24, [x21, #-16]!
  subs x22, x22, #16
  b.ne backward
  b enter
forward:
  ldp x23, x24, [x20], #16
  stp x23, x24, [x21], #16
  subs x22, x22, #16
  b.ne forward
enter:
  // Reset the reserved RAM logger after the source FD is no longer needed.
  ldr x23, =0xF0000000
  stp xzr, xzr, [x23]
  dsb sy
  ic iallu
  dsb sy
  isb
  ldr x5, =FD_BASE
  br x5
reject:
  wfe
  b reject
.ltorg
.balign 16
firmware:
