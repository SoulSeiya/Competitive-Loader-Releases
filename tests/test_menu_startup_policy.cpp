#include "../native/menu_startup_policy.h"
#include <cassert>
#include <cstdio>
int main() {
    CompetitiveMenuHelloCache cache;
    assert(cache.request(0));
    assert(!cache.request(0));
    assert(!cache.request(1));
    assert(!cache.request(59999));
    assert(cache.request(60000));
    assert(!cache.request(60001));
    assert(cache.request(120000));
    assert(cache.request(240001));
    std::puts("PASS: native hello cache starts immediately and refreshes after 60 seconds");
}
