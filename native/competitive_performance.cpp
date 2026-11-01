// Windows wait adapted from upstream v0.1.38.2 (MIT, z3xox and contributors).
// The engine is unchanged on disk. Original pacing state remains the single clock.
#include <windows.h>
#include <time.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <mmsystem.h>
#include "pacing_rules.h"

extern "C" {
void OriginalPaceWait(void) __asm__("vblank_wait");
int Port_SpeedMilli(void);
extern uint64_t sPaceNext, sPacePrev, sPaceMin, sPaceMax, gPortSleptNs;
extern unsigned sPaceCount, sPaceOff, sPaceLate, sPaceReset, gPortPaceShiftNs;
}

static bool competitivePerformanceEnabled() {
    static int on=-1;
    if(on<0) {
        const char *all=getenv("BTC_PERFORMANCE"),*v=getenv("BTC_PRECISE_TIMING");
        on=(!all||strcmp(all,"0")!=0)&&v&&strcmp(v,"0")!=0;
    }
    return on!=0;
}
static uint64_t competitiveNowNs() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC,&ts);
    return (uint64_t)ts.tv_sec*1000000000ull+(uint64_t)ts.tv_nsec;
}

typedef HANDLE (WINAPI *CompetitiveCreateTimer)(void *,const WCHAR *,DWORD,DWORD);
typedef BOOL (WINAPI *CompetitiveSetTimer)(HANDLE,const LARGE_INTEGER *,LONG,void *,void *,BOOL);
typedef BOOL (WINAPI *CompetitiveSetInfo)(HANDLE,int,void *,DWORD);
static HANDLE competitiveTimer;
static CompetitiveSetTimer competitiveSetTimer;
static void competitiveInitTimer() {
    static bool initialized;
    if(initialized) return;
    initialized=true;
    timeBeginPeriod(1);
    HMODULE kernel=GetModuleHandleW(L"kernel32.dll");
    CompetitiveSetInfo info=(CompetitiveSetInfo)GetProcAddress(kernel,"SetProcessInformation");
    struct { ULONG version,control,state; } throttle={1,0x1|0x4,0};
    BOOL policy=info?info(GetCurrentProcess(),4,&throttle,sizeof(throttle)):FALSE;
    CompetitiveCreateTimer create=(CompetitiveCreateTimer)GetProcAddress(kernel,"CreateWaitableTimerExW");
    competitiveSetTimer=(CompetitiveSetTimer)GetProcAddress(kernel,"SetWaitableTimer");
    if(create&&competitiveSetTimer) competitiveTimer=create(NULL,NULL,0x2,0x1F0003);
    // The kernel releases this process-lifetime handle at exit, as in upstream.
    fprintf(stderr,"btc: performance timer=%s process_policy=%d\n",competitiveTimer?"high-resolution":"legacy-fallback",(int)policy);
}

extern "C" void Competitive_PaceWait() {
    if(!competitivePerformanceEnabled()) { OriginalPaceWait();return; }
    const uint64_t t=competitiveNowNs();
    const uint64_t period=16683350ull*1000ull/(unsigned)Port_SpeedMilli();
    const CompetitivePacePlan plan=CompetitivePlanPace(t,sPaceNext,gPortPaceShiftNs,period);
    gPortPaceShiftNs=0;
    uint64_t after=t;
    if(plan.kind==PaceLate) ++sPaceLate;
    else if(plan.kind==PaceWait) {
        competitiveInitTimer();
        if(competitiveTimer) {
            if(plan.deadline-t>400000ull) {
                LARGE_INTEGER due;due.QuadPart=-(LONGLONG)((plan.deadline-t-400000ull)/100ull);
                if(competitiveSetTimer(competitiveTimer,&due,0,NULL,NULL,FALSE)) WaitForSingleObject(competitiveTimer,INFINITE);
            }
            while(competitiveNowNs()<plan.deadline) YieldProcessor();
        } else {
            // Original path handles timeBeginPeriod and older Windows. It must
            // see the pending shift because we have not consumed this tick yet.
            gPortPaceShiftNs=(unsigned)(plan.deadline-sPaceNext);
            OriginalPaceWait();return;
        }
        after=competitiveNowNs();gPortSleptNs+=after-t;
    } else ++sPaceReset;
    sPaceNext=plan.next;
    if(sPacePrev) {
        const uint64_t d=after-sPacePrev;
        if(d<sPaceMin) sPaceMin=d;
        if(d>sPaceMax) sPaceMax=d;
        if(d>18000000ull||d<15400000ull) ++sPaceOff;
    }
    sPacePrev=after;
    if(++sPaceCount==60) {
        if(getenv("BT3_GS_VERBOSE")) fprintf(stderr,"pace: 60 vertical blanks: %u.%02u to %u.%02u ms apart, %u reached late (not waited for), %u new grids\n",
            (unsigned)(sPaceMin/1000000ull),(unsigned)(sPaceMin/10000ull%100),
            (unsigned)(sPaceMax/1000000ull),(unsigned)(sPaceMax/10000ull%100),sPaceLate,sPaceReset);
        sPaceCount=sPaceOff=sPaceLate=sPaceReset=0;sPaceMin=~0ull;sPaceMax=0;
    }
}
