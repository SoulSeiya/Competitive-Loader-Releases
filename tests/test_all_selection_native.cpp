// Team cap test against the reviewed 0.1.38.1 member-list rules (decomp
// src/menu/menu_e_b.c, TeamSel_Input case TEAMSEL_ST_TEAM and the costume confirm).
// TeamSel_Update only animates; the cursor moves in TeamSel_Input.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#ifdef _WIN32
#include <windows.h>
static unsigned char *lowMemory(){return (unsigned char *)VirtualAlloc((void *)0x35000000,0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);}
#else
#include <sys/mman.h>
static unsigned char *lowMemory(){void *p=mmap((void *)0x35000000,0x10000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);return p==MAP_FAILED?0:(unsigned char *)p;}
#endif


extern "C" { uint32_t gCharSel,gSoloSel,gEntrySel,gUbTeamSel; }
static unsigned char *mem;
static int direction,confirm,picked[2],calls;
static int &word(uintptr_t address,int off){return *(int*)(address+off);}
static void nativeChoice(int& state,int& plate,int count,int p){
 if(state==2){if(direction)plate=(plate+direction+count)%count;else if(confirm){picked[p]=plate;state=5;}}
 else if(state==5&&confirm)picked[p]=plate;
}
static void nativeInput(uintptr_t side,int count,int p){nativeChoice(word(side,0x70),word(side,0x14),count,p);}
extern "C" {
void EntrySel_ClipGoto(int,int,char*){++calls;}
void UbTeamSel_ClipGoto(int,int,char*){++calls;}
void EntrySel_Input(int*){auto sel=*(uint32_t*)((uintptr_t)gEntrySel+0x3c4);int cur=word(sel,0x1c0);if(cur>=0&&cur<8)nativeChoice(word(sel,0x1c4),word(sel,cur*0x30+0x14),word(gEntrySel,0x1b0c),0);}
void UbTeamSel_Input(int*){auto sel=*(uint32_t*)((uintptr_t)gUbTeamSel+0x344);int cur=word(sel,0x12c);if(cur>=0&&cur<5)nativeChoice(word(sel,0x13c),word(sel,cur*0x30+0x14),word(gUbTeamSel,0x1abc),0);}
void CharSel_ClipGoto(int,int,int,char*){++calls;}
void SoloSel_ClipGoto(int,int,char*){++calls;}
void CharSel_Input(int*){for(int p=0;p<2;++p)nativeInput(*(uint32_t*)(mem+0x4f8+4*p),word(gCharSel,0x37d8+4*p),p);}
void SoloSel_Input(int*){nativeInput(*(uint32_t*)(mem+0x5000+0x21c),word(gSoloSel,0x1964),0);}
}
#include "../native/competitive_all_selection.cpp"
static uintptr_t cs(int p){return (uintptr_t)mem+0x1000+p*0x400;}
static uintptr_t ss(){return (uintptr_t)mem+0x8000;}
static void reset(){
 memset(mem,0,0x10000);gCharSel=(uint32_t)(uintptr_t)mem;gSoloSel=gCharSel+0x5000;
 for(int p=0;p<2;++p){word(gCharSel,0x4f8+p*4)=(uint32_t)cs(p);word(cs(p),0x70)=2;word(gCharSel,0x37d8+p*4)=4;picked[p]=-1;}
 word(gSoloSel,0x21c)=(uint32_t)ss();word(ss(),0x70)=2;word(gSoloSel,0x1964)=4;
 direction=confirm=calls=0;
}
static void frame(bool solo,int d=0,int c=0){direction=d;confirm=c;int r=1;if(solo)Competitive_SoloSelectInput(&r);else Competitive_CharSelectInput(&r);}
int main(){
 mem=lowMemory();assert(mem&&(uintptr_t)mem<0x100000000ULL);
 reset();frame(false,0,1);for(int p=0;p<2;++p)assert(picked[p]==1);
 reset();frame(false);frame(false,-1);for(int p=0;p<2;++p)assert(word(cs(p),0x14)==3);
 frame(false,1);for(int p=0;p<2;++p)assert(word(cs(p),0x14)==1);
 // Valid 2 and 3 remain selectable: no forced set for a particular character.
 for(int choice=1;choice<=3;++choice){reset();for(int p=0;p<2;++p)word(cs(p),0x14)=choice;frame(false,0,1);for(int p=0;p<2;++p)assert(picked[p]==choice);}
 reset();for(int p=0;p<2;++p)word(gCharSel,0x37d8+p*4)=2;frame(false,-1);frame(false,0,1);for(int p=0;p<2;++p)assert(picked[p]==1);
 reset();word(gCharSel,0x2fc)=4;frame(false,0,1);for(int p=0;p<2;++p)assert(picked[p]==0); // stage branch ignored by wrapper
 reset();frame(true,0,1);assert(picked[0]==1);
 reset();frame(true);frame(true,-1);assert(word(ss(),0x14)==3);frame(true,1);assert(word(ss(),0x14)==1);
 for(int choice=1;choice<=3;++choice){reset();word(ss(),0x14)=choice;frame(true,0,1);assert(picked[0]==choice);}
 reset();word(gSoloSel,0x1964)=1;frame(true,0,1);assert(picked[0]==1&&word(gSoloSel,0x1964)==4);
 reset();word(ss(),0x70)=5;frame(true,0,1);assert(picked[0]==1); // stale Normal cannot escape through costume confirm
 reset();word(ss(),0x70)=0;frame(true);assert(word(ss(),0x14)==0&&calls==0); // grid navigation untouched
 // All members/entrants preserve the player's set choice.
 for(int kind=0;kind<2;++kind){for(int member=0;member<(kind?5:8);++member){for(int choice=0;choice<=3;++choice){
  reset();gEntrySel=gCharSel+0xa000;gUbTeamSel=gEntrySel;
  int seloff=kind?0x344:0x3c4,stepoff=kind?0x13c:0x1c4,curoff=kind?0x12c:0x1c0,countoff=kind?0x1abc:0x1b0c;
  auto sel=(uintptr_t)mem+0xd000;word(gEntrySel,seloff)=(uint32_t)sel;word(sel,stepoff)=2;word(sel,curoff)=member;word(sel,member*0x30+0x14)=choice;word(gEntrySel,countoff)=4;
  direction=0;confirm=1;int r=1;if(kind)Competitive_UbTeamSelectInput(&r);else Competitive_EntrySelectInput(&r);
  assert(picked[0]==(choice?choice:1));
 }}}
 gCharSel=gSoloSel=0;competitiveSingleSets(nullptr,nullptr);assert(competitiveSoloSet(-1)==-1);
 puts("All selection screens OK");
}
