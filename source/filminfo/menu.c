/* Fix1: preserve P5 core/journal and nav prefix. Recipe persistence is not
 * part of this build, and changing film must not disturb the Image Control
 * items either: the nine values are the user's own setting, held in the native
 * per-slot bank, so Install and Restore only ever touch Assignment. That is the
 * stock behaviour and the P4-B camera-approved behaviour. */
#include "core.c"
#define ROOT ((volatile U*)0x55804380u)
#define UI_MAGIC 0x34415347u
/* Persistence is not re-implemented here. These are the shipped P4-B routines,
 * called at the addresses the base firmware itself publishes, exactly as the
 * rest of the firmware calls them. */
#define SHIPPED_P4_ASSIGN      0x540f4a88u
#define SHIPPED_P4_DEFAULT     0x540f4cfcu
#define SHIPPED_P4_RESTORE_ALL 0x54143c18u
#define UI_BYTES 27504u
struct state {uint8_t front[0x720];U magic,page,status;uint16_t text_scratch[33];U icon_scratch[6400];};
struct p5nav {U magic,view,focus,slot,category,pending,category_focus,grid_focus,action_focus,info_page,return_view,family_focus,highlighted,family;};
struct canvas {void*screen,*surface,*layer;struct state*state;int x,y,width,height;};
_Static_assert(sizeof(struct state)==UI_BYTES,"Original UI ABI");
_Static_assert(sizeof(struct p5nav)==56,"Original nav prefix ABI");
#include "library_data.h"
enum {MAIN,SLOTS,ENTRY,CATEGORIES,GRID,ACTION,CONFIRM,INFO,FAVORITE_NOTICE,RESTORE_MENU,RESTORE_CURRENT,RESTORE_ALL,FAMILIES};
#include "families.h"
static struct state*peek(void){U p=*ROOT;__sync_synchronize();return p>1&&((struct state*)p)->magic==UI_MAGIC?(struct state*)p:0;}
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
 if(family>=FAMILY_COUNT||index>=FAMILY_VARIANT_CAPACITY)return 0;
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
int grs_install(struct state*s,void*ui){(void)ui;struct p5nav*n=nav(s);if(n->view!=CONFIRM||n->focus!=1||n->slot>=6||!lookup(n->pending))return 0;s->status=0;int(*assign)(U,U)=(int(*)(U,U))SHIPPED_P4_ASSIGN;int ok=assign(n->slot,n->pending);if(!ok&&s->status==0)s->status=10;if(ok){s->front[0xa]=s->front[0xb]=1;go(n,ENTRY,0);}return ok;}
/* Restore keeps the same rule: default film per slot, Image Control untouched. */
int grs_restore(struct state*s,U all){struct p5nav*n=nav(s);if(n->focus!=1||n->view!=(all?RESTORE_ALL:RESTORE_CURRENT)||n->slot>=6)return 0;s->status=0;int ok;if(all){int(*ra)(void)=(int(*)(void))SHIPPED_P4_RESTORE_ALL;ok=ra();}else{int(*def)(U)=(int(*)(U))SHIPPED_P4_DEFAULT;ok=def(n->slot);}if(!ok&&!s->status)s->status=10;if(ok)go(n,ENTRY,0);return ok;}
int grs_menu_key(U event){struct state*s=peek();if(!s)return(int)event;int(*active)(void)=(int(*)(void))0x540c5a58u;if(!active())return(int)event;struct p5nav*n=nav(s);U d=0xffffffffu;/* Native event table: FDIAL +/- (34/35) -> AP9/10;
  * RDIAL +/- (36/37) -> AP24/25. These are complete detent
  * events, not directional-button press/repeat/release triples. */
 if(event==9||event==24)d=(n->view==GRID||n->view==SLOTS||n->view==FAMILIES)?3:1;
 else if(event==10||event==25)d=(n->view==GRID||n->view==SLOTS||n->view==FAMILIES)?2:0;
 else if(event==26||event==27)d=0;else if(event==29||event==30)d=1;else if(event==32||event==33||event==11)d=2;else if(event==35||event==36||event==16)d=3;
 if(event==28||event==31||event==34||event==37)return 22;
 if(d!=0xffffffffu){if(n->view==GRID||n->view==SLOTS||n->view==FAMILIES)move_grid(n,n->view==SLOTS?6:n->view==FAMILIES?family_count(n):list_count(n),d);else if(n->view==INFO)return 22;else{U count=n->view==CATEGORIES?CATEGORY_COUNT:n->view==ACTION?4:n->view==ENTRY||n->view==RESTORE_MENU?3:n->view==CONFIRM||n->view==RESTORE_CURRENT||n->view==RESTORE_ALL?2:1;n->focus=wrap(n->focus,count,d==1||d==3);}s->front[0xa]=s->front[0xb]=1;redraw(s);return 22;}
 if(event==57){if(n->view==SLOTS)return(int)event;back(n);redraw(s);return 22;}
 if(event!=14&&event!=50)return(int)event;
 switch(n->view){case SLOTS:if(n->focus<6){n->slot=n->focus;grs_set_slot(16,7,n->slot);go(n,ENTRY,0);}break;case ENTRY:if(!n->focus)go(n,CATEGORIES,n->category_focus);else if(n->focus==1)go(n,RESTORE_MENU,0);else back(n);break;case CATEGORIES:if(n->focus<CATEGORY_COUNT){n->category=n->focus;n->category_focus=n->focus;n->grid_focus=0;n->family_focus=0;go(n,has_families(n)?FAMILIES:GRID,0);}break;case FAMILIES:{U family=family_at(n,n->focus);if(family<FAMILY_COUNT){n->family=family;n->family_focus=n->focus;n->grid_focus=0;n->action_focus=0;const struct film*f=variant_at(n,family,0);if(f&&family_size(n,family)==1u){n->pending=f->id;go(n,ACTION,0);}else go(n,GRID,0);}break;}case GRID:{const struct film*f=list_at(n,n->focus);if(f){n->pending=f->id;n->grid_focus=n->focus;n->action_focus=0;go(n,ACTION,0);}break;}case ACTION:n->action_focus=n->focus;if(n->focus==0){s->status=0;go(n,CONFIRM,0);}else if(n->focus==1)go(n,FAVORITE_NOTICE,0);else if(n->focus==2){go(n,INFO,0);}else back(n);break;case CONFIRM:if(n->focus==1)grs_install(s,0);else back(n);break;case INFO:case FAVORITE_NOTICE:back(n);break;case RESTORE_MENU:if(n->focus<2){s->status=0;go(n,n->focus?RESTORE_ALL:RESTORE_CURRENT,0);}else back(n);break;case RESTORE_CURRENT:case RESTORE_ALL:if(n->focus)grs_restore(s,n->view==RESTORE_ALL);else back(n);break;default:break;}
 redraw(s);return 22;}
U grs_menu_count(void*model){if(*((uint8_t*)model+0x198)!=117||!grs_ui_context())return 0;void(*attach)(void*)=(void(*)(void*))0x540c4384u;attach(model);return 6;}
void grs_menu_label(void*model,void*text,U i){if(*((uint8_t*)model+0x198)!=117||i>=6)return;void(*set)(void*,const char*)=(void(*)(void*,const char*))0x5339e7dcu;const struct film*f=assigned(i);if(f){U k=ordinal(f->id);set(text,k<COUNT?(const char*)films[k].name:"GRSlot+");}}
U grs_menu_selected(void*model){(void)model;return slot();}int grs_menu_commit(void*model,U row){(void)model;(void)row;return 0;}
static int shooting(void){return !(*(volatile U*)0x55063dccu&1)||!*(volatile uint8_t*)0x5506821bu;}
U grs_resource_override(U public,U icon){return shooting()&&public>=30&&public<=35?(icon?677u:925u)+public-30:0;}
U*p4_text(U rid){const struct film*f=rid>=925&&rid<=930?assigned(rid-925):0;return f?(U*)f->textdesc:0;}
U*p4_icon_descriptor(U id){return id>=0x10000u&&id<0x10000u+84u?(U*)(P5_DESC_BASE+(id-0x10000u)*8):(id==683?(U*)0x540f4624u:*(U**)(0x540c1df0u+id*4));}
U*p4_icon(U iid){const struct film*f=iid>=677&&iid<=682?assigned(iid-677):0;return f?p4_icon_descriptor(f->icon):0;}
static void rect(struct canvas*c,int x,int y,int w,int h,U ink){void(*f)(struct canvas*,int,int,int,int,U)=(void(*)(struct canvas*,int,int,int,int,U))0x540c6c90u;if(w>0&&h>0&&x>=0&&y>=0&&x<=c->width-w&&y<=c->height-h)f(c,c->x+x,c->y+y,w,h,ink);}
static U grs_language(void);
#include "native_font.inc"

static U grs_language(void){
 /* Same UserData read path as the native StringView language selector. */
 void*(*get_ap)(void)=(void*(*)(void))0x5320ad88u;
 void**(*get_user_data)(void*)=(void**(*)(void*))0x5320b31cu;
 U(*read_setting)(void**)=(U(*)(void**))0x532465dcu;
 U(*map_language)(U)=(U(*)(U))0x533963f8u;
 void*ap=get_ap();
 void**data=ap?get_user_data(ap):0;
 return data&&data[1]?map_language(read_setting(data)):1u;
}
static const uint16_t*grs_label(const uint16_t*en,const uint16_t*zh){
 return grs_language()==19u?zh:en;
}
static const uint16_t*const category_zh[]={u"全部胶片",u"收藏",u"Kodak",u"Fujifilm",u"黑白",u"数码相机",u"其他胶片",u"我的 LUT"};
static const uint16_t*const studio_notes[85]={
 [1]=u"5500K",
 [2]=u"5500K",
 [4]=u"5500K",
 [5]=u"5500K",
 [6]=u"3200K",
 [7]=u"5500K",
 [8]=u"5500K",
 [9]=u"5500K",
 [10]=u"5500K",
 [11]=u"5500K",
 [12]=u"5500K",
 [13]=u"5500K",
 [14]=u"5500K",
 [15]=u"5500K",
 [16]=u"5500K",
 [17]=u"5500K",
 [18]=u"5500K",
 [39]=u"5500K",
 [43]=u"5500K",
 [45]=u"5500K",
 [46]=u"5500K",
 [47]=u"3200K",
 [48]=u"3200K",
 [49]=u"5500K",
 [50]=u"5500K",
 [51]=u"5500K",
 [52]=u"5500K",
 [53]=u"5500K",
 [54]=u"5500K",
 [55]=u"5500K",
 [56]=u"3200K",
 [57]=u"3200K",
 [58]=u"3200K",
 [59]=u"3200K",
 [60]=u"5500K",
 [61]=u"5500K",
 [62]=u"5500K",
 [63]=u"5500K",
 [64]=u"3200K",
 [65]=u"3200K",
 [66]=u"5500K",
 [67]=u"5500K",
 [68]=u"5500K",
 [69]=u"5500K",
 [70]=u"5500K",
 [71]=u"5500K",
 [73]=u"5500K",
 [74]=u"5500K",
 [75]=u"3200K",
 [76]=u"3200K",
 [77]=u"3200K",
 [78]=u"5500K",
 [79]=u"3200K",
};
static const uint16_t*const studio_authors[85]={
 [1]=u"Spektrafilm",
 [2]=u"Spektrafilm",
 [4]=u"Spektrafilm",
 [5]=u"Spektrafilm",
 [7]=u"Spektrafilm",
 [8]=u"Spektrafilm",
 [9]=u"Spektrafilm",
 [10]=u"Spektrafilm",
 [11]=u"Spektrafilm",
 [12]=u"Spektrafilm",
 [13]=u"Spektrafilm",
 [14]=u"Spektrafilm",
 [15]=u"Spektrafilm",
 [16]=u"Spektrafilm",
 [17]=u"Spektrafilm",
 [18]=u"Spektrafilm",
 [45]=u"Spectral Film LUT",
 [46]=u"Spectral Film LUT",
 [47]=u"Spectral Film LUT",
 [48]=u"Spectral Film LUT",
 [49]=u"Spectral Film LUT",
 [50]=u"Spectral Film LUT",
 [51]=u"Spectral Film LUT",
 [52]=u"Spectral Film LUT",
 [53]=u"Spectral Film LUT",
 [54]=u"Spectral Film LUT",
 [55]=u"Spectral Film LUT",
 [56]=u"Spectral Film LUT",
 [57]=u"Spectral Film LUT",
 [58]=u"Spectral Film LUT",
 [59]=u"Spectral Film LUT",
 [60]=u"Spectral Film LUT",
 [61]=u"Spectral Film LUT",
 [62]=u"Spectral Film LUT",
 [63]=u"Spectral Film LUT",
 [64]=u"Spectral Film LUT",
 [65]=u"Spectral Film LUT",
 [66]=u"Spectral Film LUT",
 [67]=u"Spectral Film LUT",
 [68]=u"Spectral Film LUT",
 [69]=u"Spectral Film LUT",
 [70]=u"Spectral Film LUT",
 [71]=u"Spectral Film LUT",
 [72]=u"Spectral Film LUT",
 [73]=u"Spectral Film LUT",
 [74]=u"Spectral Film LUT",
 [75]=u"Spectral Film LUT",
 [76]=u"Spectral Film LUT",
 [77]=u"Spectral Film LUT",
 [78]=u"Spectral Film LUT",
 [79]=u"Spectral Film LUT",
};

static int blit(struct canvas*c,const U*p,U w,U h,int x,int y){if(!c->surface||!c->layer||!p||w>(U)c->width||h>(U)c->height||x<0||y<0||x>c->width-(int)w||y>c->height-(int)h)return 0;const U desc[2]={w|(h<<16),0};void(*f)(void*,void*,int,int,int,int,U,U,const U*,const U*)=(void(*)(void*,void*,int,int,int,int,U,U,const U*,const U*))0x5320a020u;f(c->surface,c->layer,c->x+x,c->y+y,0,0,w,h,desc,p);return 1;}
static const U blue_line[3*360]={[0 ... 3*360-1]=0xffe89b29u};
static void focus_line(struct canvas*c,int x,int y,int h){if(h>360)h=360;blit(c,blue_line,3,(U)h,x,y);}
static void glyph(struct canvas*c,const U*p,int x,int y){blit(c,p,32,32,x,y);}
static void bitmap(struct canvas*c,const struct film*f,int x,int y){U i=f->icon-0x10000u;if(i>=84u)return;const U*p=((const U*const*)P5_PIXELS)[i];U*out=c->state->icon_scratch;for(U n=0;n<6400;n++)out[n]=p[(n/160)*40+(n%80)/2];blit(c,out,80,80,x,y);}
static const uint16_t*const nums[]={u"1",u"2",u"3",u"4",u"5",u"6"};
static void row(struct canvas*c,U i,U active,const uint16_t*name,const U*icon){int y=(int)i*56;rect(c,8,y+4,c->width-16,52,active?21:34);if(active)focus_line(c,8,y+4,52);if(icon)glyph(c,icon,20,y+14);text_box(c,name,icon?66:24,y+10,c->width-(icon?90:48),1,0);}
void grs_draw(struct canvas*c){/* Native Select views retain our paint callback when reused by other menus. */
 int(*active)(void)=(int(*)(void))0x540c5a58u;if(!active())return;
 struct state*s=c?c->state:0;if(!s||c->x<0||c->y<0||c->width<640||c->height<340||c->width>720||c->height>480||c->x>720-c->width||c->y>480-c->height)return;struct p5nav*n=nav(s);rect(c,0,0,c->width,c->height,34);
 if(n->view==ENTRY){row(c,0,n->focus==0,grs_label(u"Film Library", u"胶片库"),GLYPH_CATEGORY_ALL);row(c,1,n->focus==1,grs_label(u"Restore Defaults", u"恢复默认"),GLYPH_ACTION_INSTALL);row(c,2,n->focus==2,grs_label(u"Back", u"返回"),GLYPH_ACTION_BACK);return;}
 if(n->view==SLOTS||n->view==GRID||n->view==FAMILIES){U count=n->view==SLOTS?6:n->view==FAMILIES?family_count(n):list_count(n);if(!count){glyph(c,GLYPH_CATEGORY_OTHER,c->width/2-16,80);text_box(c,grs_label(u"No films in this category", u"此分类没有胶片"),20,136,c->width-40,1,1);return;}if(n->focus>=count)n->focus=count-1;U first=(n->focus/6)*6;int dx=(c->width-8)/3,dy=(c->height-8)/2,w=dx-8,h=dy-8;for(U i=0;i<6&&first+i<count;i++){U absolute=first+i;int x=8+(int)(i%3)*dx,y=8+(int)(i/3)*dy;U active=absolute==n->focus;rect(c,x,y,w,h,active?21:34);if(active)focus_line(c,x,y,h);U family=n->view==FAMILIES?family_at(n,absolute):0;const struct film*f=n->view==SLOTS?assigned(absolute):n->view==FAMILIES?variant_at(n,family,0):list_at(n,absolute);if(!f)continue;bitmap(c,f,x+(w-80)/2,y+4);text_box(c,n->view==FAMILIES?family_names[family]:(const uint16_t*)f->textdesc[1],x+8,y+84,w-16,2,1);if(n->view==SLOTS)text_box(c,nums[absolute],x+7,y+4,30,1,0);}return;}
 if(n->view==CATEGORIES){U first=(n->focus/6)*6;for(U i=0;i<6&&first+i<CATEGORY_COUNT;i++){row(c,i,first+i==n->focus,grs_label(categories[first+i].name,category_zh[first+i]),categories[first+i].glyph);U count=category_counts[first+i];if(count<102)text_box(c,count_labels[count],c->width-80,(int)i*56+10,56,1,1);}return;}
 if(n->view==ACTION){const uint16_t*const items[]={grs_label(u"Install to Slot", u"装入槽位"),grs_label(u"Favorites: Build Config", u"收藏：构建配置"),grs_label(u"Film Info", u"胶片资料"),grs_label(u"Back", u"返回")};static const U*const icons[]={GLYPH_ACTION_INSTALL,GLYPH_CATEGORY_FAVORITES,GLYPH_ACTION_INFO,GLYPH_ACTION_BACK};for(U i=0;i<4;i++)row(c,i,i==n->focus,items[i],icons[i]);return;}
 if(n->view==CONFIRM){text_box(c,s->status?grs_label(u"Install failed", u"装入失败"):grs_label(u"Install selected film?", u"装入所选胶片？"),20,8,c->width-40,1,1);U i=ordinal(n->pending);if(i<COUNT)text_box(c,metadata[i].short_name,20,56,c->width-40,1,1);text_box(c,grs_label(u"Target Golden Slot", u"目标 Golden 槽位"),20,104,c->width-80,1,1);if(n->slot<6)text_box(c,nums[n->slot],c->width-65,104,40,1,0);struct canvas sub=*c;sub.y+=164;sub.height-=164;row(&sub,0,n->focus==0,grs_label(u"Cancel", u"取消"),GLYPH_ACTION_BACK);row(&sub,1,n->focus==1,grs_label(u"Install", u"装入"),GLYPH_ACTION_INSTALL);return;}

 if(n->view==RESTORE_MENU){row(c,0,n->focus==0,grs_label(u"Restore Current Slot Default", u"恢复当前槽位的默认胶片"),GLYPH_ACTION_INSTALL);row(c,1,n->focus==1,grs_label(u"Restore All Slots Default", u"恢复全部槽位的默认胶片"),GLYPH_ACTION_INSTALL);row(c,2,n->focus==2,grs_label(u"Back", u"返回"),GLYPH_ACTION_BACK);return;}
 if(n->view==RESTORE_CURRENT||n->view==RESTORE_ALL){text_box(c,s->status?grs_label(u"Restore failed", u"恢复失败"):n->view==RESTORE_ALL?grs_label(u"Restore all six default films?", u"恢复六个槽位的默认胶片？"):grs_label(u"Restore current default film?", u"恢复当前槽位的默认胶片？"),20,8,c->width-40,2,1);struct canvas sub=*c;sub.y+=164;sub.height-=164;row(&sub,0,n->focus==0,grs_label(u"Cancel", u"取消"),GLYPH_ACTION_BACK);row(&sub,1,n->focus==1,grs_label(u"Restore", u"恢复"),GLYPH_ACTION_INSTALL);return;}
 if(n->view==FAVORITE_NOTICE){text_box(c,grs_label(u"Favorites are compile-time only.", u"收藏仅可在构建时设置。"),20,50,c->width-40,2,1);text_box(c,grs_label(u"Update build configuration.", u"请更新构建配置。"),20,154,c->width-40,1,1);text_box(c,grs_label(u"MENU / OK: Back", u"MENU / OK：返回"),20,230,c->width-40,1,1);return;}

 if(n->view==INFO){
  U i=ordinal(n->pending);if(i>=COUNT)return;
  U uid=films[i].id;
  int y=6;
  text_box(c,(const uint16_t*)films[i].textdesc[1],20,y,c->width-40,1,0);
  const uint16_t*author=studio_authors[uid];
  if(author){
   y+=50;
   text_box(c,grs_label(u"Author:",u"作者："),20,y,135,1,0);
   text_box(c,author,155,y,c->width-175,1,0);
  }
  const uint16_t*note=studio_notes[uid];
  if(note){
   y+=50;
   text_box(c,grs_label(u"Note:",u"备注："),20,y,135,1,0);
   text_box(c,note,155,y,c->width-175,1,0);
  }
 }
}
#include "native_frame.inc"
int grs_resources(void){int(*init)(void)=(int(*)(void))0x540d0000u;return init();}
/* The native callback passes a TopMenuLineView, not its text child.
 * Bind its left StringView to owned common resource 900 (physical table index 786) and clear the right
 * value through the native setters; retain the factory row geometry. */
U grs_native_title(U controller,U line){(void)controller;if(!grs_resources())return 0;
 void(*left)(U,U,U)=(void(*)(U,U,U))0x5339e274u;left(line,900u,0u);
 U(*right)(U,const char*)=(U(*)(U,const char*))0x5339e7dcu;return right(line,"");}
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
 void*(*ap)(void)=(void*(*)(void))0x5320ad88u;U*(*id)(void*)=(U*(*)(void*))0x5320aefcu;
 void*p=ap();U*i=p?id(p):0;if(!i||*i!=0x02000143u||!(*(volatile U*)0x55804374u&0x80000000u))return;
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
 rect(&c,0,0,w,h,34);row(&c,0,1,grs_label(u"Change Film", u"更换胶片"),0);
}

U p5_family_count(void){struct state*s=peek();return s?family_count(nav(s)):0;}
U p5_family_at(U index){struct state*s=peek();return s?family_at(nav(s),index):0xffffffffu;}
