"""Isolated, pinned Windows online test. Never uses the public matchmaking service."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import competitive_loader as loader


def configure(runtime: Path, session_score: bool = False, release_profile: bool = False):
    exe = runtime / "Tenkaichi3Decomp.exe"
    loader.use_official_online_profile(exe, audio_fix=release_profile, competitive_times=release_profile, session_score=session_score or release_profile)
    image = loader.validate_payload(loader.PAYLOAD, exe)
    image.build(0x60000000, image.pe.preferred_base)
    return exe, image


def prepare(args):
    root = args.lab.resolve()
    if root.exists():
        raise loader.LoaderError("Usa una carpeta de laboratorio nueva; no se sobrescriben pruebas.")
    if root == args.release.resolve() or root in args.release.resolve().parents:
        raise loader.LoaderError("El laboratorio debe estar separado de la publicación original.")
    configure(args.release.resolve())
    root.mkdir(parents=True)
    host = root / "host"
    shutil.copytree(args.release, host)
    slus, dbzp = loader._extract_competitive_iso(args.iso, host / "gamedata")
    loader.patch_dat(host / "Tenkaichi3Decomp.dat", slus, dbzp)
    loader.import_ps2_card(args.card, host)
    print("Copiando el segundo runtime aislado...", flush=True)
    shutil.copytree(host, root / "guest")
    manifest = {
        "profile": "official-online-lab", "status": "experimental",
        "exe_sha256": loader.sha256_file(host / "Tenkaichi3Decomp.exe"),
        "iso_sha256": loader.sha256_file(args.iso),
        "card_sha256": loader.sha256_file(args.card),
        "payload": {p.name: loader.sha256_file(p) for p in sorted(loader.PAYLOAD.glob("*.o"))
                    if p.name in loader.PATCH_OBJECTS},
        "limitations": "Official timers; no custom score, window lock or legacy ADX/intro patch."
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Preparado: {root}", flush=True)


def signature(runtime: Path):
    # Full game tree and save: no incompatible pair is knowingly started.
    paths = [runtime / "Tenkaichi3Decomp.exe", runtime / "Tenkaichi3Decomp.dat"]
    for name in ("gamedata", "saves"):
        paths.extend(p for p in (runtime / name).rglob("*") if p.is_file())
    result = {}
    def fingerprint(path):
        return path.relative_to(runtime).as_posix(), loader.sha256_file(path)
    print(f"Verificando {runtime.name}: {len(paths)} archivos...", flush=True)
    with ThreadPoolExecutor(max_workers=16) as pool:
        for number, (name, digest) in enumerate(pool.map(fingerprint, paths), 1):
            result[name] = digest
            if number % 10000 == 0:
                print(f"  {runtime.name}: {number}/{len(paths)}", flush=True)
    return result


def worker(args):
    runtime = (args.lab / args.worker).resolve()
    exe, image = configure(runtime, args.session_score, args.release_profile)
    env = {key: None for key in os.environ if key.startswith("BT3_")}
    env.update({
        "BT3_NET_SESSION": "1", "BT3_NET_ROLLBACK": str(args.rollback),
        "BT3_NET_DELAY": "2", "BT3_NET_SEED": "123456", "BT3_NET_RULES": "0",
        "BT3_HASH": str(runtime / "state-hashes.txt"), "BT3_GS_VERBOSE": "1",
        "BT3_VIEW": "0", "BT3_HUD_SWAP": "1", "BT3_PACED": "1",
        "BT3_NET_LAG": str(args.lag), "BT3_NET_LOSS": str(args.loss),
    })
    if args.release_profile:
        env["BT3_NET_SESSION"] = None
        env["BT3_NOMOVIE"] = "1"
        role = 1 if args.worker == "host" else 2
        env["BT3_SESSION_TEST"] = f"{role}:127.0.0.1:{args.port}:180"
    elif args.worker == "host":
        env["BT3_NET_HOST"] = str(args.port)
    else:
        env["BT3_NET_JOIN"] = f"127.0.0.1:{args.port}"
        if args.slow_start:
            env["BT3_TEST_SLOW_START"] = str(args.slow_start)
    env["BT3_NET_NAME"] = "TU - MANUAL" if args.manual_host and args.worker == "host" else "RIVAL - AUTO" if args.manual_host else args.worker
    if args.script and not (args.manual_host and args.worker == "host"):
        env["BT3_NET_SCRIPT"] = str(args.script.resolve())
    pid = loader.launch_patched(exe, image, env=env, game_log=runtime / "game.log", convert_intro=False)
    (runtime / "test-process.json").write_text(json.dumps({"pid": pid}), encoding="utf-8")
    kernel, _ = loader._windows_api()
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    handle = kernel.OpenProcess(0x00101001, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION | TERMINATE
    if not handle:
        raise loader.win_error("seguir el proceso de prueba")
    try:
        status = kernel.WaitForSingleObject(handle, args.seconds * 1000)
        if status == 0x102:
            kernel.TerminateProcess(handle, 0)
        elif status == 0xFFFFFFFF:
            kernel.TerminateProcess(handle, 1)
            raise loader.win_error("esperar el proceso de prueba")
        kernel.WaitForSingleObject(handle, 5000)
        code = ctypes.c_uint32()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise loader.win_error("leer la salida del proceso de prueba")
        (runtime / "test-process.json").write_text(json.dumps({
            "pid": pid, "exit_code": f"0x{code.value:08X}", "timed_stop": status == 0x102,
        }), encoding="utf-8")
        if code.value != 0:
            raise loader.LoaderError(f"El juego terminó con 0x{code.value:08X}; revisa game.log.")
    finally:
        kernel.CloseHandle(handle)


def read_hashes(path: Path):
    result = {}
    if path.exists():
        for line in path.read_text(errors="replace").splitlines(keepends=True):
            if not line.endswith("\n"):
                continue  # A timed stop can leave the final record half-written.
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit():
                if "hp" in parts and any(label not in parts for label in ("pos", "clock", "rnd")):
                    continue
                # Keep the LAST simulation of a blank, after rollback corrections.
                result[int(parts[0])] = parts
    return result


def analyze(root: Path):
    a, b = [read_hashes(root / side / "state-hashes.txt") for side in ("host", "guest")]
    common = sorted(a.keys() & b.keys())
    fights = [tick for tick in common if "hp" in a[tick] and "hp" in b[tick]]
    # Compare health, positions and clock; exclude view-dependent generator and raw whole-state hashes.
    differences = [tick for tick in fights if a[tick][3:a[tick].index("rnd")] != b[tick][3:b[tick].index("rnd")]]
    logs = "\n".join((root / side / "game.log").read_text(errors="replace")
                     for side in ("host", "guest") if (root / side / "game.log").exists())
    desync = "the two games differ at blank" in logs or "The two games no longer agree" in logs
    report = {"common_blanks": len(common), "common_fight_blanks": len(fights),
              "first_observed_fight_difference": differences[0] if differences else None,
              "native_desync_reported": desync,
              "result": "DIVERGENCE" if differences or desync else "INCONCLUSIVE" if not fights else "NO_DIVERGENCE_OBSERVED",
              "note": "Finite test; hash lines may lose a buffered tail when timed out. A difference needs correlation with native confirmed-input checks."}
    (root / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def run(args):
    root = args.lab.resolve()
    if (root / "result.json").exists() or any((root / side / "game.log").exists() for side in ("host", "guest")):
        raise loader.LoaderError("Esta prueba ya tiene registros; prepara otro laboratorio para conservarlos.")
    if signature(root / "host") != signature(root / "guest"):
        raise loader.LoaderError("Los datos, partidas o ejecutables de las dos instancias difieren.")
    for side in ("host", "guest"):
        configure(root / side, args.session_score, args.release_profile)
    children = []
    try:
        for side in ("host", "guest"):
            launcher = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve())]
            command = launcher + ["run", "--lab", str(root),
                       "--worker", side, "--port", str(args.port), "--seconds", str(args.seconds),
                       "--rollback", str(args.rollback), "--lag", str(args.lag), "--loss", str(args.loss),
                       "--slow-start", str(args.slow_start)]
            if args.manual_host:
                command += ["--manual-host"]
            if args.release_profile:
                command += ["--release-profile"]
            if args.session_score:
                command += ["--session-score"]
            if args.script:
                command += ["--script", str(args.script.resolve())]
            stream = (root / side / "worker.log").open("w", encoding="utf-8")
            try:
                children.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                                  creationflags=subprocess.CREATE_NO_WINDOW))
            finally:
                stream.close()
            time.sleep(0.3)
        for process in children:
            process.wait()
        if any(p.returncode for p in children):
            raise loader.LoaderError("Falló una instancia; revisa host/worker.log y guest/worker.log.")
    finally:
        for process in children:
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    return analyze(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    for arg in ("release", "iso", "card", "lab"):
        p.add_argument("--" + arg, type=Path, required=True)
    p = sub.add_parser("run")
    p.add_argument("--lab", type=Path, required=True)
    p.add_argument("--worker", choices=("host", "guest"), help=argparse.SUPPRESS)
    p.add_argument("--port", type=int, default=27935)
    p.add_argument("--seconds", type=int, default=120)
    p.add_argument("--rollback", type=int, choices=range(0, 9), default=8)
    p.add_argument("--lag", type=int, default=0)
    p.add_argument("--loss", type=int, choices=range(0, 101), default=0)
    p.add_argument("--slow-start", type=int, default=0)
    p.add_argument("--script", type=Path)
    p.add_argument("--manual-host", action="store_true", help="Host uses real controls; only guest plays the input script")
    p.add_argument("--release-profile", action="store_true", help="Include audio, competitive timers and scoreboard")
    p.add_argument("--session-score", action="store_true", help="Test the persistent scoreboard with official timers")
    p = sub.add_parser("analyze")
    p.add_argument("--lab", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "analyze":
        analyze(args.lab)
    elif args.worker:
        worker(args)
    else:
        run(args)


if __name__ == "__main__":
    try:
        main()
    except (loader.LoaderError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
