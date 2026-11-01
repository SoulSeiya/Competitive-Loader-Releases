// Presentation only. No input, result, netcode or gameplay state is modified.
// Everything here is drawn with the foreground draw list: no windows, no textures,
// no files and no network per frame. Times come from SDL_GetTicks (render side).
extern "C" int Port_HudSwap(void);

static void competitiveVisualTheme() {
    static ImGuiContext *styled;
    ImGuiContext *context=ImGui::GetCurrentContext();
    if(!context || context==styled) return;
    styled=context;
    ImGuiStyle &s=ImGui::GetStyle();
    s.WindowRounding=10; s.ChildRounding=8; s.FrameRounding=6; s.PopupRounding=8;
    s.GrabRounding=5; s.ScrollbarRounding=6;
    s.WindowPadding=ImVec2(18,16); s.FramePadding=ImVec2(10,7); s.ItemSpacing=ImVec2(10,9);
    s.Colors[ImGuiCol_WindowBg]=ImVec4(.035f,.055f,.085f,.98f);
    s.Colors[ImGuiCol_ChildBg]=ImVec4(.045f,.070f,.105f,1);
    s.Colors[ImGuiCol_PopupBg]=ImVec4(.055f,.085f,.125f,1);
    s.Colors[ImGuiCol_Border]=ImVec4(.15f,.21f,.29f,1);
    s.Colors[ImGuiCol_Text]=ImVec4(.92f,.95f,.99f,1);
    s.Colors[ImGuiCol_TextDisabled]=ImVec4(.48f,.57f,.68f,1);
    s.Colors[ImGuiCol_FrameBg]=ImVec4(.075f,.11f,.16f,1);
    s.Colors[ImGuiCol_FrameBgHovered]=ImVec4(.11f,.17f,.24f,1);
    s.Colors[ImGuiCol_FrameBgActive]=ImVec4(.15f,.21f,.30f,1);
    s.Colors[ImGuiCol_Button]=ImVec4(.11f,.16f,.23f,1);
    s.Colors[ImGuiCol_ButtonHovered]=ImVec4(.20f,.30f,.42f,1);
    s.Colors[ImGuiCol_ButtonActive]=ImVec4(.88f,.38f,.10f,1);
    s.Colors[ImGuiCol_Header]=ImVec4(.11f,.21f,.32f,1);
    s.Colors[ImGuiCol_HeaderHovered]=ImVec4(.15f,.30f,.46f,1);
    s.Colors[ImGuiCol_HeaderActive]=ImVec4(.20f,.38f,.56f,1);
    s.Colors[ImGuiCol_CheckMark]=ImVec4(1,.49f,.20f,1);
    s.Colors[ImGuiCol_SliderGrab]=ImVec4(1,.49f,.20f,1);
    s.Colors[ImGuiCol_SliderGrabActive]=ImVec4(1,.65f,.36f,1);
}

// ---- shared look -----------------------------------------------------------------
static const ImU32 competitiveInk=IM_COL32(241,245,250,255);
static const ImU32 competitiveMuted=IM_COL32(139,155,176,255);
static const ImU32 competitiveEmpty=IM_COL32(58,70,88,255);
static ImU32 competitiveAccent(int player) { return player?IM_COL32(107,185,240,255):IM_COL32(255,166,89,255); }
static ImU32 competitiveAlpha(ImU32 color,float alpha) {
    if(alpha<0)alpha=0; if(alpha>1)alpha=1;
    return (color&0x00FFFFFFu)|((ImU32)(((color>>24)&255)*alpha)<<24);
}
static float competitiveScale() {
    const ImVec2 screen=ImGui::GetIO().DisplaySize;
    float scale=screen.y/720.0f; if(scale<.65f)scale=.65f; if(scale>1.4f)scale=1.4f;
    return scale;
}
// Offline practice has no network names: the profile (BT3_NET_NAME) against the CPU.
static const char *competitiveNameOverride[2];
static const Uint64 competitivePracticeGgMs=4500;
static void competitivePracticeNames() {
    if(competitiveNameOverride[1]) return;
    const char *profile=SDL_getenv("BT3_NET_NAME");
    competitiveNameOverride[0]=profile&&*profile?profile:"Tú";
    competitiveNameOverride[1]="CPU · nivel máximo";
}
static const char *competitiveName(int player) {
    if(competitiveNameOverride[player&1]) return competitiveNameOverride[player&1];
    const char *name=Port_NetName(player);
    return name&&*name?name:player?"Jugador 2":"Jugador 1";
}
static ImVec2 competitiveMeasure(float size,const char *text) {
    return ImGui::GetFont()->CalcTextSizeA(size,1e6f,0,text);
}
// Shortens a name to fit, ending in "...", never splitting a UTF-8 character.
static const char *competitiveFit(char *out,unsigned capacity,const char *text,float size,float width) {
    SDL_snprintf(out,capacity,"%s",text);
    if(width<=0 || competitiveMeasure(size,out).x<=width) return out;
    unsigned length=(unsigned)strlen(out);
    while(length) {
        do --length; while(length && ((unsigned char)out[length]&0xC0)==0x80);
        if(length+4>capacity) continue;
        memcpy(out+length,"...",4);
        if(competitiveMeasure(size,out).x<=width) return out;
    }
    return out;
}
// align: 0 left, .5 centre, 1 right of x. A soft shadow keeps text legible over the stage.
static float competitiveText(ImDrawList *d,float size,ImVec2 p,ImU32 color,const char *text,float align=0) {
    const ImVec2 extent=competitiveMeasure(size,text);
    p.x-=extent.x*align;
    const float shadow=size>20?2.f:1.f;
    d->AddText(ImGui::GetFont(),size,ImVec2(p.x+shadow,p.y+shadow),competitiveAlpha(IM_COL32(0,0,0,255),((color>>24)&255)/255.f*.85f),text);
    d->AddText(ImGui::GetFont(),size,p,color,text);
    return extent.x;
}
static void competitivePips(ImDrawList *d,float x,float y,float scale,unsigned target,unsigned wins,int player,bool fromRight,float alpha,float fresh) {
    const float w=14*scale,h=5*scale,step=18*scale;
    for(unsigned n=0;n<target;++n) {
        const float px=fromRight?x-(n+1)*step+(step-w):x+n*step;
        const bool won=n<wins,latest=won&&n+1==wins&&fresh>0;
        ImU32 color=won?competitiveAccent(player):competitiveEmpty;
        if(latest) d->AddRectFilled(ImVec2(px-2*scale,y-2*scale),ImVec2(px+w+2*scale,y+h+2*scale),competitiveAlpha(competitiveAccent(player),.35f*fresh*alpha),3*scale);
        d->AddRectFilled(ImVec2(px,y),ImVec2(px+w,y+h),competitiveAlpha(color,alpha),2*scale);
    }
}
static void competitiveBadge(ImDrawList *d,float scale,ImVec2 anchor,float align,const char *text,ImU32 color,float alpha) {
    const float size=10.5f*scale,padX=7*scale,padY=3*scale;
    const ImVec2 extent=competitiveMeasure(size,text);
    const float w=extent.x+padX*2,h=extent.y+padY*2,x=anchor.x-w*align;
    d->AddRectFilled(ImVec2(x,anchor.y),ImVec2(x+w,anchor.y+h),competitiveAlpha(IM_COL32(7,13,22,235),alpha),3*scale);
    d->AddRect(ImVec2(x,anchor.y),ImVec2(x+w,anchor.y+h),competitiveAlpha(color,alpha),3*scale,0,1.2f*scale);
    d->AddText(ImGui::GetFont(),size,ImVec2(x+padX,anchor.y+padY),competitiveAlpha(color,alpha),text);
}

// The set as the player sees it: sides follow this copy's HUD (the joiner's own
// gauges are on the left when the game swaps them), colours stay P1 orange / P2 blue.
struct CompetitiveSet {
    unsigned wins[2], draws, target, winner; // winner: 0 none, 1 P1, 2 P2
    int me;                                  // 0 / 1, -1 unknown
    bool swapped;
    bool practice;                           // offline set against the CPU
    unsigned fight() const { return wins[0]+wins[1]+draws+1; }
    int left() const { return swapped?1:0; }
    bool setPoint(int player) const { return target>1 && !winner && wins[player]+1==target; }
};

// Render-side memory only (what was already shown), never read by the game.
struct CompetitiveMemory {
    bool active; unsigned seen[3]; Uint64 fresh[2];
    unsigned shownFight; Uint64 bannerAt;
    unsigned char history[16]; unsigned historyCount;
    void reset() { active=false; seen[0]=seen[1]=seen[2]=0; fresh[0]=fresh[1]=0; shownFight=0; bannerAt=0; historyCount=0; }
    void observe(const CompetitiveSet &s,bool show,Uint64 now) {
        // A new session restarts the confirmed counts: never carry the previous set's history.
        if(!show || s.wins[0]<seen[0] || s.wins[1]<seen[1] || s.draws<seen[2]) reset();
        if(!show) return;
        if(!active) { active=true; seen[0]=s.wins[0]; seen[1]=s.wins[1]; seen[2]=s.draws; }
        for(int p=0;p<2;++p) while(seen[p]<s.wins[p]) {
            ++seen[p]; fresh[p]=now;
            if(historyCount<16) history[historyCount++]=(unsigned char)(p+1);
        }
        while(seen[2]<s.draws) { ++seen[2]; if(historyCount<16) history[historyCount++]=4; }
    }
    float freshness(int p,Uint64 now) const {
        if(!fresh[p] || now-fresh[p]>1600) return 0;
        return 1.f-(float)(now-fresh[p])/1600.f;
    }
};

// ---- scoreboard during the set --------------------------------------------------
static void competitiveScorePanel(const CompetitiveSet &s,const CompetitiveMemory &m,Uint64 now) {
    const ImVec2 screen=ImGui::GetIO().DisplaySize;
    const float scale=competitiveScale();
    float width=480*scale; if(width>screen.x-24*scale) width=screen.x-24*scale;
    const float height=38*scale,left=(screen.x-width)*.5f,top=screen.y-height-8*scale;
    const float middle=screen.x*.5f,halfCenter=48*scale,pad=9*scale;
    ImDrawList *d=ImGui::GetForegroundDrawList();
    // No side cards: the stage remains visible behind both names. The score
    // alone gets a light scrim, with a faint border for bright stages.
    d->AddRectFilled(ImVec2(middle-halfCenter,top),ImVec2(middle+halfCenter,top+height),IM_COL32(7,13,22,72),5*scale);
    d->AddRect(ImVec2(middle-halfCenter,top),ImVec2(middle+halfCenter,top+height),IM_COL32(230,240,255,20),5*scale,0,1*scale);
    for(int side=0;side<2;++side) {
        const int player=side?1-s.left():s.left();
        const ImU32 accent=competitiveAccent(player);
        const float begin=side?middle+halfCenter+pad:left,end=side?left+width:middle-halfCenter-pad;
        const float x=side?end:begin,align=side?1.f:0.f;
        char tag[24],name[96];
        if(s.practice && player==1) SDL_snprintf(tag,sizeof(tag),"P2 CPU");
        else SDL_snprintf(tag,sizeof(tag),s.me==player?"P%d · TÚ":"P%d",player+1);
        d->PushClipRect(ImVec2(begin,top),ImVec2(end,top+height),true);
        competitiveText(d,8.5f*scale,ImVec2(x,top),competitiveAlpha(accent,.88f),tag,align);
        competitiveText(d,13*scale,ImVec2(x,top+11*scale),competitiveInk,
                        competitiveFit(name,sizeof(name),competitiveName(player),13*scale,end-begin),align);
        if(s.target && s.target<=5) {
            const float step=10*scale,w=7*scale,y=top+31*scale;
            for(unsigned n=0;n<s.target;++n) {
                const float px=side?x-(n+1)*step+(step-w):x+n*step;
                const bool won=n<s.wins[player];
                const float fresh=won&&n+1==s.wins[player]?m.freshness(player,now):0;
                d->AddRectFilled(ImVec2(px,y),ImVec2(px+w,y+2*scale),won?competitiveAlpha(accent,.85f):IM_COL32(220,230,245,55),1*scale);
                if(fresh>0) d->AddRectFilled(ImVec2(px-scale,y-scale),ImVec2(px+w+scale,y+3*scale),competitiveAlpha(accent,.18f*fresh),2*scale);
            }
        }
        d->PopClipRect();
    }
    char head[32],score[32];
    if(s.target) SDL_snprintf(head,sizeof(head),"FT%u",s.target);
    else SDL_snprintf(head,sizeof(head),"LIBRE");
    SDL_snprintf(score,sizeof(score),"%u  -  %u",s.wins[s.left()],s.wins[1-s.left()]);
    competitiveText(d,9*scale,ImVec2(middle,top+2*scale),competitiveMuted,head,.5f);
    competitiveText(d,22*scale,ImVec2(middle,top+12*scale),competitiveInk,score,.5f);
    // Set-point information is a short floating label, without another box.
    const char *point=s.setPoint(0)&&s.setPoint(1)?"DECISIVO":s.setPoint(0)||s.setPoint(1)?"PUNTO DE SET":NULL;
    if(point) competitiveText(d,8.5f*scale,ImVec2(middle,top-12*scale),competitiveAlpha(IM_COL32(255,214,102,255),.95f),point,.5f);
    else if(s.draws) {
        char text[24];SDL_snprintf(text,sizeof(text),s.draws==1?"1 empate":"%u empates",s.draws);
        competitiveText(d,8.5f*scale,ImVec2(middle,top-12*scale),competitiveMuted,text,.5f);
    }
}

// ---- short presentation at the start of every fight -----------------------------
static const Uint64 competitiveBannerMs=1500;
static void competitiveFightBanner(const CompetitiveSet &s,Uint64 shownAt,Uint64 now) {
    if(!shownAt || now<shownAt || now-shownAt>=competitiveBannerMs) return;
    const float t=(float)(now-shownAt);
    float alpha=t<220?t/220.f:t>competitiveBannerMs-450?(competitiveBannerMs-t)/450.f:1.f;
    const float ease=t<220?1.f-(1.f-t/220.f)*(1.f-t/220.f):1.f;
    const ImVec2 screen=ImGui::GetIO().DisplaySize;
    const float scale=competitiveScale();
    float width=600*scale; if(width>screen.x-40*scale) width=screen.x-40*scale;
    const float height=88*scale,middle=screen.x*.5f,top=screen.y*.22f+(1.f-ease)*8*scale;
    const float left=middle-width*.5f;
    ImDrawList *d=ImGui::GetForegroundDrawList();
    d->AddRectFilled(ImVec2(left,top),ImVec2(left+width,top+height),competitiveAlpha(IM_COL32(7,13,22,64),alpha),8*scale);
    const ImU32 l=competitiveAccent(s.left()),r=competitiveAccent(1-s.left());
    d->AddRectFilled(ImVec2(left,top),ImVec2(middle,top+3*scale),competitiveAlpha(l,alpha));
    d->AddRectFilled(ImVec2(middle,top),ImVec2(left+width,top+3*scale),competitiveAlpha(r,alpha));
    char title[32]; SDL_snprintf(title,sizeof(title),"COMBATE %u",s.fight());
    competitiveText(d,13*scale,ImVec2(middle,top+11*scale),competitiveAlpha(competitiveMuted,alpha),title,.5f);
    char score[32]; SDL_snprintf(score,sizeof(score),"%u - %u",s.wins[s.left()],s.wins[1-s.left()]);
    const float scoreSize=34*scale,nameSize=19*scale;
    const float scoreHalf=competitiveMeasure(scoreSize,score).x*.5f+18*scale;
    competitiveText(d,scoreSize,ImVec2(middle,top+30*scale),competitiveAlpha(competitiveInk,alpha),score,.5f);
    const float room=middle-scoreHalf-left-16*scale;
    char name[96];
    competitiveText(d,nameSize,ImVec2(middle-scoreHalf,top+38*scale),competitiveAlpha(l,alpha),competitiveFit(name,sizeof(name),competitiveName(s.left()),nameSize,room),1.f);
    competitiveText(d,nameSize,ImVec2(middle+scoreHalf,top+38*scale),competitiveAlpha(r,alpha),competitiveFit(name,sizeof(name),competitiveName(1-s.left()),nameSize,room),0.f);
    char line[128];
    if(s.setPoint(0)&&s.setPoint(1)) SDL_snprintf(line,sizeof(line),"COMBATE DECISIVO  ·  quien gane se lleva el set");
    else if(s.setPoint(0)||s.setPoint(1)) {
        char who[96];
        SDL_snprintf(line,sizeof(line),"PUNTO DE SET para %s",competitiveFit(who,sizeof(who),competitiveName(s.setPoint(0)?0:1),11.5f*scale,width*.6f));
    }
    else if(s.target) SDL_snprintf(line,sizeof(line),s.practice?"Primero a %u victorias  ·  CPU en dificultad máxima":"Primero a %u victorias",s.target);
    else SDL_snprintf(line,sizeof(line),"Combate libre");
    const bool point=s.setPoint(0)||s.setPoint(1);
    competitiveText(d,11.5f*scale,ImVec2(middle,top+66*scale),competitiveAlpha(point?IM_COL32(255,214,102,255):competitiveMuted,alpha),line,.5f);
}

// ---- end of the set -------------------------------------------------------------
static void competitiveWinnerPanel(const CompetitiveSet &s,const CompetitiveMemory &m,float progress,Uint64 now,Uint64 since) {
    if(!s.winner) return;
    const int champion=(int)s.winner-1;
    const ImVec2 screen=ImGui::GetIO().DisplaySize;
    const float scale=competitiveScale();
    float width=520*scale; if(width>screen.x*.92f) width=screen.x*.92f;
    const float height=230*scale,middle=screen.x*.5f;
    const float t=since&&now>since?(float)(now-since):1000.f;
    const float alpha=t<260?t/260.f:1.f;
    const float top=screen.y*.42f-height*.5f+(1.f-alpha)*12*scale,left=middle-width*.5f;
    ImDrawList *d=ImGui::GetForegroundDrawList();
    const ImU32 accent=competitiveAccent(champion);
    d->AddRectFilled(ImVec2(left,top),ImVec2(left+width,top+height),competitiveAlpha(IM_COL32(7,13,22,126),alpha),10*scale);
    d->AddRect(ImVec2(left,top),ImVec2(left+width,top+height),competitiveAlpha(IM_COL32(140,160,185,45),alpha),10*scale,0,1*scale);
    d->AddRectFilled(ImVec2(left,top),ImVec2(left+width,top+4*scale),competitiveAlpha(accent,alpha),10*scale,ImDrawFlags_RoundCornersTop);
    const float pad=22*scale;
    char head[48]; SDL_snprintf(head,sizeof(head),s.practice?"PRÁCTICA VS CPU  ·  FT%u":s.target?"SET COMPLETADO  ·  FT%u":"SET COMPLETADO",s.target);
    competitiveText(d,11*scale,ImVec2(left+pad,top+16*scale),competitiveAlpha(competitiveMuted,alpha),head);
    if(s.me==0||s.me==1)
        competitiveBadge(d,scale,ImVec2(left+width-pad,top+12*scale),1.f,s.me==champion?"VICTORIA":"DERROTA",
                         s.me==champion?accent:IM_COL32(150,160,175,255),alpha);
    competitiveText(d,48*scale,ImVec2(middle,top+34*scale),competitiveAlpha(competitiveInk,alpha),"GG",.5f);
    char name[96];
    competitiveText(d,24*scale,ImVec2(middle,top+88*scale),competitiveAlpha(accent,alpha),
                    competitiveFit(name,sizeof(name),competitiveName(champion),24*scale,width-pad*2),.5f);
    competitiveText(d,11*scale,ImVec2(middle,top+117*scale),competitiveAlpha(competitiveMuted,alpha),"gana el set",.5f);
    // Final score in this copy's side order.
    char score[32]; SDL_snprintf(score,sizeof(score),"%u - %u",s.wins[s.left()],s.wins[1-s.left()]);
    const float scoreSize=22*scale,half=competitiveMeasure(scoreSize,score).x*.5f+14*scale,row=top+138*scale;
    competitiveText(d,scoreSize,ImVec2(middle,row),competitiveAlpha(competitiveInk,alpha),score,.5f);
    const float side=middle-half-left-pad;
    competitiveText(d,14*scale,ImVec2(middle-half,row+5*scale),competitiveAlpha(competitiveAccent(s.left()),alpha),
                    competitiveFit(name,sizeof(name),competitiveName(s.left()),14*scale,side),1.f);
    competitiveText(d,14*scale,ImVec2(middle+half,row+5*scale),competitiveAlpha(competitiveAccent(1-s.left()),alpha),
                    competitiveFit(name,sizeof(name),competitiveName(1-s.left()),14*scale,side),0.f);
    // Fight by fight, as this copy confirmed them.
    if(m.historyCount) {
        const float tile=16*scale,gap=5*scale,total=m.historyCount*tile+(m.historyCount-1)*gap,y=top+172*scale;
        float x=middle-total*.5f;
        for(unsigned i=0;i<m.historyCount;++i,x+=tile+gap) {
            const unsigned r=m.history[i];
            const ImU32 color=r==1?competitiveAccent(0):r==2?competitiveAccent(1):competitiveEmpty;
            d->AddRectFilled(ImVec2(x,y),ImVec2(x+tile,y+tile),competitiveAlpha(color,alpha),4*scale);
            char n[8]; SDL_snprintf(n,sizeof(n),r==4?"E":"%u",i+1);
            competitiveText(d,10.5f*scale,ImVec2(x+tile*.5f,y+4*scale),competitiveAlpha(r==4?competitiveInk:IM_COL32(7,13,22,255),alpha),n,.5f);
        }
    }
    const float barY=top+height-16*scale,barL=left+pad,barR=left+width-pad;
    if(progress<0)progress=0; if(progress>1)progress=1;
    d->AddRectFilled(ImVec2(barL,barY),ImVec2(barR,barY+3*scale),competitiveAlpha(competitiveEmpty,alpha),2*scale);
    d->AddRectFilled(ImVec2(barL,barY),ImVec2(barL+(barR-barL)*progress,barY+3*scale),competitiveAlpha(accent,alpha),2*scale);
    competitiveText(d,10.5f*scale,ImVec2(barL,barY-15*scale),competitiveAlpha(competitiveMuted,alpha),
                    s.practice?"Revancha en el menú del juego: el siguiente combate empieza un set nuevo.":"Volviendo al menú online...");
}
