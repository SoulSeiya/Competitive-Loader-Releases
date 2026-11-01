"""Windows image decoding/resampling for the background worker. No Tk calls."""
import ctypes as C
from ctypes import wintypes as W


class BackgroundDecoder:
    def __init__(self):
        self.gd=C.WinDLL('gdiplus');self.bitmap=C.c_void_p();self.graphics=C.c_void_p();self.size=None
        self.shade=C.c_void_p()
        class Startup(C.Structure):
            _fields_=[('version',W.UINT),('callback',C.c_void_p),('background',W.BOOL),('codecs',W.BOOL)]
        class Rect(C.Structure):
            _fields_=[('x',C.c_int),('y',C.c_int),('width',C.c_int),('height',C.c_int)]
        class BitmapData(C.Structure):
            _fields_=[('width',W.UINT),('height',W.UINT),('stride',C.c_int),('format',C.c_int),('scan0',C.c_void_p),('reserved',C.c_size_t)]
        self.Rect,self.BitmapData=Rect,BitmapData
        signatures={
            'GdiplusStartup':[C.POINTER(C.c_size_t),C.POINTER(Startup),C.c_void_p],
            'GdiplusShutdown':[C.c_size_t],
            'GdipLoadImageFromFile':[W.LPCWSTR,C.POINTER(C.c_void_p)],
            'GdipGetImageWidth':[C.c_void_p,C.POINTER(W.UINT)],
            'GdipGetImageHeight':[C.c_void_p,C.POINTER(W.UINT)],
            'GdipCreateBitmapFromScan0':[C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p,C.POINTER(C.c_void_p)],
            'GdipGetImageGraphicsContext':[C.c_void_p,C.POINTER(C.c_void_p)],
            'GdipSetInterpolationMode':[C.c_void_p,C.c_int],
            'GdipCreateSolidFill':[W.UINT,C.POINTER(C.c_void_p)],
            'GdipFillRectangleI':[C.c_void_p,C.c_void_p]+[C.c_int]*4,
            'GdipDeleteBrush':[C.c_void_p],
            'GdipDrawImageRectRectI':[C.c_void_p,C.c_void_p]+[C.c_int]*9+[C.c_void_p]*3,
            'GdipBitmapLockBits':[C.c_void_p,C.POINTER(Rect),W.UINT,C.c_int,C.POINTER(BitmapData)],
            'GdipBitmapUnlockBits':[C.c_void_p,C.POINTER(BitmapData)],
            'GdipDisposeImage':[C.c_void_p], 'GdipDeleteGraphics':[C.c_void_p],
        }
        for name,args in signatures.items():
            fn=getattr(self.gd,name);fn.argtypes=args;fn.restype=W.UINT
        self.token=C.c_size_t()
        self.check(self.gd.GdiplusStartup(C.byref(self.token),C.byref(Startup(1,None,False,False)),None))
        self.check(self.gd.GdipCreateSolidFill(0xB5091424,C.byref(self.shade)))

    @staticmethod
    def check(code):
        if code:raise OSError('No se pudo decodificar el fondo animado.')

    def render(self,path,width,height):
        width=(width+3)//4*4
        if self.size!=(width,height):
            self.release_bitmap()
            self.check(self.gd.GdipCreateBitmapFromScan0(width,height,0,0x21808,None,C.byref(self.bitmap)))
            self.check(self.gd.GdipGetImageGraphicsContext(self.bitmap,C.byref(self.graphics)))
            self.check(self.gd.GdipSetInterpolationMode(self.graphics,6))
            self.size=(width,height)
        source=C.c_void_p()
        try:
            self.check(self.gd.GdipLoadImageFromFile(str(path),C.byref(source)))
            sw,sh=W.UINT(),W.UINT()
            self.check(self.gd.GdipGetImageWidth(source,C.byref(sw)));self.check(self.gd.GdipGetImageHeight(source,C.byref(sh)))
            crop_w,crop_h=sw.value,sh.value
            if crop_w/crop_h>width/height:crop_w=max(1,round(crop_h*width/height))
            else:crop_h=max(1,round(crop_w*height/width))
            self.check(self.gd.GdipDrawImageRectRectI(self.graphics,source,0,0,width,height,(sw.value-crop_w)//2,(sh.value-crop_h)//2,crop_w,crop_h,2,None,None,None))
            # Tint every frame before upload, including frames paused during play.
            self.check(self.gd.GdipFillRectangleI(self.graphics,self.shade,0,0,width,height))
            data=self.BitmapData();rect=self.Rect(0,0,width,height)
            self.check(self.gd.GdipBitmapLockBits(self.bitmap,C.byref(rect),1,0x21808,C.byref(data)))
            try:
                row=width*3
                raw=C.string_at(data.scan0,row*height) if data.stride==row else b''.join(C.string_at(data.scan0+y*data.stride,row) for y in range(height))
            finally:self.gd.GdipBitmapUnlockBits(self.bitmap,C.byref(data))
            return width,height,raw
        finally:
            if source:self.gd.GdipDisposeImage(source)

    def release_bitmap(self):
        if self.graphics:self.gd.GdipDeleteGraphics(self.graphics);self.graphics=C.c_void_p()
        if self.bitmap:self.gd.GdipDisposeImage(self.bitmap);self.bitmap=C.c_void_p()

    def close(self):
        self.release_bitmap()
        if self.shade:self.gd.GdipDeleteBrush(self.shade);self.shade=C.c_void_p()
        if self.token:self.gd.GdiplusShutdown(self.token);self.token=C.c_size_t()
