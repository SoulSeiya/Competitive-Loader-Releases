"""Avatar import using Windows' built-in image decoder; no extra runtime install."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import uuid


def convert_avatar(source,target):
    source=Path(source)
    if source.stat().st_size>10*1024*1024:raise ValueError('Elige una imagen de hasta 10 MB.')
    gd=C.WinDLL('gdiplus')
    class Startup(C.Structure):
        _fields_=[('version',W.UINT),('callback',C.c_void_p),('background',W.BOOL),('codecs',W.BOOL)]
    signatures={
        'GdiplusStartup':[C.POINTER(C.c_size_t),C.POINTER(Startup),C.c_void_p],
        'GdiplusShutdown':[C.c_size_t],
        'GdipLoadImageFromFile':[W.LPCWSTR,C.POINTER(C.c_void_p)],
        'GdipGetImageWidth':[C.c_void_p,C.POINTER(W.UINT)],
        'GdipGetImageHeight':[C.c_void_p,C.POINTER(W.UINT)],
        'GdipCreateBitmapFromScan0':[C.c_int,C.c_int,C.c_int,C.c_int,C.c_void_p,C.POINTER(C.c_void_p)],
        'GdipGetImageGraphicsContext':[C.c_void_p,C.POINTER(C.c_void_p)],
        'GdipGraphicsClear':[C.c_void_p,W.UINT],
        'GdipSetInterpolationMode':[C.c_void_p,C.c_int],
        'GdipCreatePath':[C.c_int,C.POINTER(C.c_void_p)],
        'GdipAddPathEllipse':[C.c_void_p,C.c_float,C.c_float,C.c_float,C.c_float],
        'GdipSetClipPath':[C.c_void_p,C.c_void_p,C.c_int],
        'GdipDrawImageRectRectI':[C.c_void_p,C.c_void_p]+[C.c_int]*9+[C.c_void_p]*3,
        'GdipSaveImageToFile':[C.c_void_p,W.LPCWSTR,C.c_void_p,C.c_void_p],
        'GdipDisposeImage':[C.c_void_p], 'GdipDeleteGraphics':[C.c_void_p], 'GdipDeletePath':[C.c_void_p],
    }
    for name,args in signatures.items():
        fn=getattr(gd,name);fn.argtypes=args;fn.restype=W.UINT
    def check(status):
        if status:raise ValueError('No se pudo abrir la imagen. Prueba con PNG o JPG.')
    token=C.c_size_t();image=C.c_void_p();bitmap=C.c_void_p();graphics=C.c_void_p();clip=C.c_void_p()
    check(gd.GdiplusStartup(C.byref(token),C.byref(Startup(1,None,False,False)),None))
    try:
        check(gd.GdipLoadImageFromFile(str(source.resolve()),C.byref(image)))
        width,height=W.UINT(),W.UINT()
        check(gd.GdipGetImageWidth(image,C.byref(width)));check(gd.GdipGetImageHeight(image,C.byref(height)))
        if not width.value or not height.value or width.value*height.value>16000000:
            raise ValueError('Elige una imagen de hasta 16 megapíxeles.')
        check(gd.GdipCreateBitmapFromScan0(256,256,0,0x26200A,None,C.byref(bitmap)))
        check(gd.GdipGetImageGraphicsContext(bitmap,C.byref(graphics)))
        check(gd.GdipGraphicsClear(graphics,0));check(gd.GdipSetInterpolationMode(graphics,7))
        check(gd.GdipCreatePath(0,C.byref(clip)));check(gd.GdipAddPathEllipse(clip,0,0,256,256))
        check(gd.GdipSetClipPath(graphics,clip,0))
        side=min(width.value,height.value);x=(width.value-side)//2;y=(height.value-side)//2
        check(gd.GdipDrawImageRectRectI(graphics,image,0,0,256,256,x,y,side,side,2,None,None,None))
        encoder=C.create_string_buffer(uuid.UUID('557cf406-1a04-11d3-9a73-0000f81ef32e').bytes_le)
        check(gd.GdipSaveImageToFile(bitmap,str(Path(target).resolve()),encoder,None))
    finally:
        if clip:gd.GdipDeletePath(clip)
        if graphics:gd.GdipDeleteGraphics(graphics)
        if bitmap:gd.GdipDisposeImage(bitmap)
        if image:gd.GdipDisposeImage(image)
        gd.GdiplusShutdown(token)
