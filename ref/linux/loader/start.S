.section .text.boot, "ax"
.global _start
_start:
 b entry
 .long 0
 .quad 0                         // text_offset
 .quad __end - _start           // includes BSS and stack
 .quad 0xa                      // LE, 4K, arbitrary 2M-aligned placement
 .quad 0, 0, 0
 .long 0x644d5241
 .long 0
entry:
 msr daifset, #15
 mrs x1, CurrentEL
 cmp x1, #4
 b.ne stop                      // no EL2/EL3 register access or transitions
 mrs x2, sctlr_el1
 tbnz x2, #0, stop              // cannot safely disable unknown mappings
 tbnz x2, #2, stop              // reject inherited dirty D-cache state
 msr spsel, #1
 adr x3, __stack_top
 mov sp, x3
 adr x3, vectors
 msr vbar_el1, x3
 isb
 adr x3, __bss_start
 adr x4, __bss_end
1: cmp x3, x4
 b.hs 2f
 str xzr, [x3], #8
 b 1b
2: bl loader_main               // x0 is bootloader DTB; diagnostic only
stop:
 wfe
 b stop
.balign 2048
vectors:
.rept 16
 b exception
 .balign 128
.endr
exception:
 mrs x0, esr_el1
 mrs x1, elr_el1
 mrs x2, far_el1
 bl loader_exception
 b stop
.global kernel_enter
kernel_enter:                   // x0=DTB, x1=entry
 mov x4, x1
 mov x1, xzr
 mov x2, xzr
 mov x3, xzr
 msr daifset, #15
 dsb sy
 ic iallu
 dsb sy
 isb
 br x4
.section .note.GNU-stack,"",%progbits
