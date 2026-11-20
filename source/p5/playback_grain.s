/* SPDX-License-Identifier: GPL-2.0-only */
/* Native Playback import and DISP parameter helpers from the six-slot baseline. */
.syntax unified
.arm
.text
.balign 4
.global grs_playback_import_grain
.type grs_playback_import_grain,%function
grs_playback_import_grain:
    ldr r3,[r4,#8]
    mov r2,#0
    cmp r3,#40
    blo import_store
    mov r0,r4
    mov r1,#19
    movw r12,#1236
    movt r12,#21341
    blx r12
    mov r2,#0
    cmp r0,#1
    moveq r2,#1
    cmp r0,#3
    moveq r2,#2
    cmp r0,#5
    moveq r2,#3
import_store:
    mov r0,r5
    mov r1,#140
    movw r12,#57448
    movt r12,#21339
    blx r12
    ldr r3,[r4,#8]
    ldr pc,=0x535c3e70
.ltorg
.balign 4
grain_callback:
    push {r4,lr}
    mov r4,r1
    movw r12,#44424
    movt r12,#21280
    blx r12
    movw r12,#47484
    movt r12,#21280
    blx r12
    cmp r0,#0
    beq no_photo_grain
    add r0,r0,#0x18c
    mov r1,#140
    movw r12,#57368
    movt r12,#21339
    blx r12
    b format_grain
no_photo_grain:
    mov r0,#0
format_grain:
    cmp r0,#3
    movwhi r3,#23112
    movthi r3,#21441
    movwls r3,#52696
    movtls r3,#21429
    ldrls r3,[r3,r0,lsl #2]
    mov r0,r4
    mov r1,#3
    movw r2,#11484
    movt r2,#21458
    movw r12,#4352
    movt r12,#21268
    blx r12
    movw r0,#478
    pop {r4,pc}
.ltorg
.balign 4
.global grs_playback_parameters
.type grs_playback_parameters,%function
grs_playback_parameters:
    sub r3,r2,#22
    cmp r3,#5
    bls custom_parameters
    cmp r2,#14
    ldr pc,=0x532b7d14
custom_parameters:
    mov r4,#0
    adr r5,parameter_callbacks
    ldr r6,[r11,#-0x100]
    ldr r7,[r11,#-0x104]
custom_parameter_loop:
    ldr r12,[r5,r4,lsl #2]
    mov r0,r9
    mov r1,r7
    blx r12
    strh r0,[r6]
    add r6,r6,#2
    add r7,r7,#3
    add r4,r4,#1
    cmp r4,#9
    bne custom_parameter_loop
    ldr pc,=0x532b8268
.ltorg
.balign 4
.global grs_playback_grain_row
.type grs_playback_grain_row,%function
grs_playback_grain_row:
    mrs r8,cpsr
    mov r10,r0
    movw r12,#44424
    movt r12,#21280
    blx r12
    movw r12,#47484
    movt r12,#21280
    blx r12
    cmp r0,#0
    beq grain_return
    add r0,r0,#0x18c
    mov r1,#37
    movw r12,#57368
    movt r12,#21339
    blx r12
    sub r0,r0,#1
    cmp r0,#17
    bhi grain_return
    ldrb r3,[r11,#-0xf5]
    sub r2,r3,#30
    cmp r2,#5
    bls grain_append
    cmp r3,#8
    beq grain_append
    cmp r3,#11
    beq grain_append
    cmp r3,#12
    beq grain_append
    cmp r3,#17
    beq grain_append
    sub r2,r3,#19
    cmp r2,#3
    bhi grain_return
grain_append:
    ldr r1,[r11,#-0x104]
    add r1,r1,#27
    bl grain_callback
    ldr r2,[r11,#-0x100]
    strh r0,[r2,#18]
grain_return:
    mov r0,r10
    msr cpsr_f,r8
    sub sp,r11,#40
    ldr pc,=0x532b8280
.ltorg
.balign 4
parameter_callbacks:
.word 0x532b5240,0x532b5288,0x532b52d0,0x532b5318,0x532b5360,0x532b53a8,0x532b53f0,0x532b55c0,0x532b5608
