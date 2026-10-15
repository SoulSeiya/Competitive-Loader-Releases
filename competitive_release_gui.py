"""Public Competitive Loader: reviewed upstream updates and local diagnostics."""
import ctypes
import json
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import competitive_loader as core
from competitive_gui import CompetitiveApp
from session_diagnostics import SessionDiagnostics, make_logger
from rising_room_bridge import RoomBridge

core.RELEASE_PROFILE = True
LOGS = core.HERE / "logs"


class ReleaseApp(CompetitiveApp):
    def __init__(self, root):
        self.session = None
        self.room_bridge = RoomBridge(make_logger("competitive.room", LOGS / "rising-battle.log"))
        super().__init__(root)
        root.title(f"Competitive Loader {core.APP_VERSION_TEXT}")
        def refresh(widget):
            if isinstance(widget, tk.Label):
                old = widget.cget("text")
                if old == "ONLINE  ·  T abre el chat  ·  START no pausa el combate":
                    widget.configure(text="ONLINE  ·  Tab abre el chat  ·  180 / 240 / 360 / 480 segundos")
            for child in widget.winfo_children():
                refresh(child)
        refresh(root)
        tk.Button(root, text="Abrir registros locales y online", command=self.open_logs,
                  bg=self.PANEL, fg=self.TEXT).pack(side="bottom", fill="x")
        self._append("Perfil competitivo: intro y audio corregidos; chat y pausa oficiales.\n"
                     "Marcador online persistente entre peleas y revanchas.\n"
                     "Las actualizaciones del decomp se validan antes de instalarlas.\n"
                     "Ambos jugadores necesitan el mismo Loader, decomp y memory.\n")
        if "--smoke-test" not in sys.argv and "--tournament-test" not in sys.argv:
            root.after(600, self.show_version_notes)

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
        if exe.is_file() and marker.is_file():
            def launch():
                try:
                    core.ensure_latest_release(runtime)
                except core.LoaderError:
                    self.session.local.exception("UPSTREAM_UPDATE_REJECTED_OR_UNAVAILABLE; checking installed copy")
                    print("[AVISO] No se pudo instalar una actualización compatible; se comprobará la copia instalada.")
                image = core.validate_payload(core.PAYLOAD, exe)
                image.build(0x60000000, image.pe.preferred_base)
                self.room_bridge.runtime = runtime
                env = {"BTC_ROOM_BRIDGE": self.room_bridge.name}
                pid = self.session.launch(exe, image, env=env)
                return pid
            self._run("Comprobando actualizaciones e iniciando Competitive",
                      "Competitive iniciado. Mantén el Loader abierto mientras juegas.", launch)
            return

        iso = filedialog.askopenfilename(parent=self.root, title="Elige tu ISO Competitive Edition",
                                         filetypes=[("Imagen ISO", "*.iso")])
        if not iso:
            return
        card = None
        if messagebox.askyesno(core.APP_NAME, "¿Quieres importar una memory competitiva ahora?", parent=self.root):
            card = filedialog.askopenfilename(parent=self.root, title="Elige la memory PCSX2",
                                               filetypes=[("Memory PS2", "*.ps2")]) or None
        def install():
            prepared = core.prepare_from_github(Path(iso), runtime)
            if card:
                core.import_ps2_card(Path(card), runtime)
            image = core.validate_payload(core.PAYLOAD, prepared)
            image.build(0x60000000, image.pe.preferred_base)
            self.room_bridge.runtime = prepared.parent
            return self.session.launch(prepared, image, env={"BTC_ROOM_BRIDGE": self.room_bridge.name})
        self._run("Preparando la instalación competitiva", "Instalación lista y Competitive iniciado.", install)

    def close_app(self):
        if self.session and self.session.running:
            if not messagebox.askyesno(core.APP_NAME,
                    "El juego sigue abierto. Cerrar el Loader detendrá los registros y la protección de memory online. ¿Cerrar el Loader?",
                    parent=self.root):
                return
            self.session.finish("loader_closed_while_game_running")
        elif self.session:
            self.session.dispose()
        self.room_bridge.close()
        self.root.destroy()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    bootstrap = make_logger("competitive.bootstrap", LOGS / "loader.log")
    def report_exception(kind, value, tb):
        bootstrap.error("UNHANDLED_LOADER_EXCEPTION", exc_info=(kind, value, tb))
        messagebox.showerror(core.APP_NAME, f"{value}\n\nDetalle en {LOGS / 'loader.log'}")
    sys.excepthook = report_exception
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.report_callback_exception = report_exception
    app = ReleaseApp(root)
    if "--smoke-test" in sys.argv:
        root.withdraw()
        root.update()
        app.room_bridge.close()
        root.destroy()
    else:
        if "--tournament-test" in sys.argv: root.after(200, app.play)
        root.mainloop()


if __name__ == "__main__":
    if "--tournament-bot-worker" in sys.argv:
        from rising_game_bots import run_worker
        run_worker(sys.argv[sys.argv.index("--tournament-bot-worker") + 1])
    elif "--smoke-room" in sys.argv:
        from rising_room import smoke_test
        smoke_test()
    elif "--apply-loader-update" in sys.argv:
        i = sys.argv.index("--apply-loader-update")
        core.apply_loader_update(int(sys.argv[i + 1]), Path(sys.argv[i + 2]), Path(sys.argv[i + 3]))
    elif "--finish-loader-update" in sys.argv:
        i = sys.argv.index("--finish-loader-update")
        core.finish_loader_update(int(sys.argv[i + 1]), Path(sys.argv[i + 2]))
        main()
    elif "--smoke-runtime" in sys.argv:
        exe = Path(sys.argv[sys.argv.index("--smoke-runtime") + 1]) / "Tenkaichi3Decomp.exe"
        image = core.validate_payload(core.PAYLOAD, exe)
        image.build(0x60000000, image.pe.preferred_base)
    else:
        main()
