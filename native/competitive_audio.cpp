// Playback-only ADX end-marker fix for the pinned 0.1.35.2 Windows build.
// Never indexes sPlayers or writes gPortAdxView (the rollback-visible timeline).
#include <stdint.h>
#include <stddef.h>

struct AudioPrefix {
    void *stream;
    char path[512];
    uint8_t *file;
    uint32_t size, data, channels, rate, total;
    int loop;
    uint32_t loopStart, loopEnd;
};
static_assert(offsetof(AudioPrefix, total) == 544, "reviewed Player prefix changed");

extern "C" void ADXT_StartAfs(void *, int, int);
extern "C" bool SDL_LockAudioStream(void *);
extern "C" bool SDL_UnlockAudioStream(void *);

static void trim_end_marker(AudioPrefix *p) {
    if (!p->file || p->channels < 1 || p->channels > 2 || p->data >= p->size || !p->rate)
        return;
    const size_t stride = 18u * p->channels;
    uint32_t frames = (uint32_t)((p->size - p->data) / stride);
    const uint32_t declared = p->total / 32u + (p->total % 32u != 0);
    if (frames > declared) frames = declared;
    for (uint32_t frame = 0; frame < frames; ++frame) {
        const uint8_t *block = p->file + p->data + frame * stride;
        for (uint32_t channel = 0; channel < p->channels; ++channel) {
            // CRI/FFmpeg treats a frame header with bit 15 set as end of stream.
            if (block[channel * 18u] & 0x80) {
                const uint32_t end = frame * 32u;
                if (end < p->total && (!p->loop || end < p->loopEnd)) {
                    p->total = end;
                    p->loop = 0;
                }
                return;
            }
        }
    }
}

extern "C" void Competitive_AudioStartAfs(void *adxt, int patid, int fid) {
    ADXT_StartAfs(adxt, patid, fid);
    if (!adxt || patid != 2) return;
    AudioPrefix *p = (AudioPrefix *)adxt;
    if (!p->stream || !SDL_LockAudioStream(p->stream)) return;
    trim_end_marker(p);
    SDL_UnlockAudioStream(p->stream);
}
