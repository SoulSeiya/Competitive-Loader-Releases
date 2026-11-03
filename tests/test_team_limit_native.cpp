// Team cap test against the reviewed 0.1.38.1 member-list rules (decomp
// src/menu/menu_e_b.c, TeamSel_Input case TEAMSEL_ST_TEAM and the costume confirm).
// TeamSel_Update only animates; the cursor moves in TeamSel_Input.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#ifdef _WIN32
#include <windows.h>
static unsigned char *lowMemory(){return (unsigned char *)VirtualAlloc((void *)0x35000000,0x4000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);}
#else
#include <sys/mman.h>
static unsigned char *lowMemory(){void *p=mmap((void *)0x35000000,0x4000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);return p==MAP_FAILED?0:(unsigned char *)p;}
#endif
#include "../native/ft_rules.h"
extern "C" { uint32_t sRules,gTeamSel; unsigned char gPad[2*0x1c0]; }
static bool online=true;
static unsigned practiceCap=0; // 0: no offline practice
extern "C" int Port_NetSession(){return online;}
// Same policy as competitive_score.cpp: online rules word, else the practice cap, else none.
static unsigned competitiveTeamCap(){return online?CompetitiveTeamLimit(sRules):practiceCap?practiceCap:5;}
static int clipOff,clipOn,faces;
extern "C" void TeamSel_ClipGoto(int,int,int kind,char *label){assert(kind==6);if(!strcmp(label,"fl_on_start"))++clipOn;else ++clipOff;}
extern "C" void TeamSel_RequestFace(int){++faces;}
extern "C" void TeamSel_Update(){}
#include "../native/competitive_team_limit.cpp"

static unsigned char *side;
static int &cur(){return *(int *)(side+0x12c);}
static int &count(){return *(int *)(side+0x134);}
static int &state(){return *(int *)(side+0x13c);}
enum Pad{None,Left,Right,AddMember};
static Pad pad;
// Faithful copy of the native movement for one side.
extern "C" float TeamSel_Input(int *){
    if(pad==Left&&state()==6){if(--cur()<0)cur()=5;else if(cur()>count())cur()=count();}
    if(pad==Right&&state()==6){if(++cur()>5)cur()=0;else if(cur()>count())cur()=5;}
    if(pad==AddMember){ // costume confirmed for the member under the cursor (state 5 -> 6)
        if(cur()==count()){count()=cur()+1;cur()=count();}
        state()=6;
    }
    return 0;
}
static void frame(Pad p){pad=p;Competitive_TeamSelectUpdate();int result=1;Competitive_TeamSelectInput(&result);}
static void choose(){state()=5;frame(AddMember);}

int main(){
    // Pure rule.
    assert(CompetitiveTeamCursor(1,2,2,6,2)==5);      // right from last member -> plate
    assert(CompetitiveTeamCursor(5,2,2,6,2)==1);      // left from plate -> last member
    assert(CompetitiveTeamCursor(1,1,2,6,2)==1);      // existing members stay editable
    assert(CompetitiveTeamCursor(-1,2,2,5,2)==2);     // only the member list
    assert(CompetitiveTeamCursor(-1,1,1,6,2)==1);     // below the cap the empty slot is normal
    assert(CompetitiveTeamCursor(-1,4,4,6,5)==4);     // ordinary five-member teams untouched

    unsigned char *mem=lowMemory();
    assert(mem && (uintptr_t)mem<0x100000000ULL);
    gTeamSel=(uint32_t)(uintptr_t)mem;side=mem+0x1000;
    *(uint32_t *)(mem+0x8e8)=(uint32_t)(uintptr_t)side;
    for(int m=0;m<5;++m)*(int *)(side+m*0x30+0x1c)=100+m;

    sRules=CompetitiveTeamLimitRules(CompetitiveFtRules(0x00720001,2),2);
    count()=0;cur()=0;state()=0;
    choose();assert(count()==1&&cur()==1);                      // first member, below the cap
    choose();assert(count()==2&&cur()==5);                      // cap reached: on the plate, not the empty slot
    assert(clipOn==1&&clipOff==1&&faces==1&&*(int *)(side+0x138)==100);
    frame(Left);assert(cur()==1&&*(int *)(side+0x138)==101);   // Beta5 bug: snapped back to the plate here
    frame(Left);assert(cur()==0);
    frame(Left);assert(cur()==5);                               // native wrap
    frame(Left);assert(cur()==1);
    frame(Right);assert(cur()==5);
    frame(Right);assert(cur()==0);                              // native wrap
    for(int i=0;i<20;++i){frame(i%3?Left:Right);assert(cur()!=2&&cur()>=0&&cur()<=5);}

    // Every cap from 1 to 4 can be completed, navigated and never offers a slot past it.
    for(unsigned cap=1;cap<=4;++cap){
        sRules=CompetitiveTeamLimitRules(0,cap);count()=0;cur()=0;state()=0;
        for(unsigned n=0;n<cap;++n)choose();
        assert(count()==(int)cap&&cur()==5);
        for(int i=0;i<12;++i){frame(Left);assert(cur()!=(int)cap);}
        for(int i=0;i<12;++i){frame(Right);assert(cur()!=(int)cap);}
    }
    // No cap (5) and offline selection keep the native behaviour exactly.
    sRules=CompetitiveTeamLimitRules(0,0);count()=2;cur()=1;state()=6;frame(Right);assert(cur()==2);
    online=false;sRules=CompetitiveTeamLimitRules(0,2);count()=2;cur()=1;state()=6;frame(Right);assert(cur()==2);
    // Offline practice against the CPU: the Loader's cap applies, the online rules word does not.
    practiceCap=2;sRules=0;count()=0;cur()=0;state()=0;
    choose();choose();assert(count()==2&&cur()==5);
    frame(Left);assert(cur()==1);frame(Right);assert(cur()==5);
    practiceCap=0;count()=2;cur()=1;state()=6;frame(Right);assert(cur()==2); // ordinary offline play untouched
    puts("Team limit OK");
}
