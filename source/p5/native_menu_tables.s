/* SPDX-License-Identifier: GPL-2.0-only */
/* Redirect the native descriptor readers only after the menu owner publishes
 * both tables. Otherwise execute the same MOVT as the factory instruction. */
.syntax unified
.arm
.text

.macro table_reader site, reg, pointer
.global grs_table_\site
.type grs_table_\site,%function
grs_table_\site:
    push {r12}
    mrs r12,apsr
    push {r12}
    movw r12,#0x4374
    movt r12,#0x5580
    ldr r12,[r12]
    tst r12,#0x80000000
    beq 1f
    movw r12,#\pointer
    movt r12,#0x5580
    ldr r12,[r12]
    cmp r12,#0
    movne \reg,r12
    bne 2f
1:
    movt \reg,#0x53b3
2:
    pop {r12}
    msr APSR_nzcvq,r12
    pop {r12}
    ldr pc,=0x\site+4
.size grs_table_\site,.-grs_table_\site
.endm

table_reader 531b9fe8,r4,0x4378
table_reader 531ba158,r3,0x4378
table_reader 531ba1a4,r4,0x4378
table_reader 531ba250,r3,0x4378
table_reader 531ba2b4,r3,0x4378
table_reader 531ba4c4,r3,0x4378
table_reader 531ba524,r4,0x4378
table_reader 531ba64c,r3,0x4378
table_reader 531ba804,r5,0x4378
table_reader 531ba9a8,r3,0x4378
table_reader 531baa68,r3,0x4378
table_reader 531bab44,r3,0x4378
table_reader 531bdfc8,r3,0x4378
table_reader 531be08c,r8,0x4378
table_reader 531be404,r3,0x4378
table_reader 531c5d20,r3,0x437c
table_reader 531c5d88,r2,0x437c
table_reader 531c60f4,r8,0x437c
table_reader 531c631c,r5,0x437c
table_reader 531c63f0,r3,0x437c
.ltorg
