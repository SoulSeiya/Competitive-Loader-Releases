#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
static bool rankedStartSession;
int gPortMenuMode;
static int online, calls;
struct ScoreBattleResult { int winner, reason; };
static ScoreBattleResult result;
static bool haveResult=true;
extern "C" { unsigned char gPad[2*0x1c0]; int Port_NetSession(){return online;}
ScoreBattleResult *Battle_GetResult(){return haveResult?&result:nullptr;}
void Pad_UpdateGameButtons(int pad){calls++; for(int off=0x188;off<=0x190;off+=4){unsigned v=0x1ffff;memcpy(gPad+pad*0x1c0+off,&v,4);}} }
#include "../native/competitive_ranked_input.cpp"
static unsigned word(int pad,int off){unsigned v;memcpy(&v,gPad+pad*0x1c0+off,4);return v;}
int main(){
 online=1;rankedStartSession=true;gPortMenuMode=0;result={0,0};
 for(int pad=0;pad<2;pad++){Competitive_RankedPadUpdate(pad);for(int off=0x188;off<=0x190;off+=4)assert(word(pad,off)==(0x1ffffu&~0x1000u));}
 // The original conversion still runs, and all other buttons remain intact.
 assert(calls==2);
 for(int mode=0;mode<5;mode++){
   online=mode!=0;rankedStartSession=mode!=1;gPortMenuMode=mode==2;result.winner=mode==3?1:0;haveResult=mode!=4;
   Competitive_RankedPadUpdate(0);assert(word(0,0x18c)==0x1ffff);
 }
 puts("Ranked Start OK");
}
