"""Windows Win32 + DWM helpers for detecting, launching, and docking Antigravity."""

import ctypes
import os
import re
import subprocess
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
ntdll = ctypes.windll.ntdll
gdi32 = ctypes.windll.gdi32

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
ntdll.NtQueryInformationProcess.argtypes = [
    wintypes.HANDLE,
    wintypes.ULONG,
    ctypes.c_void_p,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
ntdll.NtQueryInformationProcess.restype = ctypes.c_long

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_COMMAND_LINE_INFORMATION = 60

user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsZoomed.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.GetPixel.restype = wintypes.DWORD
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

SW_HIDE = 0
SW_RESTORE = 9
SW_SHOW = 5
SW_MINIMIZE = 6
GW_HWNDNEXT = 2
GW_HWNDPREV = 3
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
HWND_TOP = 0
MONITOR_DEFAULTTONEAREST = 2
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
GUI_INMOVESIZE = 0x00000002
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HANDLE
user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", RECT),
    ]


user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.ClipCursor.argtypes = [ctypes.POINTER(RECT)]
user32.ClipCursor.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


def _get_process_cmdline(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_string_buffer(8192)
        ret_len = wintypes.ULONG(0)
        status = ntdll.NtQueryInformationProcess(
            handle,
            PROCESS_COMMAND_LINE_INFORMATION,
            buf,
            len(buf),
            ctypes.byref(ret_len),
        )
        if status != 0:
            return ""
        us = _UNICODE_STRING.from_buffer(buf)
        return us.Buffer or ""
    finally:
        kernel32.CloseHandle(handle)


def find_browser_cdp_port(profile_dir: str) -> int:
    """Discover the --remote-debugging-port of a running Chrome/Edge using profile_dir."""
    norm_profile = os.path.normcase(os.path.normpath(profile_dir))
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    invalid_handle = wintypes.HANDLE(-1).value
    if not snap or snap == invalid_handle:
        return 0
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            exe = entry.szExeFile.lower()
            if exe in ("chrome.exe", "msedge.exe"):
                cmd = _get_process_cmdline(int(entry.th32ProcessID))
                if cmd and "--remote-debugging-port=" in cmd:
                    cmd_norm = os.path.normcase(cmd.replace("/", "\\"))
                    if norm_profile in cmd_norm:
                        match = re.search(r"--remote-debugging-port=(\d+)", cmd)
                        if match:
                            return int(match.group(1))
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return 0


def _get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_process_name(pid: int) -> str:
    """Return lowercase executable filename for a PID, or empty string."""
    path = _get_process_image_path(pid)
    return Path(path).name.lower() if path else ""


def terminate_pid(pid: int) -> bool:
    """Terminate a process by PID if accessible."""
    if not pid or pid == os.getpid():
        return False
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 0))
    finally:
        kernel32.CloseHandle(handle)


def _get_process_image_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def is_antigravity_hwnd(hwnd: int, configured_path: str = "") -> bool:
    """Return True if hwnd is a top-level main window owned by Antigravity.exe."""
    if not hwnd or not user32.IsWindow(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value or pid.value == os.getpid():
        return False
    exe_path = _get_process_image_path(pid.value)
    exe_name = Path(exe_path).name.lower() if exe_path else ""
    allowed = {"antigravity.exe"}
    if configured_path:
        cfg_name = Path(configured_path).name.lower()
        if cfg_name:
            allowed.add(cfg_name)
    return exe_name in allowed


def find_antigravity_hwnd(exclude_hwnd: int = 0, configured_path: str = "") -> int:
    """Find the primary visible top-level Antigravity window handle, or 0 if not found."""
    own_pid = os.getpid()
    allowed = {"antigravity.exe"}
    if configured_path:
        cfg_name = Path(configured_path).name.lower()
        if cfg_name:
            allowed.add(cfg_name)
    exact_matches: list[tuple[tuple[int, int], int]] = []
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if hwnd == exclude_hwnd or not user32.IsWindowVisible(hwnd) or _is_cloaked_window(hwnd):
            return True
        if user32.GetWindow(hwnd, GW_OWNER):
            return True

        is_minimized = bool(user32.IsIconic(hwnd))
        rect = RECT()
        w, h = 0, 0
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            w = rect.right - rect.left
            h = rect.bottom - rect.top
        if not is_minimized and (w < 220 or h < 180):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True

        exe_path = _get_process_image_path(pid.value)
        exe_name = Path(exe_path).name.lower() if exe_path else ""
        if exe_name in allowed:
            title = _get_window_title(hwnd)
            area = max(1, w * h)
            # Prefer non-empty titled main windows over helper windows
            score = (1 if title else 0, area)
            exact_matches.append((score, hwnd))
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    if exact_matches:
        exact_matches.sort(reverse=True)
        return exact_matches[0][1]
    return 0


def find_browser_executable() -> str:
    """Locate Chrome or Edge executable for running Gemini in native --app mode."""
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")

    candidates = [
        Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return ""


def _matches_browser_profile_or_pid(pid: int, profile_dir: str = "", browser_pid: int = 0) -> bool:
    if browser_pid and pid == browser_pid:
        return True
    if not profile_dir:
        return True
    cmd = _get_process_cmdline(pid)
    if not cmd:
        return False
    norm_profile = os.path.normcase(os.path.normpath(profile_dir))
    cmd_norm = os.path.normcase(cmd.replace("/", "\\"))
    return norm_profile in cmd_norm


def is_gemini_app_hwnd(hwnd: int, profile_dir: str = "", browser_pid: int = 0) -> bool:
    """Return True if hwnd is a valid MixGemini Chrome/Edge --app top-level window."""
    if not hwnd or not user32.IsWindow(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False
    exe_path = _get_process_image_path(pid.value)
    exe_name = Path(exe_path).name.lower() if exe_path else ""
    if exe_name not in ("chrome.exe", "msedge.exe"):
        return False
    return _matches_browser_profile_or_pid(pid.value, profile_dir=profile_dir, browser_pid=browser_pid)


def find_gemini_app_hwnd(
    browser_pid: int = 0, title_hint: str = "", profile_dir: str = ""
) -> int:
    """Find the visible top-level HWND of the spawned Gemini --app browser window."""
    pid_matches: list[tuple[int, int]] = []
    hint_matches: list[tuple[tuple[int, int], int]] = []
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if (
            not user32.IsWindowVisible(hwnd)
            or _is_cloaked_window(hwnd)
            or user32.GetWindow(hwnd, GW_OWNER)
        ):
            return True

        is_minimized = bool(user32.IsIconic(hwnd))
        rect = RECT()
        w, h = 0, 0
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            w = rect.right - rect.left
            h = rect.bottom - rect.top
        if not is_minimized and (w < 260 or h < 200):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        area = max(1, w * h)

        if browser_pid and pid.value == browser_pid:
            pid_matches.append((area, hwnd))
            return True

        exe_path = _get_process_image_path(pid.value)
        exe_name = Path(exe_path).name.lower() if exe_path else ""
        if exe_name in ("chrome.exe", "msedge.exe"):
            if not _matches_browser_profile_or_pid(
                pid.value, profile_dir=profile_dir, browser_pid=browser_pid
            ):
                return True
            title = _get_window_title(hwnd)
            title_lower = title.lower()
            if title_hint and title_hint in title:
                title_score = 2
            elif "gemini" in title_lower or "accounts.google.com" in title_lower:
                title_score = 1
            elif profile_dir or browser_pid:
                title_score = 0
            else:
                return True
            hint_matches.append(((title_score, area), hwnd))
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    if pid_matches:
        pid_matches.sort(reverse=True)
        return pid_matches[0][1]
    if hint_matches:
        hint_matches.sort(reverse=True)
        return hint_matches[0][1]
    return 0


def find_antigravity_executable(configured_path: str = "") -> str:
    """Locate Antigravity.exe from config, running process, or standard install paths."""
    if configured_path and Path(configured_path).is_file():
        return configured_path

    hwnd = find_antigravity_hwnd()
    if hwnd:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe_path = _get_process_image_path(pid.value)
        if exe_path and Path(exe_path).is_file():
            return exe_path

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    candidates = [
        Path(local_app_data) / "Programs" / "antigravity" / "Antigravity.exe",
        Path(local_app_data) / "Programs" / "Antigravity" / "Antigravity.exe",
        Path(program_files) / "Antigravity" / "Antigravity.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return ""


def launch_antigravity(configured_path: str = "") -> bool:
    """Launch Antigravity.exe detached if available."""
    exe_path = find_antigravity_executable(configured_path)
    if not exe_path:
        return False
    try:
        subprocess.Popen(
            [exe_path],
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            close_fds=True,
        )
        return True
    except OSError:
        return False


def get_work_area(hwnd: int = 0) -> tuple[int, int, int, int]:
    """Return (left, top, width, height) of the monitor work area containing hwnd."""
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        rc = info.rcWork
        return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top

    rc = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


def get_window_visual_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Return the visible DWM frame (x, y, width, height) in physical pixels."""
    ext_rect = RECT()
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(ext_rect),
        ctypes.sizeof(ext_rect),
    )
    if hr == 0:
        return (
            ext_rect.left,
            ext_rect.top,
            max(1, ext_rect.right - ext_rect.left),
            max(1, ext_rect.bottom - ext_rect.top),
        )
    win_rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(win_rect)):
        return (
            win_rect.left,
            win_rect.top,
            max(1, win_rect.right - win_rect.left),
            max(1, win_rect.bottom - win_rect.top),
        )
    return (100, 100, 1280, 840)


def _get_dwm_insets(hwnd: int) -> tuple[int, int, int, int]:
    """Return invisible DWM shadow border insets (left, top, right, bottom)."""
    win_rect = RECT()
    ext_rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(win_rect)):
        return (0, 0, 0, 0)
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(ext_rect),
        ctypes.sizeof(ext_rect),
    )
    if hr != 0:
        return (0, 0, 0, 0)
    return (
        max(0, ext_rect.left - win_rect.left),
        max(0, ext_rect.top - win_rect.top),
        max(0, win_rect.right - ext_rect.right),
        max(0, win_rect.bottom - ext_rect.bottom),
    )


def place_window_visual_rect(
    hwnd: int, x: int, y: int, width: int, height: int, activate: bool = False
) -> None:
    """Position a window so its visible DWM frame matches (x, y, width, height)."""
    if user32.IsIconic(hwnd) or user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    left_in, top_in, right_in, bottom_in = _get_dwm_insets(hwnd)
    flags = SWP_NOZORDER | SWP_SHOWWINDOW
    if not activate:
        flags |= SWP_NOACTIVATE

    user32.SetWindowPos(
        hwnd,
        0,
        x - left_in,
        y - top_in,
        width + left_in + right_in,
        height + top_in + bottom_in,
        flags,
    )


def is_window_valid(hwnd: int) -> bool:
    """Return True if hwnd refers to an existing window."""
    return bool(hwnd and user32.IsWindow(hwnd))


def is_window_visible(hwnd: int) -> bool:
    """Return True if hwnd is a valid visible window."""
    return bool(hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd))


def is_window_minimized(hwnd: int) -> bool:
    """Return True if the given window is valid and currently minimized."""
    return bool(hwnd and user32.IsWindow(hwnd) and user32.IsIconic(hwnd))


def is_window_maximized(hwnd: int) -> bool:
    """Return True if the given window is valid and currently maximized."""
    return bool(hwnd and user32.IsWindow(hwnd) and user32.IsZoomed(hwnd))


def hide_window(hwnd: int) -> None:
    """Hide a window from screen and taskbar without terminating its process."""
    if hwnd and user32.IsWindow(hwnd):
        user32.ShowWindow(hwnd, SW_HIDE)


def show_window(hwnd: int) -> None:
    """Make a previously hidden window visible again."""
    if hwnd and user32.IsWindow(hwnd):
        user32.ShowWindow(hwnd, SW_SHOW)


def minimize_window(hwnd: int) -> None:
    """Minimize the target window if it is valid and not already minimized."""
    if hwnd and user32.IsWindow(hwnd) and not user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_MINIMIZE)


def get_cursor_pos() -> tuple[int, int]:
    """Return the current mouse cursor position (x, y) in physical screen pixels."""
    pt = POINT()
    if user32.GetCursorPos(ctypes.byref(pt)):
        return int(pt.x), int(pt.y)
    return (-9999, -9999)


def is_window_in_movesize(hwnd: int) -> bool:
    """Return True if hwnd's thread is currently in a Win32 modal move/size loop."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    tid = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None)
    if not tid:
        return False
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return False
    return bool(
        (info.flags & GUI_INMOVESIZE)
        and (not info.hwndMoveSize or int(info.hwndMoveSize) == hwnd)
    )


def clip_cursor_min_x(min_x: int, max_x: int = 0, max_y: int = 0) -> None:
    """Confine the cursor horizontally to >= min_x while keeping vertical/right screen freedom."""
    vx = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    vy = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    vw = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    vh = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    right = max(int(min_x) + 1, vx + vw, int(max_x))
    bottom = max(vy + vh, int(max_y))
    rc = RECT(int(min_x), vy, right, bottom)
    user32.ClipCursor(ctypes.byref(rc))


def unclip_cursor() -> None:
    """Release any active cursor clipping rectangle."""
    user32.ClipCursor(None)


def is_left_mouse_down() -> bool:
    """Return True if the primary left mouse button is currently held down."""
    return bool(user32.GetAsyncKeyState(0x01) & 0x8000)


def get_foreground_hwnd() -> int:
    """Return the current foreground window handle, or 0."""
    return int(user32.GetForegroundWindow() or 0)


def _is_topmost_window(hwnd: int) -> bool:
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    return bool(user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE) & WS_EX_TOPMOST)


def _is_cloaked_window(hwnd: int) -> bool:
    cloaked = ctypes.c_int(0)
    hr = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_CLOAKED,
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked),
    )
    return hr == 0 and cloaked.value != 0


def _is_real_visible_window(hwnd: int) -> bool:
    if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return False
    if _is_cloaked_window(hwnd):
        return False
    rc = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rc)):
        if (rc.right - rc.left) <= 0 or (rc.bottom - rc.top) <= 0:
            return False
    return True


def sync_group_below(leader_hwnd: int, followers: list[int]) -> None:
    """Ensure followers sit immediately below leader_hwnd in Z-order without redundant SetWindowPos."""
    if not leader_hwnd or not user32.IsWindow(leader_hwnd):
        return
    valid = [h for h in followers if h and user32.IsWindow(h) and user32.IsWindowVisible(h)]
    if not valid:
        return

    leader_topmost = _is_topmost_window(leader_hwnd)
    topmost_changed = False
    for h in valid:
        if _is_topmost_window(h) != leader_topmost:
            set_topmost(h, leader_topmost)
            topmost_changed = True

    # Check if visible windows immediately below leader_hwnd already match valid
    found: list[int] = []
    seen = {leader_hwnd}
    cur = leader_hwnd
    for _ in range(2000):
        nxt = user32.GetWindow(wintypes.HWND(cur), GW_HWNDNEXT)
        if not nxt or nxt in seen:
            break
        seen.add(nxt)
        if not _is_real_visible_window(nxt):
            cur = nxt
            continue
        found.append(nxt)
        cur = nxt
        if len(found) >= len(valid):
            break

    if not topmost_changed and found == valid:
        return

    anchor = wintypes.HWND(leader_hwnd)
    for h in valid:
        user32.SetWindowPos(
            wintypes.HWND(h),
            anchor,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
        anchor = wintypes.HWND(h)


def sync_z_order_above(target_hwnd: int, overlays: list[int]) -> None:
    """Keep overlay windows in the exact same Z-order layer directly above target_hwnd."""
    if not target_hwnd or not user32.IsWindow(target_hwnd):
        return
    valid_overlays = [h for h in overlays if h and user32.IsWindow(h) and user32.IsWindowVisible(h)]
    if not valid_overlays:
        return

    target_topmost = _is_topmost_window(target_hwnd)
    topmost_changed = False
    for h in valid_overlays:
        if _is_topmost_window(h) != target_topmost:
            set_topmost(h, target_topmost)
            topmost_changed = True

    skip = set(valid_overlays)
    above_overlays: list[int] = []
    anchor = 0
    seen = {target_hwnd}
    cur = target_hwnd
    for _ in range(2000):
        prev = user32.GetWindow(wintypes.HWND(cur), GW_HWNDPREV)
        if not prev or prev in seen:
            break
        seen.add(prev)
        if not _is_real_visible_window(prev):
            cur = prev
            continue
        if prev in skip:
            above_overlays.append(prev)
            cur = prev
            continue
        anchor = prev
        break

    if not topmost_changed and above_overlays == list(reversed(valid_overlays)):
        return

    # 3-step target-relative placement avoids HWND_TOP foreground locks
    after = wintypes.HWND(target_hwnd)
    for h in valid_overlays:
        user32.SetWindowPos(
            wintypes.HWND(h),
            after,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
        after = wintypes.HWND(h)
    user32.SetWindowPos(
        wintypes.HWND(target_hwnd),
        after,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )

    first_above = 0
    seen_after = {target_hwnd}
    cur_after = target_hwnd
    for _ in range(2000):
        prev = user32.GetWindow(wintypes.HWND(cur_after), GW_HWNDPREV)
        if not prev or prev in seen_after:
            break
        seen_after.add(prev)
        if not _is_real_visible_window(prev):
            cur_after = prev
            continue
        first_above = prev
        break

    if first_above == valid_overlays[-1]:
        return

    if anchor and _is_topmost_window(anchor) == target_topmost:
        insert_after = wintypes.HWND(anchor)
    else:
        insert_after = wintypes.HWND(HWND_TOPMOST if target_topmost else HWND_TOP)

    for h in valid_overlays:
        user32.SetWindowPos(
            wintypes.HWND(h),
            insert_after,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
        insert_after = wintypes.HWND(h)


def set_window_rounded_corners(hwnd: int) -> None:
    """Apply Windows 11 native rounded corners to a frameless window."""
    if not hwnd or not user32.IsWindow(hwnd):
        return
    val = ctypes.c_int(DWMWCP_ROUND)
    dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_WINDOW_CORNER_PREFERENCE,
        ctypes.byref(val),
        ctypes.sizeof(val),
    )


def set_window_dark_titlebar(hwnd: int, dark: bool) -> None:
    """Switch the Windows 10/11 titlebar between dark and light mode."""
    if not hwnd or not user32.IsWindow(hwnd):
        return
    val = ctypes.c_int(1 if dark else 0)
    hr = dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_USE_IMMERSIVE_DARK_MODE,
        ctypes.byref(val),
        ctypes.sizeof(val),
    )
    if hr != 0:
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
            ctypes.byref(val),
            ctypes.sizeof(val),
        )


def set_topmost(hwnd: int, topmost: bool) -> None:
    """Toggle always-on-top via Win32 without recreating the HWND."""
    if not hwnd or not user32.IsWindow(hwnd):
        return
    insert_after = wintypes.HWND(HWND_TOPMOST if topmost else HWND_NOTOPMOST)
    user32.SetWindowPos(
        wintypes.HWND(hwnd),
        insert_after,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


def activate_window(hwnd: int) -> bool:
    """Restore if minimized and bring the target window to the foreground."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(hwnd, SW_SHOW)

    fg_hwnd = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
    cur_tid = kernel32.GetCurrentThreadId()
    attached = False
    if fg_tid and fg_tid != cur_tid:
        attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
    try:
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, False)
    return True


def detect_window_theme(hwnd: int, dpr: float = 1.0) -> str | None:
    """Detect 'light' or 'dark' by sampling top bar pixels of a visible foreground window."""
    if not hwnd or not _is_real_visible_window(hwnd) or user32.IsIconic(hwnd):
        return None
    tx, ty, tw, th = get_window_visual_rect(hwnd)
    if tw < round(640 * dpr) or th < round(120 * dpr):
        return None

    y = ty + max(10, round(14 * dpr))
    min_x = tx + round(120 * dpr)
    max_x = tx + tw - round(155 * dpr)
    if max_x <= min_x:
        return None

    sample_xs = [
        max(min_x, min(max_x, tx + tw - round(160 * dpr))),
        max(min_x, min(max_x, tx + tw - round(175 * dpr))),
        max(min_x, min(max_x, tx + tw - round(190 * dpr))),
    ]
    hdc = user32.GetDC(0)
    if not hdc:
        return None
    lums: list[float] = []
    try:
        for sx in sample_xs:
            color = int(gdi32.GetPixel(hdc, sx, y))
            if color == 0xFFFFFFFF:
                continue
            r = color & 0xFF
            g = (color >> 8) & 0xFF
            b = (color >> 16) & 0xFF
            lums.append(0.299 * r + 0.587 * g + 0.114 * b)
    finally:
        user32.ReleaseDC(0, hdc)

    if not lums:
        return None
    lums.sort()
    median_lum = lums[len(lums) // 2]
    return "dark" if median_lum < 128.0 else "light"
