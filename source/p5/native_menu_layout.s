/* SPDX-License-Identifier: GPL-2.0-only */
/* Layout extensions are valid only after the factory owner is ready. Preserve
 * conditions, flags and stock offsets on the allocation-failure path. */
.syntax unified
.arm
.text
.macro layout_reader site, before, after
.global grs_layout_\site
.type grs_layout_\site,%function
grs_layout_\site:
    push {r12}
    mrs r12,apsr
    push {r12}
    movw r12,#0x4374
    movt r12,#0x5580
    ldr r12,[r12]
    tst r12,#0x80000000
    beq 1f
    pop {r12}
    msr APSR_nzcvq,r12
    pop {r12}
    .inst \after
    ldr pc,=0x\site+4
1:
    pop {r12}
    msr APSR_nzcvq,r12
    pop {r12}
    .inst \before
    ldr pc,=0x\site+4
.size grs_layout_\site,.-grs_layout_\site
.ltorg
.endm
