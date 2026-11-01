"""Dark Windows title bar, retaining native move/resize and window controls."""
import ctypes
import os


def apply_dark_titlebar(window):
    result={'dark':False,'caption_color':False}
    if os.name!='nt':return result
    try:
        hwnd=int(window.native.Handle.ToInt64())
        dwm=ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        dwm.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
        dwm.restype=ctypes.c_long
        def set_attribute(attribute,value):
            data=ctypes.c_uint(value)
            return dwm(hwnd,attribute,ctypes.byref(data),ctypes.sizeof(data))==0
        result['dark']=set_attribute(20,1) or set_attribute(19,1)
        # Windows 11 supports explicit caption colours; Windows 10 uses dark mode.
        result['caption_color']=set_attribute(35,0x160D08)
        set_attribute(36,0xFAF5F1)
    except (AttributeError,OSError,TypeError,ValueError):pass
    return result
