"""Separate developer lab: record a CPU/CPU clip, then replay it in one P1/P2 window."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import struct
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import competitive_loader as core
from replay_spectator import BLOCK,HEADER,FILE_SIZE,COUNTS,clean_environment,isolated_runtime,watch


def record(source,root,seconds=20):
    runtime=isolated_runtime(source,root)
    core.RELEASE_PROFILE=True
    image=core.validate_payload(core.PAYLOAD,runtime/'Tenkaichi3Decomp.exe')
    env=clean_environment(source)
    env.update(BT3_DEMO='1',BTC_REPLAY_RECORD_CPU='1',BT3_GS='none',BT3_PACED='1',BT3_TRACE='120')
    pid=core.launch_patched(runtime/'Tenkaichi3Decomp.exe',image,env=env,game_log=runtime/'record.log',convert_intro=False,stage_memory=False)
    k,n=core._windows_api()
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    k.ReadProcessMemory.restype=W.BOOL
    k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
    k.TerminateProcess.argtypes=[W.HANDLE,W.UINT];k.CloseHandle.argtypes=[W.HANDLE]
    n.NtQueryInformationProcess.argtypes=[W.HANDLE,W.ULONG,C.c_void_p,W.ULONG,C.c_void_p]
    n.NtSuspendProcess.argtypes=[W.HANDLE];n.NtSuspendProcess.restype=C.c_long
    n.NtResumeProcess.argtypes=[W.HANDLE];n.NtResumeProcess.restype=C.c_long
    h=k.OpenProcess(0x101C11,False,pid)
    if not h:raise core.LoaderError('No se pudo seguir el proceso propio de grabación')
    def read(address,size):
        buf=C.create_string_buffer(size);got=C.c_size_t()
        if not k.ReadProcessMemory(h,C.c_void_p(address),buf,size,C.byref(got)) or got.value!=size:
            raise core.LoaderError('No se pudo leer el replay del proceso propio')
        return buf.raw
    try:
        pbi=core.PROCESS_BASIC_INFORMATION();returned=W.ULONG()
        if n.NtQueryInformationProcess(h,0,C.byref(pbi),C.sizeof(pbi),C.byref(returned)):
            raise core.LoaderError('No se pudo consultar la base de grabación')
        base=struct.unpack('<Q',read(pbi.PebBaseAddress+0x10,8))[0]
        address=base+image.pe.rvas['gBattleReplay']
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            status=W.DWORD();k.GetExitCodeProcess(h,C.byref(status))
            if status.value!=259:raise core.LoaderError('La grabación terminó antes de obtener el clip')
            raw=read(address,BLOCK)
            counts=[struct.unpack_from('<i',raw,o)[0] for o in COUNTS]
            if raw[:8]==b'btls\x07\0\0\0' and min(counts)>=seconds*30:
                if n.NtSuspendProcess(h):raise core.LoaderError('No se pudo pausar el proceso propio para capturar el replay')
                try:raw=read(address,BLOCK)
                finally:n.NtResumeProcess(h)
                path=root/'cpu-vs-cpu.bin';path.write_bytes(bytes(HEADER)+raw+bytes(FILE_SIZE-HEADER-BLOCK))
                (root/'capture.json').write_text(json.dumps({'pid':pid,'counts':counts,'seconds_requested':seconds}),encoding='utf-8')
                print('Replay CPU/CPU grabado:',path,'pistas:',counts,flush=True)
                return path
            time.sleep(.1)
        raise core.LoaderError('No se obtuvieron suficientes entradas CPU en el plazo de prueba')
    finally:
        status=W.DWORD();k.GetExitCodeProcess(h,C.byref(status))
        if status.value==259:k.TerminateProcess(h,0)
        k.CloseHandle(h)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--record-only',action='store_true')
    p.add_argument('--replay',type=Path)
    p.add_argument('--seconds',type=int,default=20,choices=range(5,31))
    args=p.parse_args()
    root=core.HERE/'logs'/'replay-spectator'/uuid.uuid4().hex;root.mkdir(parents=True)
    clip=args.replay or record(args.runtime,root/'capture',args.seconds)
    print('LAB:',root,flush=True)
    if not args.record_only:watch(args.runtime,clip,root/'viewer')


if __name__=='__main__':main()
