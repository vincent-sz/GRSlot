/* SPDX-License-Identifier: GPL-2.0-only */
/* Native factory table ownership follows the existing Change Film layout.
 * Publish only after all five stock categories and the two GRSlot descriptors
 * are complete. Keep every original row in its original order. */
enum {
 SELECT_BYTES=118*64, SUBMENU_BYTES=18*100, CATEGORY_COUNT_STOCK=5,
 SUBMENU_OFFSET=0x1e80, CATEGORY_OFFSET=0x2588,
 STOCK_CATEGORY_BYTES=900, CATEGORY_BYTES=920,
 OWNER_BYTES=CATEGORY_OFFSET+CATEGORY_COUNT_STOCK*CATEGORY_BYTES
};
_Static_assert(SUBMENU_OFFSET+SUBMENU_BYTES==CATEGORY_OFFSET,"Native SubMenu table boundary");
_Static_assert(SELECT_BYTES<=SUBMENU_OFFSET&&OWNER_BYTES==14208,"Native factory allocation size");

static void copy_menu_bytes(uint8_t*destination,const uint8_t*source,U count){
 for(U i=0;i<count;i++)destination[i]=source[i];
}

static void put_menu_word(uint8_t*destination,U value){
 for(U i=0;i<4;i++)destination[i]=(uint8_t)(value>>(8u*i));
}

static int prepare_menu_owner(const uint8_t*select,const uint8_t*submenu){
 volatile U*owned=(volatile U*)0x55804374u;
 if(owned[0]&0x80000000u)return 1;
 volatile U*categories=(volatile U*)0x55001eb8u;
 const uint8_t*original[CATEGORY_COUNT_STOCK];
 for(U i=0;i<CATEGORY_COUNT_STOCK;i++){
  U address=categories[i];
  if(!native_ram(address,STOCK_CATEGORY_BYTES)&&
     (address<0x53000000u||address>0x55000000u-STOCK_CATEGORY_BYTES||(address&3u)))return 0;
  original[i]=(const uint8_t*)address;
 }
 if(original[0][0x68]!=7u||original[0][0x8b]!=38u||!grs_resources())return 0;
 uint8_t*(*allocate)(U)=(uint8_t*(*)(U))0x536af2a8u;
 uint8_t*owner=allocate(OWNER_BYTES);
 if(!owner)return 0;
 for(U i=0;i<OWNER_BYTES;i++)owner[i]=0;
 copy_menu_bytes(owner,select,SELECT_BYTES);
 copy_menu_bytes(owner+SUBMENU_OFFSET,submenu,SUBMENU_BYTES);
 uint8_t*groups=owner+CATEGORY_OFFSET;
 for(U i=0;i<CATEGORY_COUNT_STOCK;i++){
  uint8_t*group=groups+i*CATEGORY_BYTES;
  copy_menu_bytes(group,original[i],0x1bcu);
  copy_menu_bytes(group+0x1c4u,original[i]+0x1bcu,0x98u);
  copy_menu_bytes(group+0x260u,original[i]+0x254u,0x130u);
 }
 groups[0x8b]=39;
 put_menu_word(groups+0x1bc,(U)grs_native_title);
 put_menu_word(groups+0x25c,0x02000143u);

 __sync_synchronize();
 owned[1]=(U)owner;
 owned[2]=(U)owner+SUBMENU_OFFSET;
 for(U i=0;i<CATEGORY_COUNT_STOCK;i++)categories[i]=(U)(groups+i*CATEGORY_BYTES);
 __sync_synchronize();
 __sync_fetch_and_or(&owned[0],0x80000000u);
 return 1;
}

int grs_publish_menu(const uint8_t*select,const uint8_t*submenu){
 if(!__sync_bool_compare_and_swap(&ASSIGN->menu_owner_busy,0,1))return 0;
 /* A stock-sized controller may already exist after the first failure.
  * Keep that layout for the rest of this boot. */
 int result=!ASSIGN->menu_owner_fallback&&prepare_menu_owner(select,submenu);
 if(!result)ASSIGN->menu_owner_fallback=1;
 __sync_synchronize();
 ASSIGN->menu_owner_busy=0;
 return result;
}
