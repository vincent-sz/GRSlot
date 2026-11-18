/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdint.h>
typedef uint32_t U;
struct film {
 U id;
 const char *name;
 const U *textdesc;
 U icon;
 const void *basis,*aux,*m1,*gamma,*m2;
};
#include "film_bank.h"
#define COUNT (sizeof(films)/sizeof(films[0]))
struct journal { U magic;uint16_t version,bytes;U sequence;uint16_t ids[6];U reserved,crc; };
struct assignments {
 U ready,busy,sequence,which;
 U ids[6];
 U refresh_lock,next;
 struct {U owner,identity;} seen[2];
};
#define ASSIGN ((volatile struct assignments*)0x55804384u)
_Static_assert(sizeof(struct journal)==32,"record layout");
_Static_assert(sizeof(struct assignments)<=0xbc,"reserved BSS");
static const struct film* lookup(U id){for(U i=0;i<COUNT;i++)if(films[i].id==id)return &films[i];return 0;}
static const struct film* assigned(U slot){
 if(slot>=6)return 0;
 U id=defaults[slot];
 if(ASSIGN->ready==1){__sync_synchronize();id=ASSIGN->ids[slot];}
 const struct film*f=lookup(id);return f?f:lookup(defaults[slot]);
}
