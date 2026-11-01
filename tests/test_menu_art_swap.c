// Runs the production adapted decoder/swap against a texture from the user's
// extracted files. No copyrighted texture is included in this test source.
#include <assert.h>
#include "../native/competitive_menu_art.c"

int OriginalMenuArt(const char *p,int b,char *w,size_t n) {(void)p;(void)b;(void)w;(void)n;return 77;}
unsigned OriginalMenuArtKey(void) {return 78;}
int OriginalMenuArtSwap(unsigned char *p,int w,int h) {(void)p;(void)w;(void)h;return 79;}

// Linkage for unrelated catalogue/font entry points in the included source.
// The swap test must never depend on a translation service or a user's settings.
int MenuTranslation_Ensure(void){assert(0);return 0;}
int MenuTranslation_Load(const char *p,char *w,size_t n){assert(0);return 0;}
const char *MenuTranslation_Text(const char *p){assert(0);return NULL;}
const char *MenuTranslation_Original(const char *p){assert(0);return NULL;}
const char *MenuTranslation_Group(const char *p){assert(0);return NULL;}
const char *const *MenuTranslation_StageNames(void){assert(0);return NULL;}
const char *const *MenuTranslation_SongNames(void){assert(0);return NULL;}
const char *MenuTranslation_MainOriginal(void){assert(0);return NULL;}
const char *MenuTranslation_ItemOriginal(void){assert(0);return NULL;}

static uint8_t *textureBytes,*expected;
static size_t textureSize;
static int width,height;
static int findTexture(MlBuf d,int depth) {
    if(depth>8) return 0;
    if(ml_is_texture_file(d)) {
        MlCtx *c=calloc(1,sizeof(*c));MlTex t={0};
        if(ml_art_decode(c,d,0,0,&t)>0&&t.w>0&&t.h>0&&t.w<=512&&t.h<=512) {
            width=t.w;height=t.h;textureSize=d.n;
            textureBytes=malloc(d.n);memcpy(textureBytes,d.p,d.n);
            expected=malloc((size_t)width*height*4);memcpy(expected,t.rgba,(size_t)width*height*4);
            ml_free(c);free(c);return 1;
        }
        ml_free(c);free(c);
    }
    unsigned n=ml_table_count(d);
    if(n>1024) return 0;
    for(unsigned i=1;i<=n;i++) {
        MlBuf child=ml_part(d,i);
        if(findTexture(child,depth+1)) return 1;
        size_t size=0;uint8_t *unpacked=ml_member(child,0,&size);
        if(unpacked) {int ok=findTexture((MlBuf){unpacked,size},depth+1);free(unpacked);if(ok)return 1;}
    }
    return 0;
}
static uint64_t fullHash(const uint8_t *p,size_t n) {
    uint64_t h=UINT64_C(14695981039346656037);
    for(size_t i=0;i<n;i++)h=(h^p[i])*UINT64_C(1099511628211);
    return h;
}
int main(int argc,char **argv) {
    assert(argc==2);
    if(!strcmp(argv[1],"--legacy")) {
        putenv("BTC_PERFORMANCE=0");
        assert(Competitive_MenuArt(NULL,0,NULL,0)==77);
        assert(Competitive_MenuArtKey()==78);
        assert(Competitive_MenuArtSwap(NULL,0,0)==79);
        return 0;
    }
    FILE *f=fopen(argv[1],"rb");assert(f);
    fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    uint8_t *data=malloc(n);assert(data&&fread(data,1,n,f)==(size_t)n);fclose(f);
    assert(findTexture((MlBuf){data,(size_t)n},0));
    size_t bytes=(size_t)width*height*4;
    uint8_t *input=malloc(bytes),*saved=malloc(bytes);
    memcpy(input,expected,bytes);input[0]^=1;
    uint64_t mid=CompetitiveArtRowHash(input,width,height);
    MlArt art={0};art.hash=fullHash(input,bytes);art.mid=mid;art.w=width;art.h=height;
    sArt=&art;sArtCount=1;sArtMid=&mid;sArtMidCount=1;
    sArtFile=calloc(1,sizeof(*sArtFile));sArtFile[0].p=textureBytes;sArtFile[0].n=textureSize;
    sArtSize[ml_log2(width)][ml_log2(height)]=1;
    __atomic_store_n(&sArtReady,1,__ATOMIC_RELEASE);
    assert(Competitive_MenuArtKey()==0x41525431u);
    // A true hit must still decode and replace the complete texture correctly.
    assert(Competitive_MenuArtSwap(input,width,height)==1);
    assert(memcmp(input,expected,bytes)==0);
    // Rejected middle-row data must not alter a single output byte.
    memcpy(input,expected,bytes);input[(size_t)width*(height/2)*4]^=0x5A;
    memcpy(saved,input,bytes);
    assert(Competitive_MenuArtSwap(input,width,height)==0);
    assert(memcmp(input,saved,bytes)==0);
    // A matching row is only a filter, never a replacement for the full hash.
    if(height>1) {
        memcpy(input,expected,bytes);input[0]^=0x5B;memcpy(saved,input,bytes);
        assert(CompetitiveArtRowHash(input,width,height)==mid);
        assert(Competitive_MenuArtSwap(input,width,height)==0);
        assert(memcmp(input,saved,bytes)==0);
    }
    assert(Competitive_MenuArtSwap(NULL,width,height)==0);
    assert(Competitive_MenuArtSwap(input,0,height)==0);
    printf("Production menu-art swap OK with %dx%d texture; hit, misses and legacy mode tested separately\n",width,height);
    free(input);free(saved);free(sArtFile);free(textureBytes);free(expected);free(data);
}
