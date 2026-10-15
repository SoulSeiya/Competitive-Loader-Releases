"""User-started temporary room coordinator and Cloudflare Quick Tunnel.

Only the two child processes created by this window are stopped on close.
The tunnel helper is provided separately to the host, never auto-downloaded.
"""
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox

import competitive_loader as core


class TestHost:
    def __init__(self, root):
        self.root=root
        self.children=[]
        self.files=[]
        self.url=""
        self.started=0
        self.timer=None
        self.logdir=core.HERE/"logs"/"temporary-room-host"
        self.logdir.mkdir(parents=True,exist_ok=True)
        root.title("BTC — servidor temporal para amigos")
        root.geometry("760x300")
        tk.Label(root,text="Prueba de sala por Internet",font=("Segoe UI",16,"bold")).pack(pady=12)
        tk.Label(root,text="Mantén esta ventana y tu PC encendidos. Cerrar detiene el servicio.\nLa dirección cambia al reiniciarlo. No transmite el juego ni habilita espectadores.").pack()
        self.status=tk.StringVar(value="Pulsa Iniciar para publicar únicamente el servicio de salas BTC.")
        tk.Label(root,textvariable=self.status,wraplength=720).pack(pady=10)
        self.address=tk.StringVar()
        tk.Entry(root,textvariable=self.address,state="readonly",width=95).pack(padx=10)
        bar=tk.Frame(root);bar.pack(pady=16)
        self.start_button=tk.Button(bar,text="Iniciar servidor de prueba",command=self.start)
        self.start_button.pack(side="left",padx=5)
        self.copy_button=tk.Button(bar,text="Copiar dirección",state="disabled",command=lambda: self.copy())
        self.copy_button.pack(side="left",padx=5)
        tk.Button(bar,text="Detener servidor",command=self.stop).pack(side="left",padx=5)
        root.protocol("WM_DELETE_WINDOW",self.close)

    def start(self):
        if self.children:return
        helper=core.HERE/"cloudflared.exe"
        if not helper.is_file():
            messagebox.showerror("BTC","Falta cloudflared.exe. Usa el paquete exclusivo del anfitrión.",parent=self.root)
            return
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        commands=[([sys.executable,"--room-service","--bind","127.0.0.1","--port",str(port)] if getattr(sys,"frozen",False)
                  else [sys.executable,str(Path(__file__).with_name("rising_service.py")),"--bind","127.0.0.1","--port",str(port)]),
                  [str(helper),"tunnel","--no-autoupdate","--url",f"http://127.0.0.1:{port}"]]
        self.started=time.monotonic()
        try:
            for name,command in zip(("service","tunnel"),commands):
                stream=open(self.logdir/(name+".log"),"wb")
                self.files.append(stream)
                self.children.append(subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)))
        except OSError as exc:
            self.stop();messagebox.showerror("BTC",str(exc),parent=self.root);return
        self.start_button.configure(state="disabled")
        self.status.set("Conectando el túnel de prueba…")
        self.timer=self.root.after(1000,self.check)

    def check(self):
        self.timer=None
        if not self.children:return
        if any(p.poll() is not None for p in self.children):
            self.stop()
            self.status.set(f"El servicio se detuvo. Consulta los registros en {self.logdir}.")
            return
        text=(self.logdir/"tunnel.log").read_text(encoding="utf-8",errors="replace")
        urls=re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com",text)
        # Do not announce readiness just because Cloudflare allocated a hostname.
        if urls and "Registered tunnel connection" in text and not self.url:
            self.url=urls[0]
            self.address.set(self.url)
            config=core.load_config();config["btc_room_service_url"]=self.url;core.save_config(config)
            self.copy_button.configure(state="normal")
            self.status.set("Servicio activo. Comparte esta dirección. En tu Loader ya está guardada: inicia el juego después de este paso.")
        elif not self.url and time.monotonic()-self.started>90:
            self.status.set("El túnel tarda en conectar. Revisa tunnel.log o detén el servidor y vuelve a intentarlo.")
        self.timer=self.root.after(1000,self.check)

    def copy(self):
        if self.url:self.root.clipboard_clear();self.root.clipboard_append(self.url)

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer);self.timer=None
        for process in reversed(self.children):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=4)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=4)
        self.children=[]
        for stream in self.files:stream.close()
        self.files=[];self.url="";self.address.set("")
        self.start_button.configure(state="normal");self.copy_button.configure(state="disabled")
        self.status.set("Servidor detenido. Las salas anteriores se han cerrado.")

    def close(self):
        self.stop();self.root.destroy()


def main():
    root=tk.Tk();app=TestHost(root)
    if "--smoke-room-test-host" in sys.argv:
        root.withdraw();root.update();app.close()
    else:
        root.mainloop()
