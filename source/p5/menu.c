/* SPDX-License-Identifier: GPL-2.0-only */
/* Fix1: preserve P5 core/journal and nav prefix. Recipe persistence is not
 * part of this build, and changing film must not disturb the Image Control
 * items either: the nine values are the user's own setting, held in the native
 * per-slot bank, so Install and Restore only ever touch Assignment. That is the
 * stock behaviour and the P4-B camera-approved behaviour. */
#include "core.c"
#include "native_parameters.inc"
#define ROOT ((volatile U*)0x55804380u)
#define UI_MAGIC 0x34415347u
/* Use the Assignment journal compiled into this module. */
#define UI_BYTES 27504u
struct state {uint8_t front[0x720];U magic,page,status;uint16_t text_scratch[33];U icon_scratch[6400];};
struct p5nav {U magic,view,focus,slot,category,pending,category_focus,grid_focus,action_focus,info_page,return_view,family_focus,highlighted,family;};
struct canvas {void*screen,*surface,*layer;struct state*state;int x,y,width,height;};
struct native_rect {
 void*layer;
 int x,y,width,height;
 uint8_t ink,reserved[3];
};
_Static_assert(sizeof(struct state)==UI_BYTES,"Original UI ABI");
_Static_assert(sizeof(struct p5nav)==56,"Original nav prefix ABI");
_Static_assert(sizeof(struct native_rect)==24,"Native rectangle command ABI");
#include "library_data.h"
enum {MAIN,SLOTS,ENTRY,CATEGORIES,GRID,ACTION,CONFIRM,INFO,FAVORITE_NOTICE,RESTORE_MENU,RESTORE_CURRENT,RESTORE_ALL,FAMILIES};
#include "families.h"
static struct state*peek(void){U p=*ROOT;__sync_synchronize();return p>1&&((struct state*)p)->magic==UI_MAGIC?(struct state*)p:0;}
static int native_ram(U address,U bytes){
 return address>=0x55000000u&&address<0x80000000u&&!(address&3u)&&bytes<=0x80000000u-address;
}
static int panel_matches(U expected){
 void*(*current_panel)(void)=(void*(*)(void))0x5320ad88u;
 const U*(*panel_id)(void*)=(const U*(*)(void*))0x5320aefcu;
 void*panel=current_panel();
 const U*id=panel?panel_id(panel):0;
 return native_ram((U)id,sizeof(*id))&&*id==expected;
}
static U slot(void);
static struct p5nav*nav(struct state*s){struct p5nav*n=(void*)((uint8_t*)s+UI_BYTES);if(n->magic!=0x354c4942u){for(U i=0;i<sizeof(*n);i++)((uint8_t*)n)[i]=0;n->magic=0x354c4942u;n->view=SLOTS;n->focus=slot()<6?slot():0;}return n;}
U grs_ui_bytes(void){return UI_BYTES+56;}
struct state*grs_ui_context(void){struct state*s=peek();if(s)return s;if(!__sync_bool_compare_and_swap(ROOT,0,1))return 0;void*(*alloc)(U)=(void*(*)(U))0x536af2a8u;s=alloc(grs_ui_bytes());if(!s){__sync_synchronize();*ROOT=0;return 0;}for(U i=0;i<grs_ui_bytes();i++)((uint8_t*)s)[i]=0;s->magic=UI_MAGIC;s->front[0x4f]=6;nav(s);__sync_synchronize();*ROOT=(U)s;return s;}
static U slot(void){return(*(volatile U*)0x55804374u>>16)&7u;}
void grs_set_slot(U bit,U mask,U value){if(bit==16&&mask==7&&value<6){U p=*(volatile U*)0x55804374u;*(volatile U*)0x55804374u=(p&~(7u<<16))|(value<<16);}}
U grs_group(struct state*s){(void)s;return 0;}
void grs_title(struct state*s,U mode){s->page=mode?1:0;s->front[0x560]=(uint8_t)!!mode;s->front[0x4f]=6;}
U grs_in_use_match(struct state*s,U row){(void)s;const struct film*f=assigned(slot());return f&&row&&row<=COUNT&&films[row-1].id==f->id;}
U grs_page(void){struct state*s=peek();return s?nav(s)->view:0;}
static U ordinal(U uid){for(U i=0;i<COUNT;i++)if(films[i].id==uid)return i;return 0xffffffffu;}
static U has_families(struct p5nav*n){return n->category==2u||n->category==3u;}
static U category_matches(struct p5nav*n,U i){
 if(n->category>=CATEGORY_COUNT||i>=COUNT)return 0;
 U kind=categories[n->category].kind;
 if(kind==2u)return 1;
 if(kind==1u)return metadata[i].favorite;
 return metadata[i].category==n->category;
}
static U matches(struct p5nav*n,U i){
 if(!category_matches(n,i))return 0;
 if(!has_families(n)||n->view==FAMILIES||n->view==CATEGORIES)return 1;
 U uid=films[i].id;
 return uid<sizeof(uid_family)&&uid_family[uid]==n->family;
}
static U family_size(struct p5nav*n,U family){
 U count=0;
 for(U i=0;i<COUNT;i++){
  U uid=films[i].id;
  if(category_matches(n,i)&&uid<sizeof(uid_family)&&uid_family[uid]==family)count++;
 }
 return count;
}
static U family_count(struct p5nav*n){
 U count=0;
 for(U i=0;i<FAMILY_COUNT;i++)if(family_size(n,i))count++;
 return count;
}
static U family_at(struct p5nav*n,U index){
 for(U i=0;i<FAMILY_COUNT;i++)if(family_size(n,i)){
  if(!index)return i;
  index--;
 }
 return 0xffffffffu;
}
static const struct film*variant_at(struct p5nav*n,U family,U index){
 if(family>=FAMILY_COUNT||index>=5u)return 0;
 U uid=family_variants[family][index];
 U i=ordinal(uid);
 return uid&&i<COUNT&&category_matches(n,i)?lookup(uid):0;
}
static U list_count(struct p5nav*n){if(n->category>=CATEGORY_COUNT)return 0;U count=0;for(U i=0;i<COUNT;i++)if(matches(n,i))count++;return count;}
static const struct film*list_at(struct p5nav*n,U index){if(has_families(n))return variant_at(n,n->family,index);if(n->category>=CATEGORY_COUNT)return 0;U at=0;for(U position=0;position<COUNT;position++){U i=film_order[position];if(matches(n,i)){if(at==index)return lookup(films[i].id);at++;}}return 0;}
static void redraw(struct state*s){void*v=*(void**)(s->front+0x20);if(v){void(*f)(void*)=(void(*)(void*))0x533ad308u;f(v);}}
static U wrap(U i,U count,U positive){return !count?0:positive?(i+1<count?i+1:0):(i?i-1:count-1);}
static void go(struct p5nav*n,U view,U focus){n->view=view;n->focus=focus;struct state*s=peek();if(s)s->front[0xa]=s->front[0xb]=1;}
/* Exact Fix3 absolute horizontal and same-column vertical navigation. */
static void move_grid(struct p5nav*n,U count,U d){if(!count){n->focus=0;return;}U i=n->focus<count?n->focus:count-1,c=i%3,start=i-c;if(d==0){if(i>=3)i-=3;}else if(d==1){if(count-1-start>=3){U next=start+3,remain=count-1-next;i=next+(c<remain?c:remain);}}else if(d==2)i=i?i-1:count-1;else if(d==3)i=i<count-1?i+1:0;n->focus=i;}
static void back(struct p5nav*n){switch(n->view){case SLOTS:break;case ENTRY:go(n,SLOTS,n->slot);break;case CATEGORIES:go(n,ENTRY,0);break;case FAMILIES:go(n,CATEGORIES,n->category_focus);break;case GRID:go(n,has_families(n)?FAMILIES:CATEGORIES,has_families(n)?n->family_focus:n->category_focus);break;case ACTION:if(has_families(n)&&family_size(n,n->family)==1u)go(n,FAMILIES,n->family_focus);else go(n,GRID,n->grid_focus);break;case CONFIRM:go(n,ACTION,n->action_focus);break;case INFO:case FAVORITE_NOTICE:go(n,ACTION,n->action_focus);break;case RESTORE_MENU:go(n,ENTRY,1);break;case RESTORE_CURRENT:case RESTORE_ALL:go(n,RESTORE_MENU,0);break;default:break;}}
/* Install commits Assignment only. The nine Image Control items stay exactly as
 * the user left them in this slot's native bank; nothing here reads or writes
 * them, and no engine setter is called. */
int grs_install(struct state*s,void*ui){(void)ui;struct p5nav*n=nav(s);if(n->view!=CONFIRM||n->focus!=1||n->slot>=6||!lookup(n->pending))return 0;s->status=0;int ok=p4_assign(n->slot,n->pending);if(!ok&&s->status==0)s->status=10;if(ok){s->front[0xa]=s->front[0xb]=1;go(n,ENTRY,0);}return ok;}
/* Restore keeps the same rule: default film per slot, Image Control untouched. */
int grs_restore(struct state*s,U all){struct p5nav*n=nav(s);if(n->focus!=1||n->view!=(all?RESTORE_ALL:RESTORE_CURRENT)||n->slot>=6)return 0;s->status=0;int ok=all?p4_restore_all():p4_default(n->slot);if(!ok&&!s->status)s->status=10;if(ok)go(n,ENTRY,0);return ok;}
int grs_menu_key(U event){struct state*s=peek();if(!s||!panel_matches(0x02000141u))return(int)event;struct p5nav*n=nav(s);U d=0xffffffffu;/* Native event table: FDIAL +/- (34/35) -> AP9/10;
  * RDIAL +/- (36/37) -> AP24/25. These are complete detent
  * events, not directional-button press/repeat/release triples. */
 if(event==9||event==24)d=(n->view==GRID||n->view==SLOTS||n->view==FAMILIES)?3:1;
 else if(event==10||event==25)d=(n->view==GRID||n->view==SLOTS||n->view==FAMILIES)?2:0;
 else if(event==26||event==27)d=0;else if(event==29||event==30)d=1;else if(event==32||event==33||event==11)d=2;else if(event==35||event==36||event==16)d=3;
 if(event==28||event==31||event==34||event==37)return 22;
 if(d!=0xffffffffu){if(n->view==GRID||n->view==SLOTS||n->view==FAMILIES)move_grid(n,n->view==SLOTS?6:n->view==FAMILIES?family_count(n):list_count(n),d);else if(n->view==INFO){U i=ordinal(n->pending);if(i!=0xffffffffu)n->info_page=wrap(n->info_page,(metadata[i].info_count+5)/6,d==1||d==3);}else{U count=n->view==CATEGORIES?CATEGORY_COUNT:n->view==ACTION?4:n->view==ENTRY||n->view==RESTORE_MENU?3:n->view==CONFIRM||n->view==RESTORE_CURRENT||n->view==RESTORE_ALL?2:1;n->focus=wrap(n->focus,count,d==1||d==3);}s->front[0xa]=s->front[0xb]=1;redraw(s);return 22;}
 if(event==57){if(n->view==SLOTS)return(int)event;back(n);redraw(s);return 22;}
 if(event!=14&&event!=50)return(int)event;
 switch(n->view){case SLOTS:if(n->focus<6){n->slot=n->focus;grs_set_slot(16,7,n->slot);go(n,ENTRY,0);}break;case ENTRY:if(!n->focus)go(n,CATEGORIES,n->category_focus);else if(n->focus==1)go(n,RESTORE_MENU,0);else back(n);break;case CATEGORIES:if(n->focus<CATEGORY_COUNT){n->category=n->focus;n->category_focus=n->focus;n->grid_focus=0;n->family_focus=0;go(n,has_families(n)?FAMILIES:GRID,0);}break;case FAMILIES:{U family=family_at(n,n->focus);if(family<FAMILY_COUNT){n->family=family;n->family_focus=n->focus;n->grid_focus=0;n->action_focus=0;const struct film*f=variant_at(n,family,0);if(f&&family_size(n,family)==1u){n->pending=f->id;go(n,ACTION,0);}else go(n,GRID,0);}break;}case GRID:{const struct film*f=list_at(n,n->focus);if(f){n->pending=f->id;n->grid_focus=n->focus;n->action_focus=0;go(n,ACTION,0);}break;}case ACTION:n->action_focus=n->focus;if(n->focus==0){s->status=0;go(n,CONFIRM,0);}else if(n->focus==1)go(n,FAVORITE_NOTICE,0);else if(n->focus==2){n->info_page=0;go(n,INFO,0);}else back(n);break;case CONFIRM:if(n->focus==1)grs_install(s,0);else back(n);break;case INFO:case FAVORITE_NOTICE:back(n);break;case RESTORE_MENU:if(n->focus<2){s->status=0;go(n,n->focus?RESTORE_ALL:RESTORE_CURRENT,0);}else back(n);break;case RESTORE_CURRENT:case RESTORE_ALL:if(n->focus)grs_restore(s,n->view==RESTORE_ALL);else back(n);break;default:break;}
 redraw(s);return 22;}
/* The ActionModel call site receives the event in r1 and originally copies
 * it into r5. Keep all other live registers and flags as that MOV does. */
__attribute__((naked,used)) void grs_action_input(void){
 __asm__ volatile(
  "push {r0,r2,r3,r12,lr}\n"
  "sub sp,sp,#4\n"
  "mrs r12,apsr\n"
  "str r12,[sp]\n"
  "mov r0,r1\n"
  "bl grs_menu_key\n"
  "mov r1,r0\n"
  "ldr r12,[sp]\n"
  "msr APSR_nzcvq,r12\n"
  "add sp,sp,#4\n"
  "pop {r0,r2,r3,r12,lr}\n"
  "mov r5,r1\n"
  "bx lr\n"
 );
}
/* Preserve the native factories for every stock ID. The extra two IDs are
 * valid only after the GRSlot menu owner has published its descriptors. */
__attribute__((naked,used)) void grs_select_model(void){
 __asm__ volatile(
  "movw r12,#0x4374\n"
  "movt r12,#0x5580\n"
  "ldr r12,[r12]\n"
  "tst r12,#0x80000000\n"
  "beq 1f\n"
  "movw r12,#0x141\n"
  "movt r12,#0x0200\n"
  "cmp r1,r12\n"
  "bne 1f\n"
  "mov r2,#117\n"
  "strb r2,[r0,#0x198]\n"
  "bx lr\n"
  "1: add r3,r1,#0xfe000000\n"
  "movw r12,#0x9644\n"
  "movt r12,#0x531b\n"
  "bx r12\n"
 );
}
__attribute__((naked,used)) void grs_submenu_model(void){
 __asm__ volatile(
  "movw r12,#0x4374\n"
  "movt r12,#0x5580\n"
  "ldr r12,[r12]\n"
  "tst r12,#0x80000000\n"
  "beq 1f\n"
  "movw r12,#0x143\n"
  "movt r12,#0x0200\n"
  "cmp r1,r12\n"
  "bne 1f\n"
  "mov r2,#17\n"
  "strb r2,[r0,#0x174]\n"
  "bx lr\n"
  "1: add r3,r1,#0xfe000000\n"
  "movw r12,#0x5954\n"
  "movt r12,#0x531c\n"
  "bx r12\n"
 );
}
/* Match the native ActionModel's two existing classes for the two new
 * view IDs. Preserve the original getter's flags and other registers. */
__attribute__((naked,used)) void grs_action_model_id(void){
 __asm__ volatile(
  "push {r3,r12}\n"
  "mrs r3,apsr\n"
  "ldr r0,[r0]\n"
  "movw r12,#0x4374\n"
  "movt r12,#0x5580\n"
  "ldr r12,[r12]\n"
  "tst r12,#0x80000000\n"
  "beq 1f\n"
  "movw r12,#0x141\n"
  "movt r12,#0x0200\n"
  "cmp r0,r12\n"
  "movweq r0,#0x114\n"
  "movteq r0,#0x0200\n"
  "beq 1f\n"
  "add r12,r12,#2\n"
  "cmp r0,r12\n"
  "movweq r0,#0x107\n"
  "movteq r0,#0x0200\n"
  "1: msr APSR_nzcvq,r3\n"
  "pop {r3,r12}\n"
  "bx lr\n"
 );
}
/* Native Factory chooses a constructor by r1 before the model callback. Use
 * the same two class aliases here and resume the original factory prologue. */
__attribute__((naked,used)) void grs_factory_entry(void){
 __asm__ volatile(
  "push {r0-r3,r12,lr}\n"
  "add r0,sp,#4\n"
  "bl grs_action_model_id\n"
  "str r0,[sp,#4]\n"
  "pop {r0-r3,r12,lr}\n"
  "movw r3,#0x13b\n"
  "movw r12,#0xf3bc\n"
  "movt r12,#0x5316\n"
  "bx r12\n"
 );
}
void grs_frame(void*view,void*paint_layer);
static int attach_slot_view(struct state*s,void*model){
 U view=*(U*)((uint8_t*)model+0x18c);
 if(!native_ram(view,276u))return 0;
 U*owned=(U*)(s->front+0x654);
 U table=*(U*)view;
 if(table!=(U)(owned+2)){
  if(table<0x53000008u||table>0x55000000u-184u||(table&3u))return 0;
  const U*original=(const U*)(table-8u);
  for(U i=0;i<48;i++)owned[i]=original[i];
  *(U*)(s->front+0x24)=original[21];
  owned[21]=(U)grs_frame;
  __sync_synchronize();
  *(U*)view=(U)(owned+2);
 }
 *(void**)(s->front+0x55c)=model;
 *(U*)(s->front+0x20)=view;
 return 1;
}
U grs_menu_count(void*model){
 if(!model||*((uint8_t*)model+0x198)!=117)return 0;
 struct state*s=grs_ui_context();
 return s&&attach_slot_view(s,model)?6:0;
}
void grs_menu_label(void*model,void*text,U i){if(*((uint8_t*)model+0x198)!=117||i>=6)return;void(*set)(void*,const char*)=(void(*)(void*,const char*))0x5339e7dcu;const struct film*f=assigned(i);if(f){U k=ordinal(f->id);set(text,k<COUNT?(const char*)films[k].name:"GRSlot+");}}
U grs_menu_selected(void*model){(void)model;return slot();}int grs_menu_commit(void*model,U row){(void)model;(void)row;return 0;}
static int shooting(void){return !(*(volatile U*)0x55063dccu&1)||!*(volatile uint8_t*)0x5506821bu;}
U grs_resource_override(U public,U icon){return shooting()&&public>=30&&public<=35?(icon?677u:925u)+public-30:0;}
U*p4_text(U rid){const struct film*f=rid>=925&&rid<=930?assigned(rid-925):0;return f?(U*)f->textdesc:0;}
static U*p4_icon_descriptor(U id){
 return id>=0x10000u&&id<0x10000u+COUNT?(U*)(P5_DESC_BASE+(id-0x10000u)*8):0;
}
U*p4_icon(U iid){const struct film*f=iid>=677&&iid<=682?assigned(iid-677):0;return f?p4_icon_descriptor(f->icon):0;}
static void rect(struct canvas*c,int x,int y,int w,int h,U ink){
 if(w<=0||h<=0||x<0||y<0||x>c->width-w||y>c->height-h)return;
 void(*fill)(void*,const struct native_rect*)=(void(*)(void*,const struct native_rect*))0x53208a2cu;
 const struct native_rect command={c->layer,c->x+x,c->y+y,w,h,(uint8_t)ink,{0}};
 fill(c->screen,&command);
}
#include "native_font.inc"
static int blit(struct canvas*c,const U*p,U w,U h,int x,int y){if(!c->surface||!c->layer||!p||w>(U)c->width||h>(U)c->height||x<0||y<0||x>c->width-(int)w||y>c->height-(int)h)return 0;const U desc[2]={w|(h<<16),0};void(*f)(void*,void*,int,int,int,int,U,U,const U*,const U*)=(void(*)(void*,void*,int,int,int,int,U,U,const U*,const U*))0x5320a020u;f(c->surface,c->layer,c->x+x,c->y+y,0,0,w,h,desc,p);return 1;}
static const U blue_line[3*360]={[0 ... 3*360-1]=0xffe89b29u};
static void focus_line(struct canvas*c,int x,int y,int h){if(h>360)h=360;blit(c,blue_line,3,(U)h,x,y);}
static void glyph(struct canvas*c,const U*p,int x,int y){blit(c,p,32,32,x,y);}
static void bitmap(struct canvas*c,const struct film*f,int x,int y){U i=f->icon-0x10000u;if(i>=COUNT)return;const U*p=((const U*const*)P5_PIXELS)[i];U*out=c->state->icon_scratch;for(U n=0;n<6400;n++)out[n]=p[(n/160)*40+(n%80)/2];blit(c,out,80,80,x,y);}
static const uint16_t*const nums[]={u"1",u"2",u"3",u"4",u"5",u"6"};
static void row(struct canvas*c,U i,U active,const uint16_t*name,const U*icon){int y=(int)i*56;rect(c,8,y+4,c->width-16,52,active?21:34);if(active)focus_line(c,8,y+4,52);if(icon)glyph(c,icon,20,y+14);text_box(c,name,icon?66:24,y+10,c->width-(icon?90:48),1,0);}
void grs_draw(struct canvas*c){/* Native Select views retain our paint callback when reused by other menus. */
 if(!panel_matches(0x02000141u))return;
 struct state*s=c?c->state:0;if(!s||c->x<0||c->y<0||c->width<640||c->height<340||c->width>720||c->height>480||c->x>720-c->width||c->y>480-c->height)return;struct p5nav*n=nav(s);rect(c,0,0,c->width,c->height,34);
 if(n->view==ENTRY){row(c,0,n->focus==0,u"Film Library",GLYPH_CATEGORY_ALL);row(c,1,n->focus==1,u"Restore Defaults",GLYPH_ACTION_INSTALL);row(c,2,n->focus==2,u"Back",GLYPH_ACTION_BACK);return;}
 if(n->view==SLOTS||n->view==GRID||n->view==FAMILIES){U count=n->view==SLOTS?6:n->view==FAMILIES?family_count(n):list_count(n);if(!count){glyph(c,GLYPH_CATEGORY_OTHER,c->width/2-16,80);text_box(c,u"No films in this category",20,136,c->width-40,1,1);return;}if(n->focus>=count)n->focus=count-1;U first=(n->focus/6)*6;int dx=(c->width-8)/3,dy=(c->height-8)/2,w=dx-8,h=dy-8;for(U i=0;i<6&&first+i<count;i++){U absolute=first+i;int x=8+(int)(i%3)*dx,y=8+(int)(i/3)*dy;U active=absolute==n->focus;rect(c,x,y,w,h,active?21:34);if(active)focus_line(c,x,y,h);U family=n->view==FAMILIES?family_at(n,absolute):0;const struct film*f=n->view==SLOTS?assigned(absolute):n->view==FAMILIES?variant_at(n,family,0):list_at(n,absolute);if(!f)continue;bitmap(c,f,x+(w-80)/2,y+4);text_box(c,n->view==FAMILIES?family_names[family]:(const uint16_t*)f->textdesc[1],x+8,y+84,w-16,2,1);if(n->view==SLOTS)text_box(c,nums[absolute],x+7,y+4,30,1,0);}return;}
 if(n->view==CATEGORIES){U first=(n->focus/6)*6;for(U i=0;i<6&&first+i<CATEGORY_COUNT;i++){row(c,i,first+i==n->focus,categories[first+i].name,categories[first+i].glyph);U count=category_counts[first+i];if(count<102)text_box(c,count_labels[count],c->width-80,(int)i*56+10,56,1,1);}return;}
 if(n->view==ACTION){static const uint16_t*const items[]={u"Install to Slot",u"Favorites: Build Config",u"Film Info",u"Back"};static const U*const icons[]={GLYPH_ACTION_INSTALL,GLYPH_CATEGORY_FAVORITES,GLYPH_ACTION_INFO,GLYPH_ACTION_BACK};for(U i=0;i<4;i++)row(c,i,i==n->focus,items[i],icons[i]);return;}
 if(n->view==CONFIRM){text_box(c,s->status?u"Install failed":u"Install selected film?",20,8,c->width-40,1,1);U i=ordinal(n->pending);if(i<COUNT)text_box(c,metadata[i].short_name,20,56,c->width-40,1,1);text_box(c,u"Target Golden Slot",20,104,c->width-80,1,1);if(n->slot<6)text_box(c,nums[n->slot],c->width-65,104,40,1,0);struct canvas sub=*c;sub.y+=164;sub.height-=164;row(&sub,0,n->focus==0,u"Cancel",GLYPH_ACTION_BACK);row(&sub,1,n->focus==1,u"Install",GLYPH_ACTION_INSTALL);return;}

 if(n->view==RESTORE_MENU){row(c,0,n->focus==0,u"Restore Current Slot Default",GLYPH_ACTION_INSTALL);row(c,1,n->focus==1,u"Restore All Slots Default",GLYPH_ACTION_INSTALL);row(c,2,n->focus==2,u"Back",GLYPH_ACTION_BACK);return;}
 if(n->view==RESTORE_CURRENT||n->view==RESTORE_ALL){text_box(c,s->status?u"Restore failed":n->view==RESTORE_ALL?u"Restore all six default films?":u"Restore current default film?",20,8,c->width-40,2,1);struct canvas sub=*c;sub.y+=164;sub.height-=164;row(&sub,0,n->focus==0,u"Cancel",GLYPH_ACTION_BACK);row(&sub,1,n->focus==1,u"Restore",GLYPH_ACTION_INSTALL);return;}
 if(n->view==FAVORITE_NOTICE){text_box(c,u"Favorites are compile-time only.",20,50,c->width-40,2,1);text_box(c,u"Update build configuration.",20,154,c->width-40,1,1);text_box(c,u"MENU / OK: Back",20,230,c->width-40,1,1);return;}
 if(n->view==INFO){U i=ordinal(n->pending);if(i>=COUNT)return;U start=n->info_page*6;for(U j=0;j<6&&start+j<metadata[i].info_count;j++)text_box(c,metadata[i].info[start+j],20,6+(int)j*50,c->width-40,1,0);}
}
#include "native_frame.inc"
#include "common_resources.inc"
/* The native callback passes a TopMenuLineView, not its text child.
 * Bind its left StringView to owned common resource 900 (physical table index 786) and clear the right
 * value through the native setters; retain the factory row geometry. */
U grs_native_title(U controller,U line){(void)controller;if(!grs_resources())return 0;
 void(*left)(U,U,U)=(void(*)(U,U,U))0x5339e274u;left(line,900u,0u);
 U(*right)(U,const char*)=(U(*)(U,const char*))0x5339e7dcu;return right(line,"");}
#include "native_menu_owner.inc"
/* Introspection serves tests without bypassing native key/entry dispatch. */
U p5_view(void){struct state*s=peek();return s?nav(s)->view:0xffffffffu;}
U p5_focus(void){struct state*s=peek();return s?nav(s)->focus:0;}
U p5_pending(void){struct state*s=peek();return s?nav(s)->pending:0;}
U p5_count(void){struct state*s=peek();return s?list_count(nav(s)):0;}
U p5_uid_at(U index){struct state*s=peek();const struct film*f=s?list_at(nav(s),index):0;return f?f->id:0;}
/* Native VisibleScrollList paint callback. Original traversal always runs;
 * only the owned Change Film submenu is overpainted with the existing style. */
void grs_change_frame(void*view,void*paint_layer){
 void(*original)(void*,void*)=(void(*)(void*,void*))0x5339567cu;original(view,paint_layer);
 if(!view||!paint_layer||!*((uint8_t*)view+0x9e))return;
 if(!panel_matches(0x02000143u)||!(*(volatile U*)0x55804374u&0x80000000u))return;
 U factory=*(volatile U*)0x55804378u;if(factory<0x55000000u||factory>=0x80000000u)return;
 const uint8_t*desc=(const uint8_t*)(factory+0x2526u);
 if(*(const uint16_t*)desc!=907u||desc[4]!=1u||*(const uint16_t*)(desc+6)!=908u)return;
 int(*left)(void*)=(int(*)(void*))0x536b5720u;int(*top)(void*)=(int(*)(void*))0x536b5728u;
 int(*width)(void*)=(int(*)(void*))0x536b57dcu;int(*height)(void*)=(int(*)(void*))0x536b57ecu;
 void*r=(uint8_t*)view+0x20;int x=left(r),y=top(r),w=width(r),h=height(r);
 if(x<0||y<0||w<640||w>720||h<56||h>360||x>720-w||y>480-h)return;
 struct state*s=grs_ui_context();if(!s)return;
 void*(*get)(void)=(void*(*)(void))0x5320804cu;void*m=get();if(!m)return;
 void*(*screen)(void*)=(void*(*)(void*))0x532081ecu;void*(*surface)(void*)=(void*(*)(void*))0x53208298u;
 struct canvas c={screen(m),surface(m),paint_layer,s,x,y,w,h};if(!c.screen||!c.surface)return;
 rect(&c,0,0,w,h,34);row(&c,0,1,u"Change Film",0);
}

U p5_family_count(void){struct state*s=peek();return s?family_count(nav(s)):0;}
U p5_family_at(U index){struct state*s=peek();return s?family_at(nav(s),index):0xffffffffu;}
