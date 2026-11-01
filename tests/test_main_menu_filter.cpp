#include "../native/main_menu_filter.h"
#include <cassert>
#include <cstdio>
int main() {
    int cases = 0;
    for (int online = 0; online < 2; ++online)
    for (int unlocked = 0; unlocked < 2; ++unlocked) {
        int original[12], n = 0;
        for (int item = 0; item < 11; ++item) {
            if ((!online && item == 4) || (!unlocked && item == 10)) continue;
            original[n++] = item;
            if (item == (online ? 4 : 3)) original[n++] = 11;
        }
        for (int top = 0; top < n; ++top)
        for (int cursor = 0; cursor < 4; ++cursor) {
            int items[12]; for(int i=0;i<n;++i) items[i]=original[i];
            int count=n, resultTop=top;
            const int selected=items[(top+cursor+1)%n];
            CompetitiveFilterMainMenu(items,count,resultTop,cursor);
            assert(count==n-1 && resultTop>=0 && resultTop<count);
            int k=0;
            for(int i=0;i<n;++i) if(original[i]!=11) assert(items[k++]==original[i]);
            assert(items[(resultTop+cursor+1)%count] == (selected==11 ? 0 : selected));
            CompetitiveFilterMainMenu(items,count,resultTop,cursor);
            assert(count==n-1); // No-op on subsequent calls.
            ++cases;
        }
    }
    std::printf("PASS: %d menu selection cases\n",cases);
}
