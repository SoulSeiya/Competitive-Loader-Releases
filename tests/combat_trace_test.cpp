#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef HANDLE (WINAPI *RisingOpenMapping)(DWORD,BOOL,LPCSTR);
typedef LPVOID (WINAPI *RisingMapView)(HANDLE,DWORD,DWORD,DWORD,SIZE_T);
typedef BOOL (WINAPI *RisingCloseHandle)(HANDLE);
static const char *SDL_getenv(const char *) {return 0;}
#define SDL_snprintf snprintf
extern "C" {
uint32_t gBtlSeq,gBtlChars;
int gPortResim;
static unsigned tick=100;
unsigned Port_NetTick(){return tick;}
static bool online=true;
int Port_NetSession(){return online;}
static uint32_t fighters[2];
static uint32_t objects[2];
uint32_t BtlObj_Get(int side){return side>=0&&side<2?objects[side]:0;}
const char *Port_NetName(int side){return side==0?"Alice":"Bob";}
uint32_t BtlChar_FindBySide(int s){return fighters[s];}
int BtlCharApi_GetChara(int s){return s+8;}
int PortA11y_Utf8(char *out,int cap,const uint16_t *str){int n=0;for(int i=0;str[i]&&n<cap-1;++i)if(str[i]!=0xfeff)out[n++]=(char)str[i];out[n]=0;return n;}
static int currentStage=2;
int Battle_GetStage(){return currentStage;}
int Battle_GetStartStage(){return 2;}
const char *const *MenuTranslation_StageNames(){static const char *names[35]={};names[2]="Planet Namek";return names;}
}
#include "../native/competitive_combat_trace.cpp"
int main(){
 unsigned char *mem=(unsigned char *)VirtualAlloc((void *)0x40000000,0x10000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
 assert(mem && (uintptr_t)mem<=0xffffffffu);
 gBtlSeq=(uint32_t)(uintptr_t)mem;gBtlChars=gBtlSeq;
 *(int *)mem=3;
 TraceShared shared={};combatTrace=&shared;traceAttempted=true;
 shared.epoch=1;
 // Exact reviewed TeamSel text offsets; names must follow the BTC disc, not a fixed roster.
 uint32_t *name=(uint32_t *)(mem+0x5000),*form=(uint32_t *)(mem+0x6000);
 for(int i=0;i<=161;++i)name[i]=form[i]=0x400;
 const uint16_t baseText[]={0xfeff,'B','a','r','d','o','c','k',0},formText[]={0xfeff,'S','S','J',0};
 memcpy(mem+0x5400,baseText,sizeof(baseText));memcpy(mem+0x6400,formText,sizeof(formText));
 *(uint32_t *)(mem+0x7000+0x28)=(uint32_t)(uintptr_t)name;
 *(uint32_t *)(mem+0x7000+0x2c)=(uint32_t)(uintptr_t)form;
 competitiveTraceNames((uint32_t)(uintptr_t)(mem+0x7000));
 assert(!strcmp(shared.names[8],"Bardock / SSJ"));
 for(int i=0;i<2;++i){unsigned char *f=mem+0x1000+i*0x2000;fighters[i]=(uint32_t)(uintptr_t)f;
  *(int *)(f+0xc)=i;*(int *)(f+0x964)=4;
  unsigned char *object=mem+0x8000+i*0x1000;objects[i]=(uint32_t)(uintptr_t)object;
  unsigned char *skill=mem+0xb000+i*0x200,*super=skill+0x100;
  *(uint32_t *)(object+0x930)=(uint32_t)(uintptr_t)skill;*(uint32_t *)(object+0x92c)=(uint32_t)(uintptr_t)super;
  *(int16_t *)(skill+0x10)=111+i;*(int16_t *)(super+0x18+4)=333+i;
  *(int *)(f+0x9a4+4)=i;*(int *)(f+0x994)=0;*(int *)(f+0x998)=2;*(int *)(f+0x9a4)=8+i;
  *(int *)(f+0x948)=0xfd;*(int *)(f+0x9a4+0x60)=i+1;
 }
 unsigned char before[0x10000];memcpy(before,mem,sizeof(before));
 competitiveTraceCapture();assert(!memcmp(before,mem,sizeof(before)));
 auto &row=shared.frames[100];assert(row.blank==100 && row.sides[0].action==0xfd);
 assert(row.sides[0].abilityId==111 && row.sides[0].actionFrame==4);
 assert(!strcmp(shared.playerNames[0],"Alice") && !strcmp(shared.playerNames[1],"Bob"));
 assert(row.stage==2 && row.startStage==2 && !strcmp(shared.stageCatalog[2],"Planet Namek"));
 currentStage=3;competitiveTraceCapture();assert(row.stage==3 && row.startStage==2);
 assert(row.sides[0].costume==1 && row.sides[1].costume==2);
 assert(row.sides[1].character==9 && row.sides[1].variant==2);
 gPortResim=1;*(int *)((uintptr_t)fighters[0]+0x948)=0x105;
 competitiveTraceCapture();assert(row.sides[0].action==0x105 && row.sides[0].actionClass==4 && row.resim==1);
 assert(row.sides[0].abilityId==333);
 competitiveTraceFrontier(101);assert(shared.frontier==101 && !(shared.sequence&1));
 competitiveTraceReset();assert(shared.epoch==2 && shared.latest==0);
 *(int *)((uintptr_t)fighters[0]+0x998)=100;competitiveTraceCapture();
 assert(row.epoch==2 && row.sides[0].character==-1);
 fighters[1]=0;competitiveTraceCapture();assert(row.sides[1].character==-1);
 tick+=TraceCapacity;competitiveTraceCapture();assert(row.blank==tick);
 // Offline Port_NetTick is stale; CPU FT must use the real wrapper's blank.
 online=false;shared.latest=0;
 competitiveTraceCapture(7000,false);assert(shared.latest==0);
 competitiveTraceCapture(7000,true);assert(shared.latest==7000);
 assert(shared.frames[7000%TraceCapacity].blank==7000);
 puts("combat trace tests passed");
 VirtualFree(mem,0,MEM_RELEASE);
}
