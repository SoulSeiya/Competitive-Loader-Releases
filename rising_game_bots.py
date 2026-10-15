"""Owned local game clients for tournament tests. No user game process is terminated."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

from rising_room import RoomClient, RoomError


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", W.DWORD),
                ("min_work", C.c_size_t), ("max_work", C.c_size_t), ("active", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64 * 6), ("process_mem", C.c_size_t),
                ("job_mem", C.c_size_t), ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class OwnedJob:
    def __init__(self, process):
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        k = self.kernel
        k.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
        k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
        k.CloseHandle.argtypes=[W.HANDLE]
        self.handle = k.CreateJobObjectW(None,None)
        limits=ExtendedLimits();limits.basic.flags=0x2000  # KILL_ON_JOB_CLOSE; only this worker and its descendants.
        if not self.handle or not k.SetInformationJobObject(self.handle,9,C.byref(limits),C.sizeof(limits)) or not k.AssignProcessToJobObject(self.handle,int(process._handle)):
            self.close()
            process.terminate();process.wait(timeout=5)
            raise OSError(C.get_last_error(), "No se pudo aislar el proceso del bot")

    def close(self):
        if getattr(self,"handle",None):
            self.kernel.CloseHandle(self.handle);self.handle=None


class GameBotProcesses:
    def __init__(self, server, bots, runtime, logger, local_spectator=False, human_pid=None):
        import competitive_loader as core
        self.server,self.bots,self.runtime,self.log=server,bots,Path(runtime),logger
        self.root=core.HERE/"logs"/"tournament-lab"/uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.children={}
        self.failed=set()
        self.local_spectator = local_spectator
        self.human_pid = human_pid
        self.human_minimized = False
        self.current_match = 0
        self.view_bot = 0
        self.stop=threading.Event()
        self.thread=threading.Thread(target=self._work,daemon=True)
        self.thread.start()

    def _start(self,user):
        uid=user["id"]; root=self.root/(str(uid)+"-"+uuid.uuid4().hex[:8]);root.mkdir()
        config=root/"worker.json"
        config.write_text(json.dumps(dict(source=str(self.runtime),root=str(root),port=self.server.port,bot_id=uid,
            local_view=self.local_spectator and uid==self.view_bot, background=self.local_spectator and uid!=self.view_bot)),encoding="utf-8")
        import competitive_loader as core
        command=[sys.executable]
        if not getattr(sys,"frozen",False):command.append(str(core.RESOURCE_ROOT/"competitive_release_gui.py"))
        command += ["--tournament-bot-worker",str(config)]
        env=dict(os.environ,BTC_BOT_SESSION_TOKEN=user["client"].token)
        with (root/"worker.log").open("wb") as output:
            p=subprocess.Popen(command,env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        job=OwnedJob(p)
        (root/"job-ready").touch()
        self.children[uid]=dict(process=p,job=job,root=root,last_active=time.monotonic(),placed=False)
        self.log.info("TOURNAMENT_GAME_BOT_STARTED member=%s worker_pid=%s",uid,p.pid)

    def _retire(self,uid):
        item=self.children.pop(uid)
        (item["root"]/"stop").touch()
        try:item["process"].wait(timeout=7)
        except subprocess.TimeoutExpired:pass
        finally:item["job"].close()
        self.log.info("TOURNAMENT_GAME_BOT_STOPPED member=%s",uid)

    def _work(self):
        try:
            while not self.stop.wait(.4):
                with self.server.room.lock:
                    t=self.server.room.tournament
                    active=set()
                    if t.status=="running" and t.current:
                        m=t.matches[t.current-1];active={m["p1"],m["p2"]}
                    current=t.current or 0
                    view_bot=m["p1"] if current and all(t.entrants[p].get("game_bot") for p in active) else 0
                if self.local_spectator and current != self.current_match:
                    self._restore_human()
                    # The winning bot gets a fresh background client for the human final.
                    for uid in list(self.children):self._retire(uid)
                    self.current_match,self.view_bot=current,view_bot
                with self.bots.lock:users=list(self.bots.users)
                for user in users:
                    uid=user["id"]
                    if uid in active and uid not in self.children and uid not in self.failed:
                        try:self._start(user)
                        except Exception:
                            self.failed.add(uid);self.log.exception("TOURNAMENT_GAME_BOT_START_FAILED member=%s",uid)
                            with self.server.room.lock:self.server.room._announce(f"Bot #{uid}: no pudo iniciar su juego. Consulta el registro o resuelve por WO.")
                    if uid in active and uid in self.children:self.children[uid]["last_active"]=time.monotonic()
                for uid,item in list(self.children.items()):
                    if item["process"].poll() is not None:
                        self.failed.add(uid);self._retire(uid)
                        with self.server.room.lock:self.server.room._announce(f"Bot #{uid}: se cerró su proceso. Consulta el registro antes de resolver el cruce.")
                    elif uid not in active and time.monotonic()-item["last_active"]>12:
                        self._retire(uid)
                if self.local_spectator:self._place_test_windows()
        except Exception:self.log.exception("TOURNAMENT_GAME_BOT_MANAGER_FAILED")
        finally:
            self._restore_human()
            for uid in list(self.children):self._retire(uid)

    @staticmethod
    def _windows(pid):
        user32=C.WinDLL("user32",use_last_error=True)
        user32.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
        user32.IsWindowVisible.argtypes=[W.HWND]
        callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM);found=[]
        @callback
        def visit(hwnd,_):
            owner=W.DWORD();user32.GetWindowThreadProcessId(hwnd,C.byref(owner))
            if owner.value==pid and user32.IsWindowVisible(hwnd):found.append(hwnd)
            return True
        user32.EnumWindows.argtypes=[callback,W.LPARAM]
        user32.EnumWindows(visit,0)
        return user32,found

    def _restore_human(self):
        if self.human_minimized and self.human_pid:
            user32,windows=self._windows(self.human_pid)
            user32.ShowWindow.argtypes=[W.HWND,C.c_int];user32.SetForegroundWindow.argtypes=[W.HWND]
            for hwnd in windows:user32.ShowWindow(hwnd,9);user32.SetForegroundWindow(hwnd)
        self.human_minimized=False

    def _place_test_windows(self):
        for uid,item in list(self.children.items()):
            if item["placed"]:continue
            info=item["root"]/"game-process.json"
            if not info.exists():continue
            pid=json.loads(info.read_text(encoding="utf-8"))["pid"]
            k=item["job"].kernel
            k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
            k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
            handle=k.OpenProcess(0x1000,False,pid);owned=W.BOOL()
            if not handle:continue
            valid=k.IsProcessInJob(handle,item["job"].handle,C.byref(owned)) and owned.value
            k.CloseHandle(handle)
            if not valid:continue
            user32,windows=self._windows(pid)
            if not windows:continue
            user32.SetWindowPos.argtypes=[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]
            user32.ShowWindow.argtypes=[W.HWND,C.c_int];user32.SetForegroundWindow.argtypes=[W.HWND]
            visible=uid==self.view_bot
            for hwnd in windows:
                # Off-screen windows retain a drawable/UI pump; minimizing would stop matchmaking.
                ok=user32.SetWindowPos(hwnd,None,60 if visible else -28000,60 if visible else -28000,
                    1280 if visible else 640,720 if visible else 480,0x14)
                if not ok:break
            else:
                item["placed"]=True
                if visible:
                    if self.human_pid:
                        hu,hw=self._windows(self.human_pid);hu.ShowWindow.argtypes=[W.HWND,C.c_int]
                        for hwnd in hw:hu.ShowWindow(hwnd,6)
                        self.human_minimized=bool(hw)
                    user32.SetForegroundWindow(windows[0])

    def focus(self):
        # Explicit product button: focus only a descendant of an owned job, never another user process.
        with self.server.room.lock:
            t=self.server.room.tournament
            active=set()
            if t.status=="running" and t.current:
                m=t.matches[t.current-1];active={m["p1"],m["p2"]}
        for uid,item in list(self.children.items()):
            if uid not in active:continue
            info=item["root"]/"game-process.json"
            if not info.exists():continue
            pid=json.loads(info.read_text(encoding="utf-8"))["pid"]
            k=item["job"].kernel
            k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
            k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
            h=k.OpenProcess(0x1000,False,pid)
            owned=W.BOOL()
            if not h:continue
            valid=k.IsProcessInJob(h,item["job"].handle,C.byref(owned)) and owned.value
            k.CloseHandle(h)
            if not valid:continue
            user32=C.WinDLL("user32",use_last_error=True)
            user32.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
            user32.IsWindowVisible.argtypes=[W.HWND]
            user32.ShowWindow.argtypes=[W.HWND,C.c_int];user32.SetForegroundWindow.argtypes=[W.HWND]
            callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
            found=[]
            @callback
            def visit(hwnd,_):
                owner=W.DWORD();user32.GetWindowThreadProcessId(hwnd,C.byref(owner))
                if owner.value==pid and user32.IsWindowVisible(hwnd):found.append(hwnd)
                return True
            user32.EnumWindows(visit,0)
            if found:
                user32.ShowWindow(found[0],9);user32.SetForegroundWindow(found[0]);return
        raise RoomError("El bot todavía no tiene una ventana disponible")

    def close(self):
        self.stop.set()
        self.thread.join(timeout=20)
        if self.thread.is_alive():
            # Job closure still terminates only the owned helper trees.
            for item in list(self.children.values()):item["job"].close()
        self._restore_human()


def run_worker(config_path):
    import competitive_loader as core
    from rising_room_bridge import RoomBridge
    config=json.loads(Path(config_path).read_text(encoding="utf-8"))
    token=os.environ.pop("BTC_BOT_SESSION_TOKEN")
    root=Path(config["root"]);source=Path(config["source"])
    until=time.monotonic()+8
    while not (root/"job-ready").exists() and time.monotonic()<until:time.sleep(.05)
    if not (root/"job-ready").exists():raise RuntimeError("No se recibió el aislamiento del proceso")
    runtime=root/"runtime";runtime.mkdir(exist_ok=True)
    for name in ("Tenkaichi3Decomp.exe","Tenkaichi3Decomp.exe.mem","Tenkaichi3Decomp.dat","SDL3.dll"):
        shutil.copy2(source/name,runtime/name)
    saves=source/"net_session"/"card1"
    if not saves.is_dir():saves=source/"saves"/"card1"
    shutil.copytree(saves,runtime/"saves"/"card1",dirs_exist_ok=True)
    client=RoomClient("127.0.0.1",config["port"],token)
    bridge=RoomBridge(client=client,preserve_membership=True)
    core.RELEASE_PROFILE=True
    image=core.validate_payload(core.PAYLOAD,runtime/"Tenkaichi3Decomp.exe")
    env={k:None for k in os.environ if k.startswith("BT3_") or k.startswith("BTC_")}
    env.update(BTC_ROOM_BRIDGE=bridge.name,BTC_TOURNAMENT_BOT=str(config["bot_id"]),BT3_DATA=str((source/"gamedata").resolve()),BT3_NOMOVIE="1",BT3_PACED="1",BT3_GS_VERBOSE="1",SDL_AUDIODRIVER="dummy")
    if config.get("local_view"):
        env.update(BTC_LOCAL_SPECTATOR="1",BT3_WINDOW="1280x720")
    elif config.get("background"):
        env.update(BT3_WINDOW="640x480",BT3_SCALE="1")
    env["BT3_HASH"] = str(runtime/"state-hashes.txt")
    k,_=core._windows_api();handle=None
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.TerminateProcess.argtypes=[W.HANDLE,W.DWORD];k.CloseHandle.argtypes=[W.HANDLE]
    k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
    try:
        pid=core.launch_patched(runtime/"Tenkaichi3Decomp.exe",image,env=env,game_log=runtime/"game.log",convert_intro=False)
        handle=k.OpenProcess(0x101001,False,pid)
        if not handle:raise RuntimeError("No se pudo seguir el proceso propio del bot")
        (root/"game-process.json").write_text(json.dumps(dict(pid=pid)),encoding="utf-8")
        while not (root/"stop").exists() and k.WaitForSingleObject(handle,300)==0x102:pass
        if not (root/"stop").exists():
            code=W.DWORD();k.GetExitCodeProcess(handle,C.byref(code))
            raise RuntimeError(f"El juego del bot se cerro: 0x{code.value:08X}. Consulta {runtime / 'game.log'}")
    finally:
        if handle:
            if k.WaitForSingleObject(handle,0)==0x102:k.TerminateProcess(handle,0);k.WaitForSingleObject(handle,5000)
            k.CloseHandle(handle)
        bridge.close();core._release_online_memory_handles()
