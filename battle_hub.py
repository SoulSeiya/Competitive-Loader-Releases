"""Private Rising Battle desktop interface. Uses the Loader's existing identity.

Room commands run on RoomBridge's worker. This window never launches a second
game for viewing; live spectator transport is explicitly pending.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import queue

import competitive_loader as core
from rising_room import RoomError
from rising_service import DEFAULT_ROOM_SERVICE

BG = "#0c121b"
PANEL = "#0c121b"
FIELD = "#121f2b"
BORDER = "#223542"
TEXT = "#f2f0eb"
MUTED = "#8fA5b5"
ORANGE = "#f39b53"
BLUE = "#83bed4"
GREEN = "#74d3ac"


def label(parent, text, size=10, color=TEXT, **kw):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=("Segoe UI", size), **kw)


def button(parent, text, command, primary=False):
    b=tk.Button(parent, text=text, command=command, relief="flat", bd=0,
        bg=ORANGE if primary else parent.cget("bg"), fg="#111820" if primary else TEXT,
        activebackground="#ffc086" if primary else "#21445a", activeforeground="#111820" if primary else TEXT,
        disabledforeground="#617388", cursor="hand2", padx=16, pady=10,
        highlightthickness=0,highlightbackground=ORANGE if primary else BORDER,highlightcolor=BLUE,
        font=("Segoe UI Semibold", 10))
    b._hover_timer=None;b._hover_base=b.cget('bg');b._hovering=False
    def tween(target,step=0,start=None):
        if not b.winfo_exists():return
        if step==0:
            if b._hover_timer:b.after_cancel(b._hover_timer)
            start=b.winfo_rgb(b.cget('bg'))
        goal=b.winfo_rgb(target);ratio=min(1,(step+1)/7)
        color='#'+''.join(f'{int((start[i]+(goal[i]-start[i])*ratio)/257):02x}' for i in range(3))
        b.configure(bg=color)
        b._hover_timer=b.after(16,lambda:tween(target,step+1,start)) if step<6 else None
    def enter(event=None):
        if str(b.cget('state'))=='disabled':return
        if not b._hovering:b._hover_base=b.cget('bg')
        b._hovering=True;b.configure(highlightbackground=BLUE)
        tween('#ffbd88' if primary else '#1b303f')
    def leave(event=None):
        b._hovering=False;b.configure(highlightbackground=b._hover_base)
        tween(b._hover_base)
    b.bind('<Enter>',enter);b.bind('<Leave>',leave)
    return b



class BattleHub:
    def __init__(self, owner, embedded=False):
        self.owner, self.bridge = owner, owner.room_bridge
        self.embedded = embedded
        self.root = owner.root if embedded else tk.Toplevel(owner.root)
        self.root.title("Rising Battle · Centro online privado")
        self.root.geometry("1240x800")
        self.root.minsize(900, 620)
        self.root.configure(bg=BG)
        if not embedded:self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.service = None
        self.service_url = ""
        self.last_chat = None
        self.last_users = None
        self.last_bracket = None
        self.last_notice = ""
        self.auto_launch_attempts = set()
        self.snapshot = None
        self.status = tk.StringVar(value="Crea una sala o entra con el código del anfitrión.")
        cfg = core.load_config()
        self.endpoint = tk.StringVar(value=DEFAULT_ROOM_SERVICE)
        self.name = tk.StringVar(value=cfg.get("btc_player_name", "Jugador"))
        self.room_title = tk.StringVar(value="Noche competitiva BTC")
        self.room_code = tk.StringVar()
        self.capacity = tk.StringVar(value="8")
        self.title = tk.StringVar(value="Copa Rising Battle")
        self.ft = tk.StringVar(value="2")
        self.characters = tk.StringVar(value="1")
        self.seconds = tk.StringVar(value="180")
        self.roster = tk.StringVar(value="Libre")
        self.chat_input = tk.StringVar()
        self.code_display = tk.StringVar(value="SIN SALA")
        self.role = tk.StringVar(value="Entra en una sala para ver tu próximo cruce.")
        self.online_state = tk.StringVar(value="DESCONECTADO")
        self.announcement = tk.StringVar(value="Los anuncios de los cruces aparecerán aquí.")
        style = ttk.Style()
        style.configure("Battle.Treeview", background=FIELD, fieldbackground=FIELD,
                        foreground=TEXT, borderwidth=0, rowheight=42, font=("Segoe UI", 10))
        style.configure("Battle.Treeview.Heading", background=PANEL, foreground=MUTED,
                        font=("Segoe UI Semibold", 9), relief="flat")
        style.map("Battle.Treeview", background=[("selected", "#234364")])
        self.build_layout()
        self.refresh()

    def build_layout(self):
        nav = tk.Frame(self.root, bg=FIELD, width=204)
        nav.pack(side="left", fill="y"); nav.pack_propagate(False)
        label(nav, "RISING", 25, ORANGE).pack(anchor="w", padx=22, pady=(28, 0))
        label(nav, "BATTLE", 25).pack(anchor="w", padx=22)
        label(nav, "BTC / PREVIEW PRIVADA", 8, MUTED).pack(anchor="w", padx=24, pady=(6, 28))
        self.pages, self.navigation = {}, {}
        self.page_shells,self.page_canvases={},{}
        self.current_page='online'
        for key, text in (("online", "01   Crear / entrar"), ("room", "02   Mi sala"),
                          ("tournament", "03   Torneo"), ("score", "04   Marcador"),
                          ("connection", "05   Conexión")):
            b = button(nav, text, lambda k=key: self.show(k))
            b.pack(fill="x", padx=12, pady=3); self.navigation[key] = b
        label(nav, "MISMA SESIÓN\nMISMA VENTANA", 9, MUTED, justify="left").pack(side="bottom", anchor="w", padx=24, pady=24)
        main = tk.Frame(self.root, bg=BG); main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=BG); top.pack(fill="x", padx=28, pady=(24, 12))
        label(top, "CENTRO ONLINE", 10, MUTED).pack(side="left")
        tk.Label(top, textvariable=self.online_state, bg=BG, fg=GREEN,
                 font=("Segoe UI Semibold", 9)).pack(side="right")
        body = tk.Frame(main, bg=BG); body.pack(fill="both", expand=True, padx=28)
        for key in self.navigation:
            shell=tk.Frame(body,bg=BG);self.page_shells[key]=shell
            canvas=tk.Canvas(shell,bg=BG,highlightthickness=0,yscrollincrement=24)
            scroll=ttk.Scrollbar(shell,orient='vertical',command=canvas.yview)
            scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
            canvas.configure(yscrollcommand=scroll.set)
            page=tk.Frame(canvas,bg=BG);window=canvas.create_window(0,0,window=page,anchor='nw')
            self.pages[key]=page;self.page_canvases[key]=canvas
            def resize_page(event=None,p=page,c=canvas,w=window):
                width=max(1,c.winfo_width());height=max(c.winfo_height(),p.winfo_reqheight())
                c.itemconfigure(w,width=width,height=height);c.configure(scrollregion=(0,0,width,height))
            canvas.bind('<Configure>',resize_page);page.bind('<Configure>',resize_page)
        self.build_online(); self.build_room(); self.build_tournament()
        self.build_score(); self.build_connection()
        self.status_label=tk.Label(main, textvariable=self.status, bg=BG, fg=MUTED, anchor="w", justify="left",
                 wraplength=900, font=("Segoe UI", 9))
        self.status_label.pack(fill="x", padx=28, pady=12)
        main.bind('<Configure>',lambda e:self.status_label.configure(wraplength=max(240,e.width-56)))
        self.root.bind('<MouseWheel>',self._page_wheel,add='+')
        self.show("online")

    def show(self, key):
        self.current_page=key
        for name, page in self.page_shells.items():
            page.pack_forget()
            self.navigation[name].configure(bg="#25394f" if name == key else FIELD,
                                             fg=ORANGE if name == key else MUTED)
        self.page_shells[key].pack(fill="both", expand=True)

    def _page_wheel(self,event):
        if isinstance(event.widget,(tk.Text,ttk.Treeview,ttk.Combobox,ttk.Scrollbar)):return
        if event.delta:
            self.page_canvases[self.current_page].yview_scroll(-1 if event.delta>0 else 1,'units')
            return 'break'

    def card(self, parent, title, detail=""):
        frame = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        heading=label(frame, title, 15);heading.pack(anchor="w", padx=18, pady=(14, 4))
        wrapped=[heading]
        if detail:
            subtitle=label(frame, detail, 9, MUTED, justify="left", wraplength=760);subtitle.pack(anchor="w", padx=18, pady=(0, 10));wrapped.append(subtitle)
        frame.bind('<Configure>',lambda e:[w.configure(wraplength=max(120,e.width-36)) for w in wrapped],add='+')
        return frame

    def entry(self, parent, title, variable):
        label(parent, title, 9, MUTED).pack(anchor="w", padx=18, pady=(9, 5))
        entry = tk.Entry(parent, textvariable=variable, bg=FIELD, fg=TEXT, insertbackground=ORANGE,
                         relief="flat", font=("Segoe UI", 11), highlightthickness=1, highlightbackground=BORDER)
        entry.pack(fill="x", padx=18, ipady=8)
        return entry

    def build_online(self):
        page = self.pages["online"]
        label(page, "Tu próxima batalla empieza aquí.", 23).pack(anchor="w", pady=(8, 6))
        label(page, "Una sala para todos. Un código de combate para cada cruce.", 11, MUTED).pack(anchor="w", pady=(0, 22))
        button(page,"Seleccionar carpeta del Loader / instalación existente",self.owner.select_installation).pack(anchor="w",pady=(0,10))
        self.entry(page, "NOMBRE DE JUGADOR", self.name)
        row = tk.Frame(page, bg=BG); row.pack(fill="both", expand=True, pady=20)
        for column, title, detail in ((0, "Crear una sala", "Organiza, invita y prepara las reglas."),
                                      (1, "Entrar con código", "Únete a la sala de tu anfitrión.")):
            card = self.card(row, title, detail); card.grid(row=0, column=column, sticky="nsew", padx=(0, 12) if column == 0 else (0, 0))
            row.columnconfigure(column, weight=1)
            if column == 0:
                self.entry(card, "NOMBRE DE LA SALA", self.room_title)
                self.entry(card, "PLAZAS · 2 A 32", self.capacity)
                button(card, "Crear sala y obtener código", self.create_room, True).pack(fill="x", padx=18, pady=22)
            else:
                entry = self.entry(card, "CÓDIGO BTC", self.room_code)
                entry.bind("<Return>", lambda _: self.join_room())
                button(card, "Entrar en la sala", self.join_room, True).pack(fill="x", padx=18, pady=22)
                label(card, "Solo necesitas el código de sala.\nLa conexión ya está configurada.", 10, MUTED, justify="left").pack(anchor="w", padx=18)
        button(page, "Información de conexión", lambda: self.show("connection")).pack(anchor="w", pady=(0, 12))

    def build_room(self):
        page = self.pages["room"]
        header = tk.Frame(page, bg=BG); header.pack(fill="x", pady=(8, 18))
        tk.Label(header, textvariable=self.code_display, bg=BG, fg=ORANGE,
                 font=("Segoe UI Semibold", 24)).pack(side="left")
        button(header, "Copiar código", self.copy_code).pack(side="right")
        row = tk.Frame(page, bg=BG); row.pack(fill="both", expand=True)
        self.room_columns=row
        users = self.card(row, "Jugadores", "El anfitrión administra los miembros.")
        users.grid(row=0,column=0,sticky='nsew',padx=(0,10))
        row.columnconfigure(0,weight=1,uniform='room');row.columnconfigure(1,weight=1,uniform='room');row.rowconfigure(0,weight=1)
        self.users = ttk.Treeview(users, columns=("name", "state"), show="headings", style="Battle.Treeview", selectmode="browse",height=5)
        self.users.heading("name", text="JUGADOR"); self.users.heading("state", text="ESTADO")
        self.users.column("name", width=170,minwidth=90); self.users.column("state", width=95,minwidth=70)
        self.users.pack(fill="both", expand=True, padx=12, pady=8)
        actions = tk.Frame(users, bg=PANEL); actions.pack(fill="x", padx=12, pady=12)
        button(actions, "Listo / esperando", lambda: self.send(6)).pack(side="left")
        self.kick = button(actions, "Expulsar", self.kick_user); self.kick.pack(side="right")
        chat = self.card(row, "Chat de sala", "Avisos y conversación de todos los miembros.")
        chat.grid(row=0,column=1,sticky='nsew')
        def room_columns(event,container=row):
            stacked=event.width<860
            users.grid_configure(row=0,column=0,columnspan=2 if stacked else 1,padx=0 if stacked else (0,10),pady=(0,10) if stacked else 0)
            chat.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1,columnspan=2 if stacked else 1)
            container.rowconfigure(1,weight=1 if stacked else 0)
        row.bind('<Configure>',room_columns)
        self.chat = tk.Text(chat, bg=FIELD, fg=TEXT, relief="flat", wrap="word", state="disabled",
                            width=28,height=7, font=("Segoe UI", 10), padx=12, pady=12)
        self.chat.pack(fill="both", expand=True, padx=12, pady=8)
        entry = self.entry(chat, "MENSAJE", self.chat_input); entry.bind("<Return>", lambda _: self.chat_send())
        button(chat, "Enviar mensaje", self.chat_send).pack(fill="x", padx=18, pady=12)
        bar = tk.Frame(page, bg=BG); bar.pack(fill="x", pady=18)
        button(bar, "Preparar torneo", lambda: self.show("tournament"), True).pack(side="left")
        button(bar, "Salir de la sala", lambda: self.send(5)).pack(side="right")
        duel=self.card(page,"Duelo directo","Selecciona un rival de la lista. No hace falta crear un torneo.")
        duel.pack(fill="x",pady=(0,12),before=self.room_columns)
        row=tk.Frame(duel,bg=PANEL);row.pack(fill="x",padx=12,pady=8)
        for column,(name,var,values) in enumerate((("FT",self.ft,(1,2,3,4,5)),("Segundos",self.seconds,(180,240,360,480)),("Máx. personajes",self.characters,(1,2,3,4,5)))):
            row.columnconfigure(column,weight=1,uniform='rules')
            label(row,name,9,MUTED).grid(row=0,column=column,sticky='w',padx=(0,8))
            ttk.Combobox(row,textvariable=var,values=values,state="readonly",width=5).grid(row=1,column=column,sticky='ew',padx=(0,8),pady=5)
        self.challenge_button=button(row,"Desafiar al jugador seleccionado",self.challenge,True);self.challenge_button.grid(row=2,column=0,columnspan=3,sticky='ew',pady=(4,0))
        self.duel_notice=tk.StringVar(value="Sin desafíos pendientes.")
        tk.Label(duel,textvariable=self.duel_notice,bg=PANEL,fg=BLUE,font=("Segoe UI",10),wraplength=800,anchor="w").pack(fill="x",padx=12,pady=4)
        row=tk.Frame(duel,bg=PANEL);row.pack(fill="x",padx=12,pady=(0,10))
        self.accept_button=button(row,"Aceptar duelo",lambda:self.duel_answer(31),True)
        self.decline_button=button(row,"Rechazar",lambda:self.duel_answer(32))
        self.cancel_duel=button(row,"Cancelar duelo",lambda:self.duel_answer(33))
        self.observe_button=button(row,"Observar · experimental",self.observe)
        self.stop_observe=button(row,"Dejar de observar",lambda:self.send(41))
        action_buttons=[self.accept_button,self.decline_button,self.cancel_duel,button(row,"Abrir mi juego",self.play),self.observe_button,self.stop_observe]
        def actions_resize(event,container=row):
            columns=2 if event.width<800 else 3
            for i in range(3):container.columnconfigure(i,weight=1 if i<columns else 0,uniform='duel_actions' if i<columns else '')
            for i,b in enumerate(action_buttons):b.grid(row=i//columns,column=i%columns,sticky='ew',padx=3,pady=3)
        row.bind('<Configure>',actions_resize)
        for i,b in enumerate(action_buttons):b.grid(row=i//2,column=i%2,sticky='ew',padx=3,pady=3)
        self.observer_status=tk.StringVar(value='Espectador en directo: requiere el paquete experimental.')
        tk.Label(duel,textvariable=self.observer_status,bg=PANEL,fg=MUTED,font=("Segoe UI",9),anchor='w',wraplength=800).pack(fill='x',padx=12,pady=(0,8))
        label(page, "Al marcarte listo, el juego se abrirá automáticamente cuando te toque un cruce del torneo.",
              10, BLUE, wraplength=850, justify="left").pack(anchor="w", pady=(0, 8))

    def build_tournament(self):
        page = self.pages["tournament"]
        label(page, "El camino al campeonato", 23).pack(anchor="w", pady=(8, 5))
        tk.Label(page, textvariable=self.role, bg=BG, fg=BLUE, anchor="w", font=("Segoe UI", 10)).pack(fill="x", pady=(0, 14))
        rules = self.card(page, "Reglas del torneo", "FT1 a FT5 · Tiempo configurable · Máximo de 1 a 5 personajes")
        rules.pack(fill="x")
        row = tk.Frame(rules, bg=PANEL); row.pack(fill="x", padx=18, pady=10)
        row.columnconfigure(1,weight=1)
        for index,(title, var, width) in enumerate((("Temática", self.title, 25), ("FT", self.ft, 3), ("Personajes", self.characters, 3))):
            label(row, title, 9, MUTED).grid(row=index,column=0,sticky='w',padx=(0,12),pady=5)
            tk.Entry(row, textvariable=var, bg=FIELD, fg=TEXT, insertbackground=ORANGE,
                     relief="flat", width=width, font=("Segoe UI", 11)).grid(row=index,column=1,sticky='ew' if index==0 else 'w',ipady=7,pady=5)
        self.rules_button = button(row, "Guardar", self.save_rules); self.rules_button.grid(row=3,column=0,columnspan=2,sticky='ew',pady=6)
        time_row = tk.Frame(rules, bg=PANEL); time_row.pack(fill="x", padx=18, pady=(0, 12))
        label(time_row, "Tiempo por combate (segundos)", 9, MUTED).pack(side="left", padx=(0, 12))
        ttk.Combobox(time_row, textvariable=self.seconds, values=(180,240,360,480), state="readonly", width=8).pack(side="left")
        self.saved_rules = tk.StringVar(value="")
        tk.Label(rules, textvariable=self.saved_rules, bg=PANEL, fg=BLUE, anchor="w", font=("Segoe UI", 10)).pack(fill="x", padx=18, pady=(0,12))
        row = tk.Frame(page, bg=BG); row.pack(fill="x", pady=12)
        tk.Entry(row, textvariable=self.roster, bg=FIELD, fg=TEXT, insertbackground=ORANGE,
                 relief="flat", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 10))
        button(row, "Inscribirme", lambda: self.send(11, text=self.roster.get())).pack(side="left", padx=(0, 8))
        self.start_tournament = button(row, "Iniciar y generar bracket", lambda: self.send(12), True)
        self.start_tournament.pack(side="right")
        self.bracket = tk.Canvas(page, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        self.bracket.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(page, orient="horizontal", command=self.bracket.xview)
        scroll.pack(fill="x"); self.bracket.configure(xscrollcommand=scroll.set)
        self.bracket.bind("<Configure>", lambda _: self.draw_bracket())
        tk.Label(page, textvariable=self.announcement, bg=BG, fg=MUTED, anchor="w", wraplength=850,
                 font=("Segoe UI", 9)).pack(fill="x", pady=9)
        bar = tk.Frame(page, bg=BG); bar.pack(fill="x", pady=(0, 10))
        button(bar, "Abrir mi partida", self.play, True).pack(side="left")

    def build_score(self):
        page = self.pages["score"]
        label(page, "Menos ruido. Más combate.", 23).pack(anchor="w", pady=(8, 5))
        label(page, "Vista del nuevo marcador. Los controles de abajo solo cambian esta muestra.", 10, MUTED).pack(anchor="w", pady=(0, 18))
        self.score_preview = tk.Canvas(page, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        self.score_preview.pack(fill="both", expand=True)
        self.preview_a = tk.IntVar(value=1); self.preview_b = tk.IntVar(value=0)
        self.preview_winner = False
        row = tk.Frame(page, bg=BG); row.pack(fill="x", pady=18)
        for name, value in (("P1", self.preview_a), ("P2", self.preview_b)):
            label(row, name, 10, ORANGE if name == "P1" else BLUE).pack(side="left", padx=(0, 8))
            tk.Spinbox(row, from_=0, to=5, textvariable=value, width=4, bg=FIELD, fg=TEXT,
                       buttonbackground=BORDER, relief="flat", command=self.draw_score).pack(side="left", padx=(0, 22))
            value.trace_add("write", lambda *_: self.draw_score())
        button(row, "Alternar GG / combate", self.toggle_winner).pack(side="right")
        self.score_preview.bind("<Configure>", lambda _: self.draw_score())

    def build_connection(self):
        page = self.pages["connection"]
        label(page, "Tu conexión está preparada", 23).pack(anchor="w", pady=(8, 18))
        hosted = self.card(page, "Salas BTC · Cloudflare", "Crea una sala y comparte su código. Tus amigos solo tienen que introducirlo para entrar.")
        hosted.pack(fill="x", pady=(0, 16))
        label(hosted, "Usuarios, chat y bracket alojados en Cloudflare.\nNo necesitas iniciar servicios, pegar direcciones ni abrir puertos.",
              11, BLUE, justify="left", wraplength=800).pack(anchor="w", padx=18, pady=(0, 18))
        c = self.card(page, "Cloudflare · peleas 1 contra 1", "El Worker de matchmaking existente genera los códigos de los combates.")
        c.pack(fill="x", pady=(0, 16))
        label(c, "btc-matchmaking.paulogomez41.workers.dev", 11, BLUE).pack(anchor="w", padx=18, pady=(0, 18))
        c = self.card(page, "Un anfitrión, una sesión", "La sala organiza el bracket. Cada cruce enlaza a sus dos jugadores con su propio código.")
        c.pack(fill="x")
        label(c, "El espectador en la misma ventana requiere un canal de replay en directo.\nEse transporte todavía está pendiente; este diseño no abre otro juego para observar.",
              10, MUTED, justify="left", wraplength=800).pack(anchor="w", padx=18, pady=(0, 18))

    def send(self, op, **values):
        try:
            self.bridge.submit(op, **values)
            self.status.set("Procesando…")
        except (ValueError, TypeError, queue.Full) as exc:
            self.status.set(str(exc) or "Espera a que termine la acción anterior.")

    def create_room(self):
        try: capacity = int(self.capacity.get())
        except ValueError: self.status.set("Las plazas deben ser un número entre 2 y 32."); return
        if not 2 <= capacity <= 32: self.status.set("Elige entre 2 y 32 plazas."); return
        self.send(21, address=self.endpoint.get(), name=self.name.get(), title=self.room_title.get(), capacity=capacity)
        self.show("room")

    def join_room(self):
        self.send(22, address=self.endpoint.get(), name=self.name.get(), text=self.room_code.get().strip().upper())
        self.show("room")

    def chat_send(self):
        text = self.chat_input.get().strip()
        if text: self.send(3, text=text); self.chat_input.set("")

    def challenge(self):
        selected=self.users.selection()
        if not selected or not self.snapshot:self.status.set("Selecciona al rival en la lista de jugadores.");return
        uid=int(selected[0])
        if uid==self.snapshot['self_id']:self.status.set("Selecciona a otro luchador.");return
        self.send(30,target=uid,ft=int(self.ft.get()),characters=int(self.characters.get()),seconds=int(self.seconds.get()))

    def duel_answer(self,op):
        duel=(self.snapshot or {}).get('duel')
        if duel:self.send(op,tournament_id=duel['id'])

    def observe(self):
        if not self.owner.room_bridge.observer:return
        self.play() # Reuses the existing game; starts one only when none is open.
        self.send(40)

    def kick_user(self):
        selected = self.users.selection()
        if selected and self.snapshot:
            uid = int(selected[0])
            if uid != self.snapshot["self_id"] and messagebox.askyesno("Rising Battle", "¿Expulsar al jugador seleccionado?", parent=self.root):
                self.send(4, target=uid)

    def save_rules(self):
        try: ft, characters = int(self.ft.get()), int(self.characters.get())
        except ValueError: self.status.set("FT y personajes deben ser números entre 1 y 5."); return
        if not 1 <= ft <= 5 or not 1 <= characters <= 5: self.status.set("FT y personajes: de 1 a 5."); return
        self.send(10, title=self.title.get(), ft=ft, characters=characters, seconds=int(self.seconds.get()))

    def copy_code(self):
        if self.bridge.invite:
            self.root.clipboard_clear(); self.root.clipboard_append(self.bridge.invite)
            self.status.set("Código de sala copiado.")

    def save_endpoint(self):
        from rising_service import ServiceClient
        try: url = ServiceClient(self.endpoint.get()).url.removesuffix("/v1/rooms")
        except (ValueError, RoomError) as exc: self.status.set(str(exc)); return
        cfg = core.load_config(); cfg["btc_room_service_url"] = url; cfg["btc_player_name"] = self.name.get()
        core.save_config(cfg); self.endpoint.set(url); self.status.set("Servidor guardado para la próxima conexión.")

    def open_service(self):
        if self.service and self.service.root.winfo_exists(): self.service.root.deiconify(); return
        from temporary_room_host import TestHost
        window = tk.Toplevel(self.root); self.service = TestHost(window)

    def play(self):
        if self.owner.session and self.owner.session.running:
            self.status.set("Tu partida ya está abierta. Continúa en esa misma ventana del juego.")
        else:
            self.owner.play()

    def auto_start_match(self, snapshot):
        """A ready assigned player needs the game, not only an HTTP membership.

        Make one attempt per assignment. Cancellation/failure leaves the manual
        launch button available; polling must never reopen dialogs or processes.
        """
        if not snapshot:
            return
        t = snapshot.get("combat") or snapshot.get("tournament", {})
        if t.get("status") != "running" or t.get("role") not in (1, 2) or not t.get("current"):
            return
        key = (t.get("id"), t["current"])
        if key in self.auto_launch_attempts:
            return
        if self.owner.session and self.owner.session.running:
            self.auto_launch_attempts.add(key)
            return
        me = next((u for u in snapshot.get("users", []) if u["id"] == snapshot["self_id"]), {})
        if not me.get("ready") or getattr(self.owner, "busy", False):
            return
        self.auto_launch_attempts.add(key)
        self.status.set("Te toca jugar. Abriendo tu partida en este Loader…")
        self.owner.play()

    def refresh(self):
        if not self.root.winfo_exists(): return
        if self.bridge.notice != self.last_notice or (self.bridge.ui_commands.empty() and self.status.get() == "Procesando…"):
            self.status.set(self.bridge.notice)
            self.last_notice = self.bridge.notice
        snapshot = self.bridge.snapshot
        self.snapshot = snapshot
        if self.service and self.service.url and self.service.url != self.service_url:
            self.service_url = self.service.url; self.endpoint.set(self.service_url)
        host = bool(snapshot and snapshot["self_id"] == snapshot["host_id"])
        self.online_state.set("SALA CONECTADA" if snapshot else "DESCONECTADO")
        self.code_display.set(self.bridge.invite or "SIN SALA")
        users = snapshot["users"] if snapshot else []
        if users != self.last_users:
            selected = self.users.selection()
            self.users.delete(*self.users.get_children())
            for user in users:
                suffix = " · HOST" if user["id"] == snapshot["host_id"] else ""
                if user["id"] == snapshot["self_id"]: suffix += " · TÚ"
                self.users.insert("", "end", iid=str(user["id"]), values=(user["name"] + suffix, "Listo" if user["ready"] else "Esperando"))
            if selected and self.users.exists(selected[0]): self.users.selection_set(selected[0])
            self.last_users = users
        messages = snapshot["messages"] if snapshot else []
        if messages != self.last_chat:
            follow = self.chat.yview()[1] > .95
            self.chat.configure(state="normal"); self.chat.delete("1.0", "end")
            self.chat.insert("end", "\n\n".join(m["author"] + "\n" + m["text"] for m in messages))
            self.chat.configure(state="disabled")
            if follow: self.chat.see("end")
            self.last_chat = messages
        t = snapshot.get("tournament", {}) if snapshot else {}
        duel=snapshot.get('duel',{}) if snapshot else {}
        combat=snapshot.get('combat',{}) if snapshot else {}
        me=snapshot.get('self_id') if snapshot else None
        pending=duel.get('status')=='pending'
        active=combat.get('status')=='running'
        observer=self.bridge.observer
        self.observe_button.configure(state='normal' if observer and host and active and combat.get('role')==0 else 'disabled')
        self.stop_observe.configure(state='normal' if observer and observer.watch_request else 'disabled')
        if observer:self.observer_status.set(observer.status)
        self.challenge_button.configure(state='normal' if snapshot and not pending and not active and t.get('status')!='running' else 'disabled')
        for b in (self.accept_button,self.decline_button):b.configure(state='normal' if pending and duel.get('to')==me else 'disabled')
        self.cancel_duel.configure(state='normal' if duel and (pending or active) and (host or me in (duel.get('from'),duel.get('to'))) else 'disabled')
        description=f"{duel.get('name1')} vs {duel.get('name2')} · FT{duel.get('ft')} · {duel.get('seconds')} s · máximo {duel.get('characters')} personajes"
        self.duel_notice.set(("Desafío pendiente: " if pending else "Duelo en curso: " if active else "Duelo terminado: ")+description if duel else "Sin desafíos pendientes.")
        self.saved_rules.set(f"Reglas guardadas: FT{t['ft']} · {t.get('seconds',180)} s · máximo {t['characters']} personajes" if t else "Guarda las reglas antes de iniciar el torneo.")
        self.kick.configure(state="normal" if host else "disabled")
        registration = t.get("status") == "registration"
        self.rules_button.configure(state="normal" if host and registration else "disabled")
        self.start_tournament.configure(state="normal" if host and registration and t.get("enrolled", 0) >= 2 else "disabled")
        role = t.get("role", 0)
        self.role.set((f"Cruce #{t.get('current')} · Juegas como P{role}" if role else
                       "Cruce en curso · Esperas en la sala") if t.get("status") == "running" else
                      "Inscripciones abiertas" if registration else "Entra en una sala para preparar el torneo.")
        if t.get("status") == "finished": self.role.set("GG · Campeón: " + t.get("champion_name", ""))
        self.announcement.set((messages[-1]["text"] if messages else "Los cruces se anunciarán en el chat de la sala."))
        if t != self.last_bracket:
            self.last_bracket = t; self.draw_bracket()
        self.auto_start_match(snapshot)
        self.root.after(500, self.refresh)

    def draw_bracket(self):
        c = self.bracket; c.delete("all")
        t = self.snapshot.get("tournament", {}) if self.snapshot else {}
        matches = t.get("matches", [])
        if not matches:
            c.create_text(24, 28, anchor="nw", fill=MUTED, font=("Segoe UI", 12), text="El bracket aparecerá al iniciar el torneo.")
            return
        positions, counts = {}, {}
        height = max(c.winfo_height(), 280)
        first = sum(m["round"] == 1 for m in matches)
        row_height = max(88, min(116, (height - 60) / max(1, first)))
        for m in matches:
            round = m["round"]; index = counts.get(round, 0); counts[round] = index + 1
            positions[m["id"]] = (24 + (round-1)*270, 46 + (index+.5)*(2**(round-1))*row_height-33)
        for round in range(2, max(counts)+1):
            previous = [m for m in matches if m["round"] == round-1]
            current = [m for m in matches if m["round"] == round]
            for i, match in enumerate(current):
                x, y = positions[match["id"]]
                for child in previous[2*i:2*i+2]:
                    a, b = positions[child["id"]]
                    c.create_line(a+226, b+34, x-20, b+34, x-20, y+34, x, y+34, fill=BORDER, width=2)
        for round in counts:
            c.create_text(24+(round-1)*270, 17, anchor="nw", fill=MUTED, font=("Segoe UI Semibold", 9), text="FINAL" if round == max(counts) else f"RONDA {round}")
        for m in matches:
            x, y = positions[m["id"]]; active = m["state"] == "active"
            c.create_rectangle(x, y, x+226, y+70, fill=PANEL, outline=ORANGE if active else BORDER)
            c.create_rectangle(x, y, x+3, y+70, fill=ORANGE if active else BLUE, outline="")
            for i, key in enumerate(("name1", "name2")):
                winner = m["winner"] and m["winner"] == m["p1" if i == 0 else "p2"]
                c.create_text(x+14, y+13+i*30, anchor="nw", text=m[key][:21], fill=GREEN if winner else TEXT, font=("Segoe UI", 10))
                c.create_text(x+210, y+13+i*30, anchor="ne", text=str((m.get("score") or [0, 0])[i]), fill=ORANGE if i == 0 else BLUE, font=("Segoe UI Semibold", 11))
        c.configure(scrollregion=c.bbox("all"))

    def toggle_winner(self):
        self.preview_winner = not self.preview_winner; self.draw_score()

    def draw_score(self):
        if not hasattr(self, "score_preview"): return
        c = self.score_preview; c.delete("all"); w = max(c.winfo_width(), 600); h = max(c.winfo_height(), 300)
        try: a, b = self.preview_a.get(), self.preview_b.get()
        except tk.TclError: return
        for y in range(70, h, 46): c.create_line(0, y, w, y, fill="#101f2e")
        c.create_text(w/2, h*.66, text="VISTA PREVIA DEL MARCADOR", fill="#31475d", font=("Segoe UI Semibold", 11))
        width = min(w-40, 660); x = (w-width)/2; y = 28
        c.create_rectangle(x, y, x+width, y+84, fill=PANEL, outline=BORDER)
        c.create_line(x, y, x+width*.38, y, fill=ORANGE, width=3)
        c.create_line(x+width*.62, y, x+width, y, fill=BLUE, width=3)
        for side, name, color, px in ((0, "Rising", ORANGE, x+20), (1, "Rival", BLUE, x+width-178)):
            c.create_text(px, y+15, anchor="nw", text=f"P{side+1}", fill=color, font=("Segoe UI Semibold", 9))
            c.create_text(px, y+39, anchor="nw", text=name, fill=TEXT, font=("Segoe UI Semibold", 15))
        c.create_text(w/2, y+20, text="FT2", fill=MUTED, font=("Segoe UI", 10))
        c.create_text(w/2-42, y+54, text=str(a), fill=ORANGE, font=("Segoe UI Semibold", 28))
        c.create_text(w/2+42, y+54, text=str(b), fill=BLUE, font=("Segoe UI Semibold", 28))
        c.create_text(w/2, y+54, text="—", fill=MUTED, font=("Segoe UI", 13))
        if self.preview_winner:
            c.create_rectangle(w/2-175, h/2-12, w/2+175, h/2+126, fill=PANEL, outline=ORANGE if a >= b else BLUE)
            c.create_text(w/2, h/2+6, text="SET COMPLETADO", fill=MUTED, font=("Segoe UI Semibold", 9))
            c.create_text(w/2, h/2+46, text="GG", fill=ORANGE if a >= b else BLUE, font=("Segoe UI Semibold", 30))
            c.create_text(w/2, h/2+92, text=("Rising" if a >= b else "Rival") + f"   {a} — {b}", fill=TEXT, font=("Segoe UI", 13))

    def close(self):
        if self.service and self.service.root.winfo_exists(): self.service.close()
        if not self.embedded and self.root.winfo_exists(): self.root.destroy()
