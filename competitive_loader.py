#!/usr/bin/env python3
"""Competitive Loader for Tenkaichi3Decomp (Windows x64).

Prepares an isolated runtime from an official release, installs the user's own
Competitive Edition v8.4.1 disc data, adapts the release .dat checksum and
loads the small native compatibility payload before the game starts.

No game data is distributed by this tool.  The ISO and official release are
never modified.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


APP_VERSION = (1, 4, 0)
APP_VERSION_TEXT = ".".join(str(part) for part in APP_VERSION)
APP_NAME = "Competitive Loader"
VERSION_HIGHLIGHTS = (
    "• Rising Battle: sala BTC dentro del menú online del juego.\n"
    "• Crear o unirse por IP, puerto y clave; hasta 32 usuarios.\n"
    "• Lista de usuarios, estado listo, chat y expulsión por el anfitrión.\n"
    "• La sala permanece conectada durante los combates BTC.\n"
    "• Corrección de carga de modelos de efectos, incluido el fallo detectado al atacar con Androide 16.\n"
    "• FT1 a FT5 en la pestaña Host del menú online F1.\n"
    "• Ganador en grande y GG al completar el FT; cierre de la sesión para ambos.\n"
    "• Nombre del rival conectado en la selección de personajes.\n"
    "• Botón Buscar actualizaciones sin reiniciar el Loader.\n"
    "• Conserva el marcador, bloqueo de ventana y registros de diagnóstico."
)
COMPETITIVE_SLUS_SHA1 = "28992f0d472bbb6b67cc193bb7d79b8a78bd7feb"
DBZP_SHA1 = "4f910969e05d9b25c83af7642b60da9949a4348b"
ROM_BASE, ROM_END = 0x100000, 0x2FF180
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
PAGE = 0x1000

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
PAYLOAD = RESOURCE_ROOT / "payload"
APP_ICON = RESOURCE_ROOT / "assets" / "universo_tenkaichi_ui.png"
APP_HEADER_LOGO = RESOURCE_ROOT / "assets" / "competitive_edition_logo.png"
INTRO_CONVERTER = RESOURCE_ROOT / "tools" / "ffmpeg-lite.exe"
DEFAULT_RUNTIME = HERE / "CompetitiveRuntime"
CONFIG = HERE / "competitive_loader.json"
RELEASE_PROFILE = False
REVIEWED_DECOMP_HASHES = {
    "a34fe8141d4190077e5bb8c874fb39280815535bb6b53f82e669daac1636b9b9": "v0.1.35.2",
}
SAVE_NAME = "BASLUS-21678DBZT3"
SAVE_FILE_SIZES = {
    SAVE_NAME: 0x4000,
    "icon.sys": 964,
    "dbzsm.ico": 40090,
}
_ONLINE_SAVE_HANDLES: list[int] = []
LATEST_WINDOWS_RELEASE = (
    "https://github.com/z3xox/Tenkaichi3Decomp/releases/latest/download/"
    "Tenkaichi3Decomp-windows-x64.zip"
)
LATEST_RELEASE_API = "https://api.github.com/repos/z3xox/Tenkaichi3Decomp/releases/latest"
WINDOWS_ASSET_NAME = "Tenkaichi3Decomp-windows-x64.zip"
LOADER_RELEASE_API = (
    "https://api.github.com/repos/SoulSeiya/"
    "Competitive-Loader-Releases/releases/latest"
)
LOADER_ASSET_NAME = "CompetitiveLoader-windows-x64.zip"
LOADER_UPDATE_DIR = HERE / ".competitive-update"
PRESERVED_UPDATE_NAMES = {
    "gamedata", "saves", "save-backups", "textures", "songs", "stages",
}

PATCHES = {
    # The compiler inlines both checked helpers into these two callers, so the
    # callers must be redirected as well.  Patching only the helper entries
    # leaves the old unchecked code embedded in the official executable.
    "battle_bobj_a.o": [
        "BtlObjMdl_HasLipTrack", "BtlObj_SetSubState",
        "BObjFile_GetEntry", "BtlObj_BindTables", "BtlObj_GetNode",
    ],
    "battle_btl_act_c.o": ["BtlAct_Action42"],
    "battle_btl_act_e.o": ["BtlAct_VanishStepHandler", "BtlAct_ClashExchangeHandler"],
    "battle_btl_char_flag_clash.o": ["BtlClash_UpdateC"],
    "battle_btl_char_hit.o": [
        "BtlHit_CheckDodge", "BtlHit_CheckClash", "BtlHit_TestHit", "BtlHit_ApplyHit",
    ],
    "battle_btl_char_status_anim.o": ["BtlAnim_HideModelNodes"],
    "battle_btl_obj.o": ["BtlRes_Init"],
    "battle_hud_e_d.o": ["BtlPause_CheckOpen", "BtlPause_CheckStart"],
    "battle_view_a_d.o": ["ChrView_Init"],
    "battle_view_b_c.o": ["CpuLevel_FromSetting"],
}

# These hooks redirect the executable's direct CALL sites but leave the
# original function entry intact.  The wrapper can therefore add a small
# piece of behaviour and then call the official implementation.  This keeps
# chat independent from the decomp release's UI and netplay internals.
CALL_WRAPPERS = {
    "competitive_chat.o": {
        "Ui_Event": "Competitive_UiEvent",
        "net_recv": "Competitive_NetRecv",
        "Port_NetSessionBegin": "Competitive_NetSessionBegin",
        "Port_NetArrived": "Competitive_NetArrived",
        "Battle_Load": "Competitive_BattleLoad",
        "BtlSeq_CheckBattleEnd": "Competitive_BtlSeqCheckBattleEnd",
        "Battle_Restart": "Competitive_BattleRestart",
        "BtlSeq_Update": "Competitive_BtlSeqUpdate",
        "CharSel_Draw": "Competitive_CharSelDraw",
        "ADXT_StartAfs": "Competitive_ADXTStartAfs",
    },
}
ENTRY_PATCH_TARGETS = {name for names in PATCHES.values() for name in names}
CALL_WRAPPER_TARGETS = {name for hooks in CALL_WRAPPERS.values() for name in hooks}
PATCH_TARGETS = ENTRY_PATCH_TARGETS | CALL_WRAPPER_TARGETS
PATCH_OBJECTS = tuple(PATCHES) + tuple(CALL_WRAPPERS)
PATCH_SYMBOLS = {name: name for name in ENTRY_PATCH_TARGETS}
PATCH_SYMBOLS.update({target: symbol for hooks in CALL_WRAPPERS.values() for target, symbol in hooks.items()})

# The official lobby keeps these labels as one unique ASCII block. The native
# payload changes the matching timer table; these same-size in-memory edits
# make the four choices tell the player the real Competitive duration.
COMPETITIVE_TIME_LABEL_PATCHES = {
    b"60 seconds\0": b"180 sec.\0\0\0",
    b"90 seconds\0": b"240 sec.\0\0\0",
    b"180 seconds\0": b"360 seconds\0",
    b"240 seconds\0": b"480 seconds\0",
}
ONLINE_TIME_LABEL_PATCHES = dict(COMPETITIVE_TIME_LABEL_PATCHES)


class LoaderError(RuntimeError):
    pass


class IncompatibleDecompError(LoaderError):
    pass


def use_official_online_profile(exe_path: Path, audio_fix: bool = False, competitive_times: bool = False, session_score: bool = False) -> None:
    """Opt-in laboratory profile, pinned to the locally reviewed Windows build.

    Keep competitive gameplay/model objects but do not inject the legacy native
    online/audio extensions. Call before creating any PayloadImage.
    """
    actual = sha256_file(exe_path)
    if actual not in REVIEWED_DECOMP_HASHES:
        raise IncompatibleDecompError(
            "El decomp no está revisado para este Loader; se conserva la instalación anterior. "
            f"Actualiza Competitive Loader para admitirlo. SHA-256: {actual}"
        )
    global PATCHES, CALL_WRAPPERS, ENTRY_PATCH_TARGETS, CALL_WRAPPER_TARGETS
    global PATCH_TARGETS, PATCH_OBJECTS, PATCH_SYMBOLS, ONLINE_TIME_LABEL_PATCHES
    PATCHES = {name: targets for name, targets in PATCHES.items() if name != "battle_hud_e_d.o"}
    CALL_WRAPPERS = {"competitive_audio.o": {"ADXT_StartAfs": "Competitive_AudioStartAfs"}} if audio_fix else {}
    CALL_WRAPPERS["competitive_effect_model.o"] = {"BtlObj_Create": "Competitive_EffectModelCreate"}
    if competitive_times:
        CALL_WRAPPERS["competitive_times.o"] = {"Battle_Load": "Competitive_TimeBattleLoad"}
    if session_score:
        CALL_WRAPPERS["competitive_score.o"] = {
            "_ZL9build_netv": "Competitive_RisingMenu",
            "_ZN5ImGui5BeginEPKcPbi": "Competitive_RisingBegin",
            "Ui_Event": "Competitive_WindowEvent",
            "Port_NetRulesSet": "Competitive_FtRulesSet",
            "Port_LobbyStartQuick": "Competitive_FtQuickStart",
            "_ZN5ImGui12TextDisabledEPKcz": "Competitive_FtHostRow",
            "Port_NetBeginTick": "Competitive_ScoreBeginTick",
            "Port_NetSessionBegin": "Competitive_ScoreSessionBegin",
            "Port_NetSessionEnd": "Competitive_ScoreSessionEnd",
            "BtlSeq_CheckBattleEnd": "Competitive_ScoreBattleEnd",
            "_ZN5ImGui6RenderEv": "Competitive_ScoreRender",
            "Ui_Draw": "Competitive_ScoreDraw",
            "Ui_DrawGL": "Competitive_ScoreDrawGL",
        }
    ENTRY_PATCH_TARGETS = {name for names in PATCHES.values() for name in names}
    CALL_WRAPPER_TARGETS = {name for hooks in CALL_WRAPPERS.values() for name in hooks}
    PATCH_TARGETS = ENTRY_PATCH_TARGETS | CALL_WRAPPER_TARGETS
    PATCH_OBJECTS = tuple(PATCHES) + tuple(CALL_WRAPPERS)
    PATCH_SYMBOLS = {name: name for name in ENTRY_PATCH_TARGETS}
    PATCH_SYMBOLS.update({target: symbol for hooks in CALL_WRAPPERS.values() for target, symbol in hooks.items()})
    ONLINE_TIME_LABEL_PATCHES = dict(COMPETITIVE_TIME_LABEL_PATCHES) if competitive_times else {}


def sha1_file(path: Path, chunk: int = 4 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while data := f.read(chunk):
            h.update(data)
    return h.hexdigest()


def sha256_file(path: Path, chunk: int = 4 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while data := f.read(chunk):
            h.update(data)
    return h.hexdigest()


def _github_headers(accept: str = "application/vnd.github+json") -> dict[str, str]:
    return {
        "User-Agent": f"Competitive-Loader/{APP_VERSION_TEXT}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _release_version(tag: str) -> tuple[int, int, int] | None:
    """Read v1.2, 1.2.3 and similar release tags without extra packages."""
    clean = tag.strip().lower()
    if clean.startswith("v"):
        clean = clean[1:]
    clean = clean.split("-", 1)[0]
    parts = clean.split(".")
    if not parts or len(parts) > 3 or any(not part.isdigit() for part in parts):
        return None
    values = [int(part) for part in parts]
    values.extend([0] * (3 - len(values)))
    return tuple(values)  # type: ignore[return-value]


def latest_loader_release_info() -> dict:
    """Return metadata for the latest published loader, even when it is current."""
    request = urllib.request.Request(LOADER_RELEASE_API, headers=_github_headers())
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            release = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise LoaderError("No hay una Release del loader visible en GitHub.") from exc
        raise LoaderError(f"No se pudo comprobar la actualización del loader: HTTP {exc.code}.") from exc
    except (OSError, UnicodeError, ValueError, urllib.error.URLError) as exc:
        raise LoaderError(f"No se pudo comprobar la actualización del loader: {exc}") from exc

    tag = str(release.get("tag_name") or "").strip()
    version = _release_version(tag)
    if version is None:
        raise LoaderError(f"La publicación del loader usa una versión no reconocida: {tag or '(vacía)' }.")
    asset = next(
        (item for item in release.get("assets", []) if item.get("name") == LOADER_ASSET_NAME),
        None,
    )
    return {
        "tag": tag,
        "version": version,
        "name": str(release.get("name") or tag),
        "notes": str(release.get("body") or "").strip(),
        "download_url": str(asset.get("browser_download_url") or "") if asset else "",
        "size": int(asset.get("size") or 0) if asset else 0,
        "digest": str(asset.get("digest") or "").strip().lower() if asset else "",
    }


def latest_loader_update() -> dict | None:
    """Return a newer installable loader release, or None when current."""
    info = latest_loader_release_info()
    if info["version"] <= APP_VERSION:
        return None
    if not info["download_url"]:
        raise LoaderError(f"La publicación {info['tag']} no contiene {LOADER_ASSET_NAME}.")
    return info


def _download_to(url: str, destination: Path, expected_size: int = 0) -> None:
    request = urllib.request.Request(url, headers=_github_headers("application/octet-stream"))
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            total = expected_size or int(response.headers.get("Content-Length") or 0)
            received = 0
            announced = -10
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                received += len(block)
                if total:
                    percent = min(100, received * 100 // total)
                    if percent >= announced + 10:
                        announced = percent // 10 * 10
                        print(f"      Descarga del loader: {announced}%")
    except (OSError, urllib.error.URLError) as exc:
        raise LoaderError(f"No se pudo descargar la actualización del loader: {exc}") from exc
    if expected_size and destination.stat().st_size != expected_size:
        raise LoaderError("La descarga del loader quedó incompleta; no se reemplazó la aplicación.")


def stage_loader_update(release: dict) -> Path:
    """Download and verify a future executable without touching the running one."""
    if not getattr(sys, "frozen", False):
        raise LoaderError("La actualización automática solo se instala desde Competitive Loader.exe.")
    shutil.rmtree(LOADER_UPDATE_DIR, ignore_errors=True)
    LOADER_UPDATE_DIR.mkdir(parents=True)
    archive = LOADER_UPDATE_DIR / LOADER_ASSET_NAME
    print(f"[APP] Descargando Competitive Loader {release['tag']}...")
    _download_to(release["download_url"], archive, int(release.get("size") or 0))

    digest = str(release.get("digest") or "")
    if digest:
        algorithm, separator, expected = digest.partition(":")
        if algorithm != "sha256" or not separator or len(expected) != 64:
            raise LoaderError("GitHub publicó una huella de actualización no reconocida.")
        actual = sha256_file(archive)
        if actual.lower() != expected.lower():
            raise LoaderError("La huella SHA-256 de la actualización no coincide.")

    staged_exe = LOADER_UPDATE_DIR / "Competitive Loader.update.exe"
    try:
        with zipfile.ZipFile(archive) as package:
            matches = [
                item for item in package.infolist()
                if not item.is_dir() and Path(item.filename).name.casefold() == "competitive loader.exe"
            ]
            if len(matches) != 1:
                raise LoaderError("El paquete debe contener exactamente un Competitive Loader.exe.")
            if matches[0].file_size < 100_000 or matches[0].file_size > 300_000_000:
                raise LoaderError("El ejecutable publicado tiene un tamaño no válido.")
            with package.open(matches[0]) as source, staged_exe.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    except (OSError, zipfile.BadZipFile) as exc:
        raise LoaderError(f"El paquete de actualización está dañado: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    with staged_exe.open("rb") as executable:
        if executable.read(2) != b"MZ":
            raise LoaderError("La actualización no contiene un ejecutable de Windows válido.")
    print("[OK] Actualización verificada y preparada para reiniciar.")
    return staged_exe


def schedule_loader_update(staged_exe: Path) -> None:
    """Run the verified new EXE as a detached, self-contained updater."""
    if not getattr(sys, "frozen", False):
        raise LoaderError("La actualización automática solo se instala desde Competitive Loader.exe.")
    staged_exe = staged_exe.resolve()
    if staged_exe.parent != LOADER_UPDATE_DIR.resolve() or not staged_exe.is_file():
        raise LoaderError("No se encontró la actualización preparada.")

    target = Path(sys.executable).resolve()
    flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    try:
        subprocess.Popen(
            [
                str(staged_exe), "--apply-loader-update", str(os.getpid()),
                str(target), str(HERE),
            ],
            creationflags=flags,
            close_fds=True,
        )
    except OSError as exc:
        raise LoaderError(f"Windows no pudo iniciar el instalador de la actualización: {exc}") from exc


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


def _wait_for_process(process_id: int, timeout_ms: int) -> None:
    """Wait for one process when it exists; invalid/already-ended PIDs are done."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(0x00100000, False, int(process_id))
    if handle:
        try:
            kernel32.WaitForSingleObject(handle, max(0, int(timeout_ms)))
        finally:
            kernel32.CloseHandle(handle)


def _close_loader_processes_at(target: Path) -> None:
    """Terminate only other Loader processes executing the exact target path."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid = ctypes.c_void_p(-1).value
    if not snapshot or int(snapshot) == invalid:
        return
    wanted = os.path.normcase(str(target.resolve()))
    entry = _PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            process_id = int(entry.th32ProcessID)
            if process_id != os.getpid():
                handle = kernel32.OpenProcess(0x1001, False, process_id)
                if handle:
                    try:
                        capacity = wintypes.DWORD(32768)
                        path_buffer = ctypes.create_unicode_buffer(capacity.value)
                        if kernel32.QueryFullProcessImageNameW(handle, 0, path_buffer, ctypes.byref(capacity)):
                            if os.path.normcase(str(Path(path_buffer.value).resolve())) == wanted:
                                kernel32.TerminateProcess(handle, 0)
                    finally:
                        kernel32.CloseHandle(handle)
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)


def apply_loader_update(previous_pid: int, target: Path, working_directory: Path) -> None:
    """Updater mode executed by the verified staged vNext executable."""
    source = Path(sys.executable).resolve()
    target = target.resolve()
    working_directory = working_directory.resolve()
    if source.parent.name != ".competitive-update" or target.parent != working_directory:
        raise LoaderError("Windows rechazó una ruta insegura para actualizar el Loader.")

    _wait_for_process(previous_pid, 15000)
    _close_loader_processes_at(target)
    copied = False
    for _attempt in range(80):
        try:
            shutil.copy2(source, target)
            copied = sha256_file(source) == sha256_file(target)
            if copied:
                break
        except OSError:
            pass
        time.sleep(0.25)
    if not copied:
        raise LoaderError("No se pudo reemplazar Competitive Loader.exe después de cerrar sus instancias.")

    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(target), "--finish-loader-update", str(os.getpid()), str(source.parent)],
        cwd=str(working_directory), creationflags=flags, close_fds=True,
    )


def finish_loader_update(updater_pid: int, update_directory: Path) -> None:
    """Wait until the staged updater exits, then remove its private directory."""
    expected = (HERE / ".competitive-update").resolve()
    update_directory = update_directory.resolve()
    if update_directory != expected:
        return
    _wait_for_process(updater_pid, 15000)
    for _attempt in range(40):
        try:
            shutil.rmtree(update_directory)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.25)


def align(value: int, amount: int) -> int:
    return (value + amount - 1) & ~(amount - 1)


def fnv_update(value: int, data: bytes) -> int:
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def flat_elf(path: Path) -> bytes:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise LoaderError(f"{path.name} no es un ejecutable ELF de PS2 válido.")
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    image = bytearray(ROM_END - ROM_BASE)
    for index in range(shnum):
        entry = shoff + index * shentsize
        if entry + 24 > len(data):
            raise LoaderError("La tabla ELF de SLUS_216.78 está dañada.")
        _, kind, flags, address, offset, size = struct.unpack_from("<6I", data, entry)
        if flags & 2 and kind != 8 and size and ROM_BASE <= address and address + size <= ROM_END:
            image[address - ROM_BASE:address - ROM_BASE + size] = data[offset:offset + size]
    return bytes(image)


class IsoEntry:
    __slots__ = ("name", "extent", "size", "directory")

    def __init__(self, name: str, extent: int, size: int, directory: bool):
        self.name, self.extent, self.size, self.directory = name, extent, size, directory


class Iso9660:
    """Small ISO9660 reader sufficient for the PS2 disc image."""

    SECTOR = 2048

    def __init__(self, path: Path):
        self.path = path
        self.file = path.open("rb")
        self.file.seek(16 * self.SECTOR)
        pvd = self.file.read(self.SECTOR)
        if len(pvd) != self.SECTOR or pvd[0] != 1 or pvd[1:6] != b"CD001":
            self.file.close()
            raise LoaderError("El archivo elegido no es una ISO9660 válida.")
        self.root = self._record(pvd, 156)

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @staticmethod
    def _record(data: bytes, pos: int) -> IsoEntry:
        length = data[pos]
        if length < 34 or pos + length > len(data):
            raise LoaderError("La ISO contiene un registro de directorio inválido.")
        extent = struct.unpack_from("<I", data, pos + 2)[0]
        size = struct.unpack_from("<I", data, pos + 10)[0]
        flags = data[pos + 25]
        nlen = data[pos + 32]
        raw = data[pos + 33:pos + 33 + nlen]
        if raw in (b"\x00", b"\x01"):
            name = "." if raw == b"\x00" else ".."
        else:
            name = raw.decode("ascii", "replace").split(";", 1)[0]
        return IsoEntry(name, extent, size, bool(flags & 2))

    def children(self, directory: IsoEntry) -> list[IsoEntry]:
        self.file.seek(directory.extent * self.SECTOR)
        data = self.file.read(directory.size)
        result: list[IsoEntry] = []
        pos = 0
        while pos < len(data):
            if data[pos] == 0:
                pos = align(pos + 1, self.SECTOR)
                continue
            entry = self._record(data, pos)
            if entry.name not in (".", ".."):
                result.append(entry)
            pos += data[pos]
        return result

    def find(self, parts: list[str]) -> IsoEntry:
        current = self.root
        for part in parts:
            match = next((e for e in self.children(current) if e.name.upper() == part.upper()), None)
            if match is None:
                raise LoaderError(f"La ISO no contiene {'/'.join(parts)}.")
            current = match
        return current

    def extract_file(self, entry: IsoEntry, destination: Path, progress=None):
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.file.seek(entry.extent * self.SECTOR)
        remaining = entry.size
        with destination.open("wb") as out:
            while remaining:
                data = self.file.read(min(4 << 20, remaining))
                if not data:
                    raise LoaderError(f"Lectura incompleta al extraer {entry.name}.")
                out.write(data)
                remaining -= len(data)
                if progress:
                    progress(len(data))

    def extract_tree(self, entry: IsoEntry, destination: Path, progress=None):
        destination.mkdir(parents=True, exist_ok=True)
        for child in self.children(entry):
            target = destination / child.name
            if child.directory:
                self.extract_tree(child, target, progress)
            else:
                self.extract_file(child, target, progress)


def split_afs(path: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    with path.open("rb") as src:
        head = src.read(8)
        if len(head) != 8:
            raise LoaderError(f"{path.name} está incompleto.")
        magic, count = struct.unpack("<4sI", head)
        if magic != b"AFS\0" or count > 200000:
            raise LoaderError(f"{path.name} no es un archivo AFS válido.")
        raw = src.read(count * 8)
        if len(raw) != count * 8:
            raise LoaderError(f"La tabla de {path.name} está incompleta.")
        table = struct.unpack(f"<{count * 2}I", raw)
        for index in range(count):
            offset, size = table[index * 2:index * 2 + 2]
            src.seek(offset)
            target = output / f"{index:05d}.bin"
            with target.open("wb") as dst:
                remaining = size
                while remaining:
                    data = src.read(min(4 << 20, remaining))
                    if not data:
                        raise LoaderError(f"Entrada incompleta en {path.name}: {index}.")
                    dst.write(data)
                    remaining -= len(data)
    path.unlink()
    return count


def _mpeg2_picture_types(path: Path) -> dict[int, int]:
    """Count MPEG-2 picture coding types without decoding the movie."""
    counts: dict[int, int] = {}
    tail = b""
    with path.open("rb") as movie:
        while True:
            block = movie.read(4 << 20)
            if not block:
                break
            data = tail + block
            offset = 0
            while True:
                offset = data.find(b"\x00\x00\x01\x00", offset)
                if offset < 0:
                    break
                if offset + 6 <= len(data):
                    picture_type = (data[offset + 5] >> 3) & 7
                    counts[picture_type] = counts.get(picture_type, 0) + 1
                offset += 4
            tail = data[-5:]
    return counts


def ensure_intro_compatible(runtime: Path) -> Path | None:
    """Convert the competitive opening once for the decomp's I-frame decoder.

    Tenkaichi3Decomp's compact MPEG-2 player intentionally decodes I pictures
    only.  The competitive opening also contains P/B pictures, so playing the
    ISO stream directly repeats incomplete reference frames.  Keeping an
    all-I copy avoids changing the executable and remains fully reversible.
    """
    game = runtime / "gamedata"
    intro = game / "disc" / "DATA" / "ZS3USOP.PSS"
    backup = intro.with_name("ZS3USOP.original.PSS")
    marker = game / ".competitive-intro-v2.json"
    if not intro.is_file():
        return None

    if marker.is_file():
        try:
            saved = json.loads(marker.read_text(encoding="utf-8"))
            if saved.get("format") == "all-i-v2" and saved.get("converted_sha256") == sha256_file(intro):
                print("[INTRO] Versión compatible ya preparada.")
                return intro
        except (OSError, ValueError, TypeError):
            pass

    source = backup if backup.is_file() else intro
    source_types = _mpeg2_picture_types(source)
    if source_types.get(2, 0) == 0 and source_types.get(3, 0) == 0 and source_types.get(1, 0) >= 2000:
        marker.write_text(json.dumps({
            "format": "all-i-v2",
            "original_sha256": sha256_file(source),
            "converted_sha256": sha256_file(intro),
            "converted": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2), encoding="utf-8")
        return intro

    if not INTRO_CONVERTER.is_file():
        raise LoaderError("Falta el conversor incluido para reparar la intro competitiva.")

    temporary = intro.with_name("ZS3USOP.competitive.tmp.PSS")
    temporary.unlink(missing_ok=True)
    print("[INTRO] Optimizando la intro competitiva (solo se hace una vez)...")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run([
            str(INTRO_CONVERTER), "-hide_banner", "-loglevel", "warning", "-y",
            "-c:v", "mpeg2video", "-i", str(source),
            "-map", "0:v:0", "-an", "-c:v", "mpeg2video",
            "-g", "1", "-bf", "0", "-q:v", "2", "-pix_fmt", "yuv420p",
            "-f", "vob", str(temporary),
        ], capture_output=True, text=True, errors="replace", check=False,
           creationflags=flags, timeout=10 * 60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        temporary.unlink(missing_ok=True)
        raise LoaderError(f"No se pudo preparar la intro competitiva: {exc}") from exc

    if result.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "error desconocido").strip()
        raise LoaderError(f"No se pudo convertir la intro competitiva.\n{detail[-1600:]}")

    converted_types = _mpeg2_picture_types(temporary)
    if converted_types.get(1, 0) < 2000 or converted_types.get(2, 0) or converted_types.get(3, 0):
        temporary.unlink(missing_ok=True)
        raise LoaderError("La comprobación de la intro convertida no fue válida.")

    original_hash = sha256_file(source)
    converted_hash = sha256_file(temporary)
    if not backup.exists():
        os.replace(intro, backup)
    os.replace(temporary, intro)
    marker.write_text(json.dumps({
        "format": "all-i-v2",
        "original_sha256": original_hash,
        "converted_sha256": converted_hash,
        "pictures": converted_types.get(1, 0),
        "converted": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2), encoding="utf-8")
    print(f"[OK] Intro compatible preparada: {converted_types.get(1, 0)} fotogramas.")
    return intro


def _extract_competitive_iso(iso_path: Path, game: Path):
    """Validate and extract one Competitive Edition ISO into an isolated game folder."""
    if not iso_path.is_file():
        raise LoaderError(f"No existe la ISO competitiva: {iso_path}")
    disc = game / "disc"
    slus = disc / "SLUS_216.78"
    dbzp = disc / "BIN" / "DBZP.BIN"
    marker = game / ".competitive-v8.4.1.json"
    print("[1/4] Leyendo la ISO competitiva...")
    disc.mkdir(parents=True, exist_ok=True)
    with Iso9660(iso_path) as iso:
        slus_entry = iso.find(["SLUS_216.78"])
        dbzp_entry = iso.find(["BIN", "DBZP.BIN"])
        iso.extract_file(slus_entry, slus)
        iso.extract_file(dbzp_entry, dbzp)

        slus_hash = hashlib.sha1(flat_elf(slus)).hexdigest()
        dbzp_hash = sha1_file(dbzp)
        if slus_hash != COMPETITIVE_SLUS_SHA1 or dbzp_hash != DBZP_SHA1:
            raise LoaderError(
                "La ISO no es DBZ Competitive Edition v8.4.1 compatible.\n"
                f"SLUS: {slus_hash}\nDBZP: {dbzp_hash}"
            )

        print("[2/4] Extrayendo los archivos del juego (puede tardar varios minutos)...")
        iso.extract_tree(iso.find(["DATA"]), disc / "DATA")
        # Keep all BIN files used by the port, not only DBZP.BIN.
        iso.extract_tree(iso.find(["BIN"]), disc / "BIN")

    print("[3/4] Separando los archivos AFS...")
    afs_files = sorted((disc / "DATA").glob("*.AFS"))
    if not afs_files:
        afs_files = sorted((disc / "DATA").glob("*.afs"))
    for afs in afs_files:
        count = split_afs(afs, game / afs.stem.lower())
        print(f"      {afs.name}: {count} archivos")

    marker.write_text(json.dumps({
        "edition": "DBZ Competitive Edition v8.4.1",
        "slus_sha1": COMPETITIVE_SLUS_SHA1,
        "dbzp_sha1": DBZP_SHA1,
        "installed": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2), encoding="utf-8")
    print("[OK] Datos competitivos instalados.")
    return slus, dbzp


def verify_or_install_iso(iso_path: Path, runtime: Path, force: bool = False):
    game = runtime / "gamedata"
    disc = game / "disc"
    slus = disc / "SLUS_216.78"
    dbzp = disc / "BIN" / "DBZP.BIN"
    marker = game / ".competitive-v8.4.1.json"
    ready = marker.is_file() and slus.is_file() and dbzp.is_file()
    if ready and not force:
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if saved.get("slus_sha1") == COMPETITIVE_SLUS_SHA1 and saved.get("dbzp_sha1") == DBZP_SHA1:
            print("[OK] Datos competitivos ya instalados; no se vuelven a extraer.")
            return slus, dbzp

    if game.exists() and force:
        shutil.rmtree(game)
    return _extract_competitive_iso(iso_path, game)


def replace_competitive_iso(iso_path: Path, runtime: Path) -> Path:
    """Replace only extracted disc data, restoring the previous install on any failure."""
    iso_path = iso_path.resolve()
    runtime = runtime.resolve()
    exe = runtime / "Tenkaichi3Decomp.exe"
    dat = runtime / "Tenkaichi3Decomp.dat"
    live_game = runtime / "gamedata"
    if not iso_path.is_file():
        raise LoaderError(f"No existe la ISO competitiva: {iso_path}")
    if not exe.is_file() or not dat.is_file():
        raise LoaderError("Instala Competitive Edition con Jugar antes de cambiar la ISO.")
    if _is_game_running():
        raise LoaderError("Cierra Tenkaichi3Decomp antes de instalar una ISO nueva.")

    old_config = load_config()
    old_dat = dat.read_bytes()
    backup = runtime / f".competitive-gamedata-backup-{os.getpid()}-{time.time_ns()}"
    swapped = False
    had_previous = live_game.exists()

    print("[ISO] Preparando la ISO nueva sin modificar la instalación actual...")
    with tempfile.TemporaryDirectory(prefix=".competitive-iso-", dir=runtime) as temp_text:
        staged_game = Path(temp_text) / "gamedata"
        staged_slus, staged_dbzp = _extract_competitive_iso(iso_path, staged_game)
        try:
            if had_previous:
                os.replace(live_game, backup)
            os.replace(staged_game, live_game)
            swapped = True

            # Paths change when the staged folder becomes the live installation.
            slus = live_game / staged_slus.relative_to(staged_game)
            dbzp = live_game / staged_dbzp.relative_to(staged_game)
            ensure_intro_compatible(runtime)
            patch_dat(dat, slus, dbzp)
            image = validate_payload(PAYLOAD, exe)
            image.build(0x60000000, image.pe.preferred_base)

            state = dict(old_config)
            state.update({
                "runtime": str(runtime),
                "iso": str(iso_path),
                "iso_updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "exe_sha256": sha256_file(exe),
            })
            save_config(state)
        except Exception:
            print("[ISO] La comprobación falló; restaurando la instalación anterior...")
            if swapped and live_game.exists():
                shutil.rmtree(live_game)
            if had_previous and backup.exists():
                os.replace(backup, live_game)
            dat.write_bytes(old_dat)
            save_config(old_config)
            raise

    if backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError as exc:
            print(f"[AVISO] La ISO nueva está instalada, pero no se pudo borrar el respaldo temporal: {exc}")
    print("[OK] ISO competitiva reemplazada; el decomp, los ajustes y la memory se conservaron.")
    return exe


def find_release_root(folder: Path) -> Path:
    if (folder / "Tenkaichi3Decomp.exe").is_file():
        return folder
    candidates = list(folder.rglob("Tenkaichi3Decomp.exe"))
    if len(candidates) != 1:
        raise LoaderError("No se encontró una única carpeta de Tenkaichi3Decomp en el paquete oficial.")
    return candidates[0].parent


def copy_official_release(source: Path, runtime: Path) -> Path:
    runtime.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        if source.suffix.lower() != ".zip":
            raise LoaderError("La actualización oficial debe ser una carpeta o un archivo .zip.")
        with tempfile.TemporaryDirectory(prefix="competitive-loader-") as temp:
            with zipfile.ZipFile(source) as archive:
                archive.extractall(temp)
            root = find_release_root(Path(temp))
            _copy_release_files(root, runtime)
    else:
        root = find_release_root(source)
        if root.resolve() == runtime.resolve():
            raise LoaderError("La carpeta oficial y CompetitiveRuntime deben ser diferentes.")
        _copy_release_files(root, runtime)
    exe = runtime / "Tenkaichi3Decomp.exe"
    dat = runtime / "Tenkaichi3Decomp.dat"
    if not exe.is_file() or not dat.is_file():
        raise LoaderError("El paquete oficial no contiene el ejecutable y su archivo .dat.")
    return exe


def _copy_release_files(source: Path, runtime: Path):
    print("[0/4] Copiando la actualización oficial a CompetitiveRuntime...")
    for item in source.iterdir():
        if item.name.lower() == "gamedata":
            continue
        target = runtime / item.name
        if item.name.lower() in PRESERVED_UPDATE_NAMES and target.exists():
            continue
        if item.is_file():
            shutil.copy2(item, target)
        elif item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)


def _is_game_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Tenkaichi3Decomp.exe", "/NH"],
            capture_output=True, text=True, errors="replace", check=False,
        )
        return "tenkaichi3decomp.exe" in result.stdout.lower()
    except OSError:
        return False


def _extract_release_safely(archive_path: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            total = sum(member.file_size for member in members)
            if total > 512 * 1024 * 1024:
                raise LoaderError("El paquete descargado es demasiado grande para ser una versión oficial.")
            root = destination.resolve()
            for member in members:
                target = (destination / member.filename).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise LoaderError("El ZIP descargado contiene una ruta insegura.") from exc
            archive.extractall(destination)
    except (OSError, zipfile.BadZipFile) as exc:
        raise LoaderError(f"La descarga de GitHub no es un ZIP válido: {exc}") from exc
    return find_release_root(destination)


def _validate_official_release(root: Path) -> tuple[Path, str]:
    exe = root / "Tenkaichi3Decomp.exe"
    dat = root / "Tenkaichi3Decomp.dat"
    if not exe.is_file() or not dat.is_file():
        raise LoaderError("La versión de GitHub no contiene Tenkaichi3Decomp.exe y Tenkaichi3Decomp.dat.")
    image = validate_payload(PAYLOAD, exe)
    image.build(0x60000000, image.pe.preferred_base)
    return exe, sha256_file(exe)


def _install_release_transactional(source: Path, runtime: Path):
    """Replace only official files, with a same-volume rollback on failure."""
    runtime.mkdir(parents=True, exist_ok=True)
    runtime_root = runtime.resolve()
    backup = Path(tempfile.mkdtemp(prefix=".competitive-update-backup-", dir=runtime.parent))
    moved: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for item in source.iterdir():
            if item.name.lower() in PRESERVED_UPDATE_NAMES:
                continue
            target = runtime / item.name
            if target.resolve().parent != runtime_root:
                raise LoaderError("El paquete oficial contiene un nombre de archivo inseguro.")
            saved = backup / item.name
            if target.exists():
                shutil.move(str(target), str(saved))
                moved.append((saved, target))
            installed.append(target)
            if item.is_file():
                shutil.copy2(item, target)
            elif item.is_dir():
                shutil.copytree(item, target)

        slus = runtime / "gamedata" / "disc" / "SLUS_216.78"
        dbzp = runtime / "gamedata" / "disc" / "BIN" / "DBZP.BIN"
        if not slus.is_file() or not dbzp.is_file():
            raise LoaderError("Faltan los datos competitivos instalados; ejecuta primero Jugar.")
        patch_dat(runtime / "Tenkaichi3Decomp.dat", slus, dbzp)
        _validate_official_release(runtime)
    except Exception:
        for target in reversed(installed):
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        for saved, target in reversed(moved):
            if saved.exists():
                shutil.move(str(saved), str(target))
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)


def latest_release_info() -> dict:
    """Return the latest Windows release metadata without downloading the archive."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers=_github_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            release = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeError, ValueError, urllib.error.URLError) as exc:
        raise LoaderError(f"No se pudo consultar la versión más reciente en GitHub: {exc}") from exc

    asset = next(
        (item for item in release.get("assets", []) if item.get("name") == WINDOWS_ASSET_NAME),
        None,
    )
    if not asset or not asset.get("browser_download_url"):
        raise LoaderError(f"La publicación más reciente no contiene {WINDOWS_ASSET_NAME}.")
    return {
        "tag": str(release.get("tag_name") or "").strip(),
        "asset_id": str(asset.get("id") or ""),
        "asset_updated_at": str(asset.get("updated_at") or ""),
        "download_url": str(asset["browser_download_url"]),
        "size": int(asset.get("size") or 0),
    }


def _download_latest_release(temp: Path, release_info: dict | None = None) -> tuple[Path, str, dict]:
    """Download and validate the latest published Windows release into temp."""
    print("[1/4] Conectando con las publicaciones oficiales de GitHub...")
    info = release_info or {}
    download_url = info.get("download_url", LATEST_WINDOWS_RELEASE)
    archive_path = temp / "Tenkaichi3Decomp-windows-x64.zip"
    request = urllib.request.Request(
        download_url,
        headers=_github_headers("application/octet-stream"),
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            announced = -10
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                received += len(block)
                if total:
                    percent = min(100, received * 100 // total)
                    if percent >= announced + 10:
                        announced = percent // 10 * 10
                        print(f"      Descarga: {announced}%")
    except (OSError, urllib.error.URLError) as exc:
        raise LoaderError(f"No se pudo descargar la última versión desde GitHub: {exc}") from exc

    print("[2/4] Comprobando el paquete descargado...")
    extracted = temp / "release"
    extracted.mkdir()
    release_root = _extract_release_safely(archive_path, extracted)
    new_exe, new_hash = _validate_official_release(release_root)
    del new_exe
    return release_root, new_hash, info


def update_from_github(runtime: Path, release_info: dict | None = None) -> dict:
    """Download, validate and atomically install the latest published Windows release."""
    if _is_game_running():
        raise LoaderError("Cierra Tenkaichi3Decomp antes de actualizar.")
    current_exe = runtime / "Tenkaichi3Decomp.exe"
    if not current_exe.is_file():
        raise LoaderError("CompetitiveRuntime aún no está preparado. Usa primero el botón Jugar.")

    if release_info is None:
        try:
            release_info = latest_release_info()
        except LoaderError as exc:
            print(f"[AVISO] {exc}")
            print("[AUTO] Se comprobará mediante el enlace directo de la última publicación.")
            release_info = {}

    with tempfile.TemporaryDirectory(prefix="competitive-github-update-") as temp_text:
        release_root, new_hash, info = _download_latest_release(Path(temp_text), release_info)
        old_hash = sha256_file(current_exe)
        if new_hash == old_hash:
            print("[OK] Ya tienes la última versión publicada.")
            config = load_config()
            config.update({
                "runtime": str(runtime.resolve()),
                "exe_sha256": new_hash,
                "updated_from": LATEST_WINDOWS_RELEASE,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            if info:
                config.update({
                    "release_tag": info.get("tag", ""),
                    "release_asset_id": info.get("asset_id", ""),
                    "release_asset_updated_at": info.get("asset_updated_at", ""),
                })
            save_config(config)
            return {
                "changed": False,
                "exe_sha256": new_hash,
                "release_tag": info.get("tag", ""),
            }

        print("[3/4] Instalando la actualización con respaldo temporal...")
        _install_release_transactional(release_root, runtime)
        print("[4/4] Actualización instalada y parche competitivo verificado.")

    config = load_config()
    config.update({
        "runtime": str(runtime.resolve()),
        "exe_sha256": new_hash,
        "updated_from": LATEST_WINDOWS_RELEASE,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if info:
        config.update({
            "release_tag": info.get("tag", ""),
            "release_asset_id": info.get("asset_id", ""),
            "release_asset_updated_at": info.get("asset_updated_at", ""),
        })
    save_config(config)
    return {"changed": True, "exe_sha256": new_hash, "release_tag": info.get("tag", "")}


def ensure_latest_release(runtime: Path) -> dict:
    """Check release metadata and update only when GitHub has a different Windows asset."""
    current_exe = runtime / "Tenkaichi3Decomp.exe"
    if not current_exe.is_file():
        raise LoaderError("CompetitiveRuntime aún no está preparado. Usa primero el botón Jugar.")

    print("[AUTO] Comprobando la versión oficial más reciente...")
    info = latest_release_info()
    config = load_config()
    same_asset = bool(info.get("asset_id")) and config.get("release_asset_id") == info["asset_id"]
    expected_hash = config.get("exe_sha256", "")
    if same_asset and expected_hash and sha256_file(current_exe) == expected_hash:
        tag = info.get("tag") or "publicada"
        print(f"[OK] Tenkaichi3Decomp {tag}: ya está actualizado.")
        return {"changed": False, "release_tag": tag, "exe_sha256": expected_hash}

    tag = info.get("tag") or "más reciente"
    print(f"[AUTO] Hay una versión distinta ({tag}); se instalará antes de jugar.")
    return update_from_github(runtime, info)


def patch_dat(dat_path: Path, slus_path: Path, dbzp_path: Path) -> int:
    blob = bytearray(dat_path.read_bytes())
    if len(blob) < 16 or blob[:4] != b"BT3D":
        raise LoaderError("Tenkaichi3Decomp.dat no tiene un formato compatible.")
    count, = struct.unpack_from("<I", blob, 4)
    if count > 1000000 or len(blob) != 16 + count * 16:
        raise LoaderError("Tenkaichi3Decomp.dat está dañado o usa un formato nuevo.")
    sources = [flat_elf(slus_path), dbzp_path.read_bytes()]
    value = FNV_OFFSET
    for index in range(count):
        destination, which, offset, length = struct.unpack_from("<IIII", blob, 16 + index * 16)
        del destination
        if which >= len(sources) or offset + length > len(sources[which]):
            raise LoaderError(f"El registro {index} del .dat apunta fuera de los programas de la ISO.")
        value = fnv_update(value, sources[which][offset:offset + length])
    struct.pack_into("<Q", blob, 8, value)
    dat_path.write_bytes(blob)
    print(f"[4/4] Archivo .dat adaptado (firma {value:016X}).")
    return value


class Section:
    def __init__(self, index: int, name: str, size: int, raw_size: int, raw_ptr: int,
                 reloc_ptr: int, reloc_count: int, characteristics: int, data: bytes):
        self.index = index
        self.name = name
        self.size = max(size, raw_size)
        self.raw_size = raw_size
        self.raw_ptr = raw_ptr
        self.reloc_ptr = reloc_ptr
        self.reloc_count = reloc_count
        self.characteristics = characteristics
        self.data = data
        self.remote = 0
        self.buffer_offset = 0

    @property
    def allocated(self) -> bool:
        return bool(self.characteristics & (0x20 | 0x40 | 0x80)) and not self.name.startswith(".debug")

    @property
    def alignment(self) -> int:
        code = (self.characteristics >> 20) & 0xF
        return 1 << (code - 1) if 1 <= code <= 14 else 16


class Symbol:
    def __init__(self, index: int, name: str, value: int, section: int, storage: int, aux: bool = False):
        self.index, self.name, self.value = index, name, value
        self.section, self.storage, self.aux = section, storage, aux


def coff_name(raw: bytes, strings: bytes) -> str:
    if raw[:4] == b"\0\0\0\0":
        offset, = struct.unpack_from("<I", raw, 4)
        if offset < 4 or offset - 4 >= len(strings):
            return ""
        return strings[offset - 4:].split(b"\0", 1)[0].decode("utf-8", "replace")
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


def section_name(raw: bytes, strings: bytes) -> str:
    short = raw.split(b"\0", 1)[0].decode("ascii", "replace")
    if short.startswith("/") and short[1:].isdigit():
        offset = int(short[1:])
        return strings[offset - 4:].split(b"\0", 1)[0].decode("utf-8", "replace")
    return short


class CoffObject:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) < 20:
            raise LoaderError(f"Payload dañado: {path.name}.")
        machine, nsections, _, symptr, nsymbols, optsize, _ = struct.unpack_from("<HHIIIHH", self.data, 0)
        if machine != 0x8664 or optsize != 0:
            raise LoaderError(f"Payload incompatible: {path.name}.")
        string_pos = symptr + nsymbols * 18
        if string_pos + 4 > len(self.data):
            raise LoaderError(f"Tabla de símbolos dañada: {path.name}.")
        string_size, = struct.unpack_from("<I", self.data, string_pos)
        self.strings = self.data[string_pos + 4:string_pos + max(4, string_size)]
        self.sections: dict[int, Section] = {}
        for index in range(1, nsections + 1):
            pos = 20 + (index - 1) * 40
            raw_name = self.data[pos:pos + 8]
            _, virtual_size, _, raw_size, raw_ptr, reloc_ptr, _, reloc_count, _, chars = struct.unpack_from(
                "<8sIIIIIIHHI", self.data, pos
            )
            name = section_name(raw_name, self.strings)
            # COFF .bss carries its allocation size in SizeOfRawData, with no
            # file contents (PointerToRawData=0). It must stay zero-filled.
            raw = self.data[raw_ptr:raw_ptr + raw_size] if raw_size and raw_ptr and not (chars & 0x80) else b""
            self.sections[index] = Section(index, name, virtual_size, raw_size, raw_ptr,
                                           reloc_ptr, reloc_count, chars, raw)
        self.symbols: list[Symbol] = []
        index = 0
        while index < nsymbols:
            pos = symptr + index * 18
            raw_name = self.data[pos:pos + 8]
            value, sec, _, storage, aux_count = struct.unpack_from("<IhHBB", self.data, pos + 8)
            self.symbols.append(Symbol(index, coff_name(raw_name, self.strings), value, sec, storage))
            for extra in range(aux_count):
                self.symbols.append(Symbol(index + extra + 1, "", 0, 0, 0, True))
            index += 1 + aux_count
        self.by_name = {s.name: s for s in self.symbols if s.name and not s.aux and s.section > 0}

    def relocations(self, section: Section):
        for index in range(section.reloc_count):
            pos = section.reloc_ptr + index * 10
            if pos + 10 > len(self.data):
                raise LoaderError(f"Relocación dañada en {self.path.name}:{section.name}.")
            offset, symbol, kind = struct.unpack_from("<IIH", self.data, pos)
            yield offset, symbol, kind


class PeSymbols:
    def __init__(self, path: Path):
        self.path = path
        data = path.read_bytes()
        if data[:2] != b"MZ":
            raise LoaderError("Tenkaichi3Decomp.exe no es un ejecutable PE válido.")
        peoff, = struct.unpack_from("<I", data, 0x3C)
        if data[peoff:peoff + 4] != b"PE\0\0":
            raise LoaderError("Cabecera PE inválida en Tenkaichi3Decomp.exe.")
        machine, nsections, _, symptr, nsymbols, optsize, _ = struct.unpack_from("<HHIIIHH", data, peoff + 4)
        if machine != 0x8664:
            raise LoaderError("El cargador solo admite la versión oficial Windows x64.")
        opt = peoff + 24
        magic, = struct.unpack_from("<H", data, opt)
        if magic != 0x20B:
            raise LoaderError("El ejecutable oficial no es PE32+ x64.")
        self.preferred_base, = struct.unpack_from("<Q", data, opt + 24)
        secpos = opt + optsize
        sections = {}
        self.raw_sections: list[tuple[int, bytes]] = []
        self.text_rva = 0
        self.text_data = b""
        for index in range(1, nsections + 1):
            pos = secpos + (index - 1) * 40
            name = data[pos:pos + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, virtual_address = struct.unpack_from("<II", data, pos + 8)
            raw_size, raw_pointer = struct.unpack_from("<II", data, pos + 16)
            sections[index] = (name, virtual_address, virtual_size)
            self.raw_sections.append((virtual_address, data[raw_pointer:raw_pointer + raw_size]))
            if name == ".text":
                self.text_rva = virtual_address
                self.text_data = data[raw_pointer:raw_pointer + raw_size]
        if not symptr or not nsymbols:
            raise LoaderError(
                "Esta actualización oficial no conserva su tabla de símbolos. "
                "No se puede adaptar de forma segura."
            )
        string_pos = symptr + nsymbols * 18
        if string_pos + 4 > len(data):
            raise LoaderError("La tabla de símbolos del ejecutable está incompleta.")
        string_size, = struct.unpack_from("<I", data, string_pos)
        strings = data[string_pos + 4:string_pos + max(4, string_size)]
        self.rvas: dict[str, int] = {}
        self.absolute: set[str] = set()
        index = 0
        while index < nsymbols:
            pos = symptr + index * 18
            name = coff_name(data[pos:pos + 8], strings)
            value, sec, _, _, aux_count = struct.unpack_from("<IhHBB", data, pos + 8)
            if name and sec > 0 and sec in sections:
                self.rvas.setdefault(name, sections[sec][1] + value)
            elif name and sec == -1:
                self.rvas.setdefault(name, value)
                self.absolute.add(name)
            index += 1 + aux_count

    def address(self, name: str, actual_base: int) -> int | None:
        rva = self.rvas.get(name)
        if rva is None:
            return None
        # Absolute COFF symbols are values, not RVAs.  Section symbols always
        # use the loaded image base, even when their RVA happens to be small.
        return rva if name in self.absolute else actual_base + rva

    def direct_branches_to(self, name: str) -> list[tuple[int, int]]:
        """Return (instruction RVA, opcode) for direct CALL/JMP rel32 to a symbol.

        Matching an exact 32-bit destination makes accidental byte-pattern
        matches extraordinarily unlikely, while avoiding a bundled x86
        disassembler.  Rewriting these sites complements the function-entry
        jump and covers internal linker paths that can bypass the entry hook.
        """
        target = self.rvas.get(name)
        if target is None or not self.text_data:
            return []
        result = []
        data = self.text_data
        for offset in range(len(data) - 4):
            opcode = data[offset]
            if opcode not in (0xE8, 0xE9):
                continue
            displacement, = struct.unpack_from("<i", data, offset + 1)
            instruction_rva = self.text_rva + offset
            if instruction_rva + 5 + displacement == target:
                result.append((instruction_rva, opcode))
        return result

    def literal_addresses(self, needle: bytes, actual_base: int) -> list[int]:
        """Return loaded addresses of an exact byte string in PE sections."""
        found: list[int] = []
        for section_rva, data in self.raw_sections:
            start = 0
            while True:
                offset = data.find(needle, start)
                if offset < 0:
                    break
                found.append(actual_base + section_rva + offset)
                start = offset + 1
        return found


class PayloadImage:
    def __init__(self, payload_dir: Path, pe: PeSymbols):
        self.pe = pe
        self.objects = [CoffObject(payload_dir / name) for name in PATCH_OBJECTS]
        self.size = 0
        for obj in self.objects:
            for section in obj.sections.values():
                if section.allocated:
                    self.size = align(self.size, max(16, section.alignment))
                    section.buffer_offset = self.size
                    self.size += section.size
        self.size = align(self.size, PAGE)

    def build(self, remote_base: int, actual_image_base: int) -> tuple[bytearray, dict[str, int]]:
        blob = bytearray(self.size)
        definitions: dict[str, int] = {}
        for obj in self.objects:
            for section in obj.sections.values():
                if not section.allocated:
                    continue
                section.remote = remote_base + section.buffer_offset
                blob[section.buffer_offset:section.buffer_offset + len(section.data)] = section.data
            for symbol in obj.symbols:
                sec = obj.sections.get(symbol.section)
                if symbol.name and sec and sec.allocated:
                    definitions.setdefault(symbol.name, sec.remote + symbol.value)

        replacements = {}
        missing_symbols = []
        for target, symbol in PATCH_SYMBOLS.items():
            if symbol in definitions:
                replacements[target] = definitions[symbol]
            else:
                missing_symbols.append(symbol)
        if missing_symbols:
            raise LoaderError("El payload no contiene: " + ", ".join(sorted(missing_symbols)))

        missing: set[str] = set()
        for obj in self.objects:
            for section in obj.sections.values():
                if not section.allocated:
                    continue
                for offset, symbol_index, kind in obj.relocations(section):
                    if symbol_index >= len(obj.symbols):
                        raise LoaderError(f"Símbolo de relocación inválido en {obj.path.name}.")
                    symbol = obj.symbols[symbol_index]
                    target_section = obj.sections.get(symbol.section)
                    # A compiled object also defines every unchanged global from
                    # its source file.  Those references must keep using the
                    # official executable (especially globals such as gChrView),
                    # while local/static symbols stay inside the mapped object.
                    # Only the explicit replacement functions point to payload.
                    official = self.pe.address(symbol.name, actual_image_base) if symbol.name else None
                    if symbol.name in ENTRY_PATCH_TARGETS:
                        target = replacements[symbol.name]
                    elif target_section and target_section.allocated and symbol.storage != 2:
                        target = target_section.remote + symbol.value
                    elif symbol.storage == 2 and official is not None:
                        target = official
                    elif target_section and target_section.allocated:
                        target = target_section.remote + symbol.value
                    elif symbol.section == -1:
                        target = symbol.value
                    else:
                        target = official
                        if target is None:
                            missing.add(symbol.name or f"#{symbol_index}")
                            continue
                    place_off = section.buffer_offset + offset
                    place = remote_base + place_off
                    self._apply(blob, place_off, kind, target, place, actual_image_base,
                                f"{obj.path.name}:{section.name}+{offset:X}")
        if missing:
            shown = ", ".join(sorted(missing)[:30])
            suffix = "..." if len(missing) > 30 else ""
            raise LoaderError(
                "La actualización oficial cambió símbolos que necesita el parche: " + shown + suffix
            )
        return blob, replacements

    @staticmethod
    def _apply(blob: bytearray, pos: int, kind: int, target: int, place: int,
               image_base: int, where: str):
        try:
            if kind == 0x0001:  # ADDR64
                addend, = struct.unpack_from("<Q", blob, pos)
                struct.pack_into("<Q", blob, pos, (target + addend) & 0xFFFFFFFFFFFFFFFF)
            elif kind == 0x0002:  # ADDR32
                addend, = struct.unpack_from("<I", blob, pos)
                value = target + addend
                if not 0 <= value <= 0xFFFFFFFF:
                    raise LoaderError(f"Dirección de 32 bits fuera de rango en {where}.")
                struct.pack_into("<I", blob, pos, value)
            elif kind == 0x0003:  # ADDR32NB
                addend, = struct.unpack_from("<I", blob, pos)
                value = target + addend - image_base
                if not 0 <= value <= 0xFFFFFFFF:
                    raise LoaderError(f"RVA fuera de rango en {where}.")
                struct.pack_into("<I", blob, pos, value)
            elif 0x0004 <= kind <= 0x0009:  # REL32 and REL32_1..5
                addend, = struct.unpack_from("<i", blob, pos)
                extra = kind - 0x0004
                value = target + addend - (place + 4 + extra)
                if not -0x80000000 <= value <= 0x7FFFFFFF:
                    raise LoaderError(f"Salto relativo fuera de rango en {where}.")
                struct.pack_into("<i", blob, pos, value)
            elif kind == 0x000A:  # SECTION
                raise LoaderError(f"Relocación SECTION no compatible en {where}.")
            elif kind == 0x000B:  # SECREL
                raise LoaderError(f"Relocación SECREL no compatible en sección cargable: {where}.")
            else:
                raise LoaderError(f"Relocación AMD64 desconocida 0x{kind:04X} en {where}.")
        except struct.error as exc:
            raise LoaderError(f"Relocación fuera de la sección en {where}.") from exc


def validate_payload(payload_dir: Path, exe_path: Path) -> PayloadImage:
    if RELEASE_PROFILE:
        use_official_online_profile(exe_path, audio_fix=True, competitive_times=True, session_score=True)
    missing = [name for name in PATCH_OBJECTS if not (payload_dir / name).is_file()]
    if missing:
        raise LoaderError("Faltan archivos del payload: " + ", ".join(missing))
    pe = PeSymbols(exe_path)
    absent = sorted(name for name in PATCH_TARGETS if name not in pe.rvas)
    if absent:
        raise LoaderError(
            "La actualización oficial no contiene las funciones esperadas: " + ", ".join(absent)
        )
    return PayloadImage(payload_dir, pe)


def _windows_api():
    if os.name != "nt":
        raise LoaderError("El inicio con parche solo funciona en Windows x64.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    return kernel32, ntdll


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)), ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p), ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2_0", ctypes.c_void_p), ("Reserved2_1", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_void_p), ("Reserved3", ctypes.c_void_p),
    ]


def win_error(action: str) -> LoaderError:
    return LoaderError(f"Windows no pudo {action}: {ctypes.WinError(ctypes.get_last_error())}")


def _environment_block(overrides: dict[str, str | None] | None):
    if not overrides:
        return None
    values = dict(os.environ)
    for name, value in overrides.items():
        if value is None:
            values.pop(name, None)
        else:
            values[name] = str(value)
    text = "\0".join(f"{name}={value}" for name, value in sorted(values.items(), key=lambda item: item[0].upper())) + "\0\0"
    return ctypes.create_unicode_buffer(text)


def launch_patched(
    exe_path: Path,
    image: PayloadImage,
    wait: bool = False,
    env: dict[str, str | None] | None = None,
    stage_memory: bool = True,
    log_name: str = "competitive_loader.log",
    game_log: Path | None = None,
    convert_intro: bool = True,
    game_output_fd: int | None = None,
):
    launch_env = dict(env or {})
    online_hash = ""

    if convert_intro:
        ensure_intro_compatible(exe_path.parent)

    if stage_memory:
        online_hash = stage_online_memory(exe_path.parent)
        if online_hash:
            print(f"[ONLINE] Memory competitiva preparada: {online_hash}")
            print("[ONLINE] Ambos jugadores deben mostrar exactamente el mismo SHA-256.")
            print("[ONLINE] Mantén Competitive Loader abierto durante toda la sesión online.")
        else:
            print("[AVISO] No hay una memory instalada para el online; se usará la sesión vacía del decomp.")

    launch_env["BT3_COMPETITIVE_LOADER_VERSION"] = APP_VERSION_TEXT
    launch_env["BT3_COMPETITIVE_MEMORY_SHA256"] = online_hash or "none"

    kernel32, ntdll = _windows_api()
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
        wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.WriteProcessMemory.restype = wintypes.BOOL
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.VirtualProtectEx.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.FlushInstructionCache.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t]
    kernel32.FlushInstructionCache.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    ntdll.NtQueryInformationProcess.argtypes = [
        wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
    ]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()
    log_stream = input_stream = None
    if game_log is not None and game_output_fd is not None:
        raise LoaderError("El registro del juego debe usar un solo destino.")
    capture_output = game_log is not None or game_output_fd is not None
    if capture_output:
        import msvcrt
        log_stream = game_log.open("wb") if game_log is not None else os.fdopen(os.dup(game_output_fd), "wb", buffering=0)
        input_stream = open(os.devnull, "rb")
        si.dwFlags |= 0x00000100  # STARTF_USESTDHANDLES
        si.hStdOutput = si.hStdError = msvcrt.get_osfhandle(log_stream.fileno())
        si.hStdInput = msvcrt.get_osfhandle(input_stream.fileno())
        os.set_handle_inheritable(si.hStdOutput, True)
        os.set_handle_inheritable(si.hStdInput, True)
    command = ctypes.create_unicode_buffer(f'"{exe_path}"')
    environment = _environment_block(launch_env)
    creation_flags = 0x00000004 | (0x00000400 if environment is not None else 0)
    try:
        created = kernel32.CreateProcessW(
            str(exe_path), command, None, None, capture_output, creation_flags,
            ctypes.cast(environment, ctypes.c_void_p) if environment is not None else None,
            str(exe_path.parent), ctypes.byref(si), ctypes.byref(pi),
        )
    finally:
        if log_stream is not None:
            log_stream.close()
        if input_stream is not None:
            input_stream.close()
    if not created:
        raise win_error("crear el proceso del juego")

    success = False
    try:
        pbi = PROCESS_BASIC_INFORMATION()
        returned = wintypes.ULONG()
        status = ntdll.NtQueryInformationProcess(
            pi.hProcess, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(returned)
        )
        if status != 0:
            raise LoaderError(f"No se pudo consultar el proceso suspendido (NTSTATUS 0x{status & 0xFFFFFFFF:08X}).")
        base_buf = ctypes.c_void_p()
        got = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            pi.hProcess, ctypes.c_void_p(pbi.PebBaseAddress + 0x10),
            ctypes.byref(base_buf), ctypes.sizeof(base_buf), ctypes.byref(got)
        ):
            raise win_error("leer la base del ejecutable")
        actual_base = int(base_buf.value or 0)
        if not actual_base:
            raise LoaderError("Windows devolvió una base de imagen inválida.")

        remote = 0
        for candidate in range(0x30000000, 0x78000000, 0x01000000):
            allocated = kernel32.VirtualAllocEx(
                pi.hProcess, ctypes.c_void_p(candidate), image.size, 0x3000, 0x40
            )
            if allocated:
                remote = int(allocated)
                break
        if not remote:
            raise win_error("reservar memoria compatible para el parche")

        blob, replacements = image.build(remote, actual_base)
        source = (ctypes.c_ubyte * len(blob)).from_buffer(blob)
        written = ctypes.c_size_t()
        if not kernel32.WriteProcessMemory(
            pi.hProcess, ctypes.c_void_p(remote), source, len(blob), ctypes.byref(written)
        ) or written.value != len(blob):
            raise win_error("escribir el payload")

        def write_code(address: int, data: bytes, label: str):
            old = wintypes.DWORD()
            if not kernel32.VirtualProtectEx(
                pi.hProcess, ctypes.c_void_p(address), len(data), 0x40, ctypes.byref(old)
            ):
                raise win_error(f"habilitar {label}")
            patch_buf = ctypes.create_string_buffer(data)
            if not kernel32.WriteProcessMemory(
                pi.hProcess, ctypes.c_void_p(address), patch_buf, len(data), ctypes.byref(written)
            ) or written.value != len(data):
                raise win_error(f"escribir {label}")
            check_buf = ctypes.create_string_buffer(len(data))
            checked = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(
                pi.hProcess, ctypes.c_void_p(address), check_buf, len(data), ctypes.byref(checked)
            ) or checked.value != len(data) or check_buf.raw != data:
                raise LoaderError(f"Windows no confirmó {label} después de escribirlo.")
            restored = wintypes.DWORD()
            kernel32.VirtualProtectEx(
                pi.hProcess, ctypes.c_void_p(address), len(data), old.value, ctypes.byref(restored)
            )

        direct_count = 0
        direct_by_target = {}
        for name in sorted(PATCH_TARGETS):
            target = image.pe.address(name, actual_base)
            replacement = replacements[name]
            if target is None:
                raise LoaderError(f"No se encontró {name} al aplicar el parche.")
            if name in ENTRY_PATCH_TARGETS:
                displacement = replacement - (target + 5)
                if not -0x80000000 <= displacement <= 0x7FFFFFFF:
                    raise LoaderError(f"El salto para {name} quedó fuera de rango.")
                jump = struct.pack("<Bi", 0xE9, displacement)
                write_code(target, jump, f"el parche de entrada de {name}")

            count = 0
            for branch_rva, opcode in image.pe.direct_branches_to(name):
                branch = actual_base + branch_rva
                branch_displacement = replacement - (branch + 5)
                if not -0x80000000 <= branch_displacement <= 0x7FFFFFFF:
                    raise LoaderError(f"La llamada directa a {name} quedó fuera de rango.")
                write_code(
                    branch, struct.pack("<Bi", opcode, branch_displacement),
                    f"la llamada directa a {name} en +0x{branch_rva:X}",
                )
                count += 1
            direct_by_target[name] = count
            direct_count += count

        data_patch_count = 0
        for original, replacement in ONLINE_TIME_LABEL_PATCHES.items():
            addresses = image.pe.literal_addresses(original, actual_base)
            if len(addresses) != 1:
                label = original.rstrip(b"\0").decode("ascii", "replace")
                raise LoaderError(
                    f"La etiqueta de tiempo '{label}' apareció {len(addresses)} veces; "
                    "esta versión oficial no se puede adaptar con seguridad."
                )
            write_code(addresses[0], replacement, "la etiqueta de tiempo online")
            data_patch_count += 1
        kernel32.FlushInstructionCache(pi.hProcess, None, 0)

        log_lines = [
            APP_NAME,
            time.strftime("%Y-%m-%d %H:%M:%S"),
            f"exe={exe_path}",
            f"exe_sha256={sha256_file(exe_path)}",
            f"pid={int(pi.dwProcessId)}",
            f"image_base=0x{actual_base:X}",
            f"payload_base=0x{remote:X}",
            f"entry_patches={len(ENTRY_PATCH_TARGETS)}",
            f"call_wrappers={len(CALL_WRAPPER_TARGETS)}",
            f"direct_branches={direct_count}",
            f"data_patches={data_patch_count}",
        ]
        log_lines.extend(f"{name} direct={direct_by_target[name]}" for name in sorted(direct_by_target))
        (exe_path.parent / log_name).write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        if kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            raise win_error("iniciar el juego")
        success = True
        print(
            f"[OK] Juego iniciado con {len(ENTRY_PATCH_TARGETS)} entradas, "
            f"{len(CALL_WRAPPER_TARGETS)} extensiones y "
            f"{direct_count} llamadas competitivas verificadas."
        )
        if wait:
            kernel32.WaitForSingleObject(pi.hProcess, 0xFFFFFFFF)
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)):
                raise win_error("leer el resultado del juego")
            return int(exit_code.value)
        return int(pi.dwProcessId)
    finally:
        if not success:
            kernel32.TerminateProcess(pi.hProcess, 1)
        kernel32.CloseHandle(pi.hThread)
        kernel32.CloseHandle(pi.hProcess)


def choose_file(title: str, patterns: list[tuple[str, str]]) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        value = filedialog.askopenfilename(title=title, filetypes=patterns)
        root.destroy()
        return Path(value) if value else None
    except Exception:
        return None


def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(values: dict):
    CONFIG.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")


def save_checksum_ok(path: Path) -> bool:
    data = path.read_bytes()
    if len(data) != 0x4000:
        return False
    stored_hi, stored_lo = struct.unpack_from("<II", data)
    total = 0
    for index, byte in enumerate(data[8:]):
        total = (total + (byte << 8 if index & 1 else byte)) & 0xFFFF
    return stored_hi == total >> 8 and stored_lo == (total & 0xFF)


def online_memory_fingerprint(runtime: Path) -> str | None:
    """Hash of the installed save data that affects competitive character balance."""
    main_save = runtime / "saves" / "card1" / SAVE_NAME / SAVE_NAME
    if not main_save.is_file() or not save_checksum_ok(main_save):
        return None
    return sha256_file(main_save)


def _release_online_memory_handles():
    global _ONLINE_SAVE_HANDLES
    if not _ONLINE_SAVE_HANDLES:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    for handle in _ONLINE_SAVE_HANDLES:
        kernel32.CloseHandle(wintypes.HANDLE(handle))
    _ONLINE_SAVE_HANDLES = []


def online_memory_guard_active() -> bool:
    return bool(_ONLINE_SAVE_HANDLES)


def stage_online_memory(runtime: Path) -> str | None:
    """Mirror the personal save into net_session and deny deletion while the loader remains open.

    Tenkaichi3Decomp intentionally calls remove() for the session save. Holding each file open while
    sharing reads and writes—but not deletion—keeps the common competitive save available without
    modifying or recompiling the official executable.
    """
    global _ONLINE_SAVE_HANDLES
    source = runtime / "saves" / "card1" / SAVE_NAME
    for name, expected_size in SAVE_FILE_SIZES.items():
        candidate = source / name
        if not candidate.is_file() or candidate.stat().st_size != expected_size:
            return None
    if not save_checksum_ok(source / SAVE_NAME):
        raise LoaderError("La memory instalada tiene un checksum inválido y no puede usarse online.")

    _release_online_memory_handles()
    destination = runtime / "net_session" / "card1" / SAVE_NAME
    destination.mkdir(parents=True, exist_ok=True)
    for name in SAVE_FILE_SIZES:
        shutil.copy2(source / name, destination / name)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    open_existing = 3
    generic_read = 0x80000000
    share_read_write = 0x00000001 | 0x00000002
    invalid_handle = ctypes.c_void_p(-1).value
    handles: list[int] = []
    try:
        for name in SAVE_FILE_SIZES:
            handle = kernel32.CreateFileW(
                str(destination / name), generic_read, share_read_write, None,
                open_existing, 0x00000080, None,
            )
            handle_value = int(handle) if handle is not None else invalid_handle
            if handle_value == invalid_handle:
                raise win_error(f"proteger {name} para el online")
            handles.append(handle_value)
    except Exception:
        for handle in handles:
            kernel32.CloseHandle(wintypes.HANDLE(handle))
        raise
    _ONLINE_SAVE_HANDLES = handles

    fingerprint = sha256_file(destination / SAVE_NAME)
    (runtime / "ONLINE_MEMORY_SHA256.txt").write_text(
        "MEMORY COMPETITIVA ONLINE\n"
        f"SHA-256: {fingerprint}\n\n"
        "Los dos jugadores deben tener exactamente el mismo SHA-256.\n"
        "Inicia siempre desde Competitive Loader y mantenlo abierto durante la partida.\n",
        encoding="utf-8",
    )
    return fingerprint


def import_ps2_card(card: Path, runtime: Path):
    if not card.is_file():
        raise LoaderError(f"No existe la tarjeta de PCSX2: {card}")
    if not (runtime / "Tenkaichi3Decomp.exe").is_file():
        raise LoaderError(
            "CompetitiveRuntime todavía no está preparado. Ejecuta primero Iniciar Competitive.bat."
        )
    try:
        running = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Tenkaichi3Decomp.exe", "/NH"],
            capture_output=True, text=True, errors="replace", check=False,
        ).stdout.lower()
        if "tenkaichi3decomp.exe" in running:
            raise LoaderError("Cierra Tenkaichi3Decomp antes de importar la memoria.")
    except OSError:
        pass

    try:
        from ps2_save import CardError, extract_save
    except ImportError as exc:
        raise LoaderError("Falta ps2_save.py junto al cargador.") from exc

    print(f"Tarjeta: {card}")
    print(f"SHA-256: {sha256_file(card)}")
    with tempfile.TemporaryDirectory(prefix="bt3-save-import-") as temp:
        extracted = Path(temp) / SAVE_NAME
        try:
            extract_save(card, SAVE_NAME, extracted)
        except CardError as exc:
            raise LoaderError(f"No se pudo leer la tarjeta de PCSX2: {exc}") from exc
        main_save = extracted / SAVE_NAME
        for name, expected_size in SAVE_FILE_SIZES.items():
            candidate = extracted / name
            if not candidate.is_file() or candidate.stat().st_size != expected_size:
                raise LoaderError(f"La partida extraída no contiene un {name} válido.")
        if not save_checksum_ok(main_save):
            raise LoaderError("El checksum interno de la partida de PCSX2 no es válido.")

        destination = runtime / "saves" / "card1" / SAVE_NAME
        backup = None
        if destination.exists():
            backup_root = runtime / "save-backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = backup_root / f"{SAVE_NAME}-{stamp}"
            suffix = 2
            while backup.exists():
                backup = backup_root / f"{SAVE_NAME}-{stamp}-{suffix}"
                suffix += 1
            shutil.copytree(destination, backup)

        destination.mkdir(parents=True, exist_ok=True)
        for name in SAVE_FILE_SIZES:
            shutil.copy2(extracted / name, destination / name)

    if not save_checksum_ok(destination / SAVE_NAME):
        raise LoaderError("La verificación posterior a la copia falló.")
    print("[OK] Partida de PCSX2 importada y verificada.")
    fingerprint = sha256_file(destination / SAVE_NAME)
    config = load_config()
    config["online_memory_sha256"] = fingerprint
    save_config(config)
    print(f"[ONLINE] SHA-256 de balance: {fingerprint}")
    print(f"Destino: {destination}")
    if backup is not None:
        print(f"Respaldo anterior: {backup}")
    return fingerprint


def prepare(release: Path, iso: Path, runtime: Path, force_iso: bool = False) -> Path:
    if not release.exists():
        raise LoaderError(f"No existe la actualización oficial: {release}")
    if not iso.is_file():
        raise LoaderError(f"No existe la ISO competitiva: {iso}")
    exe = copy_official_release(release, runtime)
    slus, dbzp = verify_or_install_iso(iso, runtime, force_iso)
    ensure_intro_compatible(runtime)
    patch_dat(runtime / "Tenkaichi3Decomp.dat", slus, dbzp)
    image = validate_payload(PAYLOAD, exe)
    # A full dry relocation catches missing symbols before a process is created.
    image.build(0x60000000, image.pe.preferred_base)
    state = {
        "release": str(release.resolve()), "iso": str(iso.resolve()),
        "runtime": str(runtime.resolve()), "exe_sha256": sha256_file(exe),
    }
    save_config(state)
    (runtime / "IMPORTANTE - iniciar con Competitive Loader.txt").write_text(
        "No abras Tenkaichi3Decomp.exe directamente.\n\n"
        "Inicia el juego con 'Competitive Loader.exe'.\n"
        "El parche competitivo se aplica al proceso durante ese arranque.\n",
        encoding="utf-8",
    )
    print(f"[OK] Actualización compatible: {state['exe_sha256'][:16]}...")
    return exe


def prepare_from_github(iso: Path, runtime: Path) -> Path:
    """First-time setup: the user supplies only the Competitive ISO."""
    if not iso.is_file():
        raise LoaderError(f"No existe la ISO competitiva: {iso}")
    if _is_game_running():
        raise LoaderError("Cierra Tenkaichi3Decomp antes de preparar la instalación.")

    with tempfile.TemporaryDirectory(prefix="competitive-github-setup-") as temp_text:
        try:
            release_info = latest_release_info()
        except LoaderError as exc:
            print(f"[AVISO] {exc}")
            print("[AUTO] Se usará el enlace directo de la publicación más reciente.")
            release_info = {}
        release_root, release_hash, release_info = _download_latest_release(Path(temp_text), release_info)
        exe = prepare(release_root, iso, runtime)

    state = load_config()
    state.pop("release", None)
    state.update({
        "release_source": LATEST_WINDOWS_RELEASE,
        "runtime": str(runtime.resolve()),
        "iso": str(iso.resolve()),
        "exe_sha256": release_hash,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if release_info:
        state.update({
            "release_tag": release_info.get("tag", ""),
            "release_asset_id": release_info.get("asset_id", ""),
            "release_asset_updated_at": release_info.get("asset_updated_at", ""),
        })
    save_config(state)
    return exe


def interactive(args) -> tuple[Path, Path, Path]:
    cfg = load_config()
    release_value = args.release or (None if args.select_release else cfg.get("release", ""))
    release = Path(release_value) if release_value else None
    iso = Path(args.iso or cfg.get("iso", "")) if (args.iso or cfg.get("iso")) else None
    runtime = Path(args.runtime or cfg.get("runtime", DEFAULT_RUNTIME))

    if release is None or not release.exists():
        release = choose_file(
            "Elige el ZIP oficial de Tenkaichi3Decomp",
            [("Tenkaichi3Decomp ZIP", "*.zip"), ("Todos", "*.*")],
        )
        if release is None:
            text = input("Ruta del ZIP o carpeta oficial de Tenkaichi3Decomp: ").strip().strip('"')
            release = Path(text)
    if iso is None or not iso.is_file():
        iso = choose_file(
            "Elige DBZ Competitive Edition v8.4.1",
            [("Imagen ISO", "*.iso"), ("Todos", "*.*")],
        )
        if iso is None:
            text = input("Ruta de DBZ Competitive Edition v8.4.1.iso: ").strip().strip('"')
            iso = Path(text)
    return release, iso, runtime


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--release", help="ZIP o carpeta de una versión oficial Windows x64")
    parser.add_argument("--iso", help="ISO DBZ Competitive Edition v8.4.1")
    parser.add_argument("--runtime", help="carpeta separada donde preparar el juego")
    parser.add_argument("--select-release", action="store_true", help="elegir otra actualización oficial")
    parser.add_argument("--prepare-only", action="store_true", help="preparar sin iniciar")
    parser.add_argument("--force-iso", action="store_true", help="volver a extraer la ISO")
    parser.add_argument("--check", action="store_true", help="comprobar compatibilidad sin iniciar")
    parser.add_argument("--update-github", action="store_true", help="instalar la última versión oficial publicada")
    parser.add_argument("--import-card", help="importar una tarjeta .ps2 sin iniciar el juego")
    parser.add_argument("--import-card-select", action="store_true", help="elegir una tarjeta .ps2 e importarla")
    args = parser.parse_args()

    print(f"\n{APP_NAME}\n{'=' * len(APP_NAME)}")
    if args.update_github:
        cfg = load_config()
        runtime = Path(args.runtime or cfg.get("runtime", DEFAULT_RUNTIME))
        update_from_github(runtime)
        return 0
    if args.import_card or args.import_card_select:
        cfg = load_config()
        runtime = Path(args.runtime or cfg.get("runtime", DEFAULT_RUNTIME))
        card = Path(args.import_card) if args.import_card else choose_file(
            "Elige la tarjeta de memoria de PCSX2",
            [("Tarjeta de PS2", "*.ps2"), ("Todos", "*.*")],
        )
        if card is None:
            text = input("Ruta de la tarjeta .ps2: ").strip().strip('"')
            card = Path(text)
        import_ps2_card(card, runtime)
        return 0
    release, iso, runtime = interactive(args)
    exe = prepare(release, iso, runtime, args.force_iso)
    if args.prepare_only or args.check:
        print(f"\nListo: {runtime}")
        return 0
    print("\nAplicando el parche temporal e iniciando el juego...")
    image = validate_payload(PAYLOAD, exe)
    launch_patched(exe, image)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelado.")
        raise SystemExit(130)
    except LoaderError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("\nNo se modificó el ZIP oficial ni la ISO.", file=sys.stderr)
        input("Presiona Enter para cerrar...") if sys.stdin.isatty() else None
        raise SystemExit(1)
