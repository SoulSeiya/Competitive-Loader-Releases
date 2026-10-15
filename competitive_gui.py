#!/usr/bin/env python3
"""Friendly Windows front end for Competitive Loader."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import competitive_loader as core


class QueueWriter:
    def __init__(self, events: queue.Queue):
        self.events = events

    def write(self, value: str):
        if value:
            self.events.put(("log", value))
        return len(value)

    def flush(self):
        return None


class CompetitiveApp:
    BG = "#030711"
    SIDEBAR = "#07111f"
    SURFACE = "#0b1626"
    PANEL = "#0f1d30"
    PANEL_DARK = "#07101d"
    BORDER = "#203752"
    TEXT = "#f8fafc"
    MUTED = "#8fa6bd"
    CYAN = "#38bdf8"
    GREEN = "#2dd4a7"
    ORANGE = "#ff6b00"
    ORANGE_HOVER = "#ff8126"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.pending_update: dict | None = None
        self.checking_versions = False
        root.title(core.APP_NAME)
        root.geometry("1080x850")
        root.minsize(980, 800)
        root.configure(bg=self.BG)
        try:
            self._icon_source = tk.PhotoImage(file=str(core.APP_ICON))
            factor = max(1, self._icon_source.width() // 122)
            self.icon = self._icon_source.subsample(factor, factor)
            root.iconphoto(True, self.icon)
        except tk.TclError:
            self.icon = None

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=self.PANEL_DARK, background=self.ORANGE,
                        bordercolor=self.PANEL_DARK, lightcolor=self.ORANGE, darkcolor=self.ORANGE)

        app = tk.Frame(root, bg=self.BG)
        app.pack(fill="both", expand=True)

        sidebar = tk.Frame(app, bg=self.SIDEBAR, width=252,
                           highlightthickness=1, highlightbackground="#14263b")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=self.SIDEBAR)
        brand.pack(fill="x", padx=24, pady=(28, 0))
        if self.icon is not None:
            tk.Label(brand, image=self.icon, bg=self.SIDEBAR, width=126, height=126).pack(anchor="center")
        tk.Label(brand, text="UNIVERSO TENKAICHI", fg=self.TEXT, bg=self.SIDEBAR,
                 font=("Segoe UI Semibold", 13)).pack(pady=(12, 2))
        tk.Label(brand, text="COMPETITIVE LOADER", fg=self.CYAN, bg=self.SIDEBAR,
                 font=("Segoe UI Semibold", 9)).pack()
        tk.Label(brand, text=f"VERSION {core.APP_VERSION_TEXT}", fg="#58738f", bg=self.SIDEBAR,
                 font=("Segoe UI", 8)).pack(pady=(3, 0))

        sidebar_line = tk.Frame(sidebar, bg="#17314a", height=1)
        sidebar_line.pack(fill="x", padx=24, pady=(26, 0))

        feature_list = tk.Frame(sidebar, bg=self.SIDEBAR)
        feature_list.pack(fill="x", padx=24, pady=20)
        for symbol, title, detail in (
            ("●", "Parche en memoria", "El ejecutable original permanece intacto"),
            ("●", "Actualización segura", "Te avisa al abrir y tú decides cuándo instalar"),
            ("●", "Memory sincronizada", "Balance compartido mediante SHA-256"),
            ("●", "Chat online", "Pulsa T · START queda bloqueado"),
        ):
            item = tk.Frame(feature_list, bg=self.SIDEBAR)
            item.pack(fill="x", pady=7)
            tk.Label(item, text=symbol, fg=self.GREEN, bg=self.SIDEBAR,
                     font=("Segoe UI", 7)).pack(side="left", anchor="n", pady=(3, 0))
            copy = tk.Frame(item, bg=self.SIDEBAR)
            copy.pack(side="left", fill="x", expand=True, padx=(9, 0))
            tk.Label(copy, text=title, fg=self.TEXT, bg=self.SIDEBAR,
                     font=("Segoe UI Semibold", 9)).pack(anchor="w")
            tk.Label(copy, text=detail, fg="#607b96", bg=self.SIDEBAR,
                     font=("Segoe UI", 7), wraplength=170, justify="left").pack(anchor="w", pady=(1, 0))

        credits = tk.Frame(sidebar, bg="#0b1a2b", highlightthickness=1,
                           highlightbackground="#1d3852")
        credits.pack(side="bottom", fill="x", padx=20, pady=20)
        tk.Label(credits, text="CRÉDITOS", fg=self.CYAN, bg="#0b1a2b",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=15, pady=(13, 9))
        tk.Label(credits, text="DECOMP", fg="#647f9a", bg="#0b1a2b",
                 font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=15)
        tk.Label(credits, text="z3xox", fg=self.TEXT, bg="#0b1a2b",
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=15, pady=(1, 9))
        tk.Label(credits, text="COMPETITIVE LOADER", fg="#647f9a", bg="#0b1a2b",
                 font=("Segoe UI Semibold", 7)).pack(anchor="w", padx=15)
        tk.Label(credits, text="Rising", fg=self.TEXT, bg="#0b1a2b",
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=15, pady=(1, 13))

        main = tk.Frame(app, bg=self.BG)
        main.pack(side="left", fill="both", expand=True, padx=24, pady=20)

        topbar = tk.Frame(main, bg=self.BG)
        topbar.pack(fill="x", pady=(0, 14))
        title_area = tk.Frame(topbar, bg=self.BG)
        title_area.pack(side="left")
        tk.Label(title_area, text="CENTRO DE CONTROL", fg=self.TEXT, bg=self.BG,
                 font=("Segoe UI Semibold", 19)).pack(anchor="w")
        tk.Label(title_area, text="Instala, sincroniza y juega Competitive Edition",
                 fg=self.MUTED, bg=self.BG, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))
        self.version_status_label = tk.Label(
            topbar, text="⟳  CONSULTANDO GITHUB", fg=self.GREEN, bg="#0b2b27",
            font=("Segoe UI Semibold", 8), padx=10, pady=6,
        )
        self.version_status_label.pack(side="right", anchor="n", pady=5)

        hero = tk.Frame(main, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        hero.pack(fill="x")
        hero_left = tk.Frame(hero, bg=self.SURFACE)
        hero_left.pack(side="left", fill="both", expand=True, padx=(24, 10), pady=20)
        tk.Label(hero_left, text="LISTO PARA COMBATIR", fg=self.ORANGE, bg=self.SURFACE,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tk.Label(hero_left, text="Competitive Edition", fg=self.TEXT, bg=self.SURFACE,
                 font=("Segoe UI Semibold", 23)).pack(anchor="w", pady=(2, 3))
        tk.Label(hero_left, text="Un clic comprueba la versión, protege la memory\ny aplica el parche competitivo.",
                 fg=self.MUTED, bg=self.SURFACE, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 14))
        self.play_button = self._button(
            hero_left, "▶   JUGAR COMPETITIVE", self.play, self.ORANGE, self.ORANGE_HOVER,
            font=("Segoe UI Semibold", 12), pady=12,
        )
        self.play_button.pack(fill="x")

        hero_art = tk.Frame(hero, bg=self.SURFACE, width=350)
        hero_art.pack(side="right", fill="y", padx=(5, 22), pady=15)
        hero_art.pack_propagate(False)
        try:
            self.header_logo = tk.PhotoImage(file=str(core.APP_HEADER_LOGO))
            tk.Label(hero_art, image=self.header_logo, bg=self.SURFACE, borderwidth=0,
                     highlightthickness=0).pack(expand=True)
        except tk.TclError:
            self.header_logo = None
            tk.Label(hero_art, text="COMPETITIVE\nEDITION", fg=self.TEXT, bg=self.SURFACE,
                     font=("Segoe UI Semibold", 18), justify="center").pack(expand=True)

        versions = tk.Frame(main, bg=self.BG)
        versions.pack(fill="x", pady=(14, 0))

        decomp_card = tk.Frame(versions, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        decomp_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(decomp_card, text="TENKAICHI3DECOMP", fg=self.CYAN, bg=self.PANEL,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=15, pady=(11, 6))
        decomp_versions = tk.Frame(decomp_card, bg=self.PANEL)
        decomp_versions.pack(fill="x", padx=15, pady=(0, 12))
        tk.Label(decomp_versions, text="EN GITHUB", fg="#647f9a", bg=self.PANEL,
                 font=("Segoe UI Semibold", 7)).grid(row=0, column=0, sticky="w")
        tk.Label(decomp_versions, text="INSTALADA", fg="#647f9a", bg=self.PANEL,
                 font=("Segoe UI Semibold", 7)).grid(row=0, column=1, sticky="w", padx=(40, 0))
        self.decomp_remote_label = tk.Label(decomp_versions, text="Consultando...", fg=self.TEXT, bg=self.PANEL,
                                            font=("Segoe UI Semibold", 11))
        self.decomp_remote_label.grid(row=1, column=0, sticky="w")
        self.decomp_installed_label = tk.Label(decomp_versions, text="Comprobando...", fg=self.TEXT, bg=self.PANEL,
                                               font=("Segoe UI Semibold", 11))
        self.decomp_installed_label.grid(row=1, column=1, sticky="w", padx=(40, 0))

        loader_card = tk.Frame(versions, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        loader_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(loader_card, text="COMPETITIVE LOADER", fg=self.CYAN, bg=self.PANEL,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=15, pady=(11, 6))
        loader_versions = tk.Frame(loader_card, bg=self.PANEL)
        loader_versions.pack(fill="x", padx=15)
        tk.Label(loader_versions, text="EN GITHUB", fg="#647f9a", bg=self.PANEL,
                 font=("Segoe UI Semibold", 7)).grid(row=0, column=0, sticky="w")
        tk.Label(loader_versions, text="INSTALADA", fg="#647f9a", bg=self.PANEL,
                 font=("Segoe UI Semibold", 7)).grid(row=0, column=1, sticky="w", padx=(40, 0))
        self.loader_remote_label = tk.Label(loader_versions, text="Consultando...", fg=self.TEXT, bg=self.PANEL,
                                            font=("Segoe UI Semibold", 11))
        self.loader_remote_label.grid(row=1, column=0, sticky="w")
        self.loader_installed_label = tk.Label(loader_versions, text=f"v{core.APP_VERSION_TEXT}", fg=self.TEXT,
                                               bg=self.PANEL, font=("Segoe UI Semibold", 11))
        self.loader_installed_label.grid(row=1, column=1, sticky="w", padx=(40, 0))
        self.update_button = self._button(
            loader_card, "COMPROBANDO ACTUALIZACIONES", self.install_app_update,
            "#0b2b27", "#10443d", font=("Segoe UI Semibold", 8), pady=6,
        )
        self.update_button.pack(fill="x", padx=15, pady=(8, 12))
        self.update_button.configure(state="disabled", disabledforeground=self.GREEN)
        self.check_updates_button = self._button(
            loader_card, "BUSCAR ACTUALIZACIONES", self._check_versions,
            self.PANEL_DARK, "#172a42", font=("Segoe UI Semibold", 8), pady=5,
        )
        self.check_updates_button.pack(fill="x", padx=15, pady=(0, 10))

        actions = tk.Frame(main, bg=self.BG)
        actions.pack(fill="x", pady=(14, 0))
        row = tk.Frame(actions, bg=self.BG)
        row.pack(fill="x")
        memory_card = tk.Frame(row, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        memory_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(memory_card, text="MEMORY COMPETITIVA", fg=self.CYAN, bg=self.PANEL,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=14, pady=(11, 1))
        self.import_button = self._button(
            memory_card, "Cambiar manualmente", self.import_card, self.PANEL, "#172a42",
            font=("Segoe UI Semibold", 10), pady=8,
        )
        self.import_button.pack(fill="x", padx=7, pady=(0, 7))

        future_card = tk.Frame(row, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        future_card.pack(side="left", fill="both", expand=True, padx=6)
        tk.Label(future_card, text="NUEVA INSTALACIÓN", fg=self.CYAN, bg=self.PANEL,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=14, pady=(11, 1))
        self.future_update_button = self._button(
            future_card, "Instalar ISO + memory", self.install_iso_and_memory, self.PANEL, "#172a42",
            font=("Segoe UI Semibold", 10), pady=8,
        )
        self.future_update_button.pack(fill="x", padx=7, pady=(0, 7))

        folder_card = tk.Frame(row, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        folder_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(folder_card, text="ARCHIVOS LOCALES", fg=self.CYAN, bg=self.PANEL,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=14, pady=(11, 1))
        self.folder_button = self._button(
            folder_card, "Abrir instalación", self.open_runtime, self.PANEL, "#172a42",
            font=("Segoe UI Semibold", 10), pady=8,
        )
        self.folder_button.pack(fill="x", padx=7, pady=(0, 7))

        tk.Label(actions, text="ONLINE  ·  T abre el chat  ·  START no pausa el combate",
                 fg="#66829d", bg=self.BG, font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(7, 0))

        state_box = tk.Frame(main, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        state_box.pack(fill="both", expand=True, pady=(12, 0))
        top = tk.Frame(state_box, bg=self.PANEL)
        top.pack(fill="x", padx=15, pady=(11, 7))
        tk.Label(top, text="REGISTRO DEL SISTEMA", fg=self.CYAN, bg=self.PANEL,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.state_label = tk.Label(top, text="Listo", fg=self.TEXT, bg=self.PANEL,
                                    font=("Segoe UI Semibold", 10))
        self.state_label.pack(side="right")
        self.progress = ttk.Progressbar(state_box, mode="indeterminate")
        self.progress.pack(fill="x", padx=15, pady=(0, 8))
        self.log = tk.Text(state_box, bg=self.PANEL_DARK, fg="#cfe3fa", insertbackground=self.TEXT,
                           relief="flat", wrap="word", height=7, padx=12, pady=10,
                           font=("Cascadia Mono", 8))
        self.log.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.log.configure(state="disabled")

        self._write_status()
        self._refresh_install_state()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.root.after(100, self._poll)
        self.root.after(700, self._check_versions)

    def _button(self, parent, text, command, color, hover, **options):
        button = tk.Button(
            parent, text=text, command=command, bg=color, fg="white",
            activebackground=hover, activeforeground="white", relief="flat", bd=0,
            cursor="hand2", font=options.pop("font", ("Segoe UI Semibold", 11)),
            pady=options.pop("pady", 12), disabledforeground="#73879d", **options,
        )
        button.bind("<Enter>", lambda _event: button.configure(bg=hover) if button["state"] == "normal" else None)
        button.bind("<Leave>", lambda _event: button.configure(bg=color) if button["state"] == "normal" else None)
        return button

    def _runtime(self) -> Path:
        config = core.load_config()
        return Path(config.get("runtime", core.DEFAULT_RUNTIME))

    def _write_status(self):
        runtime = self._runtime()
        if (runtime / "Tenkaichi3Decomp.exe").is_file():
            self._append(f"Instalación preparada: {runtime}\n")
            self._append("Jugar Competitive comprobará la última versión antes de iniciar.\n")
            fingerprint = core.online_memory_fingerprint(runtime)
            if fingerprint:
                self._append(f"Memory online: {fingerprint}\n")
            else:
                self._append("Memory online: no instalada. Usa Importar memory competitiva.\n")
        else:
            self._append("Primer uso: pulsa Jugar y selecciona únicamente tu ISO competitiva.\n")
            self._append("La última versión oficial para Windows se descargará automáticamente.\n")

    def _refresh_install_state(self):
        installed = (self._runtime() / "Tenkaichi3Decomp.exe").is_file()
        self.import_button.configure(state="normal" if installed and not self.busy else "disabled")
        self.future_update_button.configure(state="normal" if installed and not self.busy else "disabled")
        self.update_button.configure(state="normal" if self.pending_update is not None and not self.busy else "disabled")

    def _append(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, value: bool, label: str = "Listo"):
        self.busy = value
        state = "disabled" if value else "normal"
        for button in (self.play_button, self.import_button, self.future_update_button, self.folder_button):
            button.configure(state=state)
        self.update_button.configure(
            state="normal" if not value and self.pending_update is not None else "disabled"
        )
        self.state_label.configure(text=label)
        if value:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _run(self, label: str, success: str, action):
        if self.busy:
            return
        self._append(f"\n— {label} —\n")
        self._set_busy(True, label)

        def worker():
            writer = QueueWriter(self.events)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    result = action()
                self.events.put(("done", success, result))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "log":
                    self._append(event[1])
                elif event[0] == "done":
                    self._set_busy(False)
                    self._refresh_install_state()
                    self._append(f"{event[1]}\n")
                    messagebox.showinfo(core.APP_NAME, event[1], parent=self.root)
                elif event[0] == "error":
                    self._set_busy(False, "Se produjo un problema")
                    self._refresh_install_state()
                    self._append(f"ERROR: {event[1]}\n")
                    messagebox.showerror(core.APP_NAME, event[1], parent=self.root)
                elif event[0] == "version_status":
                    self.checking_versions = False
                    self.check_updates_button.configure(text="BUSCAR ACTUALIZACIONES", state="normal")
                    versions, errors = event[1], event[2]
                    self.decomp_remote_label.configure(text=versions["decomp_remote"])
                    self.decomp_installed_label.configure(text=versions["decomp_installed"])
                    self.loader_remote_label.configure(text=versions["loader_remote"])
                    self.loader_installed_label.configure(text=f"v{core.APP_VERSION_TEXT}")
                    self.version_status_label.configure(
                        text="✓  VERSIONES COMPROBADAS" if not errors else "⚠  COMPROBACIÓN PARCIAL",
                        fg=self.GREEN if not errors else "#ffd78a",
                        bg="#0b2b27" if not errors else "#4b3511",
                    )
                    for error in errors:
                        self._append(f"\n[VERSIONES] {error}\n")
                elif event[0] == "app_update":
                    self.pending_update = event[1]
                    if self.pending_update is None:
                        self.update_button.configure(
                            text="✓  LOADER ACTUALIZADO", bg="#0b2b27", activebackground="#10443d",
                            state="disabled", disabledforeground=self.GREEN,
                        )
                        self.update_button.bind("<Enter>", lambda _event: None)
                        self.update_button.bind("<Leave>", lambda _event: None)
                    else:
                        tag = self.pending_update["tag"]
                        self.update_button.configure(
                            text=f"⬇  ACTUALIZAR Y REINICIAR A {tag}", bg=self.ORANGE,
                            activebackground=self.ORANGE_HOVER, state="normal",
                        )
                        self.update_button.bind(
                            "<Enter>", lambda _event: self.update_button.configure(bg=self.ORANGE_HOVER)
                            if self.update_button["state"] == "normal" else None,
                        )
                        self.update_button.bind(
                            "<Leave>", lambda _event: self.update_button.configure(bg=self.ORANGE)
                            if self.update_button["state"] == "normal" else None,
                        )
                        self._append(
                            f"\n[APP] Nueva versión disponible: {tag}. "
                            "Pulsa Actualizar y reiniciar para reemplazar solo el ejecutable.\n"
                        )
                elif event[0] == "app_update_error":
                    self._append(f"\n[APP] No se pudo comprobar la app: {event[1]}\n")
                    self.update_button.configure(
                        text="⚠  SIN CONEXIÓN", bg="#4b3511", activebackground="#4b3511",
                        state="disabled", disabledforeground="#ffd78a",
                    )
                elif event[0] == "app_update_unavailable":
                    self.pending_update = None
                    self.update_button.configure(
                        text="⚠  ACTUALIZACIÓN NO DISPONIBLE", bg="#4b3511",
                        activebackground="#4b3511", state="disabled", disabledforeground="#ffd78a",
                    )
                elif event[0] == "app_update_ready":
                    self._append(
                        "[APP] Descarga verificada. Cerrando este Loader, reemplazando el ejecutable "
                        "y abriendo la versión nueva...\n"
                    )
                    self.root.quit()
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _check_versions(self):
        if self.checking_versions:
            return
        self.checking_versions = True
        self.check_updates_button.configure(text="COMPROBANDO...", state="disabled")
        def worker():
            config = core.load_config()
            runtime = self._runtime()
            versions = {
                "decomp_remote": "No disponible",
                "decomp_installed": (
                    str(config.get("release_tag") or "Versión local")
                    if (runtime / "Tenkaichi3Decomp.exe").is_file() else "No instalado"
                ),
                "loader_remote": "No disponible",
            }
            errors = []
            pending = None
            loader_checked = False
            try:
                versions["decomp_remote"] = core.latest_release_info()["tag"] or "Sin etiqueta"
            except core.LoaderError as exc:
                errors.append(f"Decomp en GitHub: {exc}")
            try:
                loader_info = core.latest_loader_release_info()
                loader_checked = True
                versions["loader_remote"] = loader_info["tag"]
                if loader_info["version"] > core.APP_VERSION:
                    if loader_info["download_url"]:
                        pending = loader_info
                    else:
                        errors.append(
                            f"Loader {loader_info['tag']}: falta {core.LOADER_ASSET_NAME}."
                        )
            except core.LoaderError as exc:
                errors.append(f"Competitive Loader en GitHub: {exc}")
            self.events.put(("version_status", versions, errors))
            self.events.put(("app_update", pending) if loader_checked else ("app_update_unavailable",))

        threading.Thread(target=worker, daemon=True).start()

    def install_app_update(self):
        release = self.pending_update
        if release is None:
            return
        if self.busy:
            return
        if core.online_memory_guard_active() or core._is_game_running():
            messagebox.showwarning(
                core.APP_NAME,
                "Cierra el juego antes de actualizar el Loader.\n\n"
                "Tu ISO instalada, la memory y la configuración se conservarán.",
                parent=self.root,
            )
            return

        self._append(f"\n— Actualizando Competitive Loader a {release['tag']} —\n")
        if release.get("notes"):
            self._append("Mejoras de esta actualización:\n" + release["notes"] + "\n")
        self._set_busy(True, "Descargando actualización")

        def worker():
            writer = QueueWriter(self.events)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    staged = core.stage_loader_update(release)
                    core.schedule_loader_update(staged)
                self.events.put(("app_update_ready", release["tag"]))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def play(self):
        runtime = self._runtime()
        exe = runtime / "Tenkaichi3Decomp.exe"
        marker = runtime / "gamedata" / ".competitive-v8.4.1.json"
        if exe.is_file() and marker.is_file():
            def launch():
                try:
                    core.ensure_latest_release(runtime)
                except core.LoaderError as exc:
                    print(f"[AVISO] {exc}")
                    print("[AUTO] Se continuará con la versión instalada.")
                image = core.validate_payload(core.PAYLOAD, exe)
                image.build(0x60000000, image.pe.preferred_base)
                return core.launch_patched(exe, image)

            self._run("Verificando e iniciando el juego",
                      "El juego se inició con el parche competitivo.", launch)
            return

        iso = filedialog.askopenfilename(
            parent=self.root, title="Elige DBZ Competitive Edition v8.4.1",
            filetypes=[("Imagen ISO", "*.iso"), ("Todos", "*.*")],
        )
        if not iso:
            return

        card = None
        if messagebox.askyesno(
            core.APP_NAME,
            "¿Quieres importar ahora la memory competitiva?\n\n"
            "Se usará tanto offline como online. Los dos jugadores deben instalar "
            "exactamente la misma memory para evitar desincronizaciones.",
            parent=self.root,
        ):
            card = filedialog.askopenfilename(
                parent=self.root, title="Elige la tarjeta de memoria de PCSX2 (opcional)",
                filetypes=[("Tarjeta de PS2", "*.ps2"), ("Todos", "*.*")],
            ) or None

        def prepare_and_launch():
            prepared = core.prepare_from_github(Path(iso), runtime)
            if card:
                print("[MEMORY] Importando la partida elegida para el primer inicio...")
                core.import_ps2_card(Path(card), runtime)
            image = core.validate_payload(core.PAYLOAD, prepared)
            return core.launch_patched(prepared, image)

        self._run(
            "Descargando y preparando Competitive Edition",
            "Instalación terminada, memory opcional aplicada y juego iniciado."
            if card else "Instalación terminada y juego iniciado.",
            prepare_and_launch,
        )

    def import_card(self):
        card = filedialog.askopenfilename(
            parent=self.root, title="Elige la tarjeta de memoria de PCSX2",
            filetypes=[("Tarjeta de PS2", "*.ps2"), ("Todos", "*.*")],
        )
        if not card:
            return
        runtime = self._runtime()
        self._run(
            "Importando memory de PCSX2",
            "La memory competitiva se importó para offline y online. Compara el SHA-256 con tu rival.",
            lambda: core.import_ps2_card(Path(card), runtime),
        )

    def install_iso_and_memory(self):
        runtime = self._runtime()
        if core.online_memory_guard_active() or core._is_game_running():
            messagebox.showwarning(
                core.APP_NAME,
                "Cierra el juego antes de instalar una ISO nueva.\n\n"
                "El Loader debe poder cambiar los datos y la memory de forma segura.",
                parent=self.root,
            )
            return

        iso = filedialog.askopenfilename(
            parent=self.root, title="Elige la nueva ISO de DBZ Competitive Edition",
            filetypes=[("Imagen ISO", "*.iso"), ("Todos", "*.*")],
        )
        if not iso:
            return

        card = None
        if messagebox.askyesno(
            core.APP_NAME,
            "¿Quieres instalar también una memory competitiva nueva?\n\n"
            "Si eliges No, se conservará la memory que ya tienes instalada.",
            parent=self.root,
        ):
            card = filedialog.askopenfilename(
                parent=self.root, title="Elige la nueva memory de PCSX2",
                filetypes=[("Tarjeta de PS2", "*.ps2"), ("Todos", "*.*")],
            )
            if not card:
                return

        memory_text = " y se importará la memory seleccionada" if card else " y se conservará la memory actual"
        if not messagebox.askyesno(
            core.APP_NAME,
            "Se validará completamente la ISO antes de reemplazar los datos actuales.\n\n"
            f"El decomp y sus ajustes se conservarán{memory_text}.\n\n¿Continuar?",
            parent=self.root,
        ):
            return

        def replace_installation():
            core.replace_competitive_iso(Path(iso), runtime)
            if card:
                print("[MEMORY] Instalando la memory elegida...")
                core.import_ps2_card(Path(card), runtime)

        success = (
            "La ISO y la memory nuevas quedaron instaladas. Ya puedes pulsar Jugar Competitive."
            if card else
            "La ISO nueva quedó instalada y se conservó la memory actual. Ya puedes pulsar Jugar Competitive."
        )
        self._run("Instalando ISO + memory", success, replace_installation)

    def open_runtime(self):
        runtime = self._runtime()
        runtime.mkdir(parents=True, exist_ok=True)
        os.startfile(runtime)

    def close_app(self):
        if core.online_memory_guard_active() and not messagebox.askyesno(
            core.APP_NAME,
            "La protección de la memory online está activa.\n\n"
            "Si cierras Competitive Loader durante la sesión, Tenkaichi3Decomp podría volver a vaciar "
            "net_session. ¿Cerrar de todos modos?",
            parent=self.root,
        ):
            return
        self.root.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    CompetitiveApp(root)
    root.mainloop()


if __name__ == "__main__":
    if "--apply-loader-update" in sys.argv:
        update_index = sys.argv.index("--apply-loader-update")
        core.apply_loader_update(
            int(sys.argv[update_index + 1]),
            Path(sys.argv[update_index + 2]),
            Path(sys.argv[update_index + 3]),
        )
    elif "--finish-loader-update" in sys.argv:
        finish_index = sys.argv.index("--finish-loader-update")
        core.finish_loader_update(
            int(sys.argv[finish_index + 1]), Path(sys.argv[finish_index + 2])
        )
        main()
    elif "--smoke-runtime" in sys.argv:
        runtime_arg = Path(sys.argv[sys.argv.index("--smoke-runtime") + 1])
        runtime_exe = runtime_arg / "Tenkaichi3Decomp.exe"
        runtime_image = core.validate_payload(core.PAYLOAD, runtime_exe)
        runtime_image.build(0x60000000, runtime_image.pe.preferred_base)
    elif "--smoke-test" in sys.argv:
        test_root = tk.Tk()
        test_root.withdraw()
        CompetitiveApp(test_root)
        test_root.update_idletasks()
        test_root.destroy()
    else:
        main()
