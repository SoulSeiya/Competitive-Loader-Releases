"""Single-window BTC interface; room and combat commands retain their existing bridge."""
import queue
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog
from battle_hub import BattleHub, BG, PANEL, FIELD, BORDER, TEXT, MUTED, ORANGE, BLUE, label, button
import competitive_loader as core
from menu_layout import action_grid,fit_columns
from table_pages import TablePages


class UnifiedHub(BattleHub):
    def card(self,parent,title,detail=''):
        # A section belongs to the page, rather than floating above another card.
        panel=tk.Frame(parent,bg=PANEL,highlightthickness=0)
        top_level=parent is getattr(self,'body',None)
        size=28 if top_level else 17
        heading=label(panel,title,size,TEXT)
        heading.configure(font=('Segoe UI Semibold',size))
        heading.pack(anchor='w',padx=24,pady=(5 if top_level else 18,10))
        if top_level:
            eyebrow=label(panel,'RISING BATTLE  /  TU ARENA',8,BLUE)
            eyebrow.pack(anchor='w',padx=24,pady=(22,2),before=heading)
        wrapped=[heading]
        if detail:
            subtitle=label(panel,detail,11,MUTED,justify='left',wraplength=720)
            subtitle.pack(anchor='w',padx=24,pady=(0,22));wrapped.append(subtitle)
        def wrap(event):
            for w in wrapped:w.configure(wraplength=max(120,event.width-48))
        panel.bind('<Configure>',wrap,add='+')
        return panel

    def wallpaper(self,parent):
        return tk.Frame(parent,bg=BG)

    def rules_selector(self,parent):
        area=tk.Frame(parent,bg=PANEL);area.pack(fill='x',padx=16,pady=12)
        label(area,'REGLAS DEL COMBATE',9,MUTED).pack(anchor='w',pady=(0,10))
        ftrow=tk.Frame(area,bg=PANEL);ftrow.pack(anchor='w')
        controls=[]
        for number in range(1,6):
            b=button(ftrow,f'FT {number}',lambda n=number:self.ft.set(str(n)))
            b.configure(padx=10,pady=8,width=7);b.grid(row=0,column=number-1,sticky='ew',padx=3)
            ftrow.columnconfigure(number-1,weight=1);controls.append((b,number))
        def selection(*_):
            for b,n in controls:
                chosen=self.ft.get()==str(n);base=ORANGE if chosen else FIELD
                b._hover_base=base;b.configure(bg=base,fg=BG if chosen else TEXT,highlightbackground=base)
        self.ft.trace_add('write',selection);selection()
        description=tk.StringVar()
        def explain(*_):description.set(f'Gana el primero en conseguir {self.ft.get()} victorias.')
        self.ft.trace_add('write',explain);explain()
        tk.Label(area,textvariable=description,bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(9,14))
        details=tk.Frame(area,bg=PANEL);details.pack(fill='x')
        for col,(title,var,values) in enumerate((('TIEMPO · SEGUNDOS',self.seconds,(180,240,360,480)),('PERSONAJES POR JUGADOR',self.characters,(1,2,3,4,5)))):
            details.columnconfigure(col,weight=1)
            label(details,title,8,BLUE).grid(row=0,column=col,sticky='w',padx=3)
            ttk.Combobox(details,textvariable=var,values=values,state='readonly',width=7,font=('Segoe UI',12)).grid(row=1,column=col,sticky='ew',padx=3,pady=8,ipady=5)

    def build_social_pages(self):
        self.inbox_panel=self.card(self.body,'Tu comunidad BTC','Comparte tu código para recibir solicitudes de amistad.')
        row=tk.Frame(self.inbox_panel,bg=PANEL);row.pack(fill='x',padx=18,pady=10)
        tk.Label(row,textvariable=self.friend_code,bg=PANEL,fg=BLUE,font=('Segoe UI Semibold',14)).pack(side='left')
        button(row,'Agregar amigo',self.add_friend,True).pack(side='right')
        self.social_tabs=tk.Frame(self.inbox_panel,bg=PANEL);self.social_tabs.pack(fill='x',padx=18,pady=(10,14))
        self.social_tab_buttons={}
        for key,title in (('friends','AMIGOS'),('requests','SOLICITUDES')):
            b=button(self.social_tabs,title,lambda k=key:self.show_social_tab(k));b.pack(side='left',padx=(0,8));self.social_tab_buttons[key]=b
        self.friends_page=tk.Frame(self.inbox_panel,bg=PANEL)
        self.requests_page=tk.Frame(self.inbox_panel,bg=PANEL)
        self.social_empty_friends=label(self.friends_page,'Tu próxima rivalidad empieza con una amistad.\nAgrega a alguien con su código BTC.',12,MUTED,justify='left')
        self.social_empty_friends.pack(anchor='w',padx=24,pady=(30,40))
        self.social_center_tree=ttk.Treeview(self.friends_page,columns=('state',),show='tree',style='Battle.Treeview',height=6)
        self.social_center_tree.column('#0',width=250);self.social_center_tree.column('state',width=140)
        fit_columns(self.social_center_tree,{'#0':3,'state':2})
        self.social_center_tree.bind('<Button-3>',lambda e:self.friend_context(e,self.social_center_tree))
        self.social_center_tree.bind('<Double-1>',lambda e:self.open_selected_friend(self.social_center_tree))
        self.social_empty_requests=label(self.requests_page,'Estás al día',18,TEXT)
        self.social_empty_requests.pack(anchor='w',padx=24,pady=(28,8))
        self.social_requests_hint=label(self.requests_page,'Tus solicitudes, invitaciones y desafíos aparecerán aquí.',10,MUTED)
        self.social_requests_hint.pack(anchor='w',padx=24,pady=(0,40))
        self.inbox_tree=ttk.Treeview(self.requests_page,columns=('name','kind'),show='headings',style='Battle.Treeview',height=6)
        self.inbox_tree.heading('name',text='JUGADOR');self.inbox_tree.heading('kind',text='SOLICITUD')
        fit_columns(self.inbox_tree,dict(name=3,kind=2))
        self.request_actions=tk.Frame(self.requests_page,bg=PANEL)
        self.request_accept=button(self.request_actions,'Aceptar / leer',lambda:self.answer_social(True),True)
        self.request_reject=button(self.request_actions,'Rechazar',lambda:self.answer_social(False))
        self.request_accept.pack(side='left',padx=(0,10));self.request_reject.pack(side='left')
        self.inbox_tree.bind('<<TreeviewSelect>>',lambda e:self.update_social_actions())
        self.show_social_tab('friends')
        self.messages_panel=self.card(self.body,'Mensajes privados')
        self.message_title=tk.StringVar(value='Selecciona un amigo')
        tk.Label(self.messages_panel,textvariable=self.message_title,bg=PANEL,fg=BLUE,font=('Segoe UI',13)).pack(anchor='w',padx=18,pady=10)
        self.dm_text=tk.Text(self.messages_panel,bg=FIELD,fg=TEXT,state='disabled',height=14,wrap='word',relief='flat',font=('Segoe UI',11),padx=14,pady=14)
        self.dm_text.pack(fill='both',expand=True,padx=16,pady=10)
        self.dm_input=tk.StringVar()
        composer=tk.Frame(self.messages_panel,bg=PANEL);composer.pack(fill='x',padx=18,pady=(4,18))
        composer.columnconfigure(0,weight=1)
        entry=tk.Entry(composer,textvariable=self.dm_input,bg=FIELD,fg=TEXT,insertbackground=ORANGE,relief='flat',font=('Segoe UI',11))
        entry.grid(row=0,column=0,sticky='ew',ipady=12,padx=(0,10));entry.bind('<Return>',lambda e:self.send_dm())
        button(composer,'Enviar',self.send_dm,True).grid(row=0,column=1,sticky='ew')
        self.challenge_panel=self.card(self.body,'Desafiar a un amigo','El rival debe aceptar. El duelo se prepara sin compartir códigos.')
        self.challenge_name=tk.StringVar();self.challenge_peer=None
        tk.Label(self.challenge_panel,textvariable=self.challenge_name,bg=PANEL,fg=BLUE,font=('Segoe UI',16)).pack(anchor='w',padx=18,pady=10)
        self.rules_selector(self.challenge_panel)
        button(self.challenge_panel,'Enviar desafío',self.send_friend_challenge,True).pack(anchor='w',padx=18,pady=16)

    def show_social_tab(self,key):
        self.friends_page.pack_forget();self.requests_page.pack_forget()
        (self.friends_page if key=='friends' else self.requests_page).pack(fill='both',expand=True,pady=(0,8))
        for name,b in self.social_tab_buttons.items():
            base='#173448' if name==key else PANEL
            b._hover_base=base;b.configure(bg=base,fg=BLUE if name==key else MUTED,highlightbackground=BLUE if name==key else PANEL)
        self.queue_viewport()

    def open_social_requests(self):
        self.show_section('inbox');self.show_social_tab('requests')

    def update_social_actions(self):
        state='normal' if self.inbox_tree.selection() else 'disabled'
        self.request_accept.configure(state=state);self.request_reject.configure(state=state)

    def update_social_content(self):
        for tree,empty in ((self.social_center_tree,self.social_empty_friends),(self.inbox_tree,self.social_empty_requests)):
            populated=bool(tree.get_children())
            if populated:
                empty.pack_forget()
                if not tree.winfo_manager():tree.pack(fill='both',expand=True,padx=18,pady=(4,8))
                tree.configure(height=1)
            else:
                tree.pack_forget()
                if not empty.winfo_manager():empty.pack(anchor='w',padx=24,pady=(28,16))
        if self.inbox_tree.get_children():
            self.social_requests_hint.pack_forget();self.request_actions.pack(fill='x',padx=18,pady=(0,16))
        else:
            self.request_actions.pack_forget()
            if not self.social_requests_hint.winfo_manager():self.social_requests_hint.pack(anchor='w',padx=24,pady=(0,32))
        self.update_social_actions()

    def social_send(self,op,**values):
        try:self.owner.social.submit(op,**values);self.status.set('Procesando solicitud social…')
        except queue.Full:self.status.set('Espera antes de enviar otra solicitud.')

    def copy_friend_code(self):
        if self.owner.social.snapshot:
            self.root.clipboard_clear();self.root.clipboard_append(self.owner.social.snapshot['me']['code']);self.status.set('Código de amigo copiado.')

    def add_friend(self):
        code=simpledialog.askstring('Agregar amigo','Código de amigo BTC:',parent=self.root)
        if code:self.social_send('add',code=code.strip().upper())

    def open_selected_friend(self,tree):
        selected=tree.selection()
        if selected:self.open_dm(selected[0])

    def open_dm(self,peer):
        friend=next((f for f in (self.owner.social.snapshot or {}).get('friends',[]) if f['id']==peer),None)
        if not friend:return
        self.chat_peer=peer;self.owner.social.chat_target=peer;self.message_title.set(friend['name'])
        self.show_section('messages');self.social_send('messages',target=peer)

    def send_dm(self):
        text=self.dm_input.get().strip()
        if text and self.chat_peer:
            if len(text)>500:self.status.set('Máximo 500 caracteres por mensaje.');return
            self.social_send('message',target=self.chat_peer,text=text);self.dm_input.set('')

    def friend_context(self,event,tree):
        peer=tree.identify_row(event.y)
        if not peer:return
        tree.selection_set(peer)
        friend=next((f for f in (self.owner.social.snapshot or {}).get('friends',[]) if f['id']==peer),None)
        if not friend:return
        menu=tk.Menu(self.root,tearoff=False,bg=FIELD,fg=TEXT,activebackground='#304a68',activeforeground=ORANGE,borderwidth=1)
        menu.add_command(label='Enviar mensaje',command=lambda:self.open_dm(peer))
        menu.add_command(label='Invitar a mi sala',command=lambda:self.invite_friend(peer),state='normal' if self.bridge.client else 'disabled')
        menu.add_command(label='Desafiar a duelo',command=lambda:self.prepare_friend_challenge(friend),state='normal' if friend['online'] else 'disabled')
        menu.add_separator();menu.add_command(label='Eliminar amigo',command=lambda:self.social_send('remove_friend',target=peer))
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()

    def room_context(self,event):
        row=self.users.identify_row(event.y)
        if not row:return
        self.users.selection_set(row)
        menu=tk.Menu(self.root,tearoff=False,bg=FIELD,fg=TEXT,activebackground='#304a68',activeforeground=ORANGE)
        menu.add_command(label='Desafiar a este jugador',command=self.challenge,state=self.challenge_button.cget('state'))
        menu.add_command(label='Agregar amigo por código…',command=self.add_friend)
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()

    def invite_friend(self,peer):
        if not self.bridge.client:return
        self.social_send('invite',target=peer,room_code=self.bridge.invite,room_token=self.bridge.client.token)

    def prepare_friend_challenge(self,friend):
        if self.bridge.client:self.status.set('Sal de tu sala actual para preparar un duelo directo con tu amigo.');return
        self.challenge_peer=friend['id'];self.challenge_name.set('Contra '+friend['name']);self.show_section('challenge')

    def send_friend_challenge(self):
        if not self.challenge_peer:return
        if self.bridge.client:self.status.set('Ya estás en otra sala. Sal antes de enviar un desafío.');return
        self.social_send('challenge',target=self.challenge_peer,ft=int(self.ft.get()),seconds=int(self.seconds.get()),characters=int(self.characters.get()))

    def answer_social(self,accept):
        selected=self.inbox_tree.selection()
        if not selected:return
        item=self.social_rows.get(selected[0])
        if not item:return
        kind,data=item
        if kind=='friend':self.social_send('accept_friend' if accept else 'reject_friend',target=data['id'])
        elif kind=='message':
            if accept:self.open_dm(data['sender'])
        else:
            if accept and self.bridge.client:self.status.set('Sal de tu sala actual antes de aceptar esta invitación.');return
            self.social_send('accept' if accept else 'decline',event=data['id'])

    def refresh_social(self):
        social=self.owner.social
        social.activity='playing' if self.owner.session and self.owner.session.running else 'tournament' if self.snapshot and self.snapshot.get('room_kind')=='tournament' else 'room' if self.snapshot else 'online'
        self.social_status.set(social.status)
        try:
            while True:self.status.set(social.notices.get_nowait())
        except queue.Empty:pass
        import time
        try:
            launch=social.launches.get_nowait();self.pending_social_launch=launch;self.social_launch_deadline=time.monotonic()+120;self.social_launch_attempt=0
        except queue.Empty:pass
        pending=getattr(self,'pending_social_launch',None)
        if pending:
            if self.bridge.client and self.bridge.invite==pending['room_code']:self.pending_social_launch=None
            elif time.monotonic()>self.social_launch_deadline:
                self.pending_social_launch=None;self.status.set('Caducó la conexión pendiente. Envía un nuevo desafío.')
            elif self.bridge.client:self.status.set('Sal de tu sala actual para abrir la invitación aceptada.')
            elif time.monotonic()-self.social_launch_attempt>5:
                try:self.bridge.submit(45,address=self.endpoint.get(),key=pending['room_code'],text=pending['token'])
                except queue.Full:pass
                else:
                    self.social_launch_attempt=time.monotonic();self.section='room';self.apply_section();self.status.set('Conectando con tu amigo…')
        snapshot=social.snapshot
        if not snapshot:return
        self.friend_code.set(snapshot['me']['code']);self.friend_code_button.configure(text=snapshot['me']['code']+'  ·  Copiar')
        unread=len(snapshot['incoming'])+len(snapshot['events']);self.requests_button.configure(text=f'Solicitudes y mensajes ({unread})')
        signature=repr((snapshot['friends'],snapshot['incoming'],snapshot['events']))
        if signature!=self.social_signature:
            self.social_signature=signature
            for tree in (self.friends_tree,self.social_center_tree):
                if tree in self.table_pages:self.table_pages[tree].reset()
                selection=tree.selection();tree.delete(*tree.get_children())
                for f in sorted(snapshot['friends'],key=lambda f:(not f['online'],f['name'].casefold())):
                    activity={'offline':'Desconectado','online':'Conectado','playing':'En el juego','room':'En sala','tournament':'En torneo'}.get(f['activity'],'Conectado')
                    tree.insert('','end',iid=f['id'],text=f['name'],values=(activity,),tags=('online' if f['online'] else 'offline',))
                tree.tag_configure('online',foreground=BLUE);tree.tag_configure('offline',foreground=MUTED)
                if selection and tree.exists(selection[0]):tree.selection_set(selection[0])
                if tree in self.table_pages:self.table_pages[tree].capture()
            self.table_pages[self.inbox_tree].reset()
            self.inbox_tree.delete(*self.inbox_tree.get_children());self.social_rows={}
            for request in snapshot['incoming']:
                key='friend:'+request['id'];self.social_rows[key]=('friend',request);self.inbox_tree.insert('','end',iid=key,values=(request['name'],'Solicitud de amistad'))
            for e in snapshot['events']:
                key='event:'+e['id'];self.social_rows[key]=(e['kind'],e)
                detail='Mensaje privado' if e['kind']=='message' else f"Desafío FT{e.get('ft')} · {e.get('seconds')} s · {e.get('characters')} personajes" if e['kind']=='challenge' else 'Invitación: '+e.get('title','Sala BTC')
                self.inbox_tree.insert('','end',iid=key,values=(e['name'],detail))
            self.table_pages[self.inbox_tree].capture()
            self.update_social_content()
        convo=social.conversation
        if convo and convo['target']==self.chat_peer:
            signature=repr(convo)
            if signature!=getattr(self,'conversation_signature',None):
                self.conversation_signature=signature;self.dm_text.configure(state='normal');self.dm_text.delete('1.0','end')
                for message in convo['messages']:
                    author='Tú' if message['sender']==snapshot['me']['id'] else self.message_title.get()
                    self.dm_text.insert('end',author+'\n'+message['text']+'\n\n')
                self.dm_text.configure(state='disabled');self.dm_text.see('end')

    def enable_tree_hover(self,tree):
        tree.tag_configure('hover',background='#203149');current=[None]
        def move(event=None):
            row=tree.identify_row(event.y) if event else None
            if row==current[0]:return
            if current[0] and tree.exists(current[0]):tree.item(current[0],tags=tuple(t for t in tree.item(current[0],'tags') if t!='hover'))
            if row:tree.item(row,tags=tuple(tree.item(row,'tags'))+('hover',))
            current[0]=row
        tree.bind('<Motion>',move);tree.bind('<Leave>',lambda e:move())

    def close(self):
        self._ui_closed=True
        self.nav_links.unbind('<Configure>')
        for timer in ('viewport_timer','transition_timer'):
            if getattr(self,timer,None):
                try:self.canvas.after_cancel(getattr(self,timer))
                except tk.TclError:pass
        if getattr(self,'animation',None):self.animation.close()
        super().close()

    def build_layout(self):
        self.root.title('Rising Battle · Competitive Edition')
        self.root.geometry('1440x880'); self.root.minsize(820,600)
        self.root.protocol('WM_DELETE_WINDOW',self.owner.close_app)
        style=ttk.Style();style.theme_use('clam')
        style.layout('Battle.Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
        style.configure('Battle.Treeview',background=PANEL,fieldbackground=PANEL,foreground=TEXT,
                        borderwidth=0,lightcolor=FIELD,darkcolor=FIELD,bordercolor=FIELD,rowheight=46,font=('Segoe UI',11))
        style.layout('Social.Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
        style.configure('Social.Treeview',background=FIELD,fieldbackground=FIELD,foreground=MUTED,
                        borderwidth=0,rowheight=44,font=('Segoe UI',10))
        style.map('Social.Treeview',background=[('selected','#234364')],foreground=[('selected',TEXT)])
        style.configure('Battle.Treeview.Heading',background=PANEL,foreground=MUTED,relief='flat',borderwidth=0,
                        lightcolor=PANEL,darkcolor=PANEL,bordercolor=PANEL,padding=(12,10),font=('Segoe UI Semibold',9))
        style.map('Battle.Treeview.Heading',background=[('active','#173448')],lightcolor=[('active',PANEL)],darkcolor=[('active',PANEL)])
        style.map('Battle.Treeview',background=[('selected','#234364')])
        style.configure('TCombobox',fieldbackground=FIELD,background=BORDER,foreground=TEXT,arrowcolor=BLUE,
                        bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=5)
        style.map('TCombobox',fieldbackground=[('readonly',FIELD)],foreground=[('readonly',TEXT)])
        style.configure('TProgressbar',background=ORANGE,troughcolor=FIELD)
        self.profile_name=tk.StringVar(value=self.owner.profile_store.profile()['name'])
        self.friends_open=True;self.friends_manual=False;self.friends_visible=False
        self.table_pages={};self.bracket_available=False
        self.name.set(self.profile_name.get());self.section='home'
        self.wallpaper_surfaces=[]
        self.dashboard=tk.Canvas(self.root,bg=BG,highlightthickness=0);self.dashboard.pack(fill='both',expand=True)
        self.app_background=self.dashboard.create_image(0,0,anchor='center')
        self.social=tk.Frame(self.dashboard,bg=FIELD,width=250);self.social.pack_propagate(False)
        social_header=tk.Frame(self.social,bg=FIELD);social_header.pack(fill='x',padx=14,pady=(10,0))
        label(social_header,'AMIGOS',9,MUTED).pack(side='left')
        close_friends=button(social_header,'×',self.close_friends)
        close_friends.configure(padx=10,pady=2);close_friends.pack(side='right')
        identity=tk.Frame(self.social,bg=FIELD);identity.pack(fill='x',padx=14,pady=(18,16))
        self.social_avatar=tk.Canvas(identity,width=64,height=64,bg=FIELD,highlightthickness=0,cursor='hand2')
        self.social_avatar.pack(side='left',padx=(0,10));self.social_avatar.bind('<Button-1>',lambda e:self.show_section('profile'))
        identity_text=tk.Frame(identity,bg=FIELD);identity_text.pack(side='left',fill='x',expand=True)
        self.social_profile=button(identity_text,self.profile_name.get(),lambda:self.show_section('profile'))
        self.social_profile.configure(padx=0,pady=4,bg=FIELD,font=('Segoe UI Semibold',12),anchor='w');self.social_profile.pack(fill='x')
        self.identity_provider=tk.StringVar(value='Perfil BTC')
        tk.Label(identity_text,textvariable=self.identity_provider,bg=FIELD,fg=BLUE,font=('Segoe UI',9)).pack(anchor='w',pady=3)
        tk.Frame(self.social,bg=BORDER,height=1).pack(fill='x')
        social_bar=tk.Frame(self.social,bg=FIELD);social_bar.pack(fill='x',padx=16,pady=(16,10))
        label(social_bar,'SOCIAL',10).pack(side='left')
        button(social_bar,'+',self.add_friend).pack(side='right')
        self.friend_code=tk.StringVar(value='Conectando…')
        self.friend_code_button=button(self.social,'Copiar mi código',self.copy_friend_code);self.friend_code_button.pack(fill='x',padx=16,pady=(0,6))
        self.requests_button=button(self.social,'Solicitudes',self.open_social_requests);self.requests_button.pack(fill='x',padx=16,pady=(0,10))
        self.friends_tree=ttk.Treeview(self.social,columns=('state',),show='tree',style='Social.Treeview',height=10,selectmode='browse')
        self.friends_tree.column('#0',width=120,minwidth=70);self.friends_tree.column('state',width=70,minwidth=55)
        self.friends_tree.pack(fill='both',expand=True,padx=12,pady=8)
        fit_columns(self.friends_tree,{'#0':3,'state':2})
        self.friends_tree.bind('<Button-3>',lambda e:self.friend_context(e,self.friends_tree))
        self.friends_tree.bind('<Double-1>',lambda e:self.open_selected_friend(self.friends_tree))
        self.social_status=tk.StringVar(value='Preparando perfil social…')
        tk.Label(self.social,textvariable=self.social_status,bg=FIELD,fg=MUTED,wraplength=210,justify='left',font=('Segoe UI',9)).pack(fill='x',padx=16,pady=16)
        self.stage=self.dashboard
        self.nav=tk.Frame(self.stage,bg='#080e15',highlightthickness=0)
        self.brand_logo=tk.PhotoImage(file=str(core.APP_HEADER_LOGO)).subsample(3)
        self.nav_brand=tk.Label(self.nav,image=self.brand_logo,bg='#080e15')
        self.nav_brand.pack(padx=8,pady=(18,14))
        self.nav_play=button(self.nav,'JUGAR  ↗',self.play,True)
        self.nav_play.configure(padx=8,pady=12)
        self.nav_play.pack(fill='x',padx=14,pady=(0,14))
        self.friend_toggle=button(self.nav,'Amigos',self.toggle_friends)
        self.friend_toggle.configure(padx=4,pady=10)
        self.friend_toggle.pack(side='bottom',fill='x',padx=10,pady=(6,14))
        self.nav_links=tk.Frame(self.nav,bg='#080e15')
        self.nav_links.pack(side='top',fill='both',expand=True,padx=8)
        self.nav_buttons={}
        for key,title in (('home','Inicio'),('online','Jugar online'),('room','Salas'),('tournament','Torneos'),('history','Historial'),('profile','Mi perfil'),('inbox','Comunidad'),('settings','Ajustes')):
            b=button(self.nav_links,title,lambda k=key:self.show_section(k))
            b.configure(padx=16,pady=10,bg='#080e15',anchor='w',font=('Segoe UI Semibold',10))
            self.nav_buttons[key]=b
        self.nav_buttons['bracket']=button(self.nav_links,'Bracket',lambda:self.show_section('bracket'))
        self.nav_buttons['bracket'].configure(state='disabled',padx=16,pady=10,anchor='w',font=('Segoe UI Semibold',10))
        self.nav_more=button(self.nav_links,'Más',self.open_navigation_menu)
        self.nav_indicator=tk.Frame(self.nav_links,bg=ORANGE,width=3)
        self.nav_links.bind('<Configure>',self.layout_navigation)
        header=self.wallpaper(self.stage);self.header=header
        self.page_title=tk.StringVar(value='Inicio')
        title_label=tk.Label(self.dashboard,textvariable=self.page_title,bg=BG,fg=TEXT,font=('Segoe UI Semibold',13),padx=12,pady=6)
        self.page_title_item=self.dashboard.create_window(24,100,window=title_label,anchor='nw')
        self.settings_button=button(header,'Inicio',lambda:self.show_section('home'))
        state_label=tk.Label(self.dashboard,textvariable=self.online_state,bg=BG,fg=MUTED,font=('Segoe UI',9),padx=12,pady=6)
        self.connection_item=self.dashboard.create_window(900,100,window=state_label,anchor='ne')
        shell=self.wallpaper(self.stage);self.shell=shell
        self.canvas=tk.Canvas(shell,bg=BG,highlightthickness=0,yscrollincrement=32)
        scroll=ttk.Scrollbar(shell,orient='vertical',command=self.scroll_view);self.page_scrollbar=scroll
        self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        # One viewport paints the background. Pages are canvas windows, rather
        # than opaque nested canvases repainting the same large bitmap.
        self.body=self.canvas;self.content=self.canvas;self.mounted_page=None
        self.content_window=self.canvas.create_window(24,18,anchor='nw',state='hidden')
        self.viewport_timer=None
        self.canvas.bind('<Configure>',self.resize_viewport)
        self.root.bind('<MouseWheel>',self.wheel,add='+')
        self.home=tk.Frame(self.body,bg=BG)
        self.hero=self.canvas
        self.animation_folder=core.RESOURCE_ROOT/'assets'/'animated-background-gif'
        self.background_source=tk.PhotoImage(file=str(self.animation_folder/'frame-0000.gif')) if self.animation_folder.is_dir() else tk.PhotoImage(file=str(core.RESOURCE_ROOT/'assets'/'dashboard_background.png')).subsample(2)
        self.background_image=self.background_source
        self.hero_background=self.hero.create_image(0,0,image=self.background_image,anchor='center')
        self.dashboard.itemconfigure(self.app_background,image=self.background_image)
        self.hero_logo=tk.PhotoImage(file=str(core.APP_HEADER_LOGO)).subsample(2)
        self.home_brand=self.hero.create_image(36,24,image=self.hero_logo,anchor='nw',tags='home')
        # Home typography is painted directly on the animated scene.
        self.game_card=tk.Frame(self.hero,bg=BG)
        self.home_kicker=self.hero.create_text(36,260,text='JUEGA. CONECTA. COMPITE.',anchor='sw',fill=BLUE,font=('Segoe UI Semibold',10),tags='home')
        self.home_title=self.hero.create_text(36,310,text='TU PRÓXIMO',anchor='sw',fill=TEXT,font=('Segoe UI Semibold',34),tags='home')
        self.home_title_accent=self.hero.create_text(36,360,text='GRAN COMBATE.',anchor='nw',fill=ORANGE,font=('Segoe UI Semibold',34),tags='home')
        self.install_state=tk.StringVar()
        self.home_install=self.hero.create_text(36,350,text='',anchor='sw',fill=MUTED,font=('Segoe UI',11),width=520,tags='home')
        self.install_state.trace_add('write',lambda *_:self.hero.itemconfigure(self.home_install,text=self.install_state.get()))
        self.owner.play_button=button(self.hero,'ENTRAR AL JUEGO  ↗',self.play,True)
        self.owner.play_button.configure(pady=14,padx=26)
        self.owner.state_label=label(self.game_card,'Listo',9,BLUE)
        self.owner.progress=ttk.Progressbar(self.game_card,mode='indeterminate')
        self.hero_card=self.hero.create_window(36,400,window=self.owner.play_button,anchor='sw',width=230,height=50,tags='home')
        self.home_room_button=button(self.hero,'Buscar una sala  →',lambda:self.show_section('room'))
        self.home_room_item=self.hero.create_window(280,400,window=self.home_room_button,anchor='sw',height=50,tags='home')
        self.home_progress_item=self.hero.create_window(282,400,window=self.game_card,anchor='sw',width=300,state='hidden')
        self.home_shelf=tk.Frame(self.hero,bg=BG)
        tk.Frame(self.home_shelf,bg=BORDER,height=1).pack(fill='x')
        shelf_body=tk.Frame(self.home_shelf,bg=BG);shelf_body.pack(fill='both',expand=True,padx=24,pady=12)
        self.home_shortcut_captions=[]
        for index,(title,description,key) in enumerate((('01   SALAS','Encuentra a tu próximo rival','room'),('02   TORNEOS','Sigue cada cruce','tournament'),('03   TU TRAYECTORIA','Tu historial competitivo','history'))):
            shelf_body.columnconfigure(index,weight=1,uniform='shortcuts')
            group=tk.Frame(shelf_body,bg=BG);group.grid(row=0,column=index,sticky='nsew',padx=8)
            b=button(group,title,lambda k=key:self.show_section(k))
            b.configure(anchor='w',padx=0,pady=6,font=('Segoe UI Semibold',10));b.pack(fill='x')
            caption=label(group,description,9,MUTED,anchor='w',justify='left',wraplength=240)
            caption.pack(anchor='w',fill='x');self.home_shortcut_captions.append(caption)
        self.home_shelf_item=self.hero.create_window(0,0,window=self.home_shelf,anchor='sw',tags='home')

        self.root.bind('<Configure>',self.dashboard_resize,add='+')
        self.dashboard.bind('<Configure>',lambda e:self.layout_dashboard(),add='+')
        self.settings=self.card(self.body,'Ajustes')
        actions=tk.Frame(self.settings,bg=PANEL);actions.pack(fill='x',padx=18,pady=(0,12))
        self.owner.folder_button=button(actions,'Elegir instalación',self.owner.select_installation)
        self.owner.import_button=button(actions,'Importar memory',self.owner.import_card)
        self.owner.future_update_button=button(actions,'Cambiar ISO',self.owner.install_iso_and_memory)
        action_grid(actions,[self.owner.folder_button,self.owner.import_button,self.owner.future_update_button],220)
        row=tk.Frame(self.settings,bg=PANEL);row.pack(fill='x',padx=18,pady=(0,12))
        button(row,'Abrir carpeta de registros',self.owner.open_logs).pack(side='left')
        label(row,'Rising Battle · 2.0 de prueba',9,MUTED).pack(side='right')
        self.owner.log=tk.Text(self.settings,bg=FIELD,fg=MUTED,height=5,wrap='word',relief='flat',state='disabled',font=('Consolas',9))
        def toggle_diagnostics():
            if self.owner.log.winfo_manager():self.owner.log.pack_forget();diagnostics.configure(text='Mostrar diagnóstico')
            else:self.owner.log.pack(fill='x',padx=18,pady=(0,14));diagnostics.configure(text='Ocultar diagnóstico')
        diagnostics=button(self.settings,'Mostrar diagnóstico',toggle_diagnostics)
        diagnostics.pack(anchor='w',padx=18,pady=(0,14))
        self.lobby_card=self.card(self.body,'Salas disponibles','Selecciona una sala para entrar. El candado indica que necesita contraseña.')
        self.directory_heading=self.lobby_card.winfo_children()[0]
        self.directory_tree=ttk.Treeview(self.lobby_card,columns=('name','host','slots','access'),show='headings',style='Battle.Treeview',height=7,selectmode='browse')
        for key,title,width in (('name','SALA',300),('host','ANFITRIÓN',160),('slots','PLAZAS',80),('access','ACCESO',130)):
            self.directory_tree.heading(key,text=title);self.directory_tree.column(key,width=width,minwidth=70)
        self.directory_tree.pack(fill='x',padx=16,pady=12)
        fit_columns(self.directory_tree,dict(name=4,host=2,slots=1,access=2))
        self.directory_tree.bind('<Double-1>',lambda e:self.join_selected())
        row=tk.Frame(self.lobby_card,bg=PANEL);row.pack(fill='x',padx=16,pady=(0,12))
        self.directory_actions=row
        self.directory_tree.pack_forget()
        action_grid(row,[button(row,'Actualizar lista',lambda:self.request_directory(force=True)),button(row,'Entrar a la sala',self.join_selected,True)])
        self.directory_notice=tk.StringVar(value='Buscando salas…')
        self.directory_notice_label=tk.Label(self.lobby_card,textvariable=self.directory_notice,bg=PANEL,fg=MUTED,font=('Segoe UI',10),anchor='w')
        self.directory_notice_label.pack(fill='x',padx=18,pady=(0,12))
        self.create_room_toggle=button(self.lobby_card,'Crear una nueva',self.toggle_creation)
        self.create_room_toggle.pack(anchor='w',padx=18,pady=(0,14))
        self.creation=tk.Frame(self.lobby_card,bg=PANEL)
        self.room_password=tk.StringVar()
        form=tk.Frame(self.creation,bg=PANEL);form.pack(fill='x')
        fields=[]
        for title,var in (('NOMBRE',self.room_title),('PLAZAS · 2 A 32',self.capacity),('CONTRASEÑA · OPCIONAL',self.room_password)):
            field=tk.Frame(form,bg=PANEL);entry=self.entry(field,title,var)
            if var is self.room_password:entry.configure(show='●')
            fields.append(field)
        action_grid(form,fields,240)
        button(self.creation,'Crear y entrar',self.create_listed_room,True).pack(fill='x',padx=18,pady=14)
        self.list_kind='casual';self.last_directory_request=0;self.directory_seen=-1
        self.room_card=tk.Frame(self.body,bg=BG)
        row=tk.Frame(self.room_card,bg=BG);row.pack(fill='x',pady=(0,12))
        tk.Label(row,textvariable=self.code_display,bg=BG,fg=ORANGE,font=('Segoe UI Semibold',18)).pack(side='left')
        button(row,'Salir',lambda:self.send(5)).pack(side='right')
        self.room_tabs=tk.Frame(self.room_card,bg=BG);self.room_tabs.pack(fill='x',pady=(0,8))
        self.room_tab='players';self.room_tab_buttons={}
        for key,title in (('players','JUGADORES'),('battle','COMBATE'),('chat','CHAT')):
            b=button(self.room_tabs,title,lambda k=key:self.show_room_tab(k));b.pack(side='left',padx=(0,8));self.room_tab_buttons[key]=b
        self.columns=tk.Frame(self.room_card,bg=BG);self.columns.pack(fill='both',expand=True)
        self.left=tk.Frame(self.columns,bg=BG);self.left.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        self.right=self.card(self.columns,'Chat de sala');self.right.grid(row=0,column=1,sticky='nsew')
        self.columns.columnconfigure(0,weight=1,uniform='main');self.columns.columnconfigure(1,weight=1,uniform='main')
        self.columns.bind('<Configure>',self.reflow)
        users=self.card(self.left,'Jugadores');self.room_users=users;users.pack(fill='both',expand=True)
        self.users=ttk.Treeview(users,columns=('name','state'),show='headings',style='Battle.Treeview',selectmode='browse',height=4)
        self.users.heading('name',text='JUGADOR');self.users.heading('state',text='ESTADO')
        self.users.column('name',width=190,minwidth=100);self.users.column('state',width=85,minwidth=70)
        self.users.pack(fill='both',expand=True,padx=12,pady=8)
        fit_columns(self.users,dict(name=3,state=2))
        row=tk.Frame(users,bg=PANEL);row.pack(fill='x',padx=12,pady=(0,12))
        button(row,'Listo / esperando',lambda:self.send(6)).pack(side='left')
        self.kick=button(row,'Expulsar',self.kick_user);self.kick.pack(side='right')
        duel=self.card(self.left,'Combate');self.duel_card=duel;duel.pack(fill='x')
        self.rules_selector(duel)
        self.challenge_button=button(duel,'Desafiar al jugador seleccionado',self.challenge,True);self.challenge_button.pack(fill='x',padx=16,pady=6)
        self.duel_notice=tk.StringVar()
        tk.Label(duel,textvariable=self.duel_notice,bg=PANEL,fg=BLUE,wraplength=390,justify='left',anchor='w',font=('Segoe UI',10)).pack(fill='x',padx=16,pady=8)
        self.duel_actions=tk.Frame(duel,bg=PANEL);self.duel_actions.pack(fill='x',padx=12)
        self.accept_button=button(self.duel_actions,'Aceptar',lambda:self.duel_answer(31),True)
        self.decline_button=button(self.duel_actions,'Rechazar',lambda:self.duel_answer(32))
        self.cancel_duel=button(self.duel_actions,'Cancelar duelo',lambda:self.duel_answer(33))
        self.observe_button=button(self.duel_actions,'Observar combate',self.observe,True)
        self.stop_observe=button(self.duel_actions,'Dejar de observar',lambda:self.send(41))
        self.observer_status=tk.StringVar()
        self.chat=tk.Text(self.right,bg=FIELD,fg=TEXT,relief='flat',wrap='word',state='disabled',height=14,width=30,font=('Segoe UI',10),padx=14,pady=14)
        self.chat.pack(fill='both',expand=True,padx=12,pady=8)
        row=tk.Frame(self.right,bg=PANEL);row.pack(fill='x',padx=12,pady=(0,12))
        entry=tk.Entry(row,textvariable=self.chat_input,bg=FIELD,fg=TEXT,insertbackground=ORANGE,relief='flat',font=('Segoe UI',11))
        entry.pack(side='left',fill='x',expand=True,ipady=10);entry.bind('<Return>',lambda e:self.chat_send())
        button(row,'Enviar',self.chat_send).pack(side='right',padx=(8,0))
        self.tournament_toggle=button(self.room_card,'Torneo  +',self.toggle_tournament)
        self.tournament_toggle.pack(fill='x',pady=14)
        self.tournament_panel=tk.Frame(self.room_card,bg=BG)
        self.pages={'tournament':self.tournament_panel}
        self.build_tournament()
        self.show_room_tab('players')
        self.status_label=tk.Label(self.root,textvariable=self.status,bg=FIELD,fg=MUTED,font=('Segoe UI',9),anchor='w',wraplength=900,padx=22,pady=10)
        self.status_label.configure(height=1)
        self.status_label.pack(fill='x',side='bottom')
        self.root.bind('<Configure>',lambda e:self.status_label.configure(wraplength=max(300,self.root.winfo_width()-44)) if e.widget is self.root else None,add='+')
        self.connected_visible=None
        self.build_home_options()
        self.build_online_options()
        self.build_profile()
        self.build_history()
        self.build_social_pages()
        from challonge_ui import ChallongePanel
        self.challonge_panel=ChallongePanel(self,self.body)
        self.social_version=-1;self.social_signature=None;self.social_rows={};self.chat_peer=None
        self.enable_tree_hover(self.friends_tree);self.enable_tree_hover(self.social_center_tree)
        self.enable_tree_hover(self.users);self.enable_tree_hover(self.directory_tree)
        self.users.bind('<Button-3>',self.room_context)
        self.reload_avatars()
        for tree in (self.directory_tree,self.history_tree,self.users,self.inbox_tree,self.social_center_tree,self.friends_tree):
            self.table_pages[tree]=TablePages(tree)
            if tree.winfo_manager()=='pack':tree.pack_configure(fill='both',expand=True)
        self.dm_text.configure(height=1);self.chat.configure(height=1)
        for panel in (self.settings,self.lobby_card,self.room_card,self.profile_panel,self.history_panel,self.online_panel,self.inbox_panel,self.messages_panel,self.challenge_panel,self.challonge_panel.frame):
            panel.bind('<Configure>',self.queue_viewport,add='+')
        self.apply_section()
        from animated_background import AnimatedBackground
        self.animation=AnimatedBackground(self.dashboard,self.app_background,self.animation_folder,lambda:self.root.state() not in ('iconic','withdrawn') and not (self.owner.session and self.owner.session.running)) if self.animation_folder.is_dir() else None
        if self.animation:self.animation.add_view(self.hero,self.hero_background)
        self.layout_dashboard()
        self.hero.tag_lower(self.hero_background)

    def wheel(self,event):
        if not isinstance(event.widget,tk.Text):return 'break'

    def scroll_view(self,*args):
        self.canvas.yview(*args)
        if getattr(self,'animation',None):self.animation.position()

    def reflow(self,event):
        return

    def show_room_tab(self,key):
        self.room_tab=key
        self.left.grid_forget();self.right.grid_forget()
        self.room_users.pack_forget();self.duel_card.pack_forget()
        if key=='chat':self.right.grid(row=0,column=0,columnspan=2,sticky='nsew')
        else:
            self.left.grid(row=0,column=0,columnspan=2,sticky='nsew')
            (self.room_users if key=='players' else self.duel_card).pack(fill='both',expand=True)
        self.columns.rowconfigure(0,weight=1)
        for name,b in self.room_tab_buttons.items():b.configure(fg=BLUE if name==key else MUTED)

    def build_home_options(self):
        self.home_credit=self.hero.create_text(0,0,text='Decomp: z3xox   ·   Competitive Loader: Rising',anchor='se',fill=MUTED,font=('Segoe UI',9),tags='home')

    def queue_viewport(self,event=None):
        if self.viewport_timer:return
        self.viewport_timer=self.canvas.after_idle(self.update_viewport)

    def update_viewport(self):
        self.viewport_timer=None
        width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height())
        page_width=max(300,width-32)
        self.page_x=16
        self.canvas.itemconfigure(self.content_window,width=page_width,height=max(1,height-16))
        self.canvas.coords(self.content_window,self.page_x,8)
        if self.page_scrollbar.winfo_manager():self.page_scrollbar.pack_forget()
        region=(0,0,width,height)
        if region!=getattr(self,'last_scrollregion',None):
            self.last_scrollregion=region;self.canvas.configure(scrollregion=region)
        self.resize_hero(None)
        self.apply_density()

    def resize_viewport(self,event):
        self.queue_viewport()

    def set_bracket_available(self,enabled):
        self.bracket_available=enabled
        self.nav_buttons['bracket'].configure(state='normal' if enabled else 'disabled')
        self.layout_navigation()
        if not enabled and self.section=='bracket':self.show_section('tournament')

    def apply_density(self):
        compact=self.root.winfo_height()<780
        if compact==getattr(self,'_compact_density',None):return
        self._compact_density=compact
        import tkinter.font as fonts
        style=ttk.Style(self.root)
        style.configure('Battle.Treeview',rowheight=28 if compact else 40,font=('Segoe UI',9 if compact else 10))
        style.configure('Battle.Treeview.Heading',padding=(8,4 if compact else 8))
        def padding(value):
            values=(value,) if isinstance(value,int) else self.root.tk.splitlist(value)
            changed=tuple(max(2,int(int(v)*.5)) if int(v)>2 else int(v) for v in values)
            return changed if len(changed)>1 else changed[0]
        def walk(widget):
            if isinstance(widget,tk.Label):
                if not hasattr(widget,'_normal_font'):widget._normal_font=fonts.Font(font=widget.cget('font')).actual()
                spec=widget._normal_font;size=spec['size']
                widget.configure(font=(spec['family'],max(9,size-3) if compact else size,spec['weight']))
            if isinstance(widget,tk.Button) and widget not in self.nav_buttons.values():widget.configure(pady=4 if compact else 9)
            if widget.winfo_manager()=='pack':
                if not hasattr(widget,'_normal_pady'):widget._normal_pady=widget.pack_info()['pady']
                widget.pack_configure(pady=padding(widget._normal_pady) if compact else widget._normal_pady)
            for child in widget.winfo_children():walk(child)
        for panel in (self.settings,self.profile_panel,self.history_panel,self.lobby_card,self.room_card,self.online_panel,self.inbox_panel,self.messages_panel,self.challenge_panel,self.challonge_panel.frame):walk(panel)
        self.profile_avatar.configure(width=64 if compact else 128,height=64 if compact else 128)
        self.profile_avatar_size=64 if compact else 128
        self.reload_avatars()

    def mount_page(self,panel):
        self.mounted_page=panel
        self.canvas.itemconfigure(self.content_window,window=panel or '',state='normal' if panel else 'hidden')
        self.canvas.itemconfigure('home',state='normal' if panel is None else 'hidden')
        self.canvas.itemconfigure(self.home_progress_item,state='normal' if panel is None and self.owner.busy else 'hidden')
        self.queue_viewport()

    def resize_hero(self,event):
        if getattr(self,'animation',None):self.animation.position()
        width=self.canvas.winfo_width();height=self.canvas.winfo_height()
        shelf=106 if height<650 else 124
        poster=max(410,height-shelf)
        compact=poster<560
        kicker=max(128,int(poster*.26))
        self.hero.coords(self.home_brand,36,24)
        self.hero.coords(self.home_kicker,38,kicker)
        self.hero.itemconfigure(self.home_kicker,anchor='nw',font=('Segoe UI Semibold',9))
        from tkinter import font as tkfont
        if not hasattr(self,'hero_fonts'):
            self.hero_fonts={n:tkfont.Font(family='Segoe UI Semibold',size=n) for n in (34,46)}
        title_font=self.hero_fonts[34 if compact else 46]
        line=title_font.metrics('linespace')
        self.hero.coords(self.home_title,34,kicker+28)
        self.hero.itemconfigure(self.home_title,anchor='nw',font=title_font,width=max(300,width-64))
        self.hero.coords(self.home_title_accent,34,kicker+32+line)
        self.hero.itemconfigure(self.home_title_accent,font=title_font,width=max(300,width-64))
        self.hero.coords(self.home_install,38,kicker+48+line*2)
        self.hero.itemconfigure(self.home_install,anchor='nw',width=max(280,min(520,width-80)))
        bottom=poster-26
        self.hero.coords(self.hero_card,38,bottom)
        self.hero.coords(self.home_room_item,282,bottom)
        self.hero.coords(self.home_progress_item,282,bottom)
        self.hero.coords(self.home_shelf_item,0,height)
        self.hero.itemconfigure(self.home_shelf_item,width=width,height=shelf)
        for caption in self.home_shortcut_captions:caption.configure(wraplength=max(140,int((width-70)/3)))
        self.hero.coords(self.home_credit,max(24,width-28),poster-4)
        self.hero.itemconfigure(self.home_credit,font=('Segoe UI',8))
    def dashboard_resize(self,event):
        if event.widget is not self.root:return
        self.layout_dashboard()

    def layout_dashboard(self):
        width=max(820,self.root.winfo_width())
        height=self.dashboard.winfo_height()
        if height<=1:height=max(560,self.root.winfo_height()-36)
        visible=self.friends_open and (width>=1360 or self.friends_manual)
        self.friends_visible=visible
        right=250 if visible and width>=1360 else 0
        rail=184 if width>=1150 else 132
        area=width-right-rail
        self.nav.place(x=0,y=0,width=rail,height=height)
        for item in (self.page_title_item,self.connection_item):self.dashboard.itemconfigure(item,state='hidden')
        self.shell.place(x=rail,y=0,width=area,height=height)
        if visible:
            self.social.place(x=width-250,y=0,width=250,height=height);self.social.lift()
        else:self.social.place_forget()
        self.friend_toggle.configure(text='Cerrar amigos' if visible else 'Amigos  +',fg=BLUE if visible else MUTED)
        self.layout_navigation();self.queue_viewport()

    def toggle_friends(self):
        self.friends_open=not self.friends_visible;self.friends_manual=True
        self.layout_dashboard()

    def close_friends(self):
        self.friends_open=False;self.friends_manual=True
        self.layout_dashboard()

    def layout_navigation(self,event=None):
        if getattr(self,'_ui_closed',False) or not self.nav_links.winfo_exists():return
        compact=self.root.winfo_height()<720
        self.hidden_navigation=[]
        for col in range(9):self.nav_links.columnconfigure(col,weight=0,minsize=0)
        self.nav_links.columnconfigure(0,weight=1)
        row=0
        key='inbox' if self.section in ('messages','challenge') else self.section
        for name,b in self.nav_buttons.items():
            b.grid_forget()
            if name=='bracket' and not self.bracket_available:continue
            selected=name==key
            base='#182430' if selected else '#080e15'
            b.configure(bg=base,fg=ORANGE if selected else MUTED,padx=12,pady=6 if compact else 10)
            b._hover_base=base
            b.grid(row=row,column=0,sticky='ew',pady=2)
            row+=1
        self.nav_more.grid_forget()
        target=self.nav_buttons.get(key)
        if target and (key!='bracket' or self.bracket_available):
            self.nav_indicator.place(in_=target,x=0,rely=.18,width=3,relheight=.64)
        else:self.nav_indicator.place_forget()
        self.nav_links.grid_anchor('nw')

    def open_navigation_menu(self):
        menu=tk.Menu(self.root,tearoff=False,bg=FIELD,fg=TEXT,activebackground='#1b303f',activeforeground=ORANGE,borderwidth=0,font=('Segoe UI',11))
        for key in self.hidden_navigation:
            menu.add_command(label=self.nav_buttons[key].cget('text').title(),command=lambda k=key:self.show_section(k))
        try:menu.tk_popup(self.nav_more.winfo_rootx(),self.nav_more.winfo_rooty()+self.nav_more.winfo_height())
        finally:menu.grab_release()

    def build_online_options(self):
        self.online_panel=self.card(self.body,'Jugar online','Tu siguiente rival, a un paso. Elige una partida directa o entra en una sala BTC.')
        choices=tk.Frame(self.online_panel,bg=PANEL);choices.pack(fill='x',padx=14,pady=(8,20))
        cards=[]
        for title,detail,action,command in (
            ('01  /  PARTIDA DIRECTA','Crea un combate privado o busca rival desde Dragon Net Battle.','Abrir el juego',self.play),
            ('02  /  SALAS BTC','Encuentra jugadores, conversa y organiza tu próximo desafío.','Explorar salas',lambda:self.show_section('room'))):
            card=tk.Frame(choices,bg=PANEL,highlightthickness=0)
            label(card,title,12,BLUE).pack(anchor='w',padx=18,pady=(20,12))
            text=label(card,detail,11,MUTED,justify='left',wraplength=350);text.pack(fill='x',padx=18,pady=(0,18))
            card.bind('<Configure>',lambda e,t=text:t.configure(wraplength=max(150,e.width-36)),add='+')
            button(card,action,command,True).pack(anchor='w',padx=18,pady=(0,20));cards.append(card)
        action_grid(choices,cards,360)

    def build_profile(self):
        self.profile_panel=self.card(self.body,'Mi perfil · Challonge','Conecta tu cuenta para importar tu nombre y tu imagen de perfil.')
        avatar_row=tk.Frame(self.profile_panel,bg=PANEL);avatar_row.pack(fill='x',padx=18,pady=14)
        self.profile_avatar=tk.Canvas(avatar_row,width=128,height=128,bg=PANEL,highlightthickness=0)
        self.profile_avatar.pack(side='left',padx=(0,18))
        avatar_actions=tk.Frame(avatar_row,bg=PANEL);avatar_actions.pack(side='left',fill='both',expand=True)
        tk.Label(avatar_actions,textvariable=self.profile_name,bg=PANEL,fg=TEXT,font=('Segoe UI Semibold',22)).pack(anchor='w',pady=(14,8))
        label(avatar_actions,'Nombre y avatar vinculados a Challonge',10,MUTED).pack(anchor='w',pady=6)
        links=tk.Frame(self.profile_panel,bg=PANEL);links.pack(fill='x',padx=14,pady=(0,12))
        action_grid(links,[button(links,'Conectar con Challonge',lambda:self.challonge_panel.login(),True),button(links,'Editar perfil en Challonge ↗',lambda:__import__('webbrowser').open('https://challonge.com/settings'))],280)
        self.profile_stats=tk.StringVar()
        self.profile_metrics=[tk.StringVar(value='0') for _ in range(3)]
        metrics=tk.Frame(self.profile_panel,bg=PANEL);metrics.pack(fill='x',padx=24,pady=(20,24))
        for index,(title,value) in enumerate(zip(('COMBATES','VICTORIAS','TORNEOS'),self.profile_metrics)):
            metrics.columnconfigure(index,weight=1)
            cell=tk.Frame(metrics,bg=PANEL);cell.grid(row=0,column=index,sticky='w')
            tk.Label(cell,textvariable=value,bg=PANEL,fg=TEXT,font=('Segoe UI Semibold',26)).pack(anchor='w')
            label(cell,title,9,MUTED).pack(anchor='w',pady=(3,0))
        label(self.profile_panel,'Se conserva el historial de este PC al vincular la cuenta.\nTu identidad te acompaña en tus partidas y salas.',10,MUTED,justify='left',wraplength=680).pack(anchor='w',padx=18,pady=(0,18))

    def reload_avatars(self):
        self.avatar_images=[]
        path=self.owner.profile_store.avatar_path()
        for canvas,size in ((self.social_avatar,64),(self.profile_avatar,getattr(self,'profile_avatar_size',128))):
            canvas.delete('all')
            canvas.create_oval(1,1,size-1,size-1,outline=ORANGE,width=2,fill=FIELD)
            if path.is_file():
                try:
                    original=tk.PhotoImage(file=str(path));photo=original.subsample(256//size)
                    self.avatar_images.append(photo);canvas.create_image(size/2,size/2,image=photo)
                    canvas.create_oval(1,1,size-1,size-1,outline=ORANGE,width=2)
                    continue
                except (OSError,tk.TclError):pass
            canvas.create_text(size/2,size/2,text=self.profile_name.get()[:1].upper(),fill=BLUE,font=('Segoe UI Semibold',int(size*.36)))

    def choose_avatar(self):
        source=filedialog.askopenfilename(parent=self.root,title='Imagen de perfil',filetypes=[('Imágenes','*.png *.jpg *.jpeg *.bmp'),('Todos los archivos','*.*')])
        if not source:return
        try:self.owner.profile_store.set_avatar(source)
        except (ValueError,OSError) as exc:self.status.set(str(exc));return
        self.reload_avatars();self.status.set('Imagen de perfil guardada en este PC.')

    def remove_avatar(self):
        self.owner.profile_store.clear_avatar();self.reload_avatars();self.status.set('Imagen de perfil retirada.')

    def save_profile(self):
        if self.snapshot or self.owner.busy or self.owner.session and self.owner.session.running:
            self.status.set('Termina la sesión y sal de la sala antes de cambiar tu nombre.');return
        try:self.owner.profile_store.rename(self.profile_name.get())
        except ValueError as exc:self.status.set(str(exc));return
        name=self.owner.profile_store.profile()['name'];self.profile_name.set(name);self.name.set(name)
        cfg=core.load_config();cfg['btc_player_name']=name;core.save_config(cfg)
        self.social_profile.configure(text=name)
        self.reload_avatars()
        self.status.set('Perfil guardado. Este nombre se usará en tus próximas partidas y salas.')

    def build_history(self):
        self.history_panel=self.card(self.body,'Tu historial','Resultados confirmados y participaciones de este perfil en salas BTC.')
        self.history_kind=tk.StringVar(value='Duelos')
        toolbar=tk.Frame(self.history_panel,bg=PANEL);toolbar.pack(fill='x',padx=18,pady=6)
        selector=ttk.Combobox(toolbar,textvariable=self.history_kind,values=('Duelos','Torneos'),state='readonly',width=16)
        selector.pack(side='left');selector.bind('<<ComboboxSelected>>',lambda e:self.refresh_history())
        button(toolbar,'Actualizar',self.refresh_history).pack(side='right')
        self.history_tree=ttk.Treeview(self.history_panel,columns=('date','type','rival','score','result'),show='headings',style='Battle.Treeview',height=8)
        for key,title,width in (('date','FECHA',150),('type','MODO',90),('rival','RIVAL',170),('score','PUNTAJE',75),('result','RESULTADO',100)):
            self.history_tree.heading(key,text=title);self.history_tree.column(key,width=width,minwidth=60)
        self.history_tree.pack(fill='x',padx=16,pady=12)
        fit_columns(self.history_tree,dict(date=3,type=2,rival=4,score=2,result=2))
        self.participation_text=tk.StringVar()
        self.history_notice=tk.Label(self.history_panel,textvariable=self.participation_text,bg=PANEL,fg=MUTED,justify='left',anchor='w',wraplength=720,font=('Segoe UI',11))
        self.history_notice.pack(fill='x',padx=24,pady=(20,28))

    def refresh_history(self):
        self.table_pages[self.history_tree].reset()
        self.history_tree.delete(*self.history_tree.get_children())
        rows=self.owner.profile_store.history()
        tours=self.owner.profile_store.participations()
        if self.history_kind.get()=='Torneos':rows=tours
        for i,r in enumerate(rows):
            from datetime import datetime
            if self.history_kind.get()=='Torneos':
                date=datetime.fromisoformat(r['created']).astimezone().strftime('%d/%m/%Y %H:%M')
                values=(date,'Torneo',r['title'],'—',{'registration':'Inscrito','running':'En curso','finished':'Finalizado'}.get(r['status'],r['status']))
            else:
                date=datetime.fromisoformat(r['finished']).astimezone().strftime('%d/%m/%Y %H:%M')
                values=(date,r['kind'],r['opponent'],f"{r['mine']} - {r['theirs']}",'Victoria' if r['won'] else 'Derrota')
            self.history_tree.insert('','end',iid=str(i),values=values)
        if rows:
            self.history_tree.configure(height=1)
            if not self.history_tree.winfo_manager():self.history_tree.pack(fill='both',expand=True,padx=18,pady=8,before=self.history_notice)
        else:self.history_tree.pack_forget()
        self.table_pages[self.history_tree].capture()
        self.participation_text.set('Todavía no hay registros en este apartado.' if not rows else '')
        stats=self.owner.profile_store.stats()
        for var,key in zip(self.profile_metrics,('played','wins','tournaments')):var.set(str(stats[key]))
        self.profile_stats.set(f"{stats['played']} combates registrados    ·    {stats['wins']} victorias    ·    {stats['tournaments']} torneos")

    def show_section(self,key):
        if key=='bracket' and not self.bracket_available:return
        self.section=key
        if key!='messages':self.owner.social.chat_target=None
        self.apply_section()
        if key in ('profile','history'):self.refresh_history()
        self.canvas.yview_moveto(0)
        self.slide_section()
        if key in ('messages','challenge','inbox'):self.canvas.after(16,lambda:self.canvas.yview_moveto(0))

    def slide_section(self):
        previous=getattr(self,'transition_timer',None)
        if previous:self.canvas.after_cancel(previous)
        def step(frame=0):
            if not self.canvas.winfo_exists():return
            x=getattr(self,'page_x',24)+int(12*(1-min(1,frame/7))**2)
            self.canvas.coords(self.content_window,x,8)
            self.transition_timer=self.canvas.after(16,lambda:step(frame+1)) if frame<7 else None
        step()

    def apply_section(self):
        key=self.section
        panel={'home':None,'online':self.online_panel,'settings':self.settings,'profile':self.profile_panel,'inbox':self.inbox_panel,'messages':self.messages_panel,'challenge':self.challenge_panel,'history':self.history_panel,'tournament':self.challonge_panel.frame,'bracket':self.challonge_panel.bracket_page}.get(key)
        if key=='room':
            panel=self.room_card if self.snapshot else self.lobby_card
            if not self.snapshot:
                next_kind='tournament' if key=='tournament' else 'casual'
                if self.list_kind!=next_kind:
                    self.directory_tree.delete(*self.directory_tree.get_children());self.directory_seen=-1;self.last_directory_request=0
                    self.directory_notice.set('Buscando…')
                self.list_kind=next_kind
                self.directory_heading.configure(text='Torneos disponibles' if key=='tournament' else 'Salas disponibles')
                self.request_directory(force=True)
            else:
                kind=self.snapshot.get('room_kind','legacy')
                self.tournament_toggle.pack_forget()
                if kind=='tournament':
                    self.duel_card.pack_forget()
                    self.tournament_panel.pack(fill='x',pady=14)
                else:
                    self.duel_card.pack(fill='x');self.tournament_panel.pack_forget()
                if (key=='tournament')!=(kind=='tournament'):
                    self.status.set('Sal de la sala actual para entrar en otra sala o torneo.')
            self.show_room_tab(self.room_tab)
        self.mount_page(panel)
        self.layout_dashboard()
        self.page_title.set({'home':'Inicio','online':'Online','room':'Salas','tournament':'Torneos','profile':'Mi perfil','history':'Historial','settings':'Ajustes','inbox':'Social','messages':'Mensajes','challenge':'Desafiar a un amigo'}.get(key,key))
        for item,b in self.nav_buttons.items():
            b._hover_base=BG;b.configure(bg=BG,fg=ORANGE if item==('inbox' if key in ('messages','challenge') else key) else MUTED,highlightthickness=0)
        self.layout_navigation()

    def toggle_creation(self):
        if self.creation.winfo_manager():
            self.creation.pack_forget();self.create_room_toggle.configure(text='Crear una nueva')
            for widget,options in self.saved_directory:widget.pack(**options)
        else:
            self.saved_directory=[]
            for widget in (self.directory_tree,self.directory_actions,self.directory_notice_label,self.table_pages[self.directory_tree].bar):
                if widget.winfo_manager()=='pack':
                    options=widget.pack_info();options.pop('in',None);self.saved_directory.append((widget,options));widget.pack_forget()
            self.create_room_toggle.configure(text='Cancelar creación')
            self.creation.pack(fill='both',expand=True)

    def request_directory(self,force=False):
        import time
        now=time.monotonic()
        if self.snapshot or (not force and now-self.last_directory_request<10):return
        if force and now-self.last_directory_request<1:return
        self.last_directory_request=now
        try:self.bridge.submit(42,address=self.endpoint.get(),key=self.list_kind)
        except queue.Full:self.directory_notice.set('Espera un momento antes de actualizar.')

    def create_listed_room(self):
        try:
            capacity=int(self.capacity.get())
            if not 2<=capacity<=32:raise ValueError('Elige entre 2 y 32 plazas.')
            password=self.room_password.get()
            if len(password.encode('utf-8'))>128:raise ValueError('La contraseña es demasiado larga.')
        except ValueError as exc:self.status.set(str(exc));return
        self.send(43,address=self.endpoint.get(),name=self.name.get(),title=self.room_title.get(),capacity=capacity,key=self.list_kind,text=password)
        self.room_password.set('')

    def join_selected(self):
        selection=self.directory_tree.selection()
        if not selection:self.status.set('Selecciona una sala de la lista.');return
        room=next((r for r in self.bridge.directory if r['room_code']==selection[0]),None)
        if not room or room['kind']!=self.list_kind:return
        if room['count']>=room['capacity']:self.status.set('La sala está llena.');return
        password=''
        if room['locked']:
            password=simpledialog.askstring('Entrar en '+room['title'],'Contraseña de la sala:',show='●',parent=self.root)
            if password is None:return
        self.send(44,address=self.endpoint.get(),name=self.name.get(),key=room['room_code'],text=password)

    def toggle_settings(self):
        self.show_section('home' if self.section=='settings' else 'settings')

    def toggle_tournament(self):
        if self.tournament_panel.winfo_manager():
            self.tournament_panel.pack_forget();self.tournament_toggle.configure(text='Torneo  +')
        else:
            self.tournament_panel.pack(fill='x');self.tournament_toggle.configure(text='Torneo  −')

    def show(self,key):
        self.show_section({'connection':'settings','online':'room'}.get(key,key))

    def refresh(self):
        if getattr(self.owner,'_closing',False):return
        if self.users in self.table_pages:self.table_pages[self.users].reset()
        super().refresh()
        if self.users in self.table_pages:self.table_pages[self.users].capture()
        self.refresh_social()
        self.challonge_panel.refresh()
        connected=bool(self.snapshot)
        if connected!=self.connected_visible:
            self.connected_visible=connected
            self.apply_section()
        if self.snapshot:self.code_display.set(self.snapshot['title'])
        elif self.section in ('room','tournament'):
            self.request_directory()
            if self.bridge.directory_version!=self.directory_seen and self.bridge.directory_kind==self.list_kind:
                self.directory_seen=self.bridge.directory_version
                self.table_pages[self.directory_tree].reset()
                selection=self.directory_tree.selection();self.directory_tree.delete(*self.directory_tree.get_children())
                for r in self.bridge.directory:
                    self.directory_tree.insert('','end',iid=r['room_code'],values=(r['title'],r['host'],f"{r['count']}/{r['capacity']}",'Con contraseña' if r['locked'] else 'Abierta'))
                if self.bridge.directory:
                    self.directory_tree.configure(height=1)
                    if not self.directory_tree.winfo_manager() and not self.creation.winfo_manager():self.directory_tree.pack(fill='both',expand=True,padx=18,pady=8,before=self.directory_actions)
                else:self.directory_tree.pack_forget()
                self.table_pages[self.directory_tree].capture()
                if selection and self.directory_tree.exists(selection[0]):self.directory_tree.selection_set(selection[0])
                self.directory_notice.set(f'{len(self.bridge.directory)} disponibles' if self.bridge.directory else 'No hay salas disponibles. Puedes crear una.')
        for b in (self.observe_button,self.stop_observe):
            if b.winfo_manager():b.pack_forget()
        for b in (self.accept_button,self.decline_button,self.cancel_duel):
            visible=str(b.cget('state'))=='normal'
            if visible and not b.winfo_manager():b.pack(fill='x',pady=3)
            elif not visible and b.winfo_manager():b.pack_forget()
        if str(self.kick.cget('state'))=='normal':
            if not self.kick.winfo_manager():self.kick.pack(side='right')
        elif self.kick.winfo_manager():self.kick.pack_forget()
        installed=(self.owner._runtime()/'Tenkaichi3Decomp.exe').is_file()
        running=bool(self.owner.session and self.owner.session.running)
        if self.owner.busy:
            if not self.owner.progress.winfo_manager():
                self.owner.state_label.pack(anchor='w',padx=18)
                self.owner.progress.pack(fill='x',padx=18,pady=(6,14))
        elif self.owner.progress.winfo_manager():
            self.owner.progress.pack_forget();self.owner.state_label.pack_forget()
        self.hero.itemconfigure(self.home_progress_item,state='normal' if self.owner.busy and self.section=='home' else 'hidden')
        if self.section=='home':self.hero.itemconfigure(self.home_room_item,state='hidden' if self.owner.busy else 'normal')
        install_text='Juego abierto · fondo en pausa' if running else 'Competitive Edition preparada' if installed else 'Elige tu instalación en Ajustes'
        if self.install_state.get()!=install_text:self.install_state.set(install_text)
        play_state=('Juego abierto' if running else 'ENTRAR AL JUEGO  ↗','disabled' if running or self.owner.busy else 'normal')
        if play_state!=getattr(self,'last_play_state',None):
            self.last_play_state=play_state;self.owner.play_button.configure(text=play_state[0],state=play_state[1])

