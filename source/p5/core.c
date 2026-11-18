/* SPDX-License-Identifier: GPL-2.0-only */
/* Native Golden DomainData services; only two new 32-byte keys are written. */
#include "p4a.h"
static const char keys[2][16]={"GRS4A_ASG0","GRS4A_ASG1"};
static U crc(const void*raw,U bytes){
 const uint8_t*p=raw;U c=~0u;
 for(U i=0;i<bytes;i++){c^=p[i];for(U j=0;j<8;j++)c=(c>>1)^(0xedb88320u&(0u-(c&1)));}
 return ~c;
}
static void* store(void){
 void*(*get)(void)=(void*(*)(void))0x53828014u;U*r=get();
 if(!r||!r[2])return 0;return *(void**)r[2];
}
static int read_record(void*s,U index,struct journal*r){
 U(*size)(void*,const char*)=(U(*)(void*,const char*))0x53825834u;
 int(*read)(void*,const char*,U,void*)=(int(*)(void*,const char*,U,void*))0x53825648u;
 if(size(s,keys[index])!=sizeof(*r))return 0;
 for(U i=0;i<sizeof(*r);i++)((uint8_t*)r)[i]=0;
 if(!read(s,keys[index],sizeof(*r),r))return 0;
 if(r->magic!=0x31415347u||r->version!=1||r->bytes!=sizeof(*r)||r->reserved||r->crc!=crc(r,28))return 0;
 for(U i=0;i<6;i++)if(!lookup(r->ids[i])&&r->ids[i]!=27u)return 0;
 return 1;
}
/* Called at the existing settings-load completion seam, before Shooting.
 * No heap, SD reads, colour copies, directory scan or boot writes. */
int p4_load(void){
 if(ASSIGN->ready==1)return 1;
 if(!__sync_bool_compare_and_swap(&ASSIGN->busy,0,1))return 0;
 void*s=store();if(!s){ASSIGN->busy=0;return 0;}
 struct journal r[2];int a=read_record(s,0,&r[0]),b=read_record(s,1,&r[1]);
 U pick=(U)(b&&(!a||(int32_t)(r[1].sequence-r[0].sequence)>0));
 for(U i=0;i<6;i++)ASSIGN->ids[i]=(a||b)&&r[pick].ids[i]!=27u?r[pick].ids[i]:defaults[i];
 ASSIGN->sequence=(a||b)?r[pick].sequence:0;ASSIGN->which=(a||b)?pick:1;
 __sync_synchronize();ASSIGN->ready=1;__sync_synchronize();ASSIGN->busy=0;return 1;
}
U p4_assignment(U slot){const struct film*f=assigned(slot);return f?f->id:0;}
U p4_film(U slot){return (U)assigned(slot);}
U p4_lookup(U id){return(U)lookup(id);}
U p4_count(void){return COUNT;}
/* Write the inactive copy, read it back, then atomically publish one slot.
 * A torn record cannot destroy the last valid journal. */
int p4_assign(U slot,U id){
 if(slot>=6||!lookup(id)||!p4_load())return 0;
 if(!__sync_bool_compare_and_swap(&ASSIGN->busy,0,1))return 0;
 if(ASSIGN->ids[slot]==id){ASSIGN->busy=0;return 1;}
 void*s=store();if(!s){ASSIGN->busy=0;return 0;}
 struct journal r={0x31415347u,1,32,ASSIGN->sequence+1,{0},0,0},check;
 for(U i=0;i<6;i++)r.ids[i]=(uint16_t)ASSIGN->ids[i];r.ids[slot]=(uint16_t)id;r.crc=crc(&r,28);
 U target=ASSIGN->which^1u;
 int(*write)(void*,const char*,U,const void*)=(int(*)(void*,const char*,U,const void*))0x53825fa8u;
 int ok=write(s,keys[target],sizeof(r),&r)&&read_record(s,target,&check);
 for(U i=0;ok&&i<sizeof(r);i++)if(((uint8_t*)&r)[i]!=((uint8_t*)&check)[i])ok=0;
 if(ok){ASSIGN->which=target;ASSIGN->sequence=r.sequence;__sync_synchronize();ASSIGN->ids[slot]=id;__sync_synchronize();}
 ASSIGN->busy=0;return ok;
}
int p4_default(U slot){return slot<6?p4_assign(slot,defaults[slot]):0;}
/* Two bounded owner markers hold no colours. Eviction only causes a harmless
 * extra native refresh. The source context itself pins the immutable film. */
U p4_changed(U owner,U public){
 if(!__sync_bool_compare_and_swap(&ASSIGN->refresh_lock,0,1))return 1;
 U identity=public<<16;const struct film*f=public>=30&&public<=35?assigned(public-30):0;
 if(f)identity|=f->id;
 U ix=2;
 for(U i=0;i<2;i++)if(ASSIGN->seen[i].owner==owner){ix=i;break;}
 U changed=1;
 if(ix<2)changed=ASSIGN->seen[ix].identity!=identity;
 else {ix=ASSIGN->next;ASSIGN->next=ix^1u;}
 ASSIGN->seen[ix].owner=owner;ASSIGN->seen[ix].identity=identity;
 __sync_synchronize();ASSIGN->refresh_lock=0;return changed;
}

/* All defaults commit as one existing-format Assignment record. This does
 * not store Recipe data or repurpose any journal field. */
int p4_restore_all(void){if(!p4_load()||!__sync_bool_compare_and_swap(&ASSIGN->busy,0,1))return 0;void*s=store();if(!s){ASSIGN->busy=0;return 0;}
 struct journal r={0x31415347u,1,32,ASSIGN->sequence+1,{0},0,0},check;U changed=0;
 for(U i=0;i<6;i++){r.ids[i]=(uint16_t)defaults[i];if(ASSIGN->ids[i]!=defaults[i])changed=1;}if(!changed){ASSIGN->busy=0;return 1;}r.crc=crc(&r,28);U target=ASSIGN->which^1u;
 int(*write)(void*,const char*,U,const void*)=(int(*)(void*,const char*,U,const void*))0x53825fa8u;
 int ok=write(s,keys[target],sizeof(r),&r)&&read_record(s,target,&check);for(U i=0;ok&&i<sizeof(r);i++)if(((uint8_t*)&r)[i]!=((uint8_t*)&check)[i])ok=0;
 if(ok){ASSIGN->which=target;ASSIGN->sequence=r.sequence;for(U i=0;i<6;i++)ASSIGN->ids[i]=defaults[i];__sync_synchronize();}ASSIGN->busy=0;return ok;}
