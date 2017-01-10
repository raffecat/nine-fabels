import os, sys, traceback
try:
    sys.path.append(os.path.dirname(__file__))
except:
    pass


def fatal():
    # http://www.arunrocks.com/blog/archives/2007/06/20/making-python-scripts-show-windows-friendly-errorsstacktrace/
    type, value, sys.last_traceback = sys.exc_info()
    lines = traceback.format_exception(type, value, sys.last_traceback)
    from ctypes import c_int, WINFUNCTYPE, windll
    from ctypes.wintypes import HWND, LPCSTR, UINT
    prototype = WINFUNCTYPE(c_int, HWND, LPCSTR, LPCSTR, UINT)
    paramflags = (1, "hwnd", 0), (1, "text", ""), (1, "caption", None), (1, "flags", 0)
    MessageBox = prototype(("MessageBoxA", windll.user32), paramflags)
    MessageBox(text="Unhandled Exception:\n"+"\n".join(lines))


import bpalace
if __name__ == "__main__":
    try:
        bpalace.main()
    except Exception:
        fatal()
