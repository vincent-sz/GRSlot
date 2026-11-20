/* SPDX-License-Identifier: GPL-2.0-only */
/* Factory continuations for the linked Assignment and RGB modules. */
.syntax unified
.arm
.text

.global grs_processing_index
.type grs_processing_index,%function
grs_processing_index:
    push {r3,r12}
    mrs r3,apsr
    sub r12,r2,#30
    cmp r12,#5
    bhi 1f
    add r1,r12,#26
    ldr r0,=GRS_PROCESSING_BASIS
    msr APSR_nzcvq,r3
    pop {r3,r12}
    ldr r12,=GRS_PROCESSING_DESCRIPTORS
    ldr pc,=0x536dc29c
1:
    msr APSR_nzcvq,r3
    pop {r3,r12}
    movw r0,#0x8d94
    ldr pc,=0x536dc290
.size grs_processing_index,.-grs_processing_index
.ltorg

.global grs_processing_aux
.type grs_processing_aux,%function
grs_processing_aux:
    push {r3,r12}
    mrs r3,apsr
    sub r12,r2,#30
    cmp r12,#5
    bhi 1f
    ldr r0,=GRS_PROCESSING_AUX
    msr APSR_nzcvq,r3
    pop {r3,r12}
    ldr pc,=0x536dc2ac
1:
    msr APSR_nzcvq,r3
    pop {r3,r12}
    movw r0,#0x8e4c
    ldr pc,=0x536dc2a8
.size grs_processing_aux,.-grs_processing_aux
.ltorg

.global grs_colour_converter
.type grs_colour_converter,%function
grs_colour_converter:
    cmp r2,#30
    blo 1f
    cmp r2,#35
    bhi 1f
    cmp r2,r2  /* Factory Standard takes the equal branch. */
    ldr pc,=0x536dbaa4
1:
    cmp r2,#11  /* Displaced factory instruction. */
    ldr pc,=0x536db800
.size grs_colour_converter,.-grs_colour_converter
.ltorg

.global grs_grain_enable
.type grs_grain_enable,%function
grs_grain_enable:
    push {r12,lr}
    mrs r12,apsr
    sub r2,r3,#30
    cmp r2,#5
    bhi 1f
    msr APSR_nzcvq,r12
    pop {r12,lr}
    ldr pc,=0x53513240
1:
    msr APSR_nzcvq,r12
    pop {r12,lr}
    sub r2,r3,#17
    ldr pc,=0x535131f0
.size grs_grain_enable,.-grs_grain_enable
.ltorg

.global grs_grain_prepare
.type grs_grain_prepare,%function
grs_grain_prepare:
    push {r0,r12}
    mrs r12,apsr
    ldrb r0,[r3,#0x77c]
    sub r0,r0,#30
    cmp r0,#5
    ldrbls r6,[r3,#0x795]
    msr APSR_nzcvq,r12
    pop {r0,r12}
    strb r6,[r3,#0x795]
    ldr pc,=0x536db9cc
.size grs_grain_prepare,.-grs_grain_prepare
.ltorg

.global grs_native_slot_count
.type grs_native_slot_count,%function
grs_native_slot_count:
    bhi 1f
    cmp r3,#0
    moveq r0,#18
    movne r0,#12
    ldr pc,=0x532c2ad4
1:
    ldr pc,=0x532c2b4c
.size grs_native_slot_count,.-grs_native_slot_count
.ltorg

.macro map_slot symbol,first,last,operation,continuation
.global \symbol
.type \symbol,%function
\symbol:
    cmp r1,#\first
    blo 1f
    cmp r1,#\last
    bhi 1f
    ldrb r12,[r0,#0x1b]
    cmp r12,#0
    bne 1f
    push {r0-r3,r12,lr}
    ldr r12,=0x532bd6d4
    blx r12
    cmp r0,#2
    pop {r0-r3,r12,lr}
    bhi 1f
    \operation r0,r1,#18
    bx lr
1:
    mov r12,sp  /* Factory function prologue. */
    ldr pc,=\continuation
.size \symbol,.-\symbol
.ltorg
.endm

map_slot grs_native_slot_forward,12,17,add,0x532c2c84
map_slot grs_native_slot_reverse,30,35,sub,0x532c2f0c

.macro icon_size symbol,continuation
.global \symbol
.type \symbol,%function
\symbol:
    movw r3,#677
    sub r3,r1,r3
    cmp r3,#5
    movls r0,#40
    bxls lr
    movw r3,#670
    ldr pc,=\continuation
.size \symbol,.-\symbol
.ltorg
.endm

icon_size grs_icon_width,0x53209fbc
icon_size grs_icon_height,0x53209ff0

.global grs_icon_draw_limit
.type grs_icon_draw_limit,%function
grs_icon_draw_limit:
    push {r0,r12}
    mrs r12,apsr
    movw r0,#677
    sub r0,r3,r0
    cmp r0,#5
    movls r1,r3
    movwhi r1,#670
    msr APSR_nzcvq,r12
    pop {r0,r12}
    ldr pc,=0x5320a7d0
.size grs_icon_draw_limit,.-grs_icon_draw_limit
.ltorg

.global grs_icon_token
.type grs_icon_token,%function
grs_icon_token:
    movw r2,#677
    sub r2,r3,r2
    cmp r2,#5
    bhi 1f
    /* LR is the caller's pixel origin at this native seam. */
    push {r0-r2,r4-r12,lr}
    sub sp,sp,#4
    mov r0,r3
    ldr r12,=GRS_ICON
    blx r12
    mov r3,r0
    add sp,sp,#4
    pop {r0-r2,r4-r12,lr}
    ldr r2,=0x550020fc
    cmp lr,#0
    ldr pc,=0x5320a814
1:
    ldr r2,=0x550020fc
    cmp lr,#0
    ldr r3,[r2,r3,lsl #2]
    ldr pc,=0x5320a814
.size grs_icon_token,.-grs_icon_token
.ltorg

.global grs_icon_blit
.type grs_icon_blit,%function
grs_icon_blit:
    push {r0-r3,r12,lr}
    mrs r12,apsr
    push {r12,lr}
    ldr r0,[sp,#48]
    ldr r1,=GRS_ICON_DESCRIPTORS
    cmp r0,r1
    blo 1f
    sub r0,r0,r1
    tst r0,#7
    bne 1f
    lsr r0,r0,#3
    cmp r0,#GRS_FILM_COUNT
    bhs 1f
    ldr r1,=GRS_ICON_PIXELS
    ldr r2,[r1,r0,lsl #2]
    str r2,[sp,#52]
1:
    pop {r12,lr}
    msr APSR_nzcvq,r12
    pop {r0-r3,r12,lr}
    mov r12,sp
    ldr pc,=0x5320a024
.size grs_icon_blit,.-grs_icon_blit
.ltorg

.macro shooting_token symbol,icon,stock,continuation
.global \symbol
.type \symbol,%function
\symbol:
    push {r0-r3,r12,lr}
    mrs r0,apsr
    push {r0,lr}
    mov r0,r1
    mov r1,#\icon
    ldr r12,=GRS_RESOURCE_OVERRIDE
    blx r12
    cmp r0,#0
    beq 1f
    str r0,[sp,#8]
    pop {r0,lr}
    msr APSR_nzcvq,r0
    pop {r0-r3,r12,lr}
    bx lr
1:
    pop {r0,lr}
    msr APSR_nzcvq,r0
    pop {r0-r3,r12,lr}
    .word \stock
    ldr pc,=\continuation
.size \symbol,.-\symbol
.ltorg
.endm

shooting_token grs_shoot_name,0,0xe1a0c00d,0x532a9860
shooting_token grs_list_name,0,0xe351000a,0x532922b8
shooting_token grs_shoot_icon,1,0xe1a0c00d,0x532a998c
shooting_token grs_list_icon,1,0xe351000a,0x532935e0

.global grs_colour_source
.type grs_colour_source,%function
grs_colour_source:
    push {r0-r3,r12,lr}
    mrs r0,apsr
    push {r0,lr}
    ldrb r0,[r7,#0x77c]
    sub r0,r0,#30
    cmp r0,#5
    bhi 1f
    ldr r1,[r4,#8]
    ldr r12,=GRS_NATIVE_FILM
    blx r12
    cmp r0,#0
    beq 1f
    ldr r1,[r0,#16]
    str r1,[r4,#8]
    ldr r1,[r0,#20]
    str r1,[r4,#24]
    ldr r1,=0x53dc2ba0
    str r1,[r4,#12]
1:
    pop {r0,lr}
    msr APSR_nzcvq,r0
    pop {r0-r3,r12,lr}
    .word 0x130f15ec  /* Displaced factory instruction. */
    ldr pc,=0x536dc2cc
.size grs_colour_source,.-grs_colour_source
.ltorg

.global grs_gamma_gate
.type grs_gamma_gate,%function
grs_gamma_gate:
    push {r0-r2,r12}
    mrs r12,apsr
    ldr r0,[r4,#24]
    ldr r1,=GRS_CURVE_TABLE
    mov r2,#GRS_FILM_COUNT
1:
    ldr r3,[r1],#16
    cmp r0,r3
    beq 2f
    subs r2,r2,#1
    bne 1b
    ldrb r3,[r4,#0x9b]  /* Displaced factory instruction. */
    b 3f
2:
    mov r3,#1
3:
    msr APSR_nzcvq,r12
    pop {r0-r2,r12}
    ldr pc,=0x536e8698
.size grs_gamma_gate,.-grs_gamma_gate
.ltorg

.global grs_gamma_getter
.type grs_gamma_getter,%function
grs_gamma_getter:
    push {r4-r8,lr}
    mrs r8,apsr
    ldr r4,[r4,#24]
    ldr r5,=GRS_CURVE_TABLE
    mov r6,#GRS_FILM_COUNT
1:
    ldr r7,[r5]
    cmp r4,r7
    beq 2f
    add r5,r5,#16
    subs r6,r6,#1
    bne 1b
    msr APSR_nzcvq,r8
    pop {r4-r8,lr}
    ldr pc,=0x536eedf0  /* Original target of the factory BL. */
2:
    ldr r7,[r5,#4]
    str r7,[r1]
    ldr r7,[r5,#8]
    str r7,[r2]
    ldr r7,[r5,#12]
    str r7,[r3]
    mov r7,#0
    strb r7,[r0]
    msr APSR_nzcvq,r8
    pop {r4-r8,pc}
.size grs_gamma_getter,.-grs_gamma_getter
.ltorg

.global grs_colour_refresh
.type grs_colour_refresh,%function
grs_colour_refresh:
    push {r0-r2,r12,lr}
    mrs r0,apsr
    push {r0,r3,lr}
    mov r0,r4
    ldr r1,[r11,#-52]
    ldr r12,=GRS_CHANGED
    blx r12
    pop {r1,r3,lr}
    orr r3,r3,r0
    str r3,[r11,#-0xcc]  /* Displaced factory instruction. */
    msr APSR_nzcvq,r1
    pop {r0-r2,r12,lr}
    ldr pc,=0x536dcb84
.size grs_colour_refresh,.-grs_colour_refresh
.ltorg

.global grs_boot_assignments
.type grs_boot_assignments,%function
grs_boot_assignments:
    push {r0-r12,lr}
    mrs r0,apsr
    push {r0,lr}
    ldr r12,=GRS_LOAD
    blx r12
    ldr r12,=GRS_PARAMETER_RESTORE
    blx r12
    pop {r0,lr}
    msr APSR_nzcvq,r0
    pop {r0-r12,lr}
    sub sp,r11,#40  /* Displaced factory instruction. */
    ldr pc,=0x5324b430
.size grs_boot_assignments,.-grs_boot_assignments
.ltorg
