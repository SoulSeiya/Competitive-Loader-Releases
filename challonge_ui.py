"""Challonge identity and bracket panel. No network requests on Tk's thread."""
import queue
import tkinter as tk
from tkinter import ttk, simpledialog
import webbrowser
from battle_hub import PANEL,FIELD,BORDER,TEXT,MUTED,ORANGE,BLUE,label,button
from challonge_client import tournament_identifier
from menu_layout import action_grid
from tournament_view import TournamentView


class ChallongePanel:
    def __init__(self,hub,parent):
        self.hub=hub;self.manager=hub.owner.challonge_organizer;self.authorization_manager=self.manager;self.seen=-1
        self.reader=hub.owner.challonge_shared
        self.title=tk.StringVar(value='Elige tu próximo torneo')
        self.frame=hub.card(parent,'Torneos','Sigue la competición y consulta sus cruces sin salir de Rising Battle.')
        self.title_label=self.frame.winfo_children()[0];self.title_label.configure(textvariable=self.title)
        self.community=tk.StringVar(value=self.manager.community or 'universotenkaichi')
        self.link=tk.StringVar(value='https://challonge.com/es/trunksprofecyI')
        load=tk.Frame(self.frame,bg=PANEL);load.pack(fill='x',padx=24,pady=(0,12));load.columnconfigure(0,weight=1)
        link_entry=tk.Entry(load,textvariable=self.link,bg=FIELD,fg=TEXT,insertbackground=BLUE,relief='flat',font=('Segoe UI',11),highlightthickness=1,highlightbackground=BORDER)
        link_entry.grid(row=0,column=0,sticky='ew',ipady=12,padx=(0,12));link_entry.bind('<Return>',lambda e:self.submit('import',self.link.get()))
        button(load,'Cargar torneo',lambda:self.submit('import',self.link.get()),True).grid(row=0,column=1,sticky='ew')
        self.summary=tk.StringVar(value='Cuadro, participantes y resultados en un mismo lugar.')
        tk.Label(self.frame,textvariable=self.summary,bg=PANEL,fg=BLUE,font=('Segoe UI',10),anchor='w').pack(fill='x',padx=24,pady=(0,18))
        self.bracket_page=tk.Frame(parent,bg=PANEL)
        tk.Label(self.bracket_page,textvariable=self.title,bg=PANEL,fg=TEXT,font=('Segoe UI Semibold',16),anchor='w').pack(fill='x',padx=(16,160),pady=(10,4))
        button(self.bracket_page,'Cerrar vista',lambda:self.submit('close')).place(relx=1,x=-12,y=8,anchor='ne')
        tk.Label(self.bracket_page,textvariable=self.summary,bg=PANEL,fg=BLUE,font=('Segoe UI',9),anchor='w').pack(fill='x',padx=16,pady=(0,8))
        self.view=TournamentView(self.bracket_page);self.view.pack(fill='both',expand=True,padx=12,pady=(0,6))
        self.bracket=self.view.canvas
        self.overview=tk.Frame(self.frame,bg=PANEL)
        # The overview is mounted only when a real tournament is loaded.
        self.metric_values=[tk.StringVar(value='—') for _ in range(3)]
        for column,(title,value) in enumerate(zip(('PARTICIPANTES','CRUCES COMPLETADOS','FORMATO'),self.metric_values)):
            self.overview.columnconfigure(column,weight=1)
            group=tk.Frame(self.overview,bg=PANEL);group.grid(row=0,column=column,sticky='w')
            tk.Label(group,textvariable=value,bg=PANEL,fg=TEXT,font=('Segoe UI Semibold',16)).pack(anchor='w')
            label(group,title,8,MUTED).pack(anchor='w',pady=(6,0))
        self.empty=tk.Frame(self.frame,bg=PANEL)
        self.empty.pack(fill='both',expand=True,padx=24,pady=18)
        label(self.empty,'Tu próximo torneo empieza aquí.',20,TEXT).pack(anchor='w',pady=(14,10))
        label(self.empty,'Pega su enlace de Challonge para consultar participantes y resultados.\nEl bracket se abrirá en su propia pestaña.',11,MUTED,justify='left',wraplength=640).pack(anchor='w')
        self.open_bracket=button(self.frame,'Abrir pestaña Bracket',lambda:hub.show_section('bracket'),True)
        self.open_bracket.configure(state='disabled');self.open_bracket.pack(anchor='w',padx=24,pady=12)
        self.footer=tk.Frame(self.frame,bg=PANEL);self.footer.pack(fill='x',padx=24,pady=(10,8))
        action_grid(self.footer,[button(self.footer,'Actualizar',lambda:self.submit('refresh')),button(self.footer,'Abrir en Challonge ↗',self.open_tournament),button(self.footer,'Organizador ▾',self.toggle_admin)],220)
        self.admin_frame=tk.Frame(self.frame,bg=FIELD)
        self.auth_text=tk.StringVar(value='Organizador sin conectar')
        self.auth_label=tk.Label(self.admin_frame,textvariable=self.auth_text,bg=FIELD,fg=BLUE,anchor='w',wraplength=650,font=('Segoe UI',11));self.auth_label.pack(fill='x',padx=18,pady=8)
        self.device_button=button(self.admin_frame,'Abrir autorización ↗',self.authorize)
        self.copy_authorization=button(self.admin_frame,'Copiar enlace para el organizador',self.copy_authorize)
        hub.entry(self.admin_frame,'COMUNIDAD · VACÍO PARA TORNEOS PERSONALES',self.community)
        tools=tk.Frame(self.admin_frame,bg=FIELD);tools.pack(fill='x',padx=14,pady=8)
        action_grid(tools,[button(tools,'Conectar organizador',lambda:self.login(True)),button(tools,'Vincular este torneo',lambda:self.submit('publish',self.link.get()),True)],240)
        self.auth_status=tk.StringVar()
        tk.Label(self.admin_frame,textvariable=self.auth_status,bg=FIELD,fg=MUTED,wraplength=650,anchor='w',font=('Segoe UI',9)).pack(fill='x',padx=18,pady=8)
        button(self.admin_frame,'Volver a Torneos',self.toggle_admin).pack(anchor='w',padx=18,pady=8)
        self.state=tk.StringVar(value=self.reader.status)
        tk.Label(self.frame,textvariable=self.state,bg=PANEL,fg=MUTED,font=('Segoe UI',9),wraplength=900,anchor='w').pack(fill='x',padx=24,pady=(8,12))
        label(self.frame,'Consulta de Challonge · la conexión automática de combates y el envío de resultados están pendientes.',9,MUTED,justify='left',wraplength=900).pack(anchor='w',padx=24,pady=(0,20))
        self.frame.bind('<Configure>',lambda e:self.title_label.configure(wraplength=max(200,e.width-48)),add='+')

    def submit(self,op,value=''):
        if op in ('import','publish'):
            try:tournament_identifier(value)
            except ValueError as exc:self.hub.status.set(str(exc));return
        try:
            self.reader.submit(op,value,self.community.get())
        except queue.Full:self.hub.status.set('Espera a que termine la petición anterior.')

    def open_tournament(self):
        try:key=tournament_identifier(self.link.get())
        except ValueError as exc:self.hub.status.set(str(exc));return
        webbrowser.open('https://challonge.com/'+key)

    def toggle_admin(self):
        if self.admin_frame.winfo_manager():
            self.admin_frame.pack_forget()
            for widget,options in self.saved_main:widget.pack(**options)
        else:
            self.saved_main=[]
            for widget in self.frame.winfo_children():
                if widget is not self.admin_frame and widget.winfo_manager()=='pack':
                    options=widget.pack_info();options.pop('in',None);self.saved_main.append((widget,options));widget.pack_forget()
            self.admin_frame.pack(fill='both',expand=True,padx=16,pady=10)

    def login(self,organizer=False):
        if self.hub.snapshot or self.hub.owner.session and self.hub.owner.session.running:
            self.hub.status.set('Cierra la partida y sal de la sala antes de vincular el perfil.');return
        manager=self.manager if organizer else self.hub.owner.challonge
        self.authorization_manager=manager
        if not organizer:self.hub.show_section('tournament')
        if not self.admin_frame.winfo_manager():self.toggle_admin()
        try:
            if organizer:manager.submit('community',self.community.get())
            manager.submit('login')
        except queue.Full:self.hub.status.set('Espera a que termine la petición anterior.')

    def configure(self):
        client_id=simpledialog.askstring('Aplicación Challonge','Client ID público de Rising Battle (no Client Secret):',initialvalue=self.manager.client_id,parent=self.hub.root)
        if client_id:self.submit('config',client_id.strip())

    def authorize(self):
        grant=self.authorization_manager.device
        if grant:webbrowser.open(grant.get('verification_uri_complete') or grant['verification_uri'])

    def copy_authorize(self):
        grant=self.authorization_manager.device
        if not grant:return
        self.hub.root.clipboard_clear()
        self.hub.root.clipboard_append(grant.get('verification_uri_complete') or grant['verification_uri'])
        self.hub.status.set('Enlace de autorización copiado. Compártelo solo con el organizador; caduca en pocos minutos.')

    def refresh(self):
        manager=self.manager;self.reader.visible=self.hub.section in ('tournament','bracket')
        self.state.set(self.reader.status)
        self.auth_status.set(self.authorization_manager.status)
        identity=manager.identity
        grant=self.authorization_manager.device
        self.auth_text.set('Código: '+grant['user_code'] if grant else 'Organizador: '+identity['username'] if identity else 'Organizador sin conectar · tu perfil de jugador es independiente')
        if grant:
            if not self.device_button.winfo_manager():self.device_button.pack(fill='x',padx=18,pady=8,after=self.auth_label)
            if not self.copy_authorization.winfo_manager():self.copy_authorization.pack(fill='x',padx=18,pady=4,after=self.device_button)
        else:self.device_button.pack_forget();self.copy_authorization.pack_forget()
        for event_manager in (manager,self.hub.owner.challonge):
          try:
            while True:
                kind,data=event_manager.events.get_nowait()
                if kind=='profile':
                    name=self.hub.owner.profile_store.profile()['name']
                    self.hub.profile_name.set(name);self.hub.name.set(name);self.hub.social_profile.configure(text=name)
                    self.hub.identity_provider.set('Challonge · '+data['username'])
                    self.hub.reload_avatars()
                elif kind=='device':self.hub.status.set('Autoriza el código '+data['user_code']+' con el botón Abrir autorización.')
          except queue.Empty:pass
        if self.reader.version==self.seen:return
        self.seen=self.reader.version;snapshot=self.reader.snapshot
        self.open_bracket.configure(state='normal' if snapshot else 'disabled')
        self.hub.set_bracket_available(bool(snapshot))
        if snapshot:
            kind={'single elimination':'Eliminación simple','double elimination':'Doble eliminación','round robin':'Todos contra todos','swiss':'Suizo'}.get(snapshot['kind'],snapshot['kind'])
            self.title.set(snapshot['title'])
            matches=snapshot.get('matches',[])
            completed=sum(bool(m.get('winner')) or m['state'] in ('complete','completed') for m in matches)
            self.summary.set(f"{kind}  ·  {len(snapshot.get('participants',[]))} participantes  ·  {completed}/{len(matches)} cruces finalizados")
        else:
            self.title.set('Elige tu próximo torneo')
            self.summary.set('Cuadro, participantes y resultados en un mismo lugar.')
        if snapshot:
            self.empty.pack_forget()
            if not self.overview.winfo_manager():self.overview.pack(fill='x',padx=24,pady=(12,16),before=self.open_bracket)
            for value,text in zip(self.metric_values,(str(len(snapshot.get('participants',[]))),f'{completed} / {len(matches)}',kind)):
                value.set(text)
        else:
            self.overview.pack_forget()
            for value in self.metric_values:value.set('—')
            if not self.empty.winfo_manager():self.empty.pack(fill='both',expand=True,padx=24,pady=18,before=self.open_bracket)
        self.view.render(snapshot)
