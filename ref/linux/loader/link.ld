ENTRY(_start)
PHDRS { text PT_LOAD FLAGS(5); ro PT_LOAD FLAGS(4); data PT_LOAD FLAGS(6); }
SECTIONS {
 . = 0;
 .text : { KEEP(*(.text.boot)) *(.text*) } :text
 . = ALIGN(4096);
 .rodata : { *(.rodata*) } :ro
 . = ALIGN(4096);
 .data : { *(.data*) } :data
 .got : { *(.got*) } :data
 ASSERT(SIZEOF(.got) == 0, "absolute GOT entries break relocation")
 . = ALIGN(16);
 __bss_start = .;
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } :data
 . = ALIGN(16); __bss_end = .;
 . += 16384; __stack_top = .;
 . = ALIGN(4096); __end = .;
 ASSERT(__end <= 0x100000, "loader overlaps payload")
 /DISCARD/ : { *(.comment*) *(.note*) *(.eh_frame*) }
}
