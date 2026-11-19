"""SVG icons and Dark/Light QSS themes for MixGemini."""

import winreg
from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt


def detect_windows_theme() -> str:
    """Return 'light' or 'dark' based on Windows AppsUseLightTheme setting."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if int(val) == 1 else "dark"
    except OSError:
        return "light"
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICONS_SVG = {
    "gemini": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 3c.9 4.6 4.4 8.1 9 9-4.6.9-8.1 4.4-9 9-.9-4.6-4.4-8.1-9-9 '
        '4.6-.9 8.1-4.4 9-9z"/>'
        "</svg>"
    ),
    "antigravity": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/>'
        "</svg>"
    ),
    "split": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
        '<line x1="12" y1="4" x2="12" y2="20"/>'
        "</svg>"
    ),
    "new_chat": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 5v14M5 12h14"/>'
        "</svg>"
    ),
    "reload": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12a9 9 0 1 1-2.64-6.36"/>'
        '<polyline points="21 3 21 9 15 9"/>'
        "</svg>"
    ),
    "back": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="15 18 9 12 15 6"/>'
        "</svg>"
    ),
    "forward": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="9 18 15 12 9 6"/>'
        "</svg>"
    ),
    "pin": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 17v5"/>'
        '<path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>'
        "</svg>"
    ),
    "sun": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>'
        "</svg>"
    ),
    "moon": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
        "</svg>"
    ),
    "sliders": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="4" y1="21" x2="4" y2="14"/>'
        '<line x1="4" y1="10" x2="4" y2="3"/>'
        '<line x1="12" y1="21" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12" y2="3"/>'
        '<line x1="20" y1="21" x2="20" y2="16"/>'
        '<line x1="20" y1="12" x2="20" y2="3"/>'
        '<line x1="1" y1="14" x2="7" y2="14"/>'
        '<line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="17" y1="16" x2="23" y2="16"/>'
        "</svg>"
    ),
    "eye_off": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>'
        '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>'
        '<line x1="1" y1="1" x2="23" y2="23"/>'
        "</svg>"
    ),
    "panel_left": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="16" rx="2.5"/>'
        '<line x1="9" y1="4" x2="9" y2="20"/>'
        "</svg>"
    ),
    "caption_min": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.1" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="3" y1="12" x2="21" y2="12"/>'
        "</svg>"
    ),
    "caption_max": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.1" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/>'
        "</svg>"
    ),
    "caption_close": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.1" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="4" y1="4" x2="20" y2="20"/>'
        '<line x1="20" y1="4" x2="4" y2="20"/>'
        "</svg>"
    ),
}


@lru_cache(maxsize=64)
def make_svg_icon(name: str, color: str, size: int = 20) -> QIcon:
    """Render an inline SVG icon at 2x scale for crisp HiDPI display."""
    svg_template = ICONS_SVG[name]
    svg_bytes = svg_template.format(color=color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)


def get_theme_palette(theme: str) -> dict[str, str]:
    """Return color tokens for the requested UI theme."""
    if theme == "light":
        return {
            "rail_bg": "#f2f4f8",
            "rail_border": "#e0e4ec",
            "header_bg": "#f8f9fc",
            "header_border": "#e3e7ef",
            "surface": "#ffffff",
            "surface_hover": "#e8edf6",
            "text_primary": "#1e2430",
            "text_muted": "#647084",
            "accent": "#2563eb",
            "accent_soft": "#e0ebff",
            "accent_text": "#ffffff",
            "icon": "#3b4559",
            "icon_active": "#ffffff",
            "status_ok": "#16a34a",
            "status_off": "#94a3b8",
            "slider_groove": "#d7deea",
        }
    return {
        "rail_bg": "#14161a",
        "rail_border": "#262932",
        "header_bg": "#1b1d23",
        "header_border": "#282c36",
        "surface": "#252832",
        "surface_hover": "#313543",
        "text_primary": "#e8ecf4",
        "text_muted": "#9aa3b2",
        "accent": "#3b82f6",
        "accent_soft": "#1f3252",
        "accent_text": "#ffffff",
        "icon": "#b8c0cf",
        "icon_active": "#ffffff",
        "status_ok": "#22c55e",
        "status_off": "#64748b",
        "slider_groove": "#333846",
    }


@lru_cache(maxsize=4)
def build_stylesheet(theme: str) -> str:
    """Build the QSS stylesheet for the given theme ('dark' or 'light')."""
    p = get_theme_palette(theme)
    return f"""
QMainWindow, QWidget#RootWidget {{
    background-color: {p['rail_bg']};
    color: {p['text_primary']};
}}

QWidget#LeftRail {{
    background-color: {p['rail_bg']};
    border-right: 1px solid {p['rail_border']};
}}

QWidget#GeminiHeader {{
    background-color: {p['header_bg']};
    border-bottom: 1px solid {p['header_border']};
}}

QLabel {{
    color: {p['text_primary']};
}}

QLabel#MutedLabel {{
    color: {p['text_muted']};
    font-size: 12px;
}}

QLabel#FontValueBadge {{
    background-color: {p['surface']};
    color: {p['text_primary']};
    border: 1px solid {p['rail_border']};
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 12px;
    font-weight: 600;
}}

QLabel#BrandBadge {{
    color: {p['accent']};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

QToolButton#RailBtn {{
    background-color: transparent;
    color: {p['text_muted']};
    border: none;
    border-radius: 10px;
    padding: 1px 2px;
    font-size: 11px;
    font-weight: 500;
}}

QToolButton#RailBtn:hover {{
    background-color: {p['surface_hover']};
    color: {p['text_primary']};
}}

QToolButton#RailBtn:checked {{
    background-color: {p['accent']};
    color: {p['accent_text']};
    font-weight: 600;
}}

QPushButton#HeaderIconBtn, QPushButton#FontStepBtn {{
    background-color: {p['surface']};
    color: {p['text_primary']};
    border: 1px solid {p['rail_border']};
    border-radius: 7px;
    padding: 4px 8px;
    font-size: 12px;
}}

QPushButton#HeaderIconBtn:hover, QPushButton#FontStepBtn:hover {{
    background-color: {p['surface_hover']};
}}

QPushButton#HeaderIconBtn:checked {{
    background-color: {p['accent_soft']};
    color: {p['accent']};
    border-color: {p['accent']};
    font-weight: 600;
}}

QPushButton#ResetFontBtn {{
    background-color: transparent;
    color: {p['text_muted']};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 7px;
    font-size: 11.5px;
}}

QPushButton#ResetFontBtn:hover {{
    background-color: {p['surface_hover']};
    color: {p['text_primary']};
}}

QSlider::groove:horizontal {{
    border: none;
    height: 4px;
    background: {p['slider_groove']};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {p['accent']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {p['accent']};
    border: 2px solid {p['accent_text']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QFrame#SettingsPopover {{
    background-color: {p['header_bg']};
    border: 1px solid {p['rail_border']};
    border-radius: 8px;
}}

QLabel#SectionTitle {{
    color: {p['text_primary']};
    font-size: 12.5px;
    font-weight: 600;
}}

QPushButton#SegBtn {{
    background-color: {p['surface']};
    color: {p['text_muted']};
    border: 1px solid {p['rail_border']};
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 12px;
}}

QPushButton#SegBtn:hover {{
    background-color: {p['surface_hover']};
    color: {p['text_primary']};
}}

QPushButton#SegBtn:checked {{
    background-color: {p['accent']};
    color: {p['accent_text']};
    border-color: {p['accent']};
    font-weight: 600;
}}

QWidget#GeminiTitleBar {{
    background-color: {p['header_bg']};
    border-bottom: 1px solid {p['header_border']};
}}

QLabel#TitleBarText {{
    color: {p['text_primary']};
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#CaptionBtn, QPushButton#CaptionCloseBtn {{
    background-color: transparent;
    color: {p['text_muted']};
    border: none;
    border-radius: 0px;
    padding: 0px;
}}

QPushButton#CaptionBtn:hover {{
    background-color: {p['surface_hover']};
    color: {p['text_primary']};
}}

QPushButton#CaptionCloseBtn:hover {{
    background-color: #e81123;
    color: #ffffff;
}}

QWidget#EdgeSensorBar {{
    background-color: {p['accent']};
    border-radius: 2px;
}}

QFrame#TopPillBar {{
    background-color: {p['rail_bg']};
    border: 1px solid {p['rail_border']};
    border-radius: 8px;
}}

QFrame#InlinePillBar {{
    background-color: {p['rail_bg']};
    border: 1px solid {p['rail_border']};
    border-radius: 14px;
}}

QPushButton#PillModeBtn {{
    background-color: transparent;
    color: {p['text_muted']};
    border: none;
    border-radius: 11px;
    padding: 3px 9px;
    font-size: 11.5px;
    font-weight: 500;
}}

QPushButton#PillModeBtn:hover {{
    background-color: {p['surface_hover']};
    color: {p['text_primary']};
}}

QPushButton#PillModeBtn:checked {{
    background-color: {p['accent']};
    color: {p['accent_text']};
    font-weight: 600;
}}

QPushButton#PillToolBtn {{
    background-color: transparent;
    color: {p['text_muted']};
    border: none;
    border-radius: 10px;
    padding: 3px;
}}

QPushButton#PillToolBtn:hover {{
    background-color: {p['surface_hover']};
}}

QPushButton#PillToolBtn:checked {{
    background-color: {p['accent_soft']};
}}
"""


TRANSLATIONS = {
    "zh-CN": {
        "gemini": "Gemini",
        "ag": "AG",
        "split": "分屏",
        "pin": "置顶",
        "theme": "主题",
        "settings": "设置",
        "hide": "隐藏",
        "exit": "退出",
        "tray_show": "显示 Mix 边栏",
        "tray_hide": "隐藏 Mix 边栏",
        "online": "● 在线",
        "offline": "○ 未启动",
        "launching": "● 启动中",
        "tip_brand": "按住可拖动导航栏",
        "tip_gemini": "Ctrl+1 — Gemini 聊天",
        "tip_ag": "Ctrl+2 — 切换到 Antigravity",
        "tip_split": "Ctrl+3 — 左右并排分屏（再次点击恢复原状态）",
        "tip_pin": "窗口置顶（同时置顶当前工作区窗口）",
        "tip_theme": "切换 MixGemini 与 Gemini 深浅主题",
        "tip_settings": "打开常用设置（字号、语言、启动视图）",
        "tip_collapse_to_pill": "收起左栏并切换为顶部胶囊模式",
        "tip_expand_rail": "展开左侧导航栏",
        "tip_hide": "隐藏到系统托盘（可点击右下角托盘图标恢复）",
        "tip_exit": "关闭 MixGemini 与 Gemini 窗口",
        "font_title": "Gemini 对话字号",
        "reset": "重置",
        "startup_title": "启动默认视图",
        "edge_title": "左边缘模式",
        "edge_push": "留边防撞",
        "edge_auto": "贴边滑出",
        "edge_pill": "顶部胶囊",
        "lang_title": "界面语言",
        "shortcut_hint": "快捷键: Ctrl+1 Gemini · Ctrl+2 AG · Ctrl+3 分屏\n字号: Ctrl+- / Ctrl+= / Ctrl+0",
    },
    "zh-TW": {
        "gemini": "Gemini",
        "ag": "AG",
        "split": "分割",
        "pin": "置頂",
        "theme": "主題",
        "settings": "設定",
        "hide": "隱藏",
        "exit": "離開",
        "tray_show": "顯示 Mix 邊欄",
        "tray_hide": "隱藏 Mix 邊欄",
        "online": "● 線上",
        "offline": "○ 未啟動",
        "launching": "● 啟動中",
        "tip_brand": "按住可拖曳導覽列",
        "tip_gemini": "Ctrl+1 — Gemini 對話",
        "tip_ag": "Ctrl+2 — 切換到 Antigravity",
        "tip_split": "Ctrl+3 — 左右並排分割（再次點擊恢復原狀態）",
        "tip_pin": "視窗置頂（同時置頂目前工作區視窗）",
        "tip_theme": "切換 MixGemini 與 Gemini 深淺主題",
        "tip_settings": "開啟常用設定（字級、語言、啟動視圖）",
        "tip_collapse_to_pill": "收起左欄並切換為頂部膠囊模式",
        "tip_expand_rail": "展開左側導覽列",
        "tip_hide": "隱藏到系統匣（可點擊右下角系統匣圖示恢復）",
        "tip_exit": "關閉 MixGemini 與 Gemini 視窗",
        "font_title": "Gemini 對話字級",
        "reset": "重設",
        "startup_title": "啟動預設視圖",
        "edge_title": "左邊緣模式",
        "edge_push": "留邊防撞",
        "edge_auto": "貼邊滑出",
        "edge_pill": "頂部膠囊",
        "lang_title": "介面語言",
        "shortcut_hint": "快捷鍵: Ctrl+1 Gemini · Ctrl+2 AG · Ctrl+3 分割\n字級: Ctrl+- / Ctrl+= / Ctrl+0",
    },
    "en": {
        "gemini": "Gemini",
        "ag": "AG",
        "split": "Split",
        "pin": "Pin",
        "theme": "Theme",
        "settings": "Setup",
        "hide": "Hide",
        "exit": "Quit",
        "tray_show": "Show Mix Rail",
        "tray_hide": "Hide Mix Rail",
        "online": "● Online",
        "offline": "○ Offline",
        "launching": "● Starting",
        "tip_brand": "Drag to move navigation rail",
        "tip_gemini": "Ctrl+1 — Gemini Chat",
        "tip_ag": "Ctrl+2 — Switch to Antigravity",
        "tip_split": "Ctrl+3 — Side-by-side Split (click again to restore)",
        "tip_pin": "Always on top (rail + active workspace)",
        "tip_theme": "Toggle MixGemini & Gemini light/dark theme",
        "tip_settings": "Open settings (font size, language, startup view)",
        "tip_collapse_to_pill": "Collapse left rail and switch to Top Pill mode",
        "tip_expand_rail": "Expand left navigation rail",
        "tip_hide": "Hide to system tray (click tray icon to restore)",
        "tip_exit": "Close MixGemini & Gemini window",
        "font_title": "Gemini Chat Font Size",
        "reset": "Reset",
        "startup_title": "Default Startup View",
        "edge_title": "Left Edge Behavior",
        "edge_push": "Anti-Overlap",
        "edge_auto": "Auto-Slide",
        "edge_pill": "Top Pill",
        "lang_title": "Language",
        "shortcut_hint": "Shortcuts: Ctrl+1 Gemini · Ctrl+2 AG · Ctrl+3 Split\nFont: Ctrl+- / Ctrl+= / Ctrl+0",
    },
}


def tr(lang: str, key: str) -> str:
    """Return translated UI string for lang ('zh-CN', 'zh-TW', 'en')."""
    table = TRANSLATIONS.get(lang, TRANSLATIONS["zh-CN"])
    return table.get(key, TRANSLATIONS["zh-CN"].get(key, key))
