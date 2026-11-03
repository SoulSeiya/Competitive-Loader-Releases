#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
static bool rankedStartSession;
int gPortMenuMode;
static int online, calls;
static int control[2];
extern "C" { uint32_t gBtlSeq; }
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
struct ScoreBattleResult { int winner, reason; };
static ScoreBattleResult result;
static bool haveResult=true;
extern "C" { unsigned char gPad[2*0x1c0]; int Port_NetSession(){return online;}
int BattleSide_GetControl(int side){return control[side];}
ScoreBattleResult *Battle_GetResult(){return haveResult?&result:nullptr;}
void Pad_UpdateGameButtons(int pad){calls++; for(int off=0x188;off<=0x190;off+=4){unsigned v=0x1ffff;memcpy(gPad+pad*0x1c0+off,&v,4);}} }
#include "../native/competitive_ranked_input.cpp"
static unsigned word(int pad,int off){unsigned v;memcpy(&v,gPad+pad*0x1c0+off,4);return v;}
int main(){
 #ifdef _WIN32
 auto seq=(int*)VirtualAlloc((void*)0x36000000,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
#else
 auto seq=(int*)mmap((void*)0x36000000,0x1000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
#endif
 assert(seq && (uintptr_t)seq<0x100000000ULL);gBtlSeq=(uint32_t)(uintptr_t)seq;*seq=3;
 online=1;rankedStartSession=true;gPortMenuMode=0;result={0,0};
 for(int pad=0;pad<2;pad++){Competitive_RankedPadUpdate(pad);for(int off=0x188;off<=0x190;off+=4)assert(word(pad,off)==(0x1ffffu&~0x1000u));}
 // The original conversion still runs, and all other buttons remain intact.
 assert(calls==2);
 // Stage/camera and character intros can be skipped by either player.
 for(int phase=0;phase<=1;++phase){*seq=phase;for(int pad=0;pad<2;++pad){Competitive_RankedPadUpdate(pad);assert(word(pad,0x18c)==0x1ffff);}}
 // Ready and live combat strip held/pressed/repeat even if Start was held during the intro.
 for(int phase=2;phase<=3;++phase){*seq=phase;for(int pad=0;pad<2;++pad){Competitive_RankedPadUpdate(pad);for(int off=0x188;off<=0x190;off+=4)assert(word(pad,off)==(0x1ffffu&~0x1000u));}}
 // A missing battle sequence must never be dereferenced.
 gBtlSeq=0;Competitive_RankedPadUpdate(0);assert(word(0,0x18c)==0x1ffff);gBtlSeq=(uint32_t)(uintptr_t)seq;*seq=3;
 // Casual online and local P1/P2 have exactly the same battle-only lock.
 for(int mode=0;mode<3;++mode){
  online=mode!=2;rankedStartSession=mode==0;control[0]=control[1]=0;
  for(int phase=0;phase<=6;++phase){*seq=phase;
   for(int pad=0;pad<2;++pad){Competitive_RankedPadUpdate(pad);for(int off=0x188;off<=0x190;off+=4)
    assert(word(pad,off)==((phase==2||phase==3)?(0x1ffffu&~0x1000u):0x1ffffu));}
  }
 }
 // CPU on either side, CPU/CPU, training opponent: Start keeps working.
 for(int cpu=1;cpu<=3;++cpu){control[0]=(cpu&1)?2:0;control[1]=(cpu&2)?2:0;
  for(int net=0;net<=1;++net){online=net;rankedStartSession=true;for(int phase=0;phase<=6;++phase){*seq=phase;
   for(int pad=0;pad<2;++pad){Competitive_RankedPadUpdate(pad);assert(word(pad,0x18c)==0x1ffff);}
  }}
 }
 control[0]=control[1]=0;*seq=3;
 for(int mode=0;mode<3;mode++){
   gPortMenuMode=mode==0;result.winner=mode==1?1:0;haveResult=mode!=2;
   Competitive_RankedPadUpdate(0);assert(word(0,0x18c)==0x1ffff);
 }
 puts("Ranked Start OK");
}
