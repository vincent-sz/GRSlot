/* SPDX-License-Identifier: GPL-2.0-only */
.syntax unified
.arm
.text

.global grs_measure_name
.type grs_measure_name,%function
grs_measure_name:
    push {r0-r3,r12,lr}
    mov r1,r0
    mov r0,r7
    ldr r12,=GRS_COMMON_TEXT
    blx r12
    cmp r0,#0
    beq 1f
    mov r7,r0
    pop {r0-r3,r12,lr}
    mov r9,r0
    sub r8,r11,#176
    mov r0,r8
    ldr pc,=0x53396700
1:
    pop {r0-r3,r12,lr}
    movw r3,#785
    ldr pc,=0x533966d8
.size grs_measure_name,.-grs_measure_name
.ltorg

.global grs_draw_name
.type grs_draw_name,%function
grs_draw_name:
    push {r0-r2,r12,lr}
    sub sp,sp,#4
    mov r1,r0
    mov r0,r7
    ldr r12,=GRS_COMMON_TEXT
    blx r12
    cmp r0,#0
    beq 1f
    mov r3,r0
    add sp,sp,#4
    pop {r0-r2,r12,lr}
    ldr pc,=0x5339710c
1:
    add sp,sp,#4
    pop {r0-r2,r12,lr}
    movw r3,#785
    ldr pc,=0x533970f0
.size grs_draw_name,.-grs_draw_name
.ltorg
