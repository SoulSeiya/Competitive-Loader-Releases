"""Upload opaque BGR pixels to the existing Tk 8.6 image on Tk's thread."""
import ctypes as C


class PhotoBlock(C.Structure):
    _fields_ = [('pixels', C.c_char_p), ('width', C.c_int), ('height', C.c_int),
                ('pitch', C.c_int), ('pixel_size', C.c_int), ('offset', C.c_int * 4)]


class BackgroundPhoto:
    def __init__(self, photo):
        # Resolve the already loaded Tk DLL, using the interpreter that owns photo.
        self.dll = C.CDLL('tk86.dll')
        self.interp = photo.tk.interpaddr()
        self.dll.Tk_FindPhoto.argtypes = [C.c_void_p, C.c_char_p]
        self.dll.Tk_FindPhoto.restype = C.c_void_p
        self.dll.Tk_PhotoPutBlock.argtypes = [C.c_void_p, C.c_void_p,
            C.POINTER(PhotoBlock)] + [C.c_int] * 5
        self.dll.Tk_PhotoPutBlock.restype = C.c_int
        self.photo = photo
        self.handle = self.dll.Tk_FindPhoto(self.interp, str(photo).encode())
        if not self.handle:
            raise RuntimeError('No se pudo preparar el fondo.')

    def put(self, frame):
        width, height, pixels = frame
        if width <= 0 or height <= 0 or len(pixels) != width * height * 3:
            raise ValueError('Fotograma inválido')
        if (self.photo.width(), self.photo.height()) != (width, height):
            self.photo.configure(width=width, height=height)
        # Tk 8.6 treats an alpha offset outside the pixel as fully opaque.
        block = PhotoBlock(pixels, width, height, width * 3, 3, (2, 1, 0, 3))
        if self.dll.Tk_PhotoPutBlock(self.interp, self.handle, C.byref(block),
                                    0, 0, width, height, 1):
            raise RuntimeError('No se pudo presentar el fondo.')
