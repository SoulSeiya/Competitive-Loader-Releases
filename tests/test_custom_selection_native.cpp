// Team cap test against the reviewed 0.1.38.1 member-list rules (decomp
// src/menu/menu_e_b.c, TeamSel_Input case TEAMSEL_ST_TEAM and the costume confirm).
// TeamSel_Update only animates; the cursor moves in TeamSel_Input.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#ifdef _WIN32
#include <windows.h>
static unsigned char *lowMemory(){return (unsigned char *)VirtualAlloc((void *)0x35000000,0x6000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);}
#else
#include <sys/mman.h>
static unsigned char *lowMemory(){void *p=mmap((void *)0x35000000,0x6000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);return p==MAP_FAILED?0:(unsigned char *)p;}
#endif

static bool online=true;

extern "C" { uint32_t gTeamSel; unsigned char gPad[2*0x1c0]; int Port_NetSession(){return online;} }
static unsigned competitiveTeamCap(){return 5;}
extern "C" void TeamSel_ClipGoto(int,int,int,char *){}
extern "C" void TeamSel_RequestFace(int){}
extern "C" void TeamSel_Update(){}
#include "../native/competitive_team_limit.cpp"
static unsigned char *mem,*sides[2];
static int direction,confirm,selected[2];
static int& field(int p,int offset){return *(int*)(sides[p]+offset);}
static int& plates(int p){return *(int*)(mem+0x3c28+4*p);}
extern "C" float TeamSel_Input(int*){
 for(int p=0;p<2;++p){
  int& st=field(p,0x13c);int& plate=field(p,field(p,0x12c)*0x30+0x14);
  if(st==2){
   if(direction){plate=(plate+direction+plates(p))%plates(p);}
   else if(confirm && (*(unsigned*)(gPad+p*0x1c0+0x18c)&0x200)){
    // Observe what the actual menu would accept, not just the corrected cursor after input.
    selected[p]=plate;st=5;
   }
  }else if(st==5 && confirm && (*(unsigned*)(gPad+p*0x1c0+0x18c)&0x200))selected[p]=plate;
 }
 return 0;
}
static void reset(int n){
 memset(mem,0,0x6000);memset(gPad,0xff,sizeof(gPad));
 for(int p=0;p<2;++p){sides[p]=mem+0x1000+p*0x500;*(uint32_t*)(mem+0x8e8+4*p)=(uint32_t)(uintptr_t)sides[p];field(p,0x13c)=2;plates(p)=n;selected[p]=-1;}
 online=true;direction=confirm=0;
}
static void frame(int d=0,int c=0){direction=d;confirm=c;int result=1;Competitive_TeamSelectUpdate();Competitive_TeamSelectInput(&result);}
int main(){
 mem=lowMemory();assert(mem && (uintptr_t)mem<0x100000000ULL);gTeamSel=(uint32_t)(uintptr_t)mem;
 reset(4);frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==1); // first confirm skips Normal, both players
 for(int choice=1;choice<=3;++choice){reset(4);for(int p=0;p<2;++p)field(p,0x14)=choice;frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==choice);}
 reset(4);frame();for(int p=0;p<2;++p)assert(field(p,0x14)==1);
 frame(-1);for(int p=0;p<2;++p)assert(field(p,0x14)==3); // up from first custom wraps to last
 frame(1);for(int p=0;p<2;++p)assert(field(p,0x14)==1);
 for(int k=0;k<30;++k){frame(k%2?1:-1);for(int p=0;p<2;++p)assert(field(p,0x14)>=1&&field(p,0x14)<=3);}
 reset(2);frame(-1);frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==1); // saved-custom list: only one custom
 reset(4);for(int p=0;p<2;++p){field(p,0x12c)=1;field(p,0x44)=0;}frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==1); // another member
 reset(4);for(int p=0;p<2;++p)field(p,0x13c)=5;frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==1); // re-entry with stale Normal
 reset(1);frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==1); // native Normal-only mode now offers saved sets
 reset(4);online=false;frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==1); // offline must also require a custom set
 reset(4);*(int*)(mem+0x3bc)=4;frame(0,1);for(int p=0;p<2;++p)assert(selected[p]==0); // stage selection is untouched
 puts("Custom selection OK");
}
