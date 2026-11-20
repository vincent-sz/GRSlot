/* SPDX-License-Identifier: GPL-2.0-only */
/* GRSlot's native menu labels. Preserve every factory-language table prefix. */
enum { COMMON_NATIVE_COUNT=786, COMMON_OWNED_COUNT=25, COMMON_LANGUAGE_COUNT=21 };
struct common_text {U attributes;const uint16_t*label;};
#define TEXT(s) {0x100u+(U)(sizeof(u##s)/sizeof(uint16_t)),u##s}
static const struct common_text common_labels[COMMON_OWNED_COUNT]={
 TEXT("GRSlot"),TEXT("GRSlot"),TEXT("OFF"),TEXT("ON"),TEXT("DEFAULT"),TEXT("FILM"),
 TEXT("LIBRARY"),TEXT("GRSLOT"),TEXT("Change Film"),TEXT(""),TEXT(""),TEXT(""),TEXT(""),
 TEXT(""),TEXT(""),TEXT("Films in use"),TEXT("Film Library"),TEXT("OK"),TEXT("Back"),
 TEXT("Slot Default Film"),TEXT("SD ERROR"),TEXT("EMPTY"),TEXT("DEFAULT"),TEXT("FILM"),TEXT("GRSlot")
};
#undef TEXT
static const U factory_common_roots[COMMON_LANGUAGE_COUNT]={
 0x55009a88u,0x55004490u,0x55005d20u,0x55006968u,0x5500f080u,0x5500cba8u,0x55008e40u,
 0x5500b318u,0x55003848u,0x5500fcc8u,0x550050d8u,0x5500bf60u,0x55002c00u,0x550081f8u,
 0x550121a0u,0x550075b0u,0x5500d7f0u,0x5500a6d0u,0x55011558u,0x5500e438u,0x55010910u
};

static int publish_common_resources(void){
 volatile U* roots=(volatile U*)0x55002bacu;
 const U stride=COMMON_NATIVE_COUNT+COMMON_OWNED_COUNT;
 U first=roots[0];
 if(first!=factory_common_roots[0]){
  if(!native_ram(first,COMMON_LANGUAGE_COUNT*stride*sizeof(U)))return 0;
  for(U i=0;i<COMMON_LANGUAGE_COUNT;i++){
   U table=roots[i];
   if(table!=first+i*stride*sizeof(U)||((const U*)table)[COMMON_NATIVE_COUNT]!=(U)&common_labels[0])return 0;
  }
  return 1;
 }
 for(U i=0;i<COMMON_LANGUAGE_COUNT;i++)if(roots[i]!=factory_common_roots[i])return 0;
 U*(*alloc)(U)=(U*(*)(U))0x536af2a8u;
 U* replacement=alloc(COMMON_LANGUAGE_COUNT*stride*sizeof(U));
 if(!replacement)return 0;
 for(U language=0;language<COMMON_LANGUAGE_COUNT;language++){
  const U* old=(const U*)factory_common_roots[language];
  U* table=replacement+language*stride;
  for(U i=0;i<COMMON_NATIVE_COUNT;i++)table[i]=old[i];
  for(U i=0;i<COMMON_OWNED_COUNT;i++)table[COMMON_NATIVE_COUNT+i]=(U)&common_labels[i];
 }
 __sync_synchronize();
 for(U i=1;i<COMMON_LANGUAGE_COUNT;i++)roots[i]=(U)(replacement+i*stride);
 __sync_synchronize();
 roots[0]=(U)replacement;
 return 1;
}

int grs_resources(void){
 if(!__sync_bool_compare_and_swap(&ASSIGN->common_resource_busy,0,1))return 0;
 int result=publish_common_resources();
 __sync_synchronize();
 ASSIGN->common_resource_busy=0;
 return result;
}

const U* grs_common_text(U id,U language){
 if(language>=COMMON_LANGUAGE_COUNT)return 0;
 if(id>=900u&&id<925u)return (const U*)&common_labels[id-900u];
 return p4_text(id);
}
