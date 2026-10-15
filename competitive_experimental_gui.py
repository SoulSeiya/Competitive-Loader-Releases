"""Playable graphical Loader using the reviewed 0.1.35.2 online profile."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog

import competitive_loader as core
from competitive_gui import CompetitiveApp

core.CONFIG = core.HERE / "competitive_experimental.json"


class ExperimentalApp(CompetitiveApp):
    def __init__(self, root):
        super().__init__(root)
        root.title("Competitive Loader — Experimental 0.1.35.2")
        self.play_button.configure(text="JUGAR COMPETITIVE · EXPERIMENTAL")
        replacements = {
            "ONLINE  ·  T abre el chat  ·  START no pausa el combate": "ONLINE  ·  Tab abre el chat  ·  El menú no detiene la pelea",
            "Un clic comprueba la versión, protege la memory\ny aplica el parche competitivo.": "Decomp 0.1.35.2 fijado para esta prueba.\nProtege la memory y aplica las reglas competitivas.",
            "Actualización segura": "Versión fijada",
            "Te avisa al abrir y tú decides cuándo instalar": "Esta prueba utiliza decomp 0.1.35.2",
        }
        def update_labels(widget):
            if isinstance(widget, tk.Label) and widget.cget("text") in replacements:
                widget.configure(text=replacements[widget.cget("text")])
            for child in widget.winfo_children():
                update_labels(child)
        update_labels(root)
        self._append("Perfil nuevo: combate competitivo + red, chat y pausa oficiales.\n"
                     "Chat: Tab. Tiempos online: 180, 240, 360, 480 segundos y sin límite.\n"
                     "Sin marcador ni bloqueo de ventana propios.\n"
                     "Solo decomp 0.1.35.2 revisado. Mantén el Loader abierto durante el online.\n"
                     "Ambos jugadores deben usar este mismo perfil y la misma memory.\n")

    def _check_versions(self):
        # A new upstream release must be reviewed before this experimental profile uses it.
        self.events.put(("version_status", {
            "decomp_remote": "0.1.35.2 · versión fijada",
            "decomp_installed": "0.1.35.2 · se verifica al jugar",
            "loader_remote": "Perfil experimental local",
        }, []))

    def _refresh_install_state(self):
        super()._refresh_install_state()
        self.future_update_button.configure(state="disabled", text="ISO fija para esta prueba")
        self.update_button.configure(state="disabled", text="PERFIL EXPERIMENTAL FIJADO")

    def play(self):
        runtime = self._runtime()
        if not (runtime / "Tenkaichi3Decomp.exe").is_file():
            folder = filedialog.askdirectory(parent=self.root, title="Elige la instalación competitiva preparada con decomp 0.1.35.2")
            if not folder:
                return
            runtime = Path(folder)

        def launch():
            exe = runtime / "Tenkaichi3Decomp.exe"
            core.use_official_online_profile(exe, audio_fix=True, competitive_times=True)
            if not (runtime / "gamedata" / ".competitive-v8.4.1.json").is_file():
                raise core.LoaderError("Esta carpeta no tiene los datos competitivos preparados.")
            image = core.validate_payload(core.PAYLOAD, exe)
            image.build(0x60000000, image.pe.preferred_base)
            core.save_config({"runtime": str(runtime.resolve()), "release_tag": "0.1.35.2"})
            return core.launch_patched(exe, image, convert_intro=True)

        self._run("Iniciando Competitive con el perfil nuevo",
                  "Competitive iniciado con el perfil experimental de 0.1.35.2.", launch)


def main():
    root = tk.Tk()
    app = ExperimentalApp(root)
    if "--smoke-test" in sys.argv:
        root.withdraw()
        root.update()
        root.destroy()
    else:
        root.mainloop()


if __name__ == "__main__":
    main()
