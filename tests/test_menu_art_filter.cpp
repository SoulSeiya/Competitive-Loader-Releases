#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <vector>
#include "../native/menu_art_filter.h"

int main() {
    // Matching pictures always pass the cheap gate. A nonmatching middle row is
    // rejected; a collision/same row must still go through the original full test.
    for(int w=1;w<=512;w*=2) for(int h=1;h<=512;h*=2) {
        std::vector<uint8_t> image((size_t)w*h*4),copy;
        for(size_t i=0;i<image.size();i++) image[i]=(uint8_t)(i*17+w+h);
        copy=image;
        const uint64_t row=CompetitiveArtRowHash(image.data(),w,h);
        assert(row==CompetitiveArtRowHash(copy.data(),w,h));
        const size_t middle=(size_t)w*(h/2)*4;
        copy[middle]^=0x5A;
        assert(row!=CompetitiveArtRowHash(copy.data(),w,h));
        copy=image;
        if(h>1) {
            const size_t other=h/2==0?(size_t)w*4:0;
            copy[other]^=0x5A;
            assert(row==CompetitiveArtRowHash(copy.data(),w,h));
            assert(memcmp(copy.data(),image.data(),image.size())!=0);
        }
    }
    // Main-menu art matches only its first 96 rows; altering the bottom 32
    // (the PC's own menu item) must not cause a false rejection.
    std::vector<uint8_t> menu(512*128*4,12),withPcItem=menu;
    memset(withPcItem.data()+512*96*4,99,512*32*4);
    assert(CompetitiveArtRowHash(menu.data(),512,128)==CompetitiveArtRowHash(withPcItem.data(),512,128));
}
