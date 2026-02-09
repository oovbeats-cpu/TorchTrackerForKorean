"""Pure Win32 GDI overlay window for TITrack.

Runs as a SEPARATE PROCESS from the main pywebview application.
Creating ANY Win32 window in the same process as pywebview breaks easy_drag.

Usage: python -m titrack --overlay --host 127.0.0.1 --port 8000

No pywebview dependency - creates its own Win32 window via ctypes.
Renders stats text with GDI, supports click-through, drag handle,
game window state sync, opacity, and scale control.
"""

import ctypes
import ctypes.wintypes
import json
import os
import sys
import threading
import time
import urllib.request
from ctypes import POINTER, WINFUNCTYPE, byref, c_int, c_void_p, cast
from ctypes.wintypes import (
    HWND, UINT, RECT, POINT, BOOL, LPARAM, WPARAM,
    DWORD, HINSTANCE, HMENU, LPCWSTR, MSG, HDC, HBRUSH
)

from titrack.config.logging import get_logger

logger = get_logger()

# ── Win32 Constants ──────────────────────────────────────────────

# Window styles
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

GWL_EXSTYLE = -20

WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_APPWINDOW = 0x00040000

LWA_ALPHA = 0x02
LWA_COLORKEY = 0x01

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
HWND_TOPMOST = ctypes.wintypes.HWND(-1)

# Window class styles
CS_DBLCLKS = 0x0008

# Messages
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_NCHITTEST = 0x0084
WM_TIMER = 0x0113
WM_LBUTTONDBLCLK = 0x0203
WM_MOVING = 0x0216
WM_USER = 0x0400
WM_APP_REPAINT = WM_USER + 1

HTTRANSPARENT = -1
HTCAPTION = 2
HTCLIENT = 1
HTNOWHERE = 0

# GDI
TRANSPARENT = 1
DT_CENTER = 0x0001
DT_RIGHT = 0x0002
DT_VCENTER = 0x0004
DT_SINGLELINE = 0x0020
DT_END_ELLIPSIS = 0x8000
DT_NOPREFIX = 0x0800

# Icon loading
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
DI_NORMAL = 0x0003

FW_BOLD = 700
FW_NORMAL = 400
DEFAULT_CHARSET = 1
OUT_DEFAULT_PRECIS = 0
CLIP_DEFAULT_PRECIS = 0
CLEARTYPE_QUALITY = 5
ANTIALIASED_QUALITY = 4
DEFAULT_PITCH = 0
FF_SWISS = 0x20

# UpdateLayeredWindow constants
BI_RGB = 0
DIB_RGB_COLORS = 0
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
ULW_ALPHA = 0x02

# System metrics
SM_CXSCREEN = 0
SM_CYSCREEN = 1

# ── ctypes function bindings ─────────────────────────────────────

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Window procedure type
WNDPROC = WINFUNCTYPE(ctypes.c_longlong, HWND, UINT, WPARAM, LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", UINT),
        ("style", UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", c_void_p),
        ("hCursor", c_void_p),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
        ("hIconSm", c_void_p),
    ]


# user32 functions
FindWindowW = user32.FindWindowW
FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
FindWindowW.restype = HWND

GetWindowLongPtrW = user32.GetWindowLongPtrW
GetWindowLongPtrW.argtypes = [HWND, c_int]
GetWindowLongPtrW.restype = ctypes.c_longlong

SetWindowLongPtrW = user32.SetWindowLongPtrW
SetWindowLongPtrW.argtypes = [HWND, c_int, ctypes.c_longlong]
SetWindowLongPtrW.restype = ctypes.c_longlong

GetWindowRect = user32.GetWindowRect
GetWindowRect.argtypes = [HWND, POINTER(RECT)]
GetWindowRect.restype = BOOL

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [HWND, HWND, c_int, c_int, c_int, c_int, UINT]
SetWindowPos.restype = BOOL

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [HWND, c_int]
ShowWindow.restype = BOOL

IsIconic = user32.IsIconic
IsIconic.argtypes = [HWND]
IsIconic.restype = BOOL

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [HWND]
IsWindowVisible.restype = BOOL

GetCursorPos = user32.GetCursorPos
GetCursorPos.argtypes = [POINTER(POINT)]
GetCursorPos.restype = BOOL

SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
SetLayeredWindowAttributes.argtypes = [HWND, ctypes.c_uint, ctypes.c_ubyte, ctypes.c_uint]
SetLayeredWindowAttributes.restype = BOOL

GetSystemMetrics = user32.GetSystemMetrics
GetSystemMetrics.argtypes = [c_int]
GetSystemMetrics.restype = c_int

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p, c_int]
GetWindowTextW.restype = c_int

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.argtypes = []
GetForegroundWindow.restype = HWND

EnumWindows = user32.EnumWindows
WNDENUMPROC = WINFUNCTYPE(BOOL, HWND, LPARAM)

RegisterClassExW = user32.RegisterClassExW
RegisterClassExW.argtypes = [POINTER(WNDCLASSEXW)]
RegisterClassExW.restype = ctypes.c_ushort

CreateWindowExW = user32.CreateWindowExW
CreateWindowExW.argtypes = [
    DWORD, LPCWSTR, LPCWSTR, DWORD,
    c_int, c_int, c_int, c_int,
    HWND, HMENU, HINSTANCE, c_void_p
]
CreateWindowExW.restype = HWND

DefWindowProcW = user32.DefWindowProcW
DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
DefWindowProcW.restype = ctypes.c_longlong

DestroyWindow = user32.DestroyWindow
DestroyWindow.argtypes = [HWND]
DestroyWindow.restype = BOOL

PostQuitMessage = user32.PostQuitMessage
PostQuitMessage.argtypes = [c_int]
PostQuitMessage.restype = None

GetMessageW = user32.GetMessageW
GetMessageW.argtypes = [POINTER(MSG), HWND, UINT, UINT]
GetMessageW.restype = BOOL

TranslateMessage = user32.TranslateMessage
TranslateMessage.argtypes = [POINTER(MSG)]
TranslateMessage.restype = BOOL

DispatchMessageW = user32.DispatchMessageW
DispatchMessageW.argtypes = [POINTER(MSG)]
DispatchMessageW.restype = ctypes.c_longlong

PostMessageW = user32.PostMessageW
PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
PostMessageW.restype = BOOL

InvalidateRect = user32.InvalidateRect
InvalidateRect.argtypes = [HWND, POINTER(RECT), BOOL]
InvalidateRect.restype = BOOL

SetTimer = user32.SetTimer
SetTimer.argtypes = [HWND, ctypes.POINTER(ctypes.c_uint), UINT, c_void_p]
SetTimer.restype = ctypes.POINTER(ctypes.c_uint)

KillTimer = user32.KillTimer
KillTimer.argtypes = [HWND, ctypes.POINTER(ctypes.c_uint)]
KillTimer.restype = BOOL

# GDI functions
BeginPaint = user32.BeginPaint
PAINTSTRUCT = ctypes.c_byte * 72  # PAINTSTRUCT is 72 bytes on x64
BeginPaint.argtypes = [HWND, ctypes.c_void_p]
BeginPaint.restype = HDC

EndPaint = user32.EndPaint
EndPaint.argtypes = [HWND, ctypes.c_void_p]
EndPaint.restype = BOOL

GetClientRect = user32.GetClientRect
GetClientRect.argtypes = [HWND, POINTER(RECT)]
GetClientRect.restype = BOOL

FillRect = user32.FillRect
FillRect.argtypes = [HDC, POINTER(RECT), HBRUSH]
FillRect.restype = c_int

DrawTextW = user32.DrawTextW
DrawTextW.argtypes = [HDC, LPCWSTR, c_int, POINTER(RECT), UINT]
DrawTextW.restype = c_int

SetBkMode = gdi32.SetBkMode
SetBkMode.argtypes = [HDC, c_int]
SetBkMode.restype = c_int

SetTextColor = gdi32.SetTextColor
SetTextColor.argtypes = [HDC, ctypes.c_uint]
SetTextColor.restype = ctypes.c_uint

CreateFontW = gdi32.CreateFontW
CreateFontW.argtypes = [
    c_int, c_int, c_int, c_int, c_int,
    DWORD, DWORD, DWORD, DWORD, DWORD,
    DWORD, DWORD, DWORD, LPCWSTR
]
CreateFontW.restype = c_void_p

SelectObject = gdi32.SelectObject
SelectObject.argtypes = [HDC, c_void_p]
SelectObject.restype = c_void_p

DeleteObject = gdi32.DeleteObject
DeleteObject.argtypes = [c_void_p]
DeleteObject.restype = BOOL

CreateSolidBrush = gdi32.CreateSolidBrush
CreateSolidBrush.argtypes = [ctypes.c_uint]
CreateSolidBrush.restype = HBRUSH

CreatePen = gdi32.CreatePen
CreatePen.argtypes = [c_int, c_int, ctypes.c_uint]
CreatePen.restype = c_void_p

MoveToEx = gdi32.MoveToEx
MoveToEx.argtypes = [HDC, c_int, c_int, POINTER(POINT)]
MoveToEx.restype = BOOL

LineTo = gdi32.LineTo
LineTo.argtypes = [HDC, c_int, c_int]
LineTo.restype = BOOL

class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

GetTextExtentPoint32W = gdi32.GetTextExtentPoint32W
GetTextExtentPoint32W.argtypes = [HDC, LPCWSTR, c_int, POINTER(SIZE)]
GetTextExtentPoint32W.restype = BOOL

GetModuleHandleW = kernel32.GetModuleHandleW
GetModuleHandleW.argtypes = [LPCWSTR]
GetModuleHandleW.restype = HINSTANCE

# Icon functions
LoadImageW = user32.LoadImageW
LoadImageW.argtypes = [HINSTANCE, LPCWSTR, UINT, c_int, c_int, UINT]
LoadImageW.restype = c_void_p

DrawIconEx = user32.DrawIconEx
DrawIconEx.argtypes = [HDC, c_int, c_int, c_void_p, c_int, c_int, UINT, HBRUSH, UINT]
DrawIconEx.restype = BOOL

DestroyIcon = user32.DestroyIcon
DestroyIcon.argtypes = [c_void_p]
DestroyIcon.restype = BOOL


# ── UpdateLayeredWindow structures ──────────────────────────────

class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]

# UpdateLayeredWindow support
CreateCompatibleDC = gdi32.CreateCompatibleDC
CreateCompatibleDC.argtypes = [HDC]
CreateCompatibleDC.restype = HDC

DeleteDC = gdi32.DeleteDC
DeleteDC.argtypes = [HDC]
DeleteDC.restype = BOOL

CreateDIBSection = gdi32.CreateDIBSection
CreateDIBSection.argtypes = [HDC, c_void_p, UINT, POINTER(c_void_p), c_void_p, DWORD]
CreateDIBSection.restype = c_void_p

UpdateLayeredWindow = user32.UpdateLayeredWindow
UpdateLayeredWindow.argtypes = [HWND, HDC, POINTER(POINT), POINTER(SIZE), HDC, POINTER(POINT), ctypes.c_uint, POINTER(BLENDFUNCTION), DWORD]
UpdateLayeredWindow.restype = BOOL

GetDC = user32.GetDC
GetDC.argtypes = [HWND]
GetDC.restype = HDC

ReleaseDC = user32.ReleaseDC
ReleaseDC.argtypes = [HWND, HDC]
ReleaseDC.restype = c_int


def RGB(r, g, b):
    return r | (g << 8) | (b << 16)


# ── Constants ────────────────────────────────────────────────────

BAR_HEIGHT = 38
DRAG_HANDLE_WIDTH = 20
DEFAULT_WIDTH = 940
MIN_GAME_WINDOW_SIZE = 200
API_HEALTH_MAX_FAILURES = 15  # 15 * 2s = 30s before auto-exit

# Colors
COLOR_BG = RGB(18, 18, 30)
COLOR_DRAG_BG = RGB(22, 22, 36)
COLOR_LABEL = RGB(180, 180, 200)
COLOR_VALUE = RGB(224, 224, 224)
COLOR_PROFIT = RGB(78, 204, 163)
COLOR_PROFIT_NEG = RGB(231, 76, 60)
COLOR_ACCENT = RGB(255, 215, 0)
COLOR_ACCENT_DIM = RGB(184, 150, 14)
COLOR_CONTRACT = RGB(93, 173, 226)
COLOR_DIVIDER = RGB(40, 40, 56)
COLOR_DRAG_DOTS = RGB(60, 60, 80)
COLOR_UNIT = RGB(80, 80, 100)
COLOR_KEY = RGB(255, 0, 255)       # Magenta for transparent background
COLOR_LOCK_BG = RGB(180, 40, 40)   # Red background for lock icon (legacy, unused)

# Column definitions: (label, key, width, value_color)
COLUMNS = [
    ("수익", "profit", 120, COLOR_PROFIT),
    ("시간", "run_time", 100, COLOR_VALUE),
    ("누적", "total_profit", 120, COLOR_VALUE),
    ("총시간", "total_time", 130, COLOR_VALUE),
    ("맵핑/h", "map_hr", 110, COLOR_ACCENT),
    ("총/h", "total_hr", 100, COLOR_ACCENT_DIM),
    ("계약", "contract", 120, COLOR_CONTRACT),
]


class OverlayManager:
    """Pure Win32 GDI overlay - runs as a separate subprocess.

    Creates its own Win32 window, renders stats with GDI,
    polls HTTP API for data and config, syncs with game window state.
    """

    GAME_TITLES = ["Torchlight: Infinite", "토치라이트: 인피니트"]

    def __init__(self):
        self._overlay_hwnd = None
        self._game_hwnd = None
        self._running = False
        self._overlay_visible = False
        self._user_visible = True  # User toggle from main window
        self._click_through = True
        self._lock = threading.Lock()
        self._scale = 1.0
        self._base_width = DEFAULT_WIDTH
        self._opacity = 230  # 0-255
        self._api_host = "127.0.0.1"
        self._api_port = 8000

        # Lock/unlock state (starts locked)
        self._locked = True

        # Visible columns (all visible by default)
        self._visible_columns = [
            "profit", "run_time", "total_profit", "total_time",
            "map_hr", "total_hr", "contract"
        ]

        # Text shadow toggle
        self._text_shadow = True

        # Shared data (updated by API polling thread)
        self._data = {
            "profit": "--",
            "profit_negative": False,
            "run_time": "--:--",
            "total_profit": "--",
            "total_time": "00:00",
            "map_hr": "0",
            "total_hr": "0",
            "contract": "--",
            "profit_unit": "결정",
        }

        # Font handles (created once)
        self._font_label = None
        self._font_value = None
        self._font_unit = None
        self._font_drag = None

        # Brush handles
        self._bg_brush = None
        self._drag_brush = None
        self._lock_brush = None

        # Icon handles
        self._icon_lock = None
        self._icon_unlock = None

        # WndProc reference (prevent GC)
        self._wndproc_ref = None

        # Threads
        self._window_thread = None
        self._api_thread = None
        self._game_thread = None
        self._mouse_thread = None
        self._config_thread = None

        # Window ready event
        self._window_ready = threading.Event()

    def start(self, api_host="127.0.0.1", api_port=8000):
        """Start overlay in a background thread. Non-blocking."""
        self._api_host = api_host
        self._api_port = api_port
        self._running = True

        # Window thread creates the Win32 window and runs message pump
        self._window_thread = threading.Thread(
            target=self._run_window, daemon=True
        )
        self._window_thread.start()

        # Wait for window creation
        if not self._window_ready.wait(timeout=5):
            logger.warning("Overlay window creation timed out")
            return

        # Start all helper threads
        self._game_thread = threading.Thread(
            target=self._monitor_game_window, daemon=True
        )
        self._game_thread.start()

        self._api_thread = threading.Thread(
            target=self._poll_api, daemon=True
        )
        self._api_thread.start()

        self._mouse_thread = threading.Thread(
            target=self._poll_mouse, daemon=True
        )
        self._mouse_thread.start()

        self._config_thread = threading.Thread(
            target=self._poll_config, daemon=True
        )
        self._config_thread.start()

        logger.info("Overlay manager started (subprocess mode)")

    def stop(self):
        """Stop all threads and destroy window."""
        self._running = False
        if self._overlay_hwnd:
            try:
                PostMessageW(self._overlay_hwnd, WM_DESTROY, 0, 0)
            except Exception:
                pass
        if self._window_thread:
            self._window_thread.join(timeout=3)

    # ── Public API ───────────────────────────────────────────────

    def set_opacity(self, value):
        """Set overlay opacity (0.0 - 1.0)."""
        if not self._overlay_hwnd:
            return False
        try:
            self._opacity = int(max(0.1, min(1.0, float(value))) * 255)
            self._apply_layered_attrs()
            return True
        except Exception as e:
            logger.error(f"Failed to set opacity: {e}")
            return False

    def set_scale(self, scale):
        """Set overlay scale (0.8 - 1.5). Resizes window width."""
        if not self._overlay_hwnd:
            return False
        try:
            self._scale = max(0.8, min(1.5, float(scale)))
            self._recreate_fonts(self._scale)
            self._calculate_base_width()
            new_w = int(self._base_width * self._scale)
            new_h = int(BAR_HEIGHT * max(1.0, self._scale))
            rect = RECT()
            if GetWindowRect(self._overlay_hwnd, byref(rect)):
                SetWindowPos(
                    self._overlay_hwnd, HWND_TOPMOST,
                    rect.left, rect.top, new_w, new_h,
                    SWP_NOACTIVATE
                )
                self._request_repaint()
            return True
        except Exception as e:
            logger.error(f"Failed to set scale: {e}")
            return False

    # ── Window Thread ────────────────────────────────────────────

    def _run_window(self):
        """Create Win32 window and run message pump (must be on own thread)."""
        try:
            hinstance = GetModuleHandleW(None)

            # Must keep reference to prevent GC
            self._wndproc_ref = WNDPROC(self._wndproc)

            # Register window class
            class_name = "TITrackOverlayClass"
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.style = CS_DBLCLKS
            wc.lpfnWndProc = self._wndproc_ref
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = hinstance
            wc.hIcon = None
            wc.hCursor = None
            wc.hbrBackground = None
            wc.lpszMenuName = None
            wc.lpszClassName = class_name
            wc.hIconSm = None

            atom = RegisterClassExW(byref(wc))
            if not atom:
                logger.error("Failed to register overlay window class")
                self._window_ready.set()
                return

            # Calculate initial base width from visible columns
            self._calculate_base_width()

            # Create window (initially hidden)
            screen_w = GetSystemMetrics(SM_CXSCREEN)
            x = (screen_w - self._base_width) // 2
            y = 10

            ex_style = (
                WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
                | WS_EX_TOPMOST | WS_EX_TRANSPARENT
            )

            self._overlay_hwnd = CreateWindowExW(
                ex_style,
                class_name,
                "TITrack Overlay",
                WS_POPUP,
                x, y, self._base_width, BAR_HEIGHT,
                None, None, hinstance, None
            )

            if not self._overlay_hwnd:
                logger.error("Failed to create overlay window")
                self._window_ready.set()
                return

            # Create GDI resources (must be before _apply_layered_attrs which may render)
            self._create_gdi_resources()

            # Set layered window attributes (triggers initial render in transparent mode)
            self._apply_layered_attrs()

            logger.info(f"Overlay window created (HWND: {self._overlay_hwnd})")
            self._window_ready.set()

            # Message pump
            msg = MSG()
            while self._running:
                ret = GetMessageW(byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                TranslateMessage(byref(msg))
                DispatchMessageW(byref(msg))

        except Exception as e:
            logger.error(f"Overlay window thread error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup_gdi_resources()
            self._window_ready.set()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """Window procedure for overlay."""
        if msg == WM_PAINT:
            # All rendering is via UpdateLayeredWindow - just validate the region
            self._on_paint(hwnd)
            return 0

        if msg == WM_LBUTTONDBLCLK:
            # Check if double-click is in lock icon area (RIGHT side)
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            client_rect = RECT()
            GetClientRect(hwnd, byref(client_rect))
            client_width = client_rect.right
            if x >= (client_width - DRAG_HANDLE_WIDTH):
                self._locked = not self._locked
                self._apply_layered_attrs()
                self._http_post_config({"locked": self._locked})
            return 0

        if msg == WM_NCHITTEST:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            rect = RECT()
            if GetWindowRect(hwnd, byref(rect)):
                local_x = x - rect.left
                window_width = rect.right - rect.left
                if local_x >= (window_width - DRAG_HANDLE_WIDTH):
                    return HTCLIENT  # Always HTCLIENT for lock area (receives dblclick)
                if self._locked:
                    return HTTRANSPARENT  # Click-through when locked
                else:
                    return HTCAPTION  # Full drag when unlocked
            return HTCLIENT

        if msg == WM_MOVING:
            if self._game_hwnd:
                new_rect = ctypes.cast(lparam, POINTER(RECT)).contents
                game_rect = RECT()
                if GetWindowRect(self._game_hwnd, byref(game_rect)):
                    ow = new_rect.right - new_rect.left
                    oh = new_rect.bottom - new_rect.top
                    # Clamp to game window
                    if new_rect.left < game_rect.left:
                        new_rect.left = game_rect.left
                        new_rect.right = new_rect.left + ow
                    if new_rect.top < game_rect.top:
                        new_rect.top = game_rect.top
                        new_rect.bottom = new_rect.top + oh
                    if new_rect.right > game_rect.right:
                        new_rect.right = game_rect.right
                        new_rect.left = new_rect.right - ow
                    if new_rect.bottom > game_rect.bottom:
                        new_rect.bottom = game_rect.bottom
                        new_rect.top = new_rect.bottom - oh
            return 1  # TRUE = allow modified position

        if msg == WM_DESTROY:
            PostQuitMessage(0)
            return 0

        return DefWindowProcW(hwnd, msg, wparam, lparam)

    # ── GDI Resources ────────────────────────────────────────────

    def _create_gdi_resources(self):
        """Create fonts and brushes."""
        self._font_label = CreateFontW(
            -11, 0, 0, 0, FW_NORMAL, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._font_value = CreateFontW(
            -14, 0, 0, 0, FW_BOLD, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._font_unit = CreateFontW(
            -10, 0, 0, 0, FW_NORMAL, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._font_drag = CreateFontW(
            -11, 0, 0, 0, FW_NORMAL, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._bg_brush = CreateSolidBrush(COLOR_BG)
        self._drag_brush = CreateSolidBrush(COLOR_DRAG_BG)
        self._lock_brush = CreateSolidBrush(COLOR_LOCK_BG)

        # Load lock/unlock icons from static assets
        self._load_icons()

    def _recreate_fonts(self, scale):
        """Delete old fonts and recreate with scaled sizes."""
        for obj in [self._font_label, self._font_value, self._font_unit, self._font_drag]:
            if obj:
                DeleteObject(obj)

        self._font_label = CreateFontW(
            int(-11 * scale), 0, 0, 0, FW_NORMAL, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._font_value = CreateFontW(
            int(-14 * scale), 0, 0, 0, FW_BOLD, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._font_unit = CreateFontW(
            int(-10 * scale), 0, 0, 0, FW_NORMAL, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )
        self._font_drag = CreateFontW(
            int(-11 * scale), 0, 0, 0, FW_NORMAL, 0, 0, 0,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_SWISS,
            "Pretendard"
        )

    def _load_icons(self):
        """Load lock/unlock icons from static assets directory."""
        try:
            from titrack.config.paths import get_static_dir
            assets_dir = get_static_dir() / "assets"
            lock_path = str(assets_dir / "lock.ico")
            unlock_path = str(assets_dir / "unlock.ico")

            icon_size = max(12, BAR_HEIGHT - 6)

            if os.path.exists(lock_path):
                self._icon_lock = LoadImageW(
                    None, lock_path, IMAGE_ICON,
                    icon_size, icon_size, LR_LOADFROMFILE
                )
            if os.path.exists(unlock_path):
                self._icon_unlock = LoadImageW(
                    None, unlock_path, IMAGE_ICON,
                    icon_size, icon_size, LR_LOADFROMFILE
                )

            if self._icon_lock and self._icon_unlock:
                logger.info("Overlay icons loaded successfully")
            else:
                logger.warning(f"Failed to load overlay icons (lock={self._icon_lock}, unlock={self._icon_unlock})")
        except Exception as e:
            logger.warning(f"Failed to load overlay icons: {e}")

    def _cleanup_gdi_resources(self):
        """Delete GDI objects."""
        for obj in [
            self._font_label, self._font_value, self._font_unit,
            self._font_drag, self._bg_brush, self._drag_brush,
            self._lock_brush
        ]:
            if obj:
                DeleteObject(obj)

        # Destroy icon handles
        if self._icon_lock:
            DestroyIcon(self._icon_lock)
        if self._icon_unlock:
            DestroyIcon(self._icon_unlock)

    # ── Layered Window Attributes ────────────────────────────────

    def _apply_layered_attrs(self):
        """Apply layered window attributes based on lock state.

        CRITICAL: We ALWAYS use UpdateLayeredWindow for BOTH modes.
        Mixing SetLayeredWindowAttributes and UpdateLayeredWindow is NOT allowed
        by Win32 API - once SetLayeredWindowAttributes is called, UpdateLayeredWindow
        will silently fail until WS_EX_LAYERED is cleared and re-set.
        By using UpdateLayeredWindow exclusively, we avoid this mode conflict.

        Locked = transparent background (per-pixel alpha, only text visible)
        Unlocked = solid background with opacity (rendered into bitmap)
        """
        if not self._overlay_hwnd:
            return
        self._render_ulw(transparent=self._locked)

    # ── Width Calculation ────────────────────────────────────────

    def _calculate_base_width(self):
        """Calculate width based on visible columns."""
        total = DRAG_HANDLE_WIDTH + 4  # drag handle + padding
        active_cols = [(l, k, w, c) for l, k, w, c in COLUMNS if k in self._visible_columns]
        for i, (_, _, col_w, _) in enumerate(active_cols):
            total += col_w
            if i < len(active_cols) - 1:
                total += 3  # divider
        self._base_width = max(total + 4, DRAG_HANDLE_WIDTH + 60)  # minimum width
        return self._base_width

    # ── Painting ─────────────────────────────────────────────────

    def _draw_text_with_shadow(self, hdc, text, rect, flags, color):
        """Draw text with optional 1px black shadow."""
        if self._text_shadow:
            shadow_rect = RECT(rect.left + 1, rect.top + 1, rect.right + 1, rect.bottom + 1)
            SetTextColor(hdc, RGB(0, 0, 0))
            DrawTextW(hdc, text, -1, byref(shadow_rect), flags)
        SetTextColor(hdc, color)
        DrawTextW(hdc, text, -1, byref(rect), flags)

    def _paint_content(self, hdc, total_w, total_h, alpha_mode=False):
        """Paint overlay content with 1-row layout (label + value side by side).

        Args:
            hdc: Device context to paint to
            total_w: Width of the paint area
            total_h: Height of the paint area
            alpha_mode: If True, skip background fills for transparent areas
                       (used with UpdateLayeredWindow where DIB is pre-cleared to transparent)
        """
        SetBkMode(hdc, TRANSPARENT)

        # Background
        if not alpha_mode:
            client_rect = RECT(0, 0, total_w, total_h)
            FillRect(hdc, byref(client_rect), self._bg_brush)

        # Filter columns to only render visible ones
        active_cols = [(l, k, w, c) for l, k, w, c in COLUMNS if k in self._visible_columns]

        # Calculate proportional column widths to fill available space
        padding_left = 4
        lock_area = DRAG_HANDLE_WIDTH + 1  # +1 for divider
        divider_space = max(0, len(active_cols) - 1) * 3
        available_w = total_w - padding_left - lock_area - divider_space - 4
        total_base = sum(w for _, _, w, _ in active_cols) or 1
        col_widths = [max(40, int(available_w * w / total_base)) for _, _, w, _ in active_cols]

        old_font = SelectObject(hdc, self._font_drag)
        x = padding_left
        data = self._data.copy()

        for i, (label, key, _, val_color) in enumerate(active_cols):
            col_w = col_widths[i]

            # Determine value color
            if key == "profit" and data.get("profit_negative"):
                color = COLOR_PROFIT_NEG
            else:
                color = val_color

            # Measure label width for tight label-value coupling
            SelectObject(hdc, self._font_label)
            text_size = SIZE()
            GetTextExtentPoint32W(hdc, label, len(label), byref(text_size))
            label_w = text_size.cx

            # Draw label (right-aligned in its portion, pushed against value)
            label_rect = RECT(x, 0, x + label_w + 2, total_h)
            label_flags = DT_RIGHT | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX
            self._draw_text_with_shadow(hdc, label, label_rect, label_flags, COLOR_LABEL)

            # Draw value immediately after label (left-aligned, no gap)
            SelectObject(hdc, self._font_value)
            val_start = x + label_w + 3
            val_rect = RECT(val_start, 0, x + col_w, total_h)
            val_flags = DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX | DT_END_ELLIPSIS
            self._draw_text_with_shadow(hdc, str(data.get(key, "--")), val_rect, val_flags, color)

            x += col_w

            # Divider (except after last column)
            if i < len(active_cols) - 1:
                self._draw_vline(hdc, x, 4, total_h - 4)
                x += 3

        # Draw divider BEFORE the lock area (right side)
        lock_area_left = total_w - DRAG_HANDLE_WIDTH
        self._draw_vline(hdc, lock_area_left, 4, total_h - 4)

        # Lock/drag handle area (RIGHT side)
        lock_rect = RECT(lock_area_left, 0, total_w, total_h)

        if not self._locked:
            # Unlocked: show dark background (solid mode is active)
            if not alpha_mode:
                FillRect(hdc, byref(lock_rect), self._bg_brush)

        # Draw lock/unlock icon
        icon = self._icon_lock if self._locked else self._icon_unlock
        if icon:
            icon_size = max(14, total_h - 10)
            ix = lock_area_left + (DRAG_HANDLE_WIDTH - icon_size) // 2
            iy = (total_h - icon_size) // 2
            DrawIconEx(hdc, ix, iy, icon, icon_size, icon_size, 0, None, DI_NORMAL)
        else:
            # Fallback to text if icons not loaded
            dot_rect = RECT(lock_area_left, 0, total_w, total_h)
            text_flags = DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX
            if self._locked:
                self._draw_text_with_shadow(hdc, "\u00D7", dot_rect, text_flags, RGB(255, 255, 255))
            else:
                self._draw_text_with_shadow(hdc, "\u22EE\u22EE", dot_rect, text_flags, COLOR_DRAG_DOTS)

        # Restore
        SelectObject(hdc, old_font)

    def _render_ulw(self, transparent=True):
        """Render overlay using UpdateLayeredWindow for BOTH modes.

        Always uses UpdateLayeredWindow to avoid mode conflicts with
        SetLayeredWindowAttributes (which makes UpdateLayeredWindow silently fail).

        Args:
            transparent: True = transparent bg (locked), False = solid bg (unlocked)
        """
        if not self._overlay_hwnd:
            return
        if not self._font_label:
            return  # GDI resources not yet created

        try:
            # Get window dimensions
            win_rect = RECT()
            if not GetWindowRect(self._overlay_hwnd, byref(win_rect)):
                return
            w = win_rect.right - win_rect.left
            h = win_rect.bottom - win_rect.top
            if w <= 0 or h <= 0:
                return

            # Create memory DC
            screen_dc = GetDC(None)
            mem_dc = CreateCompatibleDC(screen_dc)

            # Create 32-bit ARGB DIB section (top-down)
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # negative = top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = BI_RGB

            pBits = c_void_p()
            hBitmap = CreateDIBSection(
                mem_dc, byref(bmi), DIB_RGB_COLORS, byref(pBits), None, 0
            )
            if not hBitmap or not pBits.value:
                DeleteDC(mem_dc)
                ReleaseDC(None, screen_dc)
                return

            old_bmp = SelectObject(mem_dc, hBitmap)

            # Clear DIB to all zeros (BGRA 0,0,0,0 = fully transparent black)
            buf_size = w * h * 4
            ctypes.memset(pBits.value, 0, buf_size)

            if transparent:
                # ── Transparent mode (locked) ──
                # Paint content WITHOUT background fill (alpha_mode=True)
                self._paint_content(mem_dc, w, h, alpha_mode=True)

                # Fix alpha channel:
                # GDI sets alpha=0 on all pixels it writes to in 32-bit DIBs.
                # We reconstruct alpha from pixel brightness (premultiplied alpha).
                # Background pixels (0,0,0) stay at alpha=0 (transparent).
                raw = ctypes.string_at(pBits.value, buf_size)
                pixels = bytearray(raw)

                for i in range(0, buf_size, 4):
                    # BGRA format: pixels[i]=B, [i+1]=G, [i+2]=R, [i+3]=A
                    max_ch = pixels[i]
                    if pixels[i + 1] > max_ch:
                        max_ch = pixels[i + 1]
                    if pixels[i + 2] > max_ch:
                        max_ch = pixels[i + 2]
                    if max_ch > 12:
                        pixels[i + 3] = min(255, max_ch * 3)

                ctypes.memmove(pBits.value, bytes(pixels), buf_size)
            else:
                # ── Solid mode (unlocked) ──
                # Paint content WITH background fill (alpha_mode=False)
                self._paint_content(mem_dc, w, h, alpha_mode=False)

                # Set ALL pixels to fully opaque (alpha=255).
                # The SourceConstantAlpha in BLENDFUNCTION controls overall opacity.
                raw = ctypes.string_at(pBits.value, buf_size)
                pixels = bytearray(raw)

                for i in range(3, buf_size, 4):
                    pixels[i] = 255

                ctypes.memmove(pBits.value, bytes(pixels), buf_size)

            # Set up UpdateLayeredWindow parameters
            pt_src = POINT(0, 0)
            sz = SIZE(w, h)
            blend = BLENDFUNCTION()
            blend.BlendOp = AC_SRC_OVER
            blend.BlendFlags = 0
            blend.AlphaFormat = AC_SRC_ALPHA

            if transparent:
                blend.SourceConstantAlpha = 255  # Per-pixel alpha controls opacity
            else:
                blend.SourceConstantAlpha = self._opacity  # Uniform opacity over solid bg

            UpdateLayeredWindow(
                self._overlay_hwnd, screen_dc,
                None,  # keep current window position
                byref(sz), mem_dc, byref(pt_src),
                0, byref(blend), ULW_ALPHA
            )

            # Cleanup GDI resources
            SelectObject(mem_dc, old_bmp)
            DeleteObject(hBitmap)
            DeleteDC(mem_dc)
            ReleaseDC(None, screen_dc)

        except Exception as e:
            logger.error(f"ULW render error: {e}")
            import traceback
            traceback.print_exc()

    def _on_paint(self, hwnd):
        """Handle WM_PAINT - just validate the region.

        All actual rendering is done via UpdateLayeredWindow in _render_ulw().
        WM_PAINT handler must still call BeginPaint/EndPaint to prevent
        infinite WM_PAINT messages.
        """
        ps = PAINTSTRUCT()
        BeginPaint(hwnd, ctypes.byref(ps))
        EndPaint(hwnd, ctypes.byref(ps))

    def _draw_vline(self, hdc, x, y1, y2):
        """Draw a vertical divider line."""
        pen = CreatePen(0, 1, COLOR_DIVIDER)
        old_pen = SelectObject(hdc, pen)
        MoveToEx(hdc, x, y1, None)
        LineTo(hdc, x, y2)
        SelectObject(hdc, old_pen)
        DeleteObject(pen)

    def _request_repaint(self):
        """Request a repaint of the overlay window via UpdateLayeredWindow."""
        if self._overlay_hwnd:
            try:
                self._render_ulw(transparent=self._locked)
            except Exception:
                pass

    # ── Config Polling ───────────────────────────────────────────

    def _poll_config(self):
        """Poll overlay config from API (opacity, scale, visibility, lock, columns, etc.)."""
        base = f"http://{self._api_host}:{self._api_port}/api"

        while self._running:
            try:
                data = self._http_get(f"{base}/overlay/config")
                if data:
                    # Opacity
                    opacity = data.get("opacity", 0.9)
                    new_opacity = int(max(0.1, min(1.0, opacity)) * 255)
                    if new_opacity != self._opacity and self._overlay_hwnd:
                        self._opacity = new_opacity
                        self._apply_layered_attrs()

                    # Scale
                    scale = data.get("scale", 1.0)
                    new_scale = max(0.8, min(1.5, scale))
                    if abs(new_scale - self._scale) > 0.01:
                        self.set_scale(new_scale)

                    # Visibility (user toggle)
                    visible = data.get("visible", True)
                    if visible != self._user_visible:
                        self._user_visible = visible
                        if not visible:
                            self._hide_overlay()

                    # Locked state (locked = transparent bg, unlocked = solid bg)
                    locked = data.get("locked", True)
                    if locked != self._locked:
                        self._locked = locked
                        self._apply_layered_attrs()

                    # Visible columns
                    columns = data.get("visible_columns")
                    if columns is not None and set(columns) != set(self._visible_columns):
                        self._visible_columns = columns
                        self._calculate_base_width()
                        # Resize window
                        if self._overlay_hwnd:
                            new_w = int(self._base_width * self._scale)
                            rect = RECT()
                            if GetWindowRect(self._overlay_hwnd, byref(rect)):
                                SetWindowPos(
                                    self._overlay_hwnd, HWND_TOPMOST,
                                    rect.left, rect.top, new_w,
                                    int(BAR_HEIGHT * max(1.0, self._scale)),
                                    SWP_NOACTIVATE
                                )
                        self._request_repaint()

                    # Text shadow
                    text_shadow = data.get("text_shadow", True)
                    if text_shadow != self._text_shadow:
                        self._text_shadow = text_shadow
                        self._request_repaint()


            except Exception:
                pass

            time.sleep(2)

    # ── API Polling ──────────────────────────────────────────────

    def _poll_api(self):
        """Poll HTTP API for data updates. Auto-exits if API unreachable."""
        base = f"http://{self._api_host}:{self._api_port}/api"
        consecutive_failures = 0

        while self._running:
            try:
                any_success = False
                changed = False

                # Fetch active run
                try:
                    data = self._http_get(f"{base}/runs/active")
                    if data is not None:
                        any_success = True
                        val = data.get("net_value_fe") or data.get("total_value") or 0
                        new_profit = self._format_fe(val)
                        new_neg = val < 0
                        if self._data["profit"] != new_profit or self._data["profit_negative"] != new_neg:
                            self._data["profit"] = new_profit
                            self._data["profit_negative"] = new_neg
                            changed = True
                    else:
                        if self._data["profit"] != "--":
                            self._data["profit"] = "--"
                            self._data["profit_negative"] = False
                            changed = True
                except Exception:
                    pass

                # Fetch time state
                try:
                    data = self._http_get(f"{base}/time")
                    if data is not None:
                        any_success = True
                        run_sec = data.get("current_map_play_seconds", 0)
                        total_sec = data.get("total_play_seconds", 0)
                        mapping_state = data.get("mapping_play_state", "stopped")
                        contract = data.get("contract_setting", "--")

                        new_run = "--:--" if (mapping_state == "stopped" and run_sec == 0) else self._format_time(run_sec)
                        new_total = self._format_time(total_sec)
                        new_contract = str(contract) if contract else "--"

                        if self._data["run_time"] != new_run:
                            self._data["run_time"] = new_run
                            changed = True
                        if self._data["total_time"] != new_total:
                            self._data["total_time"] = new_total
                            changed = True
                        if self._data["contract"] != new_contract:
                            self._data["contract"] = new_contract
                            changed = True
                except Exception:
                    pass

                # Fetch performance
                try:
                    data = self._http_get(f"{base}/runs/performance")
                    if data is not None:
                        any_success = True
                        new_map = self._format_fe(data.get("profit_per_hour_mapping", 0))
                        new_total = self._format_fe(data.get("profit_per_hour_total", 0))
                        new_profit = self._format_fe(data.get("total_net_profit_fe", 0))

                        if self._data["map_hr"] != new_map:
                            self._data["map_hr"] = new_map
                            changed = True
                        if self._data["total_hr"] != new_total:
                            self._data["total_hr"] = new_total
                            changed = True
                        if self._data["total_profit"] != new_profit:
                            self._data["total_profit"] = new_profit
                            changed = True
                except Exception:
                    pass

                if changed:
                    self._request_repaint()

                # API health watchdog
                if any_success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= API_HEALTH_MAX_FAILURES:
                        logger.info("API unreachable for 30s, overlay subprocess exiting")
                        self._running = False
                        break

            except Exception as e:
                logger.error(f"API poll error: {e}")

            time.sleep(2)

    def _http_get(self, url):
        """Simple HTTP GET, returns parsed JSON or None."""
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        return None

    def _http_post_config(self, updates):
        """POST config update to API."""
        try:
            url = f"http://{self._api_host}:{self._api_port}/api/overlay/config"
            data = json.dumps(updates).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=1)
        except Exception:
            pass

    @staticmethod
    def _format_fe(v):
        """Format FE value for display with comma formatting."""
        if v is None:
            return "--"
        try:
            n = float(v)
        except (ValueError, TypeError):
            return "--"
        return f"{n:,.1f}"

    @staticmethod
    def _format_time(sec):
        """Format seconds as HH:MM:SS or MM:SS."""
        if sec is None or sec < 0:
            return "--:--"
        sec = int(sec)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    # ── Click-through ────────────────────────────────────────────

    def _set_click_through(self, enabled):
        """Toggle WS_EX_TRANSPARENT on the overlay window."""
        if not self._overlay_hwnd:
            return
        try:
            ex_style = GetWindowLongPtrW(self._overlay_hwnd, GWL_EXSTYLE)
            if enabled:
                new_style = ex_style | WS_EX_TRANSPARENT
            else:
                new_style = ex_style & ~WS_EX_TRANSPARENT
            if new_style != ex_style:
                SetWindowLongPtrW(self._overlay_hwnd, GWL_EXSTYLE, new_style)
                self._click_through = enabled
        except Exception:
            pass

    def _poll_mouse(self):
        """Poll mouse position to toggle click-through based on lock state."""
        while self._running:
            try:
                if not self._overlay_hwnd or not self._overlay_visible:
                    time.sleep(0.05)
                    continue

                pt = POINT()
                GetCursorPos(byref(pt))

                overlay_rect = RECT()
                if not GetWindowRect(self._overlay_hwnd, byref(overlay_rect)):
                    time.sleep(0.05)
                    continue

                in_lock_area = (
                    overlay_rect.right - DRAG_HANDLE_WIDTH <= pt.x <= overlay_rect.right
                    and overlay_rect.top <= pt.y <= overlay_rect.bottom
                )
                in_overlay = (
                    overlay_rect.left <= pt.x <= overlay_rect.right
                    and overlay_rect.top <= pt.y <= overlay_rect.bottom
                )

                if self._locked:
                    # When locked: only lock area is interactive (for double-click to unlock)
                    if in_lock_area:
                        self._set_click_through(False)
                    else:
                        self._set_click_through(True)
                else:
                    # When unlocked: entire overlay is interactive (for dragging)
                    if in_overlay:
                        self._set_click_through(False)
                    else:
                        self._set_click_through(True)


            except Exception:
                pass

            time.sleep(0.05)

    # ── Game Window Monitoring ───────────────────────────────────

    def _find_game_window(self):
        """Find game window by title."""
        result = [None]

        def _callback(hwnd, _lparam):
            if not IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(256)
            GetWindowTextW(hwnd, buf, 256)
            title = buf.value.strip()
            for game_title in self.GAME_TITLES:
                if title == game_title or title.startswith(game_title):
                    rect = RECT()
                    if GetWindowRect(hwnd, byref(rect)):
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > MIN_GAME_WINDOW_SIZE and h > MIN_GAME_WINDOW_SIZE:
                            result[0] = hwnd
                            return False
            return True

        cb = WNDENUMPROC(_callback)
        EnumWindows(cb, 0)
        return result[0]

    def _is_game_foreground(self):
        """Check if game window is foreground."""
        if not self._game_hwnd:
            return False
        try:
            return GetForegroundWindow() == self._game_hwnd
        except Exception:
            return False

    def _position_overlay_in_game(self):
        """Position overlay at top-right of game window, clamped to game bounds."""
        if not self._overlay_hwnd or not self._game_hwnd:
            return
        try:
            game_rect = RECT()
            if GetWindowRect(self._game_hwnd, byref(game_rect)):
                overlay_w = int(self._base_width * self._scale)
                overlay_h = int(BAR_HEIGHT * max(1.0, self._scale))
                x = game_rect.left + 10
                y = game_rect.top + 10

                # Clamp to game window bounds
                if x < game_rect.left:
                    x = game_rect.left
                if y < game_rect.top:
                    y = game_rect.top
                if x + overlay_w > game_rect.right:
                    x = game_rect.right - overlay_w
                if y + overlay_h > game_rect.bottom:
                    y = game_rect.bottom - overlay_h

                SetWindowPos(
                    self._overlay_hwnd, HWND_TOPMOST,
                    x, y, 0, 0,
                    SWP_NOSIZE | SWP_NOACTIVATE
                )
        except Exception as e:
            logger.error(f"Failed to position overlay: {e}")

    def _show_overlay(self):
        """Show overlay without activating."""
        if self._overlay_hwnd and not self._overlay_visible:
            ShowWindow(self._overlay_hwnd, SW_SHOWNOACTIVATE)
            SetWindowPos(
                self._overlay_hwnd, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
            self._overlay_visible = True
            self._request_repaint()

    def _hide_overlay(self):
        """Hide overlay."""
        if self._overlay_hwnd and self._overlay_visible:
            ShowWindow(self._overlay_hwnd, SW_HIDE)
            self._overlay_visible = False

    def _monitor_game_window(self):
        """Monitor game window state - show/hide overlay accordingly.

        Overlay is shown only when:
        - User has enabled it (_user_visible == True)
        - Game window is found and is foreground
        - Game is not minimized
        """
        game_found_before = False
        was_showing = False
        prev_user_visible = self._user_visible

        while self._running:
            try:
                game_hwnd = self._find_game_window()

                # Detect user toggle: False->True transition
                if self._user_visible and not prev_user_visible:
                    if game_hwnd and not IsIconic(game_hwnd) and self._is_game_foreground():
                        self._game_hwnd = game_hwnd
                        self._show_overlay()
                        self._position_overlay_in_game()
                        was_showing = True
                        game_found_before = True
                prev_user_visible = self._user_visible

                if game_hwnd and self._user_visible:
                    self._game_hwnd = game_hwnd

                    if not game_found_before:
                        logger.info("Game window found, positioning overlay")
                        self._position_overlay_in_game()
                        game_found_before = True

                    if IsIconic(game_hwnd):
                        if was_showing:
                            logger.info("Game minimized, hiding overlay")
                        self._hide_overlay()
                        was_showing = False
                    elif self._is_game_foreground():
                        if not was_showing:
                            logger.info("Game is foreground, showing overlay")
                        self._show_overlay()
                        was_showing = True
                    else:
                        if was_showing:
                            logger.info("Game moved to background, hiding overlay")
                        self._hide_overlay()
                        was_showing = False
                else:
                    if game_hwnd:
                        self._game_hwnd = game_hwnd
                    else:
                        self._game_hwnd = None

                    if game_found_before and not game_hwnd:
                        logger.info("Game window lost, hiding overlay")
                        game_found_before = False
                    elif game_found_before and not self._user_visible:
                        logger.info("Overlay disabled by user")
                        game_found_before = False

                    if was_showing:
                        self._hide_overlay()
                        was_showing = False

            except Exception as e:
                logger.error(f"Game monitor error: {e}")

            time.sleep(1)


# ── Subprocess Entry Point ───────────────────────────────────────

def run_overlay_main():
    """Entry point for overlay subprocess mode.

    Called from __main__.py when --overlay flag is detected.
    Parses --host and --port arguments, sets up logging,
    creates the overlay, and runs until the API becomes unreachable
    or the process is terminated.
    """
    import signal

    # Parse command line args (sys.argv[0]=exe, [1]=--overlay, [2:]=rest)
    host = "127.0.0.1"
    port = 8000

    args = sys.argv[2:] if len(sys.argv) > 2 else []
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1

    # Set up logging for subprocess
    from titrack.config.logging import setup_logging
    from titrack.config.paths import is_frozen
    setup_logging(portable=is_frozen(), console=False)

    logger.info(f"Overlay subprocess starting (host={host}, port={port})")

    om = OverlayManager()

    def signal_handler(sig, frame):
        logger.info("Overlay subprocess received signal, stopping")
        om.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    om.start(api_host=host, api_port=port)

    # Keep alive until stopped (by API health watchdog or signal)
    try:
        while om._running:
            time.sleep(1)
    except KeyboardInterrupt:
        om.stop()

    logger.info("Overlay subprocess exiting")
    return 0
