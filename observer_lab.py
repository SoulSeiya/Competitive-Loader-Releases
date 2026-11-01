"""Private Windows shared-memory spectator lab, deliberately separate from the GUI.

The native writer only publishes confirmed pads. This module performs copying,
recording and (later) network IO outside the game thread.
"""
import ctypes as C
import mmap
import uuid

RING=8192
MAGIC=0x53435442

class Header(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('magic','version','serial','mode','error','closed','seed','rules')]+[
        ('options',C.c_uint32*2),('first',C.c_uint32),('next',C.c_uint32),('read',C.c_uint32),
        ('scores',C.c_uint32*2),('read_serial',C.c_uint32),('names',(C.c_char*64)*2)]

class Frame(C.Structure):
    _fields_=[('tick',C.c_uint32),('pads',C.c_ubyte*36)]

class Shared(C.Structure):
    _fields_=[('header',Header),('frames',Frame*RING)]

assert C.sizeof(Header)==192 and C.sizeof(Frame)==40

class ObserverMapping:
    def __init__(self):
        self.name='Local\\BTC-Observer-'+uuid.uuid4().hex
        self.memory=mmap.mmap(-1,C.sizeof(Shared),tagname=self.name)
        self.shared=Shared.from_buffer(self.memory)
        self.shared.header.magic=MAGIC;self.shared.header.version=1
        self.serial=0;self.cursor=0

    def drain(self,limit=240):
        """Return (metadata, first tick, bytes) or None, then acknowledge copied input."""
        h=Header.from_buffer_copy(self.memory[:192])
        if h.mode!=1 or not h.serial or h.serial&1:return None
        if h.error:raise ValueError('El publicador perdió entradas; se detuvo la transmisión sin afectar el combate')
        if h.serial!=self.serial:self.serial=h.serial;self.cursor=h.first
        start=self.cursor;end=min(h.next,start+limit)
        if not h.first<=start<=end or h.next-start>RING:raise ValueError('Entradas fuera del búfer')
        pads=bytearray()
        for tick in range(start,end):
            frame=Frame.from_buffer_copy(self.shared.frames[tick%RING])
            if frame.tick!=tick:raise ValueError('Secuencia compartida inválida')
            pads.extend(frame.pads)
        if self.shared.header.serial!=h.serial:return None
        self.cursor=end
        self.shared.header.read=end;self.shared.header.read_serial=h.serial
        return h,start,bytes(pads)

    def prepare_view(self,source):
        """Install validated session scalars, keeping activation separate from data."""
        h=self.shared.header
        h.serial=1
        h.mode=0;h.error=h.closed=0
        h.seed=source.seed;h.rules=source.rules
        h.options[:]=source.options[:]
        for p in range(2):h.names[p].value=source.names[p].value
        h.first=h.next=h.read=source.first;h.read_serial=2
        h.serial=2

    def feed(self,start,pads):
        h=self.shared.header
        if len(pads)%36 or start!=h.next:raise ValueError('Entradas del espectador no contiguas')
        count=len(pads)//36
        if start+count-h.read>RING:return False
        for index in range(count):
            tick=start+index;frame=self.shared.frames[tick%RING]
            frame.tick=tick;frame.pads[:]=pads[index*36:(index+1)*36]
        h.next=start+count
        if h.mode==0 and h.next-h.first>=120:h.mode=2
        return True

    def finish(self):self.shared.header.closed=1
    def stop(self):self.shared.header.mode=4
    def close(self):
        del self.shared
        self.memory.close()
