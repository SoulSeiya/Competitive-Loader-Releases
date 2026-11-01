#pragma once
#include <stddef.h>
#include <stdint.h>
static inline uint64_t CompetitiveArtRowHash(const uint8_t *rgba,int w,int h) {
    uint64_t hash=UINT64_C(14695981039346656037);
    const uint8_t *row=rgba+(size_t)w*(size_t)(h/2)*4;
    for(size_t i=0;i<(size_t)w*4;i++) hash=(hash^row[i])*UINT64_C(1099511628211);
    return hash;
}
