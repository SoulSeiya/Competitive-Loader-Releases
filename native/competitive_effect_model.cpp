#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

// The reviewed game uses 32-bit addresses inside its resource/heap records.
struct EffectHeapBlock {
    uint32_t magic, used, fromTail, alignment, size, data, dataSize, unused;
};
struct EffectModelResource {
    uint32_t model, size, id, original;
    uint32_t otherFiles[8];
};
static_assert(sizeof(EffectHeapBlock) == 0x20, "native heap layout");
static_assert(sizeof(EffectModelResource) == 0x30, "native effect resource layout");
extern "C" {
extern uint32_t gHeapStart[2], gHeapEnd[2];
int BtlObj_Create(int, void *, int);
}
#ifdef _MSC_VER
#define EffectModelLog fprintf
#else
extern "C" int EffectModelLog(FILE *, const char *, ...) __asm__("fprintf");
#endif

static size_t effect_model_available(uint32_t model) {
    for (unsigned heap = 0; heap < 2; ++heap) {
        uintptr_t cursor = gHeapStart[heap], end = gHeapEnd[heap];
        if (!cursor || model < cursor || model >= end) continue;
        while (cursor < end && end - cursor >= sizeof(EffectHeapBlock)) {
            const EffectHeapBlock *block = (const EffectHeapBlock *)cursor;
            if (block->magic != 0x53484254 || block->size < 0x24 || block->size > end - cursor) break;
            const uintptr_t data = block->data;
            const uintptr_t limit = data + block->dataSize;
            if (block->used == 1 && data >= cursor + sizeof(EffectHeapBlock) &&
                    limit <= cursor + block->size - 4 && model >= data && model < limit)
                return (size_t)(limit - model);
            cursor += block->size;
        }
    }
    return 0;
}

static uint32_t effect_model_length(const uint32_t *pack, size_t available) {
    if (!pack || available < 20 || available > 0x7fffffff) return 0;
    const uint32_t model = pack[3] & ~3u, next = pack[4] & ~3u;
    // Model buffers use this offset table even when their first word isn't a
    // counted-archive header. Require the model header to stay in its owner.
    if (model < 20 || next <= model || next > available || next - model < 0x70) return 0;
    const uint32_t count = pack[0];
    if (count >= 4 && count <= (available / 4) - 2) {
        const size_t header = ((size_t)count + 2) * 4;
        const uint32_t first = pack[1] & ~3u, total = pack[count + 1] & ~3u;
        if (first >= header && first <= model && next <= total && total <= available) return total;
    }
    // Otherwise use the remaining live allocation as the checked upper bound.
    // Never manufacture an unlimited length or read outside its parent block.
    return (uint32_t)available;
}

extern "C" int Competitive_EffectModelCreate(int type, void *resource, int active) {
    EffectModelResource *res = (EffectModelResource *)resource;
    if (type == 1 && res && res->model && res->size == 0x20 && !res->id && !res->original) {
        bool borrowed = true;
        for (unsigned i = 0; i < 8; ++i) if (res->otherFiles[i]) borrowed = false;
        if (borrowed) {
            // EftObj_Create sets size=0x20 for an embedded model, not its byte
            // length. Recover its real extent inside the owning live allocation
            // so the existing checked table binder can accept valid entries.
            const size_t available = effect_model_available(res->model);
            const uint32_t length = effect_model_length((const uint32_t *)(uintptr_t)res->model, available);
            if (length) {
                res->size = length;
                EffectModelLog(stderr, "bt3: effect model: embedded size 32 -> %u (allocation remainder %zu)\n", length, available);
            } else {
                EffectModelLog(stderr, "bt3: effect model: cannot validate embedded model %08x (allocation remainder %zu)\n", res->model, available);
            }
        }
    }
    return BtlObj_Create(type, resource, active);
}
