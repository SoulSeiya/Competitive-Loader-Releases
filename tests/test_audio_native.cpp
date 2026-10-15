#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "../native/competitive_audio.cpp"

static int starts, locks, unlocks;
static bool allow_lock = true;
extern "C" void ADXT_StartAfs(void *, int, int) { ++starts; }
extern "C" bool SDL_LockAudioStream(void *) { ++locks; return allow_lock; }
extern "C" bool SDL_UnlockAudioStream(void *) { ++unlocks; return true; }

int main(int argc, char **argv) {
    if (argc == 2) {
        FILE *fp = fopen(argv[1], "rb");
        assert(fp);
        fseek(fp, 0, SEEK_END);
        const long size = ftell(fp);
        rewind(fp);
        uint8_t *file = (uint8_t *)malloc(size);
        assert(file && fread(file, 1, size, fp) == (size_t)size);
        fclose(fp);
        AudioPrefix real = {};
        real.stream = &real;
        real.file = file;
        real.size = (uint32_t)size;
        real.data = ((unsigned)file[2] << 8 | file[3]) + 4;
        real.channels = file[7];
        real.rate = (unsigned)file[8] << 24 | (unsigned)file[9] << 16 | (unsigned)file[10] << 8 | file[11];
        real.total = (unsigned)file[12] << 24 | (unsigned)file[13] << 16 | (unsigned)file[14] << 8 | file[15];
        const uint32_t before = real.total;
        Competitive_AudioStartAfs(&real, 2, 0);
        printf("Real ADX: %u -> %u playback samples\n", before, real.total);
        assert(real.total < before);
        free(file);
        return 0;
    }
    uint8_t audio[64 + 18 * 8] = {};
    struct { AudioPrefix prefix; uint8_t extra[1024]; } larger = {};
    AudioPrefix *p = &larger.prefix;
    memset(larger.extra, 0x5a, sizeof(larger.extra));
    p->stream = p;
    p->file = audio;
    p->size = sizeof(audio);
    p->data = 64;
    p->channels = 1;
    p->rate = 44100;
    p->total = 256;
    p->loop = 1;
    p->loopEnd = 256;
    audio[64 + 2 * 18] = 0x80;
    uint8_t original[sizeof(audio)];
    memcpy(original, audio, sizeof(audio));
    Competitive_AudioStartAfs(p, 2, 0);
    assert(p->total == 64 && p->loop == 0);
    assert(starts == 1 && locks == 1 && unlocks == 1);
    assert(memcmp(original, audio, sizeof(audio)) == 0);
    for (unsigned i = 0; i < sizeof(larger.extra); ++i) assert(larger.extra[i] == 0x5a);
    // Stereo: the marker may be in the second channel's frame header.
    memset(audio, 0, sizeof(audio));
    p->channels = 2;
    p->total = 128;
    audio[64 + 36 + 18] = 0x80;
    Competitive_AudioStartAfs(p, 2, 1);
    assert(p->total == 32);
    // Bit 15 inside compressed samples is not an end marker.
    memset(audio, 0, sizeof(audio));
    audio[64 + 2] = 0x80;
    p->total = 128;
    Competitive_AudioStartAfs(p, 2, 1);
    assert(p->total == 128);
    audio[64] = 0x80;
    allow_lock = false;
    Competitive_AudioStartAfs(p, 2, 1);
    assert(p->total == 128);
    allow_lock = true;
    Competitive_AudioStartAfs(p, 1, 1);
    assert(p->total == 128);
    puts("Audio tests OK: mono/stereo EOF, sample alignment, lock failure, AFS scope, larger Player, unchanged file.");
}
