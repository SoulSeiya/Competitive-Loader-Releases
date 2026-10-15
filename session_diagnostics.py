"""Local diagnostics for one launch; never uploads logs or game data."""
from datetime import datetime
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import shutil
import threading
import uuid

import competitive_loader as core


def make_logger(name: str, path: Path):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class SessionDiagnostics:
    def __init__(self, logs_root: Path, runtime: Path):
        ident = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.path = logs_root / ident
        self.path.mkdir(parents=True)
        self.runtime = runtime
        self.local = make_logger("competitive.local." + ident, self.path / "local.log")
        self.online = make_logger("competitive.online." + ident, self.path / "online.log")
        self.summary = {"loader_version": core.APP_VERSION_TEXT, "runtime": str(runtime),
                        "started_at": datetime.now().astimezone().isoformat(),
                        "platform": platform.platform(), "status": "preparing",
                        "online_observed": False, "desync_observed": False}
        self.running = False
        self._reader = None
        self._initial_crash = self._crash_signature()
        self.local.info("SESSION_START %s", ident)
        self.online.info("SESSION_START %s; esperando actividad de red", ident)
        self._write_summary()

    def _crash_signature(self):
        p = self.runtime / "bt3_crash.txt"
        return (p.stat().st_mtime_ns, p.stat().st_size) if p.is_file() else None

    def _write_summary(self):
        path = self.path / "session.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.summary, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)

    def record_engine_line(self, line: str):
        line = line.rstrip("\r\n")
        self.local.info("GAME %s", line)
        low = line.lower()
        if any(word in low for word in ("bt3: net:", "net:", "relay", "rollback", "desync", "gameplay data:", "memory")):
            self.online.info("%s", line)
        if "net: connected" in low or "net: joining" in low or "net: hosting" in low:
            self.summary["online_observed"] = True
        if "the two games differ" in low or "the two games no longer agree" in low or "(desync)" in low:
            self.summary["desync_observed"] = True

    def _read_output(self, fd: int):
        try:
            with os.fdopen(fd, "rb", buffering=65536) as stream:
                while True:
                    line = stream.readline(65536)
                    if not line:
                        break
                    self.record_engine_line(line.decode("utf-8", errors="replace"))
        except Exception:
            self.local.exception("No se pudo leer la salida del juego")

    def _metadata(self, exe: Path):
        self.summary.update({
            "exe_sha256": core.sha256_file(exe),
            "decomp_release": core.REVIEWED_DECOMP_HASHES.get(core.sha256_file(exe), "unreviewed"),
            "memory_sha256": core.online_memory_fingerprint(self.runtime),
            "dat_sha256": core.sha256_file(self.runtime / "Tenkaichi3Decomp.dat"),
            "payload_sha256": {name: core.sha256_file(core.PAYLOAD / name) for name in core.PATCH_OBJECTS},
            "profile": "competitive-release", "timers": [180, 240, 360, 480, "unlimited"],
        })
        self.local.info("COMPATIBILITY_OK exe=%s decomp=%s", self.summary["exe_sha256"], self.summary["decomp_release"])
        self.online.info("VERSIONS loader=%s decomp=%s memory_sha256=%s payload=%s",
                         core.APP_VERSION_TEXT, self.summary["decomp_release"],
                         self.summary["memory_sha256"], json.dumps(self.summary["payload_sha256"]))
        self._write_summary()

    def launch(self, exe: Path, image, env: dict | None = None):
        self._metadata(exe)
        read_fd, write_fd = os.pipe()
        self._reader = threading.Thread(target=self._read_output, args=(read_fd,), daemon=True)
        self._reader.start()
        try:
            launch_env = {"BT3_GS_VERBOSE": "1"}
            launch_env.update(env or {})
            pid = core.launch_patched(exe, image, game_output_fd=write_fd, env=launch_env)
        finally:
            os.close(write_fd)
        self.running = True
        patch_log = self.runtime / "competitive_loader.log"
        if patch_log.is_file():
            shutil.copy2(patch_log, self.path / "patch.log")
        self.summary.update({"pid": pid, "status": "running"})
        self._write_summary()
        threading.Thread(target=self._monitor, args=(pid,), daemon=True).start()
        return pid

    def _monitor(self, pid: int):
        kernel, _ = core._windows_api()
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel.GetExitCodeProcess.restype = ctypes.c_int
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x101000, False, pid)
        try:
            if not handle:
                self.finish("exit_unavailable")
                return
            status = kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
            code = ctypes.c_uint32()
            if status == 0xFFFFFFFF or not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                self.finish("exit_unavailable")
                return
            if self._reader:
                self._reader.join(timeout=3)
            self.summary["exit_code"] = f"0x{code.value:08X}"
            self.finish("desync" if self.summary["desync_observed"] else "closed" if code.value == 0 else "abnormal_exit")
        except Exception:
            self.local.exception("Error siguiendo el proceso del juego")
            self.finish("monitor_error")
        finally:
            if handle:
                kernel.CloseHandle(handle)
            core._release_online_memory_handles()
            self.running = False

    def finish(self, status: str):
        crash = self._crash_signature()
        if crash and crash != self._initial_crash:
            shutil.copy2(self.runtime / "bt3_crash.txt", self.path / "bt3_crash.txt")
            self.summary["crash_report"] = "bt3_crash.txt"
            status = "crash"
        self.summary.update({"status": status, "finished_at": datetime.now().astimezone().isoformat()})
        self.local.info("SESSION_END status=%s exit=%s", status, self.summary.get("exit_code", "not_started"))
        self.online.info("SESSION_END status=%s online=%s desync=%s", status,
                         self.summary["online_observed"], self.summary["desync_observed"])
        self._write_summary()

    def dispose(self):
        for logger in (self.local, self.online):
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
