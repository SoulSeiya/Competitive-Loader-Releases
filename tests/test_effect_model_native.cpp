#include <windows.h>
#include <assert.h>
#include <string.h>
#include "../native/competitive_effect_model.cpp"
extern "C" { uint32_t gHeapStart[2], gHeapEnd[2]; }
static unsigned calls, observed;
extern "C" int BtlObj_Create(int, void *resource, int active) {
    ++calls;
    observed = ((EffectModelResource *)resource)->size;
    assert(active == 1);
    return 7;
}
// This is the pre-existing loader's checked access that rejected effect models.
static const void *checked_model(const EffectModelResource &r) {
    const uint32_t *p = (const uint32_t *)(uintptr_t)r.model;
    return p[3] < p[4] && p[4] <= r.size ? (const char *)p + p[3] : NULL;
}
int main() {
    void *region = NULL;
    for (uintptr_t at = 0x40000000; at < 0x70000000 && !region; at += 0x1000000)
        region = VirtualAlloc((void *)at, 0x10000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    assert(region);
    const uintptr_t start = (uintptr_t)region;
    gHeapStart[0] = (uint32_t)start; gHeapEnd[0] = (uint32_t)(start + 0x10000);
    EffectHeapBlock *block = (EffectHeapBlock *)region;
    *block = {0x53484254, 1, 0, 0x20, 0x10000, (uint32_t)(start + 0x20), 0xffdc, 0};
    uint32_t *pack = (uint32_t *)(start + 0x220);
    pack[0] = 16; pack[1] = 0x50; pack[2] = 0x50;
    pack[3] = 0x100; pack[4] = 0x200; pack[17] = 0x300;
    EffectModelResource r = {};
    r.model = (uint32_t)(uintptr_t)pack; r.size = 0x20;
    assert(!checked_model(r)); // reproduces the null model passed to BindFiles
    assert(Competitive_EffectModelCreate(1, &r, 1) == 7);
    assert(r.size == 0x300 && observed == 0x300 && checked_model(r) == (char *)pack + 0x100);
    assert(effect_model_length(pack, 0x1ff) == 0); // truncated model stays rejected
    pack[0] = 0xffffffff;
    assert(effect_model_length(pack, 0x1000) == 0x1000); // non-counted header uses the verified owner span
    pack[0] = 16;
    r.size = 0x20; r.id = 123;
    Competitive_EffectModelCreate(1, &r, 1);
    assert(r.size == 0x20); // real file descriptors aren't synthetic effects
    r.id = 0; r.otherFiles[0] = 1;
    Competitive_EffectModelCreate(1, &r, 1);
    assert(r.size == 0x20);
    r.otherFiles[0] = 0;
    Competitive_EffectModelCreate(0, &r, 1);
    assert(r.size == 0x20);
    block->used = 0;
    Competitive_EffectModelCreate(1, &r, 1);
    assert(r.size == 0x20); // never trust a released allocation
    block->used = 1; block->size = 0;
    assert(effect_model_available(r.model) == 0); // malformed heap cannot loop
    assert(calls == 5);
    VirtualFree(region, 0, MEM_RELEASE);
    puts("Effect model OK: reproduces null model, restores bounded extent, leaves ordinary resources unchanged.");
}
