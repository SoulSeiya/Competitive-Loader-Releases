"""Viewport-sized tournament pages. No scrollbars or scroll-based navigation."""
import math
import tkinter as tk
from tkinter import ttk, font, messagebox
from battle_hub import PANEL,FIELD,BORDER,TEXT,MUTED,ORANGE,BLUE,button
from menu_layout import action_grid,fit_columns

STATES={'pending':'Pendiente','open':'Listo para jugar','underway':'En juego','complete':'Finalizado','completed':'Finalizado'}

class TournamentView(tk.Frame):
    def __init__(self,parent):
        super().__init__(parent,bg=PANEL)
        self.snapshot=None;self.tab='main';self.zoom=1.;self.selected=None
        self.round_page=0;self.match_page=0;self.visible_match_ids=[];self.pending=None
        bar=tk.Frame(self,bg=PANEL);bar.pack(fill='x',pady=(0,6));self.toolbar=bar;bar.columnconfigure(0,weight=1)
        self.tab_area=tk.Frame(bar,bg=PANEL);self.tab_area.grid(row=0,column=0,sticky='ew')
        self.zoom_area=tk.Frame(bar,bg=PANEL);self.zoom_area.grid(row=0,column=1,sticky='e')
        self.tabs={}
        for key,title in (('main','CUADRO PRINCIPAL'),('losers','LOSERS'),('players','PARTICIPANTES')):
            b=button(self.tab_area,title,lambda k=key:self.show(k));b.configure(padx=7,pady=6);self.tabs[key]=b
        action_grid(self.tab_area,list(self.tabs.values()),160)
        self.zoom_label=tk.Label(self.zoom_area,bg=PANEL,fg=MUTED,font=('Segoe UI',9),width=5)
        button(self.zoom_area,'−',lambda:self.resize(-.15)).grid(row=0,column=0)
        self.zoom_label.grid(row=0,column=1)
        button(self.zoom_area,'+',lambda:self.resize(.15)).grid(row=0,column=2)
        bar.bind('<Configure>',self.layout_toolbar)
        self.navigation=tk.Frame(self,bg=PANEL);self.navigation.pack(side='bottom',fill='x',pady=6)
        self.navigation.columnconfigure(0,weight=1);self.navigation.columnconfigure(1,weight=1)
        rounds=tk.Frame(self.navigation,bg=PANEL);rounds.grid(row=0,column=0,sticky='w')
        self.round_previous=button(rounds,'‹',lambda:self.navigate('round',-1));self.round_previous.pack(side='left')
        self.round_text=tk.Label(rounds,bg=PANEL,fg=BLUE,font=('Segoe UI',9),width=22);self.round_text.pack(side='left')
        self.round_next=button(rounds,'›',lambda:self.navigate('round',1));self.round_next.pack(side='left')
        matches=tk.Frame(self.navigation,bg=PANEL);matches.grid(row=0,column=1,sticky='e')
        self.match_previous=button(matches,'‹',lambda:self.navigate('match',-1));self.match_previous.pack(side='left')
        self.match_text=tk.Label(matches,bg=PANEL,fg=MUTED,font=('Segoe UI',9),width=22);self.match_text.pack(side='left')
        self.match_next=button(matches,'›',lambda:self.navigate('match',1));self.match_next.pack(side='left')
        self.detail=tk.StringVar(value='Selecciona un cruce para consultar su resultado.')
        detail_area=tk.Frame(self,bg=PANEL);detail_area.pack(side='bottom',fill='x',pady=4)
        self.detail_label=tk.Label(detail_area,textvariable=self.detail,bg=PANEL,fg=MUTED,font=('Segoe UI',9),height=2,justify='left',anchor='w')
        self.detail_label.pack(side='left',fill='x',expand=True)
        self.detail_button=button(detail_area,'Detalle',self.open_detail);self.detail_button.pack(side='right')
        self.detail_button.configure(state='disabled',pady=4)
        self.area=tk.Frame(self,bg=FIELD);self.area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(self.area,bg=FIELD,width=1,height=1,highlightthickness=0)
        self.players=ttk.Treeview(self.area,columns=('seed','name','rank'),show='headings',height=1,style='Battle.Treeview')
        for key,title in (('seed','SEED'),('name','PARTICIPANTE / EQUIPO'),('rank','PUESTO')):
            self.players.heading(key,text=title)
        fit_columns(self.players,dict(seed=1,name=7,rank=1))
        self.players.bind('<MouseWheel>',lambda e:'break');self.canvas.bind('<MouseWheel>',lambda e:'break')
        self.canvas.bind('<Configure>',self.queue_render)
        self.players.bind('<Configure>',self.queue_render,add='+')
        self.bind('<Configure>',self.layout_view,add='+')
        self.show('main')

    def layout_toolbar(self,event=None):
        stacked=self.toolbar.winfo_width()<640
        if stacked==getattr(self,'_stacked_toolbar',None):return
        self._stacked_toolbar=stacked
        self.tab_area.grid_configure(columnspan=2 if stacked else 1)
        self.zoom_area.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1,columnspan=2 if stacked else 1)

    def layout_view(self,event=None):
        self.detail_label.configure(wraplength=max(180,self.winfo_width()-110))
        self.queue_render()

    def queue_render(self,event=None):
        if self.pending is None:self.pending=self.after_idle(self._render_idle)

    def _render_idle(self):
        self.pending=None;self.render(self.snapshot)

    def show(self,key):
        self.tab=key;self.round_page=0;self.match_page=0
        self.canvas.pack_forget();self.players.pack_forget()
        (self.players if key=='players' else self.canvas).pack(fill='both',expand=True)
        for tab,b in self.tabs.items():
            base='#173448' if tab==key else PANEL;b._hover_base=base
            b.configure(bg=base,fg=BLUE if tab==key else MUTED,highlightbackground=BLUE if tab==key else PANEL)
        self.render(self.snapshot)

    def resize(self,delta):
        self.zoom=round(min(1.3,max(.85,self.zoom+delta)),2);self.render(self.snapshot)

    def navigate(self,kind,delta):
        if kind=='round':self.round_page=max(0,min(self.round_pages-1,self.round_page+delta));self.match_page=0
        else:self.match_page=max(0,min(self.match_pages-1,self.match_page+delta))
        self.render(self.snapshot)

    def choose(self,match_id):self.selected=match_id;self.render(self.snapshot)

    def open_detail(self):
        if self.selected:messagebox.showinfo('Detalle del cruce',self.detail.get(),parent=self.winfo_toplevel())

    def _buttons(self):
        for b,enabled in ((self.round_previous,self.round_page>0),(self.round_next,self.round_page+1<self.round_pages),(self.match_previous,self.match_page>0),(self.match_next,self.match_page+1<self.match_pages)):
            b.configure(state='normal' if enabled else 'disabled')

    def render(self,snapshot):
        self.snapshot=snapshot;c=self.canvas;c.delete('all');self.visible_match_ids=[]
        self.zoom_label.configure(text=f'{int(self.zoom*100)}%')
        matches=snapshot.get('matches',[]) if snapshot else []
        has_losers=any(m['round']<0 for m in matches)
        self.tabs['losers'].configure(state='normal' if has_losers else 'disabled')
        if self.tab=='losers' and not has_losers:self.show('main');return
        selected=next((m for m in matches if m['id']==self.selected),None)
        self.detail.set(f"Cruce {selected['identifier']} · {STATES.get(selected['state'],selected['state'])}\n{selected['name1']}  vs  {selected['name2']}\nResultado: {selected.get('scores') or 'Sin resultado publicado'}" if selected else 'Selecciona un cruce para consultar su resultado.')
        self.detail_button.configure(state='normal' if selected else 'disabled')
        self.round_pages=self.match_pages=1
        if self.tab=='players':
            rows=snapshot.get('participants',[]) if snapshot else []
            row_height=int(ttk.Style(self).lookup('Battle.Treeview','rowheight') or 32)
            capacity=max(1,(self.players.winfo_height()-32)//row_height)
            self.match_pages=max(1,math.ceil(len(rows)/capacity));self.match_page=min(self.match_page,self.match_pages-1)
            self.players.delete(*self.players.get_children())
            start=self.match_page*capacity
            for index,p in enumerate(rows[start:start+capacity]):
                a=p.get('attributes',p);self.players.insert('','end',iid=str(start+index),values=(a.get('seed') or '—',a.get('name','Por definir'),a.get('final_rank') or '—'))
            self.round_text.configure(text='Participantes')
            self.match_text.configure(text=f'Página {self.match_page+1}/{self.match_pages}')
            self._buttons();return
        width=max(1,c.winfo_width());height=max(1,c.winfo_height())
        c.configure(scrollregion=(0,0,width,height));c.xview_moveto(0);c.yview_moveto(0)
        rounds=sorted({m['round'] for m in matches if (m['round']<0)==(self.tab=='losers')},key=abs)
        columns=max(1,min(len(rounds) or 1,int(width/(280*self.zoom))))
        self.round_pages=max(1,math.ceil(len(rounds)/columns));self.round_page=min(self.round_page,self.round_pages-1)
        shown=rounds[self.round_page*columns:(self.round_page+1)*columns]
        rows=max(1,int((height-46)/(170*self.zoom)))
        most=max((sum(m['round']==r for m in matches) for r in shown),default=0)
        self.match_pages=max(1,math.ceil(most/rows));self.match_page=min(self.match_page,self.match_pages-1)
        self.round_text.configure(text=f'Rondas · {self.round_page+1}/{self.round_pages}')
        self.match_text.configure(text=f'Cruces · {self.match_page+1}/{self.match_pages}')
        self._buttons()
        if not rounds:
            c.create_text(20,24,text='Challonge todavía no ha generado los cruces.',anchor='nw',width=max(100,width-40),fill=MUTED,font=('Segoe UI',11));return
        gap=14;card_width=max(1,(width-24-gap*(columns-1))/columns)
        card_height=max(1,(height-54-gap*(rows-1))/rows)
        name_font=font.Font(self,font=('Segoe UI',max(9,int(11*self.zoom))))
        for col,round_no in enumerate(shown):
            x=12+col*(card_width+gap)
            c.create_text(x,12,text=('LOSERS · ' if round_no<0 else 'RONDA ')+str(abs(round_no)),anchor='nw',fill=BLUE,font=('Segoe UI Semibold',10))
            group=[m for m in matches if m['round']==round_no]
            for row,m in enumerate(group[self.match_page*rows:(self.match_page+1)*rows]):
                y=40+row*(card_height+gap);bottom=y+card_height;tag='match:'+m['id'];self.visible_match_ids.append(m['id'])
                active=m['state'] in ('open','underway');outline=BLUE if m['id']==self.selected else ORANGE if active else BORDER
                c.create_rectangle(x,y,x+card_width,bottom,fill=PANEL,outline=outline,tags=tag)
                c.create_text(x+12,y+10,text=f"{m['identifier']} · {STATES.get(m['state'],m['state'])}",anchor='nw',fill=ORANGE if active else MUTED,font=('Segoe UI',9),tags=tag)
                available=max(1,int((card_height-70)/2/name_font.metrics('linespace')))
                for side in (1,2):
                    name=m['name'+str(side)];text=self.fit_name(name,name_font,max(30,card_width-24),available)
                    pos=y+34+(side-1)*max(20,(card_height-68)/2)
                    c.create_text(x+12,pos,text=text,anchor='nw',fill=ORANGE if m.get('winner') and m['winner']==m['p'+str(side)] else TEXT,font=name_font,tags=tag)
                c.create_text(x+card_width-12,bottom-10,text=str(m.get('scores') or '—'),anchor='se',fill=BLUE,font=('Segoe UI Semibold',10),tags=tag)
                c.tag_bind(tag,'<Button-1>',lambda e,key=m['id']:self.choose(key))
                c.tag_bind(tag,'<Double-1>',lambda e:self.open_detail())

    @staticmethod
    def fit_name(text,face,width,lines):
        result=[];remaining=text
        for index in range(lines):
            if face.measure(remaining)<=width:result.append(remaining);return '\n'.join(result)
            size=1
            while size<len(remaining) and face.measure(remaining[:size+1]+('…' if index==lines-1 else ''))<=width:size+=1
            if index==lines-1:result.append(remaining[:size].rstrip()+'…');return '\n'.join(result)
            cut=remaining.rfind(' ',0,size+1);cut=cut if cut>0 else size
            result.append(remaining[:cut]);remaining=remaining[cut:].lstrip()
        return '\n'.join(result)
