// Three entry points share this one private cache. Original mode is for A/B only.
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "menu_art_filter.h"
extern int OriginalMenuArt(const char *,int,char *,size_t) __asm__("MenuLabels_Art");
extern unsigned OriginalMenuArtKey(void) __asm__("MenuLabels_ArtKey");
extern int OriginalMenuArtSwap(unsigned char *,int,int) __asm__("MenuLabels_ArtSwap");
static int btcArtEnabled(void) {
    static int on=-1;
    if(on<0) {
        const char *all=getenv("BTC_PERFORMANCE"),*v=getenv("BTC_FAST_MENU_ART");
        on=(!all||strcmp(all,"0")!=0)&&(!v||strcmp(v,"0")!=0);
    }
    return on;
}
#define MenuLabels_Art Competitive_MenuArt
#define MenuLabels_ArtKey Competitive_MenuArtKey
#define MenuLabels_ArtSwap Competitive_MenuArtSwap
#include "vendor_1381/gs/menu_labels.c"
