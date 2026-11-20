/* SPDX-License-Identifier: GPL-2.0-only */
/* Six native UserData tails. Factory UserData layout and field order stay intact. */
enum {GOLDEN_USERDATA_BASE=0xb28,GOLDEN_SLOTS=6,GOLDEN_GROUPS=3,GOLDEN_FIELDS=10};
enum {GOLDEN_VALUES=GOLDEN_SLOTS*GOLDEN_GROUPS*GOLDEN_FIELDS};
#define GOLDEN_CURRENT ((void*)0x55063f30u)
static const uint8_t golden_field_index[16]={0,1,2,3,4,5,6,255,255,255,255,255,255,7,8,9};
static const char parameter_keys[2][16]={"GRS2P_PARAM0","GRS2P_PARAM1"};
struct parameter_record {U magic,sequence;uint8_t values[GOLDEN_VALUES];U checksum;};
_Static_assert(sizeof(struct parameter_record)==192,"Golden parameter record layout");

static uint8_t* parameter_tail(void*owner){
 if(!owner)return 0;
 uint8_t*data=*(uint8_t**)((uint8_t*)owner+4);
 return data?data+GOLDEN_USERDATA_BASE:0;
}

static uint8_t* golden_parameter(void*owner,U group,U field,U slot){
 if(!owner||group>=GOLDEN_GROUPS||field>=sizeof(golden_field_index)||slot>=GOLDEN_SLOTS)return 0;
 U index=golden_field_index[field];
 if(index>=GOLDEN_FIELDS)return 0;
 uint8_t*tail=parameter_tail(owner);
 return tail?tail+2*((slot*GOLDEN_GROUPS+group)*GOLDEN_FIELDS+index):0;
}

static int parameter_read(void*domain,U index,struct parameter_record*out){
 U(*size)(void*,const char*)=(U(*)(void*,const char*))0x53825834u;
 int(*read)(void*,const char*,U,void*)=(int(*)(void*,const char*,U,void*))0x53825648u;
 const char*key=parameter_keys[index];
 if(size(domain,key)!=sizeof(*out)||!read(domain,key,sizeof(*out),out))return 0;
 if(out->magic!=0x31505347u||out->checksum!=crc(out,sizeof(*out)-4))return 0;
 for(U i=0;i<GOLDEN_VALUES;i++)if(out->values[i]>(i%GOLDEN_FIELDS==GOLDEN_FIELDS-1?3u:8u))return 0;
 return 1;
}

/* Return 2 when neither journal copy validates. */
static U parameter_pick(void*domain,struct parameter_record records[2]){
 int first=parameter_read(domain,0,&records[0]);
 int second=parameter_read(domain,1,&records[1]);
 if(second&&(!first||(int32_t)(records[1].sequence-records[0].sequence)>0))return 1;
 return first?0u:2u;
}

static int parameter_commit(uint8_t*tail,uint8_t*parameter,U value){
 void*domain=store();if(!domain)return 0;
 struct parameter_record records[2],next,readback;
 U previous=parameter_pick(domain,records);
 U index=previous<2?previous^1u:0u;
 next.magic=0x31505347u;
 next.sequence=previous<2?records[previous].sequence+1:1;
 for(U i=0;i<GOLDEN_VALUES;i++)next.values[i]=tail[2*i];
 next.values[(U)(parameter-tail)/2]=(uint8_t)value;
 next.checksum=crc(&next,sizeof(next)-4);
 int(*write)(void*,const char*,U,const void*)=(int(*)(void*,const char*,U,const void*))0x53825fa8u;
 if(!write(domain,parameter_keys[index],sizeof(next),&next)||!parameter_read(domain,index,&readback))return 0;
 const uint8_t*actual=(const uint8_t*)&readback;
 const uint8_t*expected=(const uint8_t*)&next;
 for(U i=0;i<sizeof(next);i++)if(actual[i]!=expected[i])return 0;
 return 1;
}

int grs_parameter_get(void*owner,U group,U field,U slot){
 const uint8_t*parameter=golden_parameter(owner,group,field,slot);
 return parameter?*parameter:-1;
}

/* route is an internal ARM handoff: low byte group, next byte field. */
int grs_parameter_set(void*owner,U route,U value,U slot){
 U field=route>>8;
 if(value>(field==15u?3u:8u))return 0;
 uint8_t*parameter=golden_parameter(owner,route&255u,field,slot);
 if(!parameter)return 0;
 if(owner!=GOLDEN_CURRENT){*parameter=(uint8_t)value;return 1;}
 if(!__sync_bool_compare_and_swap(&ASSIGN->parameter_busy,0,1))return 0;
 int ok=*parameter==value||parameter_commit(parameter_tail(owner),parameter,value);
 if(ok)*parameter=(uint8_t)value;
 __sync_synchronize();ASSIGN->parameter_busy=0;
 return ok;
}

void grs_parameter_restore_current(void){
 uint8_t*tail=parameter_tail(GOLDEN_CURRENT);
 if(!tail||!__sync_bool_compare_and_swap(&ASSIGN->parameter_busy,0,1))return;
 void*domain=store();
 if(domain){
  struct parameter_record records[2];
  U index=parameter_pick(domain,records);
  if(index<2)for(U i=0;i<GOLDEN_VALUES;i++)tail[2*i]=records[index].values[i];
 }
 __sync_synchronize();ASSIGN->parameter_busy=0;
}

void grs_parameter_seed(void*data){
 if(!data)return;
 uint16_t*rows=(uint16_t*)((uint8_t*)data+GOLDEN_USERDATA_BASE);
 for(U group=0;group<GOLDEN_SLOTS*GOLDEN_GROUPS;group++){
  for(U field=0;field<GOLDEN_FIELDS-1;field++)*rows++=4;
  *rows++=0;
 }
}

/* Called while the native submit record is still owned by its builder. */
void grs_restore_parameter_record(void*owner,uint8_t*record){
 static const uint16_t offsets[GOLDEN_FIELDS]={0xb9,0xba,0xbb,0xbc,0xbd,0xbe,0xc0,0xcf,0xd0,0xd1};
 if(!owner||!record)return;
 const uint8_t*data=*(const uint8_t**)((uint8_t*)owner+4);
 if(!data||data[0x44])return;
 U group=data[0x1c0];
 if(group>=GOLDEN_GROUPS)return;
 U public=data[0x1c2+2*group];
 if(public<30u||public>=30u+GOLDEN_SLOTS)return;
 const uint8_t*settings=data+GOLDEN_USERDATA_BASE+2*((public-30u)*GOLDEN_GROUPS+group)*GOLDEN_FIELDS;
 for(U i=0;i<GOLDEN_FIELDS;i++)if(settings[i*2]>(i==GOLDEN_FIELDS-1?3u:8u))return;
 record[0xb8]=(uint8_t)public;
 for(U i=0;i<GOLDEN_FIELDS;i++)record[offsets[i]]=settings[2*i];
}

void grs_seed_raw_slots(uint8_t*raw,void*owner){
 static const uint8_t fields[GOLDEN_FIELDS]={0,1,2,3,4,5,6,13,14,15};
 if(!raw||!parameter_tail(owner))return;
 for(U group=0;group<GOLDEN_GROUPS;group++){
  uint8_t*rows=raw+0x400+340*group;
  const uint8_t*standard=rows+17;
  for(U slot=0;slot<GOLDEN_SLOTS;slot++){
   uint8_t*row=rows+17*(slot+14);
   for(U i=0;i<17;i++)row[i]=standard[i];
   for(U i=0;i<GOLDEN_FIELDS;i++){
    int value=grs_parameter_get(owner,group,fields[i],slot);
    if(value>=0)row[fields[i]]=(uint8_t)value;
   }
  }
 }
}
