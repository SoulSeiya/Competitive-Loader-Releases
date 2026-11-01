"""Offline replay playback with the native local P1/P2 layout.

This is not a live online spectator transport. It never supplies pad inputs.
"""
from pathlib import Path
import shutil
import struct
import uuid

import competitive_loader as core

HEADER=0x38
BLOCK=0x1ABA8
FILE_SIZE=0x1AC00
TRACK_SIZE=0xD2F8
COUNTS=(0x5A8+0xD2F0,0x5A8+TRACK_SIZE+0xD2F0)


def split_replay(data):
    if len(data)!=FILE_SIZE:
        raise core.LoaderError("El replay debe ser un archivo BT3 de 0x1AC00 bytes")
    block=data[HEADER:]
    if block[:8]!=b'btls\x07\0\0\0':
        raise core.LoaderError("Replay incompatible: se requiere el formato btls versión 7")
    for offset in COUNTS:
        count,=struct.unpack_from('<i',block,offset)
        if not 1<=count<=9000:
            raise core.LoaderError("El replay no contiene dos pistas válidas")
    result=bytearray(data)
    # Only the presentation rule changes. Keep inputs, characters and rules intact.
    struct.pack_into('<i',result,HEADER+0x24,1)
    return bytes(result)


def isolated_runtime(source,root):
    source,root=Path(source),Path(root)
    runtime=root/'runtime';runtime.mkdir(parents=True,exist_ok=False)
    for name in ('Tenkaichi3Decomp.exe','Tenkaichi3Decomp.exe.mem','Tenkaichi3Decomp.dat','SDL3.dll'):
        shutil.copy2(source/name,runtime/name)
    card=source/'net_session'/'card1'
    if not card.is_dir():card=source/'saves'/'card1'
    if card.is_dir():shutil.copytree(card,runtime/'saves'/'card1')
    return runtime


def clean_environment(source):
    import os
    env={k:None for k in os.environ if k.startswith(('BT3_','BTC_'))}
    env.update(BT3_DATA=str((Path(source)/'gamedata').resolve()),BT3_NOMOVIE='1',
               SDL_AUDIODRIVER='dummy')
    return env


def watch(source,replay,root=None,extra_env=None,wait=True):
    root=Path(root) if root else core.HERE/'logs'/'replay-spectator'/uuid.uuid4().hex
    root.mkdir(parents=True,exist_ok=True)
    path=root/'split-replay.bin';path.write_bytes(split_replay(Path(replay).read_bytes()))
    runtime=isolated_runtime(source,root)
    if extra_env and any(k.startswith('BT3_SHOT') for k in extra_env):
        (runtime/'port'/'build'/'shots').mkdir(parents=True)
    core.RELEASE_PROFILE=True
    image=core.validate_payload(core.PAYLOAD,runtime/'Tenkaichi3Decomp.exe')
    env=clean_environment(source)
    env.update(BT3_REPLAY=str(path.resolve()),BTC_REPLAY_SPLIT='1',BT3_GS='gpu',BT3_TRACE='120',BT3_PACED='1',SDL_AUDIODRIVER=None)
    env.update(extra_env or {})
    return core.launch_patched(runtime/'Tenkaichi3Decomp.exe',image,env=env,
        game_log=runtime/'replay.log',convert_intro=False,stage_memory=False,wait=wait)
