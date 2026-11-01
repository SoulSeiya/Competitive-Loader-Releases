"""Public Competitive Loader: reviewed upstream updates and local diagnostics."""
import ctypes
import json
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import competitive_loader as core
from competitive_gui import CompetitiveApp
from session_diagnostics import SessionDiagnostics, make_logger
from rising_room_bridge import RoomBridge

core.RELEASE_PROFILE = True
LOGS = core.HERE / "logs"


class ReleaseApp(CompetitiveApp):
    def _runtime(self):
        runtime=super()._runtime()
        if "--rules-bot-test" in sys.argv and not (runtime/"Tenkaichi3Decomp.exe").is_file():
            installed=Path.home()/"Desktop"/"BTC Decomp"/"CompetitiveRuntime"
            if (installed/"Tenkaichi3Decomp.exe").is_file():return installed
        return runtime

    def __init__(self, root):
        from player_profile import ProfileStore
        self.profile_store=ProfileStore(initial_name=core.load_config().get("btc_player_name","Jugador"))
        from social_client import SocialManager
        self.social=SocialManager(self.profile_store)
        from challonge_client import ChallongeManager
        self.challonge=ChallongeManager(self.profile_store)
        self.challonge_organizer=ChallongeManager(self.profile_store,organizer=True)
        from challonge_shared import SharedBracketManager
        self.challonge_shared=SharedBracketManager(self.profile_store,self.challonge_organizer)
        self.session = None
        self.online_hub = None
        self.room_bridge = RoomBridge(make_logger("competitive.room", LOGS / "rising-battle.log"),profile_store=self.profile_store)
        import queue
        self.root=root;self.events=queue.Queue();self.busy=False
        self.pending_update=None;self.checking_versions=False
        root.configure(bg=self.BG)
        try:
            self.icon=tk.PhotoImage(file=str(core.APP_ICON));root.iconphoto(True,self.icon)
        except tk.TclError:self.icon=None
        from client_hub import ClientHub
        self.online_hub=ClientHub(self,embedded=True)
        self._write_status();self._refresh_install_state()
        root.after(100,self._poll)

    def open_online_hub(self):
        self.root.deiconify();self.root.lift()

    def _write_status(self):
        installed=(self._runtime()/'Tenkaichi3Decomp.exe').is_file()
        self._append('Instalación preparada. Motor fijo; se comprueba su compatibilidad al iniciar.\n' if installed else
                     'Selecciona tu instalación generada en Ajustes.\n')

    def _refresh_install_state(self):
        installed=(self._runtime()/'Tenkaichi3Decomp.exe').is_file()
        running=bool(self.session and self.session.running)
        for b in (self.import_button,self.future_update_button):
            b.configure(state='normal' if installed and not self.busy and not running else 'disabled')
        self.folder_button.configure(state='disabled' if self.busy or running else 'normal')

    def _set_busy(self,value,label='Listo'):
        self.busy=value
        self.play_button.configure(state='disabled' if value else 'normal')
        self.state_label.configure(text=label)
        if value:self.progress.start(12)
        else:self.progress.stop()
        self._refresh_install_state()

    def _poll(self):
        if getattr(self,'_closing',False):return
        import queue
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='log':self._append(event[1])
                elif event[0]=='done':
                    self._set_busy(False);self._append(event[1]+'\n')
                    self.online_hub.status.set('Juego iniciado.' if self.session and self.session.running else 'Operación completada.')
                elif event[0]=='error':
                    self._set_busy(False,'Revisa el problema');self._append('ERROR: '+event[1]+'\n')
                    messagebox.showerror('Rising Battle',event[1],parent=self.root)
                elif event[0]=='loader_release':
                    self.checking_versions=False
                    self.online_hub.display_release(info=event[1],error=event[2])
                    if len(event)>3:self.online_hub.set_release_history(event[3])
                elif event[0]=='app_update_ready':
                    self._append('Actualización verificada; reiniciando el Loader.\n')
                    self.close_app()
                    return
        except queue.Empty:pass
        self.root.after(100,self._poll)

    def select_installation(self):
        if getattr(self,'busy',False) or self.session and self.session.running:
            messagebox.showinfo("Instalación BTC","Cierra tu juego antes de cambiar la instalación.",parent=self.root);return
        folder=filedialog.askdirectory(parent=self.root,title="Carpeta del Loader con CompetitiveRuntime, o carpeta CompetitiveRuntime")
        if not folder:return
        def prepare_selected():
            from candidate_installation import prepare_existing
            runtime=prepare_existing(folder)
            cfg=core.load_config();cfg['runtime']=str(runtime);core.save_config(cfg)
            self.room_bridge.runtime=runtime
            print(f"Instalación de prueba seleccionada: {runtime}")
        self._run("Preparando BTC 0.1.38.1", "Base BTC preparada; tu instalación anterior se conserva.", prepare_selected)

    def _check_versions(self):
        if self.checking_versions or self.busy:return
        import threading
        self.checking_versions=True
        self.check_updates_button.configure(text='Buscando…',state='disabled')
        self.online_hub.release_state.set('Consultando las publicaciones del Loader…')
        def worker():
            try:
                from client_updates import release_history
                info=core.latest_loader_release_info()
                result=("loader_release",info,None,release_history(info))
            except Exception as exc:result=("loader_release",None,str(exc))
            self.events.put(result)
        threading.Thread(target=worker,name='Loader release check',daemon=True).start()

    def show_version_notes(self):
        marker = core.HERE / "loader-version-seen.json"
        try:
            previous = json.loads(marker.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError, AttributeError):
            previous = None
        if previous == core.APP_VERSION_TEXT:
            return
        messagebox.showinfo(
            f"Novedades · Competitive Loader {core.APP_VERSION_TEXT}",
            f"Competitive Loader {core.APP_VERSION_TEXT}\n\n{core.VERSION_HIGHLIGHTS}",
            parent=self.root,
        )
        try:
            temporary = marker.with_suffix(".tmp")
            temporary.write_text(json.dumps({"version": core.APP_VERSION_TEXT}), encoding="utf-8")
            os.replace(temporary, marker)
        except OSError as exc:
            self._append(f"No se pudo guardar la versión del aviso: {exc}\n")

    def open_logs(self):
        LOGS.mkdir(parents=True, exist_ok=True)
        os.startfile(self.session.path if self.session else LOGS)

    def configure_matchmaking(self):
        if self.busy or (self.session and self.session.running):
            messagebox.showinfo(core.APP_NAME,"Cierra el juego para cambiar el servidor de las próximas sesiones.",parent=self.root)
            return
        config=core.load_config()
        from btc_matchmaking import DEFAULT_MATCHMAKING
        value=simpledialog.askstring("Matchmaking BTC","URL de nuestro Worker de peleas (https://…).\nNo es la URL del servicio de salas/torneos.\nVacío: códigos desactivados hasta configurar el Worker.",
                                     initialvalue=config.get("btc_matchmaking_url",DEFAULT_MATCHMAKING),parent=self.root)
        if value is None:return
        from btc_matchmaking import validate_url
        try:value=validate_url(value)
        except ValueError as exc:
            messagebox.showerror(core.APP_NAME,str(exc),parent=self.root);return
        config["btc_matchmaking_url"]=value
        core.save_config(config)
        self._append("Matchmaking BTC configurado para el próximo inicio.\n" if value else
                     "Sin Worker BTC: códigos de pelea pendientes; offline e IP siguen disponibles.\n")

    def configure_room_service(self):
        self.open_online_hub()
        self.online_hub.show("connection")

    def _append(self, text):
        super()._append(text)
        if self.session:
            self.session.local.info("LOADER %s", text.rstrip())

    def _run(self, label, success, action):
        if self.busy:
            return
        if self.session and self.session.running:
            messagebox.showwarning(core.APP_NAME, "Cierra el juego antes de realizar esta operación.", parent=self.root)
            return
        if self.session:
            self.session.dispose()
        self.session = SessionDiagnostics(LOGS, self._runtime())
        diagnostic = self.session
        def recorded_action():
            try:
                result = action()
                if "pid" not in diagnostic.summary:
                    diagnostic.finish("completed")
                return result
            except Exception as exc:
                diagnostic.local.exception("OPERATION_FAILED %s", label)
                diagnostic.finish("incompatible" if isinstance(exc, core.IncompatibleDecompError) else "preparation_failed")
                if not diagnostic.running:
                    core._release_online_memory_handles()
                raise
        super()._run(label, success + f"\nRegistros: {diagnostic.path}", recorded_action)

    def play(self):
        runtime = self._runtime()
        exe = runtime / "Tenkaichi3Decomp.exe"
        marker = runtime / "gamedata" / ".competitive-v8.4.1.json"
        if exe.is_file() and (marker.is_file() or (runtime/'gamedata').is_dir()):
            def launch():
                # Private 2.0 preview keeps the installed reviewed motor fixed.
                image = core.validate_payload(core.PAYLOAD, exe)
                image.build(0x60000000, image.pe.preferred_base)
                self.room_bridge.runtime = runtime
                env = {"BTC_ROOM_BRIDGE": self.room_bridge.name,"BT3_NET_NAME":self.profile_store.profile()["name"]}
                if "--spectator-tournament-test" in sys.argv:env["BTC_TOURNAMENT_DEMO_USER"]="1"
                pid = self.session.launch(exe, image, env=env)
                self._game_started(pid)
                return pid
            self._run("Comprobando compatibilidad e iniciando Competitive",
                      "Competitive iniciado. Mantén el Loader abierto mientras juegas.", launch)
            return

        self.select_installation()
        runtime=self._runtime()
        if (runtime/'Tenkaichi3Decomp.exe').is_file() and (runtime/'gamedata').is_dir():
            self.play()

    def _game_started(self,pid):
        self.room_bridge.game_pid=pid
        if "--rules-bot-test" in sys.argv and not self.room_bridge.client:
            self.room_bridge.submit(26, name="Rising")
            self._append("Prueba privada: tú contra un bot. Abre Torneo, guarda las reglas y pulsa Iniciar y generar bracket.\n")
        if "--spectator-tournament-test" in sys.argv:
            from rising_room_bridge import Command
            shared=self.room_bridge.shared
            if shared.command_seq!=shared.ack_seq:raise core.LoaderError("La sala está ocupada; reinicia la prueba")
            shared.command=Command(op=24,name=b"UT Rising")
            shared.command_seq+=1
            self._append("Prueba de tres: pulsa Iniciar torneo. Primero observas bots vs bots; despues juegas la final. FT1 / 180 segundos.\n")

    def close_app(self):
        if getattr(self,'_closing',False):return
        if self.session and self.session.running:
            if not messagebox.askyesno(core.APP_NAME,
                    "El juego sigue abierto. Cerrar el Loader detendrá los registros y la protección de memory online. ¿Cerrar el Loader?",
                    parent=self.root):
                return
            self.session.finish("loader_closed_while_game_running")
        elif self.session:
            self.session.dispose()
        self._closing=True
        # This Tk interpreter belongs only to this application. Stop pending
        # repaint/hover/poll callbacks before destroying any of their controls.
        callback_owners={}
        def stop_layout(widget):
            widget.unbind('<Configure>')
            for command in widget._tclCommands or []:callback_owners[command]=widget
            for child in widget.winfo_children():stop_layout(child)
        stop_layout(self.root)
        for callback in self.root.tk.call('after','info'):
            command=self.root.tk.call('after','info',callback)[0]
            callback_owners.get(command,self.root).after_cancel(callback)
        if self.online_hub:
            self.online_hub.close()
        self.challonge.close()
        self.challonge_organizer.close()
        self.challonge_shared.close()
        self.social.close()
        self.room_bridge.close()
        self.root.destroy()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    bootstrap = make_logger("competitive.bootstrap", LOGS / "loader.log")
    def report_exception(kind, value, tb):
        bootstrap.error("UNHANDLED_LOADER_EXCEPTION", exc_info=(kind, value, tb))
        if any(arg.startswith('--smoke-') for arg in sys.argv):raise SystemExit(1)
        messagebox.showerror(core.APP_NAME, f"{value}\n\nDetalle en {LOGS / 'loader.log'}")
    sys.excepthook = report_exception
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    if '--smoke-background' in sys.argv:root.attributes('-alpha',0)
    root.report_callback_exception = report_exception
    app = ReleaseApp(root)
    if '--smoke-background' in sys.argv:
        import time
        try:
            until=time.monotonic()+1.5
            while time.monotonic()<until:root.update();time.sleep(.005)
            assert app.online_hub.animation.frames_displayed>=3
            assert app.online_hub.animation.error is None
        finally:app.close_app()
        return
    if "--smoke-test" in sys.argv or "--smoke-hub" in sys.argv:
        root.withdraw()
        if "--smoke-hub" in sys.argv:
            root.update_idletasks()
            for width,height in ((1180,820),(860,620),(1500,900)):
                root.geometry(f'{width}x{height}');root.update_idletasks()
            app.online_hub.toggle_settings();app.online_hub.show('tournament')
            root.update_idletasks()
        root.update()
        app.close_app()
    else:
        root.after(200, app.open_online_hub)
        root.after(1000,app.social.start)
        root.after(1500,app._check_versions)
        if any(flag in sys.argv for flag in ("--tournament-test","--spectator-tournament-test","--rules-bot-test")): root.after(200, app.play)
        root.mainloop()


if __name__ == "__main__":
    if getattr(sys,"frozen",False) and Path(sys.executable).stem=="BTC - Prueba de reglas" and "--tournament-bot-worker" not in sys.argv:
        sys.argv.append("--rules-bot-test")
    if "--watch-replay" in sys.argv:
        from replay_spectator import watch
        replay=Path(sys.argv[sys.argv.index("--watch-replay")+1]).resolve()
        result=watch(Path(core.load_config().get("runtime",core.DEFAULT_RUNTIME)),replay)
        if result:raise SystemExit(result)
    elif any(flag in sys.argv for flag in ("--room-test-host","--smoke-room-test-host","--four-player-room-test-host")):
        from temporary_room_host import main as host_main
        host_main()
    elif "--tournament-bot-worker" in sys.argv:
        from rising_game_bots import run_worker
        run_worker(sys.argv[sys.argv.index("--tournament-bot-worker") + 1])
    elif "--smoke-room" in sys.argv:
        from rising_room import smoke_test
        smoke_test()
    elif "--smoke-service" in sys.argv:
        from rising_service import smoke_test
        smoke_test()
    elif "--room-service" in sys.argv:
        from rising_service import main as service_main
        sys.argv.remove("--room-service")
        service_main()
    elif "--apply-loader-update" in sys.argv:
        i = sys.argv.index("--apply-loader-update")
        core.apply_loader_update(int(sys.argv[i + 1]), Path(sys.argv[i + 2]), Path(sys.argv[i + 3]))
    elif "--finish-loader-update" in sys.argv:
        i = sys.argv.index("--finish-loader-update")
        core.finish_loader_update(int(sys.argv[i + 1]), Path(sys.argv[i + 2]))
        main()
    elif "--smoke-shared-challonge" in sys.argv:
        from challonge_shared import SharedChallongeClient
        try:
            snapshot=SharedChallongeClient().request('https://challonge.com/es/trunksprofecyI')['tournament']
            assert len(snapshot['participants'])==10
            assert any(m['p1'] and m['p2'] and m['name1']!='Por decidir' for m in snapshot['matches'])
        except Exception:raise SystemExit(1)
    elif "--smoke-runtime" in sys.argv:
        exe = Path(sys.argv[sys.argv.index("--smoke-runtime") + 1]) / "Tenkaichi3Decomp.exe"
        image = core.validate_payload(core.PAYLOAD, exe)
        image.build(0x60000000, image.pe.preferred_base)
    else:
        main()
