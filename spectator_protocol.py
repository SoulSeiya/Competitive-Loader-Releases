"""Confirmed-input spectator stream. Never transports executable memory or predictions.

This protocol is private until native playback has passed combat-state checks.
"""
import base64
import hashlib
import json
import re
import struct

VERSION = 1
PAD_BYTES = 18
FRAME_BYTES = 2 * PAD_BYTES
CHUNK_FRAMES = 48
MAX_FRAMES = 60 * 60 * 60 * 3  # 3 hours at 60 vertical blanks/second
MAX_META_BYTES = 2048
FRAME = struct.Struct('<I36s')
HEX256 = re.compile(r'^[0-9a-f]{64}$')


class SpectatorError(ValueError):
    pass


def validate_header(value):
    if not isinstance(value, dict):
        raise SpectatorError('Cabecera de espectador inválida')
    if len(json.dumps(value, ensure_ascii=False).encode()) > MAX_META_BYTES:
        raise SpectatorError('Cabecera de espectador demasiado grande')
    if value.get('version') != VERSION:
        raise SpectatorError('Protocolo de espectador incompatible')
    for name, limit in (('tournament_id',64),('generation',64)):
        v = value.get(name)
        if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,'+str(limit)+'}',v):
            raise SpectatorError('Identidad de transmisión inválida')
    for name, lo, hi in (('match',1,31),('seed',0,0xffffffff),('rules',0,0xffffffff),('first_tick',0,MAX_FRAMES)):
        v=value.get(name)
        if type(v) is not int or not lo<=v<=hi:
            raise SpectatorError('Parámetro de sesión inválido')
    for name in ('exe_sha256','payload_sha256','data_sha256','memory_sha256'):
        if not isinstance(value.get(name),str) or not HEX256.fullmatch(value[name]):
            raise SpectatorError('Huella de compatibilidad inválida')
    names, options=value.get('names'),value.get('options')
    if not isinstance(names,list) or len(names)!=2 or any(not isinstance(n,str) or not n or len(n.encode())>64 or any(ord(c)<32 for c in n) for n in names):
        raise SpectatorError('Nombres de jugadores inválidos')
    if not isinstance(options,list) or len(options)!=2 or any(type(v) is not int or not 0<=v<=0xffffffff for v in options):
        raise SpectatorError('Opciones de sesión inválidas')
    return json.loads(json.dumps(value))


def compatible(header, fingerprints):
    header=validate_header(header)
    for name in ('exe_sha256','payload_sha256','data_sha256','memory_sha256'):
        if header[name]!=fingerprints.get(name):
            raise SpectatorError('El espectador necesita la misma versión y datos BTC que los jugadores')
    return header


def encode_chunk(start, pads):
    if type(start) is not int or not 0<=start<MAX_FRAMES:
        raise SpectatorError('Secuencia de entradas inválida')
    if not isinstance(pads,bytes) or not pads or len(pads)%FRAME_BYTES or len(pads)>FRAME_BYTES*CHUNK_FRAMES or start+len(pads)//FRAME_BYTES>MAX_FRAMES:
        raise SpectatorError('Bloque de entradas inválido')
    return dict(start=start,count=len(pads)//FRAME_BYTES,pads=base64.b64encode(pads).decode('ascii'),sha256=hashlib.sha256(pads).hexdigest())


def decode_chunk(value):
    if not isinstance(value,dict) or type(value.get('start')) is not int or type(value.get('count')) is not int:
        raise SpectatorError('Bloque de entradas inválido')
    encoded=value.get('pads')
    if not isinstance(encoded,str) or len(encoded)>CHUNK_FRAMES*FRAME_BYTES*4//3+4:
        raise SpectatorError('Bloque demasiado grande')
    try: pads=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):raise SpectatorError('Entradas codificadas inválidas') from None
    checked=encode_chunk(value['start'],pads)
    if checked!=value:
        raise SpectatorError('Bloque de entradas corrupto')
    return pads


class InputStream:
    """An append-only, generation-specific confirmed stream with idempotent delivery."""
    def __init__(self,header):
        self.header=validate_header(header)
        self.first=self.next=self.header['first_tick']
        self.pads=bytearray()
        self.finished=False

    def append(self,generation,chunk):
        if generation!=self.header['generation']:
            raise SpectatorError('La transmisión pertenece a otra sesión')
        pads=decode_chunk(chunk);start=chunk['start'];end=start+chunk['count']
        if start<self.first or start>self.next:
            raise SpectatorError('Faltan entradas anteriores; se debe recuperar la secuencia')
        if start<self.next:
            a=(start-self.first)*FRAME_BYTES;b=a+len(pads)
            if end>self.next or self.pads[a:b]!=pads:
                raise SpectatorError('Un bloque confirmado no puede cambiar')
            return False
        if self.finished:
            raise SpectatorError('La transmisión ya terminó')
        self.pads.extend(pads);self.next=end
        return True

    def finish(self,generation,end):
        if generation!=self.header['generation'] or type(end) is not int or end!=self.next:
            raise SpectatorError('Final de transmisión inválido')
        self.finished=True

    def frame(self,tick):
        if type(tick) is not int or not self.first<=tick<self.next:
            raise SpectatorError('El espectador debe esperar entradas confirmadas')
        at=(tick-self.first)*FRAME_BYTES
        return bytes(self.pads[at:at+FRAME_BYTES])
