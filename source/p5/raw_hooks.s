/* SPDX-License-Identifier: GPL-2.0-only */
.syntax unified
.arm
.text

.macro entry name
.balign 4
.global \name
.type \name,%function
\name:
.endm
.macro tail name
.size \name,.-\name
.ltorg
.endm

entry grs_public_to_raw
    sub r3,r1,#30
    cmp r3,#5
    addls r0,r3,#14
    bxls lr
    sub r1,r1,#11
    ldr pc,=0x53288d60
tail grs_public_to_raw

entry grs_raw_to_public
    sub r3,r1,#14
    cmp r3,#5
    addls r0,r3,#30
    bxls lr
    mov r12,sp
    ldr pc,=0x5328905c
tail grs_raw_to_public

entry grs_public_to_raw_menu
    sub r3,r1,#30
    cmp r3,#5
    movls r0,#0
    bxls lr
    sub r1,r1,#11
    ldr pc,=0x5318dea4
tail grs_public_to_raw_menu

entry grs_raw_select_guard
    cmp r1,#2
    movhi r1,#0
    cmp r2,#13
    moveq r2,#1
    cmp r2,#20
    movhs r2,#1
    add r12,r0,r1
    ldr pc,=0x53289308
tail grs_raw_select_guard

entry grs_raw_seed_tail
    push {r0-r12,lr}
    ldr r12,=0x5320ad88
    blx r12
    ldr r12,=0x5320b31c
    blx r12
    mov r1,r0
    mov r0,r5
    ldr r12,=GRS_SEED_RAW
    blx r12
    pop {r0-r12,lr}
    ldr r3,[r11,#-0x60]
    ldr pc,=0x5328903c
tail grs_raw_seed_tail

/* DNG Image Control tag 79. Golden slots use their six assigned file codes;
 * all factory modes still use the untouched native tag encoder. */
entry grs_dng_tone_write
    push {r3,r12}
    mrs r12,apsr
    ldrb r3,[r2,#0x77c]
    sub r3,r3,#30
    cmp r3,#5
    bhi 1f
    add r2,r3,#0x10c
    mov r0,r1
    mov r1,#0
    msr APSR_nzcvq,r12
    pop {r3,r12}
    ldr pc,=0x535d02c8
1:
    msr APSR_nzcvq,r12
    pop {r3,r12}
    ldr pc,=0x535c780c
tail grs_dng_tone_write

entry grs_dng_tone_read
    push {r3,r12}
    mrs r12,apsr
    sub r3,r0,#0x10c
    cmp r3,#5
    bhi 1f
    add r0,r3,#30
    msr APSR_nzcvq,r12
    pop {r3,r12}
    mov r3,r0
    ldr pc,=0x535bf7e4
1:
    msr APSR_nzcvq,r12
    pop {r3,r12}
    sub r0,r0,#0x100
    ldr pc,=0x535bf7c8
tail grs_dng_tone_read

/* DISP uses the six slot icon aliases for the tone stored in the photo.
 * The factory switch still handles its original tones. */
entry grs_playback_icon
    push {r12}
    mrs r12,apsr
    push {r12}
    sub r12,r3,#30
    cmp r12,#5
    bhi 1f
    movw r0,#677
    add r0,r0,r12
    pop {r12}
    msr APSR_nzcvq,r12
    pop {r12}
    ldr pc,=0x532b6f54
1:
    pop {r12}
    msr APSR_nzcvq,r12
    pop {r12}
    sub r3,r3,#8
    ldr pc,=0x532b6f38
tail grs_playback_icon
