"""A floating, click-through, always-on-top picture for Windows (per-pixel alpha).

Used to show a large glowing Trinity knot near the bottom of the screen while you talk.
Pure ctypes: no extra dependencies. All Win32 calls happen on the overlay's own thread.

    ov = Overlay(); ov.start()
    ov.show(pil_rgba_image)   # call as often as you like (latest image wins)
    ov.hide()
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes as wt

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST = 0x80000, 0x20, 0x8
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 2, 0, 1
PM_REMOVE, DIB_RGB_COLORS, BI_RGB = 1, 0, 0
MONITOR_DEFAULTTONEAREST = 2
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def _api():
    u = ctypes.WinDLL("user32", use_last_error=True)
    g = ctypes.WinDLL("gdi32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    u.DefWindowProcW.restype = LRESULT
    u.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    u.CreateWindowExW.restype = wt.HWND
    u.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    u.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    u.GetDC.restype = wt.HDC
    u.GetDC.argtypes = [wt.HWND]
    u.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    u.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
                                      wt.HDC, ctypes.POINTER(wt.POINT), wt.COLORREF,
                                      ctypes.POINTER(BLENDFUNCTION), wt.DWORD]
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
    u.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
    u.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    u.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    u.DestroyWindow.argtypes = [wt.HWND]
    u.MonitorFromPoint.restype = wt.HMONITOR
    u.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
    u.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
    u.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    g.CreateCompatibleDC.restype = wt.HDC
    g.CreateCompatibleDC.argtypes = [wt.HDC]
    g.CreateDIBSection.restype = wt.HBITMAP
    g.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
    g.SelectObject.restype = wt.HGDIOBJ
    g.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    g.DeleteObject.argtypes = [wt.HGDIOBJ]
    g.DeleteDC.argtypes = [wt.HDC]
    k.GetModuleHandleW.restype = wt.HMODULE
    k.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    return u, g, k


def to_premultiplied_bgra(img) -> bytes:
    """PIL RGBA -> premultiplied BGRA bytes, as UpdateLayeredWindow expects."""
    import numpy as np
    a = np.asarray(img.convert("RGBA"), dtype=np.uint16)
    alpha = a[..., 3:4]
    rgb = (a[..., :3] * alpha + 127) // 255
    out = np.concatenate([rgb[..., ::-1], alpha], axis=-1).astype(np.uint8)
    return out.tobytes()


def bottom_centre(w: int, h: int, work, gap: int) -> tuple[int, int]:
    """Top-left position that centres a w x h box above the bottom of a work-area rect."""
    left, top, right, bottom = work
    return left + (right - left - w) // 2, bottom - h - gap


class Overlay:
    def __init__(self, position: str = "bottom", gap: int = 40):
        self.position = position  # "bottom" (centre of the monitor under the mouse) or "cursor"
        self.gap = gap
        self._lock = threading.Lock()
        self._pending = None      # PIL image to show, or False to hide, or None for no change
        self._ready = threading.Event()
        self._stop = False
        self._thread = None
        self.ok = False

    # Public API (any thread)
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(5)
        return self.ok

    def show(self, img):
        with self._lock:
            self._pending = img

    def hide(self):
        with self._lock:
            self._pending = False

    def stop(self):
        self._stop = True

    # Overlay thread
    def _run(self):
        try:
            self._setup()
            self.ok = True
        except Exception as e:  # never take the app down for a visual
            print(f"(no overlay: {e})", flush=True)
            self._ready.set()
            return
        self._ready.set()
        msg = wt.MSG()
        visible, size, anchor = False, None, None
        while not self._stop:
            while self.u.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                self.u.TranslateMessage(ctypes.byref(msg))
                self.u.DispatchMessageW(ctypes.byref(msg))
            with self._lock:
                item, self._pending = self._pending, None
            if item is False:
                if visible:
                    self.u.ShowWindow(self.hwnd, SW_HIDE)
                    visible, anchor = False, None
            elif item is not None:
                if anchor is None:
                    anchor = self._anchor(item.size)  # fix the position for this appearance
                self._draw(item, anchor)
                if not visible:
                    self.u.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
                    self.u.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
                    visible = True
            time.sleep(1 / 60)
        self.u.DestroyWindow(self.hwnd)

    def _setup(self):
        self.u, self.g, self.k = _api()
        try:
            ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2
        except Exception:
            pass
        hinst = self.k.GetModuleHandleW(None)
        self._wndproc = WNDPROC(lambda h, m, w, l: self.u.DefWindowProcW(h, m, w, l))
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "VoiceAnywhereOverlay"
        self.u.RegisterClassW(ctypes.byref(wc))  # fails harmlessly if already registered
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self.hwnd = self.u.CreateWindowExW(ex, "VoiceAnywhereOverlay", "Voice Anywhere", WS_POPUP,
                                           0, 0, 1, 1, None, None, hinst, None)
        if not self.hwnd:
            raise OSError(ctypes.get_last_error())
        self._dib = None  # (w, h, hdc_mem, hbmp, bits)

    def _dpi_scale(self):
        try:
            return ctypes.windll.user32.GetDpiForWindow(self.hwnd) / 96
        except Exception:
            return 1.0

    def _anchor(self, size):
        pt = wt.POINT()
        self.u.GetCursorPos(ctypes.byref(pt))
        w, h = size
        if self.position == "cursor":
            return pt.x - w // 2, pt.y - h - 30
        mon = self.u.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        self.u.GetMonitorInfoW(mon, ctypes.byref(mi))
        r = mi.rcWork
        return bottom_centre(w, h, (r.left, r.top, r.right, r.bottom), int(self.gap * self._dpi_scale()))

    def _ensure_dib(self, w, h):
        if self._dib and self._dib[:2] == (w, h):
            return self._dib
        if self._dib:
            self.g.DeleteObject(self._dib[3])
            self.g.DeleteDC(self._dib[2])
        screen = self.u.GetDC(None)
        hdc = self.g.CreateCompatibleDC(screen)
        self.u.ReleaseDC(None, screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = w, -h  # top-down
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        hbmp = self.g.CreateDIBSection(hdc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        self.g.SelectObject(hdc, hbmp)
        self._dib = (w, h, hdc, hbmp, bits)
        return self._dib

    def _draw(self, img, anchor):
        w, h = img.size
        _, _, hdc, _, bits = self._ensure_dib(w, h)
        data = to_premultiplied_bgra(img)
        ctypes.memmove(bits, data, len(data))
        screen = self.u.GetDC(None)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        self.u.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wt.POINT(*anchor)), ctypes.byref(wt.SIZE(w, h)),
                                   hdc, ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
        self.u.ReleaseDC(None, screen)
