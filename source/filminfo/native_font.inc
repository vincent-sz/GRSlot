/* Reused native font adapter from SelectionFix; input is already UTF16. */
static void text_cmd(struct canvas*c,U*cmd,const uint16_t*w,U n,int x,int y,int width){
 for(U i=0;i<14;i++)cmd[i]=0;
 cmd[0]=(U)c->layer;cmd[1]=(U)(c->x+x);cmd[2]=(U)(c->y+y);cmd[3]=(U)width;cmd[4]=40;
 cmd[5]=cmd[1];cmd[6]=cmd[2];cmd[7]=cmd[3];cmd[8]=40;
 uint8_t*b=(uint8_t*)cmd;b[36]=(uint8_t)grs_language();b[37]=31;b[38]=34;
 b[46]=(uint8_t)(n+1);b[47]=1;cmd[12]=(U)w;
}
static int text_width(void*font,U*cmd){
 U extent[2]={0,0};void(*measure)(U*,void*,U*)=(void(*)(U*,void*,U*))0x53208d7cu;
 measure(extent,font,cmd);return(int)extent[0];
}
static void text_box(struct canvas*c,const uint16_t*w,int x,int y,int width,U lines,U center){
 if(!w||width<=0||y<0||y+40>c->height)return;
 /* Card display names omit manufacturer prefixes only. Preserve the GSL
  * name, UID, category names and Golden/RAW resource tables verbatim. */
 if(lines>1){
  const char*brands[2]={"Kodak ","Fujifilm "};
  for(U k=0;k<2;k++){U j=0;while(brands[k][j]&&w[j]==(uint8_t)brands[k][j])j++;if(!brands[k][j]&&w[j]){w+=j;break;}}
 }
 void*(*get)(void)=(void*(*)(void))0x5320804cu;void*(*font_get)(void*)=(void*(*)(void*))0x53208224u;
 void(*draw)(void*,const U*)=(void(*)(void*,const U*))0x532090c4u;
 void*m=get();if(!m)return;void*f=font_get(m);if(!f)return;
 U total=0;while(total<32&&w[total])total++;
 if(lines>1){U cmd[14];text_cmd(c,cmd,w,total,x,y,width);if(text_width(f,cmd)<=width){y+=(int)(lines-1)*20;lines=1;}}
 U pos=0;uint16_t*t=c->state->text_scratch;
 for(U line=0;line<lines&&pos<total&&y+(int)(line*40)+40<=c->height;line++){
  while(pos<total&&w[pos]==' ')pos++;if(pos>=total)break;
  U n=total-pos;for(U j=0;j<n;j++)t[j]=w[pos+j];t[n]=0;
  U cmd[14];text_cmd(c,cmd,t,n,x,y+(int)line*40,width);
  int measured=text_width(f,cmd);
  if(measured>width){
   U best=0,lo=1,hi=n;
   while(lo<=hi){U j=(lo+hi)/2;uint16_t keep=t[j];t[j]=0;text_cmd(c,cmd,t,j,x,y+(int)line*40,width);int fit=text_width(f,cmd);t[j]=keep;if(fit<=width){best=j;lo=j+1;}else hi=j-1;}
   if(!best)return;
   U split=best;while(split&&t[split]!=' ')split--;n=split?split:best;t[n]=0;
   text_cmd(c,cmd,t,n,x,y+(int)line*40,width);measured=text_width(f,cmd);
  }
  if(center&&measured<width){int dx=(width-measured)/2;text_cmd(c,cmd,t,n,x+dx,y+(int)line*40,measured);}
  else text_cmd(c,cmd,t,n,x,y+(int)line*40,width);
  draw(f,cmd);pos+=n;
 }
}
