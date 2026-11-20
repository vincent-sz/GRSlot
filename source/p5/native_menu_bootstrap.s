/* SPDX-License-Identifier: GPL-2.0-only */
/* Keep the factory arguments and flags while setting up the owned tables. */
.syntax unified
.arm
.text
.global grs_menu_bootstrap
.type grs_menu_bootstrap,%function
grs_menu_bootstrap:
    push {r0-r3,r12,lr}
    mrs r2,apsr
    push {r2,r3}
    ldr r0,=GRS_SELECT
    ldr r1,=GRS_SUBMENU
    ldr r12,=GRS_PUBLISH
    blx r12
    pop {r2,r3}
    msr APSR_nzcvq,r2
    pop {r0-r3,r12,lr}
    ldr pc,=GRS_RESUME
.size grs_menu_bootstrap,.-grs_menu_bootstrap
.ltorg
