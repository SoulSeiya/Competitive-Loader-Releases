"""Game client presentation over the real room/social bridge. No demo actions."""
import tkinter as tk
from tkinter import ttk
import webbrowser
from unified_hub import UnifiedHub
from battle_hub import BG, PANEL, FIELD, TEXT, MUTED, ORANGE, BLUE, label, button
import competitive_loader as core
from client_updates import note_pages


RELEASES_URL = 'https://github.com/SoulSeiya/Competitive-Loader-Releases/releases'


class ClientHub(UnifiedHub):
    def build_layout(self):
        self.client_ready = False
        super().build_layout()
        if self.animation:
            self.animation.close()
            self.animation = None
        self.background_source=tk.PhotoImage(file=str(core.RESOURCE_ROOT/'assets'/'client_background.png'))
        self.background_image=self.background_source
        self.hero.itemconfigure(self.hero_background,image=self.background_image)
        self.dashboard.itemconfigure(self.app_background,image='')
        self.root.title('Rising Battle · Cliente privado')
        self.root.geometry('1380x820')
        # The header replaces the old navigation rail. Controls keep their real callbacks.
        for child in self.nav.winfo_children():
            child.pack_forget()
        self.nav_brand.pack(side='left', padx=(20,14), pady=12)
        self.nav_play.pack(side='left', padx=(0,20), pady=18)
        self.friend_toggle.pack(side='right', padx=16)
        self.friend_toggle.configure(text='Amigos', command=self.toggle_friends)
        self.nav_links.pack(side='left', fill='both', expand=True)
        self.nav_buttons['inbox'].configure(text='AMIGOS')
        self.home_title_text = 'Tu próximo'
        self.home_title_accent_text = 'gran combate.'
        self.hero.itemconfigure(self.home_title, text=self.home_title_text)
        self.hero.itemconfigure(self.home_title_accent, text=self.home_title_accent_text, fill=BLUE)
        self.hero.itemconfigure(self.home_kicker, text='COMPETITIVE EDITION / RISING BATTLE', fill=ORANGE)
        self.hero.itemconfigure(self.home_brand, image=self.hero_logo)
        for child in self.home_shelf.winfo_children():
            child.destroy()
        self.home_shortcut_captions = []
        shelf = tk.Frame(self.home_shelf, bg=BG)
        shelf.pack(fill='both', expand=True, padx=24, pady=8)
        for col,(title,detail,key) in enumerate((('SALAS BTC  →','Encuentra a tu próximo rival','room'),('TUS AMIGOS  →','Conversa, invita y desafía','inbox'))):
            shelf.columnconfigure(col,weight=1)
            group=tk.Frame(shelf,bg=BG);group.grid(row=0,column=col,sticky='nsew',padx=8)
            button(group,title,lambda k=key:self.show_section(k)).pack(anchor='w')
            caption=label(group,detail,9,MUTED);caption.pack(anchor='w')
            self.home_shortcut_captions.append(caption)
        self.news = tk.Frame(self.hero,bg=FIELD,highlightthickness=1,highlightbackground='#263544')
        self.news_item=self.hero.create_window(0,0,window=self.news,anchor='ne',tags='home')
        label(self.news,'NOVEDADES DEL LOADER',9,ORANGE).pack(anchor='w',padx=18,pady=(16,8))
        label(self.news,'Instalado: '+core.APP_VERSION_TEXT+' · Motor BTC fijo',8,MUTED).pack(anchor='w',padx=18,pady=(0,8))
        self.history_choice=ttk.Combobox(self.news,state='readonly',values=('Esta versión',))
        self.history_choice.current(0);self.history_choice.pack(fill='x',padx=18,pady=(0,10))
        self.history_choice.bind('<<ComboboxSelected>>',self.select_release_notes)
        self.release_history_rows=[]
        self.release_heading=tk.StringVar(value='Buscando publicaciones…')
        tk.Label(self.news,textvariable=self.release_heading,bg=FIELD,fg=TEXT,font=('Segoe UI Semibold',15),anchor='w').pack(fill='x',padx=18)
        self.release_state=tk.StringVar(value='La consulta se realiza en segundo plano.')
        self.release_status_label=tk.Label(self.news,textvariable=self.release_state,bg=FIELD,fg=BLUE,font=('Segoe UI',9),justify='left',anchor='w',wraplength=330)
        self.release_status_label.pack(fill='x',padx=18,pady=(8,12))
        self.notes_text=tk.Text(self.news,bg=FIELD,fg=MUTED,relief='flat',wrap='word',font=('Segoe UI',10),height=4,state='disabled',takefocus=True)
        self.notes_text.pack(fill='both',expand=True,padx=18)
        pages=tk.Frame(self.news,bg=FIELD);pages.pack(fill='x',padx=12,pady=4)
        button(pages,'‹',lambda:self.change_note(-1)).pack(side='left')
        self.notes_count=tk.StringVar(value='1 / 1')
        tk.Label(pages,textvariable=self.notes_count,bg=FIELD,fg=MUTED,font=('Segoe UI',9)).pack(side='left')
        button(pages,'›',lambda:self.change_note(1)).pack(side='left')
        button(pages,'Ver en GitHub ↗',lambda:webbrowser.open(RELEASES_URL)).pack(side='right')
        actions=tk.Frame(self.news,bg=FIELD);actions.pack(fill='x',padx=18,pady=(4,16))
        self.owner.check_updates_button=button(actions,'Buscar',self.owner._check_versions)
        self.owner.check_updates_button.pack(side='left')
        self.owner.update_button=button(actions,'Actualizar y reiniciar',self.owner.install_app_update,True)
        self.owner.update_button.pack(side='right');self.owner.update_button.configure(state='disabled')
        self.note_chunks=note_pages(core.VERSION_HIGHLIGHTS);self.note_index=0;self.change_note(0)
        self.release_info=None
        self.set_release_history([])
        self.news_summary=tk.Frame(self.hero,bg=FIELD,highlightthickness=1,highlightbackground='#263544')
        self.hero.itemconfigure(self.news_item,window=self.news_summary)
        label(self.news_summary,'NOVEDADES / GITHUB',9,ORANGE).pack(anchor='w',padx=16,pady=(12,6))
        tk.Label(self.news_summary,textvariable=self.release_heading,bg=FIELD,fg=TEXT,font=('Segoe UI Semibold',12),anchor='w').pack(fill='x',padx=16)
        tk.Label(self.news_summary,textvariable=self.release_state,bg=FIELD,fg=BLUE,font=('Segoe UI',9),anchor='w').pack(fill='x',padx=16,pady=4)
        button(self.news_summary,'Ver cambios y actualizaciones  →',lambda:self.show_section('updates')).pack(anchor='w',padx=8,pady=(0,6))
        # No typed character roster: only the numerical limit is configured here.
        label(self.duel_card,'Los personajes se eligen dentro del juego.',9,MUTED).pack(anchor='w',padx=16,pady=(0,10))
        # The native backend is retained for future private tournament work, but no
        # tournament navigation, organizer polling or spectator entry is shipped here.
        self.challonge_panel.refresh=lambda:None
        self.tournament_toggle.pack_forget()
        self.client_ready=True
        self._compact_density=None
        self.layout_dashboard()
        self.apply_section()

    def build_profile(self):
        self.profile_panel=self.card(self.body,'Mi perfil','Tu identidad se usa automáticamente en salas y combates.')
        row=tk.Frame(self.profile_panel,bg=PANEL);row.pack(fill='x',padx=24,pady=12)
        self.profile_avatar=tk.Canvas(row,width=128,height=128,bg=PANEL,highlightthickness=0)
        self.profile_avatar.pack(side='left',padx=(0,24))
        actions=tk.Frame(row,bg=PANEL);actions.pack(side='left',fill='both',expand=True)
        label(actions,'NOMBRE DE JUGADOR',9,MUTED).pack(anchor='w',pady=(8,10))
        tk.Entry(actions,textvariable=self.profile_name,bg=FIELD,fg=TEXT,insertbackground=ORANGE,relief='flat',font=('Segoe UI',14)).pack(fill='x',ipady=8)
        button(actions,'Guardar nombre',self.save_profile,True).pack(anchor='w',pady=12)
        buttons=tk.Frame(self.profile_panel,bg=PANEL);buttons.pack(fill='x',padx=24,pady=12)
        button(buttons,'Cambiar imagen',self.choose_avatar).pack(side='left')
        button(buttons,'Quitar imagen',self.remove_avatar).pack(side='left',padx=12)
        self.profile_stats=tk.StringVar();self.profile_metrics=[tk.StringVar(value='0') for _ in range(3)]
        tk.Label(self.profile_panel,textvariable=self.profile_stats,bg=PANEL,fg=BLUE,font=('Segoe UI',11)).pack(anchor='w',padx=24,pady=16)
        label(self.profile_panel,'El perfil y el historial se guardan en este PC.',10,MUTED).pack(anchor='w',padx=24,pady=8)

    def build_history(self):
        super().build_history()
        for child in self.history_panel.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget,ttk.Combobox):widget.configure(values=('Duelos',))

    def layout_dashboard(self):
        if not getattr(self,'client_ready',False):
            return super().layout_dashboard()
        width=max(820,self.root.winfo_width());height=max(480,self.dashboard.winfo_height())
        top=78
        visible=self.friends_open and (width>=1200 or self.friends_manual)
        self.friends_visible=visible
        right=242 if visible and width>=1200 else 0
        self.nav.place(x=0,y=0,width=width,height=top)
        self.shell.place(x=0,y=top,width=width-right,height=height-top)
        for item in (self.page_title_item,self.connection_item):self.dashboard.itemconfigure(item,state='hidden')
        if visible:
            self.social.place(x=width-242,y=top,width=242,height=height-top);self.social.lift()
        else:self.social.place_forget()
        self.friend_toggle.configure(text='Amigos  ×' if visible else 'Amigos  +')
        self.layout_navigation();self.queue_viewport()

    def layout_navigation(self,event=None):
        if not getattr(self,'client_ready',False):
            return super().layout_navigation(event)
        for b in self.nav_buttons.values():b.grid_forget()
        self.nav_more.grid_forget();self.nav_indicator.place_forget()
        for col in range(10):self.nav_links.columnconfigure(col,weight=0,minsize=0)
        width=self.root.winfo_width()
        links=('home','room','inbox') if width<1050 else ('home','room','inbox','history')
        key='inbox' if self.section in ('messages','challenge') else self.section
        for col,name in enumerate(links):
            b=self.nav_buttons[name];base='#080e15'
            b.configure(text={'home':'INICIO','room':'SALAS','inbox':'AMIGOS','history':'HISTORIAL'}[name],bg=base,fg=ORANGE if name==key else MUTED,padx=12,pady=18,anchor='center')
            b._hover_base=base;b.grid(row=0,column=col,sticky='ns',padx=3)
        self.hidden_navigation=['profile','settings','updates']+(['history'] if width<1050 else [])
        if 'updates' not in self.nav_buttons:
            self.nav_buttons['updates']=button(self.nav_links,'Novedades',lambda:self.show_section('updates'))
        self.nav_more.configure(text='PERFIL / AJUSTES',padx=10,pady=18)
        self.nav_more.grid(row=0,column=len(links),sticky='ns')
        self.nav_links.grid_anchor('w')

    def show_section(self,key):
        if key in ('tournament','bracket'):
            self.status.set('Los torneos se incorporarán en una versión posterior.')
            return
        super().show_section(key)

    def apply_section(self):
        if getattr(self,'client_ready',False) and self.section=='updates':
            self.mount_page(self.news);self.layout_dashboard();self.layout_navigation()
            return
        super().apply_section()

    def resize_hero(self,event):
        if not getattr(self,'client_ready',False):return super().resize_hero(event)
        w=max(600,self.canvas.winfo_width());h=max(400,self.canvas.winfo_height())
        wide=w>=1070
        compact=h<600 and not wide
        margin=32 if w>800 else 24
        self.hero.coords(self.hero_background,w/2,h/2)
        self.dashboard.coords(self.app_background,self.dashboard.winfo_width()/2,self.dashboard.winfo_height()/2)
        self.hero.coords(self.home_brand,margin,8 if compact else 18)
        self.hero.coords(self.home_kicker,margin,100 if compact else 126)
        self.hero.coords(self.home_title,margin,120 if compact else 151)
        self.hero.coords(self.home_title_accent,margin,158 if compact else 192)
        for item in (self.home_title,self.home_title_accent):self.hero.itemconfigure(item,font=('Segoe UI',29),anchor='nw')
        self.hero.coords(self.home_install,margin,204 if compact else 242);self.hero.itemconfigure(self.home_install,width=410,anchor='nw')
        bottom=276 if compact else 324
        self.hero.coords(self.hero_card,margin,bottom)
        self.hero.coords(self.home_room_item,margin+242,bottom)
        self.hero.coords(self.home_progress_item,margin+242,bottom)
        news_width=min(390,w-2*margin) if wide else w-2*margin
        if wide:
            self.hero.coords(self.news_item,w-margin,h-240)
            self.hero.itemconfigure(self.news_item,width=news_width,height=150)
        else:
            self.hero.coords(self.news_item,w-margin,288 if compact else 344)
            self.hero.itemconfigure(self.news_item,width=news_width,height=max(126,h-(366 if compact else 422)))
        self.release_status_label.configure(wraplength=news_width-38)
        self.hero.coords(self.home_shelf_item,0,h)
        self.hero.itemconfigure(self.home_shelf_item,width=w,height=76)
        self.hero.itemconfigure(self.home_credit,state='hidden')

    def change_note(self,delta):
        self.note_index=max(0,min(len(self.note_chunks)-1,self.note_index+delta))
        self.notes_text.configure(state='normal');self.notes_text.delete('1.0','end')
        self.notes_text.insert('1.0',self.note_chunks[self.note_index]);self.notes_text.configure(state='disabled')
        self.notes_count.set(f'{self.note_index+1} / {len(self.note_chunks)}')

    def set_release_history(self,rows):
        self.release_history_rows=[{'tag':core.APP_VERSION_TEXT,'name':'Esta versión · '+core.APP_VERSION_TEXT,'notes':core.VERSION_HIGHLIGHTS}]+rows
        self.history_choice.configure(values=tuple(r['name'] for r in self.release_history_rows))
        self.history_choice.current(1 if rows else 0)

    def select_release_notes(self,event=None):
        index=self.history_choice.current()
        if not 0<=index<len(self.release_history_rows):return
        self.note_chunks=note_pages(self.release_history_rows[index]['notes'])
        self.note_index=0;self.change_note(0)

    def display_release(self,info=None,error=None):
        from client_updates import classify_release
        self.release_info=info
        self.owner.pending_update=None
        if error:
            self.release_heading.set('No se pudo consultar GitHub')
            self.release_state.set('Puedes seguir jugando y volver a intentarlo.')
            self.note_chunks=note_pages(error+'\n\nNOVEDADES DE ESTA VERSIÓN\n'+core.VERSION_HIGHLIGHTS)
        else:
            state=classify_release(info)
            self.release_heading.set(info.get('name') or info['tag'])
            self.release_state.set({'current':'Estás al día.','available':f"Actualización disponible: {info['tag']}",'missing_asset':'Publicación encontrada; falta el paquete del Loader.'}[state])
            self.note_chunks=note_pages(info.get('notes'))
            if state=='available':self.owner.pending_update=info
        self.note_index=0;self.change_note(0)
        self.owner.check_updates_button.configure(text='Reintentar' if error else 'Buscar',state='normal')
        self.update_install_button()

    def update_install_button(self):
        blocked=self.owner.busy or bool(self.owner.session and self.owner.session.running)
        self.owner.update_button.configure(state='normal' if self.owner.pending_update and not blocked else 'disabled')

    def refresh(self):
        super().refresh()
        if getattr(self,'client_ready',False):
            self.tournament_toggle.pack_forget()
            self.update_install_button()

    def show_room_tab(self,key):
        # Full combat rules get a separate tab; wide windows show players + chat.
        if not getattr(self,'client_ready',False) or self.root.winfo_width()<1200 or key=='battle':
            return super().show_room_tab(key)
        self.room_tab=key
        self.left.grid_forget();self.right.grid_forget();self.duel_card.pack_forget()
        self.left.grid(row=0,column=0,sticky='nsew',padx=(0,16))
        self.right.grid(row=0,column=1,sticky='nsew')
        self.room_users.pack(fill='both',expand=True)
        self.columns.rowconfigure(0,weight=1)
        for name,b in self.room_tab_buttons.items():b.configure(fg=BLUE if name==key else MUTED)

    def reflow(self,event):
        mode=self.root.winfo_width()>=1200
        if mode!=getattr(self,'room_wide',None):
            self.room_wide=mode
            self.show_room_tab(getattr(self,'room_tab','players'))
