/* SPDX-License-Identifier: GPL-2.0-only */
/* Reused native Select underlay/body/parent-title lifetime. */
void grs_frame(void*view,void*paint_layer){
 struct state*s=peek();if(!s)return;
 void(*original)(void*,void*)=*(void(**)(void*,void*))(s->front+0x24);
 /* Preserve native Select child traversal and View paint bookkeeping BEFORE
  * the scoped full-body overpaint. Never disable the host View to hide rows.
  * Its original children finish inside this synchronous call; grs_draw then
  * covers only the body, leaving the native parent title/footer intact. */
 if(original)original(view,paint_layer);
 if(!paint_layer||!*((uint8_t*)view+0x9e)||*(int*)((uint8_t*)view+0x38)<640||*(int*)((uint8_t*)view+0x3c)<300)return;
 void*(*get)(void)=(void*(*)(void))0x5320804cu;void*manager=get();if(!manager)return;
 void*(*screen)(void*)=(void*(*)(void*))0x532081ecu;void*(*surface)(void*)=(void*(*)(void*))0x53208298u;
 struct canvas c={screen(manager),surface(manager),paint_layer,s,*(int*)((uint8_t*)view+0x30),*(int*)((uint8_t*)view+0x34),*(int*)((uint8_t*)view+0x38),*(int*)((uint8_t*)view+0x3c)};
 if(c.screen&&c.surface)grs_draw(&c);
}
