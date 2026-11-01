// Offline practice rules passed by the Loader (BTC_PRACTICE_*), CPU level and time index.
#include <assert.h>
#include <stdio.h>
#include "../native/competitive_practice.h"
int main(){
    CompetitivePracticeRules r={};
    assert(CompetitivePracticeParse("2","180","2",r) && r.ft==2 && r.seconds==180 && r.characters==2);
    assert(CompetitivePracticeParse("5","480","5",r) && r.ft==5 && r.seconds==480 && r.characters==5);
    // Anything unexpected keeps practice off (normal game).
    const char *bad[][3]={{0,"180","2"},{"","180","2"},{"0","180","2"},{"6","180","2"},{"2","200","2"},
                          {"2","180","0"},{"2","180","6"},{"2x","180","2"},{"-1","180","2"},{"2","18000","2"},{"2"," 180","2"}};
    for(auto &b:bad){CompetitivePracticeRules keep={9,9,9};assert(!CompetitivePracticeParse(b[0],b[1],b[2],keep)&&keep.ft==9);}
    assert(CompetitivePracticeTimeIndex(180)==1 && CompetitivePracticeTimeIndex(240)==2 &&
           CompetitivePracticeTimeIndex(360)==3 && CompetitivePracticeTimeIndex(480)==4 && CompetitivePracticeTimeIndex(60)==-1);
    // Max difficulty = CpuLevel_FromSetting(4) = 29; "no CPU" (-1) is never turned into a CPU.
    assert(CompetitivePracticeCpu(0)==29 && CompetitivePracticeCpu(13)==29 && CompetitivePracticeCpu(29)==29);
    assert(CompetitivePracticeCpu(-1)==-1 && CompetitivePracticeCpu(-999)==-999);
    puts("Practice OK");
}
