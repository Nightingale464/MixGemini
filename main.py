"""MixGemini: Zero-flicker unified switcher for Gemini (native Chrome/Edge --app) + Antigravity."""

import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cdp_client import (
    close_browser_via_cdp,
    dispatch_cdp,
    find_free_port,
    get_current_gemini_url,
    inject_js_into_gemini,
    list_page_targets,
    set_color_scheme_on_gemini,
    set_language_on_gemini,
    sync_gemini_if_navigated,
)
from config import DATA_DIR, RESOURCE_DIR, load_config, save_config
from css_injector import build_injection_js
from ui_assets import build_stylesheet, detect_windows_theme, get_theme_palette, make_svg_icon, tr
from win_bridge import (
    activate_window,
    clip_cursor_min_x,
    detect_window_theme,
    find_antigravity_hwnd,
    find_browser_cdp_port,
    find_browser_executable,
    find_gemini_app_hwnd,
    get_cursor_pos,
    get_foreground_hwnd,
    get_process_name,
    get_window_visual_rect,
    get_work_area,
    hide_window,
    is_antigravity_hwnd,
    is_gemini_app_hwnd,
    is_left_mouse_down,
    is_window_in_movesize,
    is_window_maximized,
    is_window_minimized,
    is_window_valid,
    is_window_visible,
    launch_antigravity,
    minimize_window,
    place_window_visual_rect,
    set_topmost,
    set_window_dark_titlebar,
    set_window_rounded_corners,
    show_window,
    sync_group_below,
    sync_z_order_above,
    terminate_pid,
    unclip_cursor,
)

APP_ICON_ICO = RESOURCE_DIR / "assets" / "mixgemini.ico"
APP_ICON_PNG = RESOURCE_DIR / "assets" / "mixgemini.png"
GEMINI_URL = "https://gemini.google.com/app"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"
CDP_PORT_FILE = DATA_DIR / "cdp_port.txt"
PID_FILE = DATA_DIR / "mixgemini.pid"
RAIL_WIDTH = 68
TITLEBAR_HEIGHT = 38


class PillControlsFrame(QFrame):
    """Shared compact pill controls used both inline inside GeminiTitleBar and as floating TopPillBar."""

    def __init__(
        self,
        rail: "MixRailWindow",
        inline: bool = False,
        parent: QWidget | None = None,
        flags: Qt.WindowType = Qt.WindowType.Widget,
    ) -> None:
        super().__init__(parent, flags)
        self.setObjectName("InlinePillBar" if inline else "TopPillBar")
        self._rail = rail
        self._inline = inline
        self.setFixedHeight(28 if inline else 32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*((6, 2, 6, 2) if inline else (10, 3, 10, 3)))
        layout.setSpacing(3 if inline else 4)

        self.logo_label = QLabel(self)
        self.logo_label.setFixedSize(18, 18)
        if not inline and APP_ICON_PNG.is_file():
            pm = QPixmap(str(APP_ICON_PNG)).scaled(
                36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            pm.setDevicePixelRatio(2)
            self.logo_label.setPixmap(pm)
            layout.addWidget(self.logo_label)
        else:
            self.logo_label.hide()

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.gemini_btn = self._make_mode_btn("Gemini")
        self.ag_btn = self._make_mode_btn("AG")
        self.split_btn = self._make_mode_btn("分屏")
        self.mode_group.addButton(self.gemini_btn, 0)
        self.mode_group.addButton(self.ag_btn, 1)
        self.mode_group.addButton(self.split_btn, 2)

        self.gemini_btn.clicked.connect(lambda: rail.switch_mode("gemini"))
        self.ag_btn.clicked.connect(lambda: rail.switch_mode("antigravity"))
        self.split_btn.clicked.connect(lambda: rail.switch_mode("split"))

        layout.addWidget(self.gemini_btn)
        layout.addWidget(self.ag_btn)
        layout.addWidget(self.split_btn)

        self.dot_label = QLabel("●", self)
        self.dot_label.setFixedWidth(12)
        self.dot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dot_label)

        self.pin_btn = self._make_tool_btn(checkable=True)
        self.pin_btn.toggled.connect(rail.pin_btn.setChecked)
        self.theme_btn = self._make_tool_btn(checkable=False)
        self.theme_btn.clicked.connect(rail._toggle_theme)
        self.settings_btn = self._make_tool_btn(checkable=False)
        self.settings_btn.clicked.connect(lambda: rail._toggle_settings_popover(from_pill=True))
        self.expand_btn = self._make_tool_btn(checkable=False)
        self.expand_btn.clicked.connect(rail._expand_rail_from_pill)
        self.hide_btn = self._make_tool_btn(checkable=False)
        self.hide_btn.clicked.connect(rail._hide_rail)

        layout.addWidget(self.pin_btn)
        layout.addWidget(self.theme_btn)
        layout.addWidget(self.settings_btn)
        layout.addWidget(self.expand_btn)
        layout.addWidget(self.hide_btn)

    def _make_mode_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setObjectName("PillModeBtn")
        btn.setCheckable(True)
        btn.setFixedHeight(22 if self._inline else 24)
        return btn

    def _make_tool_btn(self, checkable: bool) -> QPushButton:
        btn = QPushButton(self)
        btn.setObjectName("PillToolBtn")
        btn.setCheckable(checkable)
        btn.setIconSize(QSize(14, 14))
        btn.setFixedSize(22 if self._inline else 24, 22 if self._inline else 24)
        return btn

    def apply_language(self, lang: str) -> None:
        self.gemini_btn.setText(tr(lang, "gemini"))
        self.gemini_btn.setToolTip(tr(lang, "tip_gemini"))
        self.ag_btn.setText(tr(lang, "ag"))
        self.ag_btn.setToolTip(tr(lang, "tip_ag"))
        self.split_btn.setText(tr(lang, "split"))
        self.split_btn.setToolTip(tr(lang, "tip_split"))
        self.pin_btn.setToolTip(tr(lang, "tip_pin"))
        self.theme_btn.setToolTip(tr(lang, "tip_theme"))
        self.settings_btn.setToolTip(tr(lang, "tip_settings"))
        self.expand_btn.setToolTip(tr(lang, "tip_expand_rail"))
        self.hide_btn.setToolTip(tr(lang, "tip_hide"))
        if not self._inline:
            self.adjustSize()

    def sync_state(self, mode: str, theme: str, ag_running: bool, pinned: bool) -> None:
        p = get_theme_palette(theme)
        icon_color = p["icon"]
        mapping = {"gemini": self.gemini_btn, "antigravity": self.ag_btn, "split": self.split_btn}
        mapping.get(mode, self.gemini_btn).setChecked(True)

        self.pin_btn.blockSignals(True)
        self.pin_btn.setChecked(pinned)
        self.pin_btn.blockSignals(False)

        self.pin_btn.setIcon(make_svg_icon("pin", p["accent"] if pinned else icon_color, 14))
        self.theme_btn.setIcon(
            make_svg_icon("sun" if theme == "dark" else "moon", icon_color, 14)
        )
        self.settings_btn.setIcon(make_svg_icon("sliders", icon_color, 14))
        self.expand_btn.setIcon(make_svg_icon("panel_left", icon_color, 14))
        self.hide_btn.setIcon(make_svg_icon("eye_off", icon_color, 14))
        dot_color = p["status_ok"] if ag_running else p["status_off"]
        self.dot_label.setStyleSheet(f"font-size: 9px; color: {dot_color};")

    def set_theme_btn_visible(self, visible: bool) -> None:
        if self.theme_btn.isHidden() == visible:
            self.theme_btn.setVisible(visible)
            if not self._inline:
                self.adjustSize()


class TopPillBar(PillControlsFrame):
    """Floating top pill window shown when GeminiTitleBar is absent or too narrow."""

    def __init__(self, rail: "MixRailWindow") -> None:
        super().__init__(
            rail,
            inline=False,
            parent=None,
            flags=Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)


class GeminiTitleBar(QWidget):
    """Theme-synced overlay titlebar bound to the Gemini --app window."""

    def __init__(self, rail: "MixRailWindow") -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setObjectName("GeminiTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._rail = rail
        self._drag_offset = None
        self._pre_max_rect: tuple[int, int, int, int] | None = None
        self._caption_theme = "light"
        self.setFixedHeight(TITLEBAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(16, 16)
        self.title_label = QLabel("Google Gemini", self)
        self.title_label.setObjectName("TitleBarText")

        self.pill = PillControlsFrame(rail, inline=True, parent=self)
        self.pill.hide()

        self.min_btn = QPushButton(self)
        self.min_btn.setObjectName("CaptionBtn")
        self.min_btn.setFixedSize(46, TITLEBAR_HEIGHT)
        self.min_btn.setIconSize(QSize(12, 12))
        self.min_btn.clicked.connect(self._on_minimize)

        self.max_btn = QPushButton(self)
        self.max_btn.setObjectName("CaptionBtn")
        self.max_btn.setFixedSize(46, TITLEBAR_HEIGHT)
        self.max_btn.setIconSize(QSize(12, 12))
        self.max_btn.clicked.connect(self._on_maximize)

        self.close_btn = QPushButton(self)
        self.close_btn.setObjectName("CaptionCloseBtn")
        self.close_btn.setFixedSize(46, TITLEBAR_HEIGHT)
        self.close_btn.setIconSize(QSize(12, 12))
        self.close_btn.installEventFilter(self)
        self.close_btn.clicked.connect(rail.close)

        caption_row = QHBoxLayout()
        caption_row.setContentsMargins(0, 0, 0, 0)
        caption_row.setSpacing(0)
        caption_row.addWidget(self.min_btn)
        caption_row.addWidget(self.max_btn)
        caption_row.addWidget(self.close_btn)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.pill)
        layout.addStretch(1)
        layout.addLayout(caption_row)

        self.setMouseTracking(True)
        self.installEventFilter(self)
        for child in (
            self.icon_label,
            self.title_label,
            self.min_btn,
            self.max_btn,
            self.close_btn,
            self.pill,
            *self.pill.findChildren(QWidget),
        ):
            child.setMouseTracking(True)
            child.installEventFilter(self)

    def _hit_resize_edge(self, local_pos) -> str:
        x = local_pos.x()
        y = local_pos.y()
        w = self.width()
        top_margin = 6
        side_margin = 5
        corner_w = 14
        if y <= top_margin and x <= corner_w:
            return "top_left"
        if y <= top_margin and x >= w - corner_w:
            return "top_right"
        if y <= top_margin:
            return "top"
        if x <= side_margin:
            return "left"
        if x >= w - side_margin:
            return "right"
        return ""

    @staticmethod
    def _cursor_for_edge(edge: str) -> Qt.CursorShape | None:
        mapping = {
            "top": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top_left": Qt.CursorShape.SizeFDiagCursor,
            "top_right": Qt.CursorShape.SizeBDiagCursor,
        }
        return mapping.get(edge)

    def set_pill_visible(self, visible: bool, narrow: bool = False) -> None:
        if self.pill.isHidden() == visible:
            self.pill.setVisible(visible)
        show_title = not (visible and narrow)
        if self.title_label.isHidden() == show_title:
            self.title_label.setVisible(show_title)

    def update_theme(self, theme: str) -> None:
        self._caption_theme = theme
        p = get_theme_palette(theme)
        self.icon_label.setPixmap(make_svg_icon("gemini", p["accent"], 16).pixmap(16, 16))
        self.min_btn.setIcon(make_svg_icon("caption_min", p["icon"], 12))
        self.max_btn.setIcon(make_svg_icon("caption_max", p["icon"], 12))
        self.close_btn.setIcon(make_svg_icon("caption_close", p["icon"], 12))

    def eventFilter(self, obj, event) -> bool:
        if obj is self.close_btn:
            if event.type() == QEvent.Type.Enter:
                self.close_btn.setIcon(make_svg_icon("caption_close", "#ffffff", 12))
            elif event.type() == QEvent.Type.Leave:
                p = get_theme_palette(self._caption_theme)
                self.close_btn.setIcon(make_svg_icon("caption_close", p["icon"], 12))

        etype = event.type()
        if etype == QEvent.Type.MouseMove:
            if self._rail._resize_edge:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    self._rail._update_target_resize()
                    self._rail._snap_to_active_window()
                    return True
                self._rail._end_target_resize()
            if self._drag_offset is None:
                local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                edge = self._hit_resize_edge(local_pos)
                cursor = self._cursor_for_edge(edge)
                if cursor is not None:
                    self.setCursor(cursor)
                    if isinstance(obj, QWidget) and obj is not self:
                        obj.setCursor(cursor)
                else:
                    self.unsetCursor()
                    if isinstance(obj, QWidget) and obj is not self:
                        obj.unsetCursor()
        elif etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                edge = self._hit_resize_edge(local_pos)
                if edge and self._rail._start_target_resize(edge):
                    self._drag_offset = None
                    return True
        elif etype == QEvent.Type.MouseButtonRelease:
            if self._rail._resize_edge:
                self._rail._end_target_resize()
                return True
        return super().eventFilter(obj, event)

    def _on_minimize(self) -> None:
        hwnd = self._rail._get_gemini_hwnd()
        if hwnd:
            minimize_window(hwnd)

    def _on_maximize(self) -> None:
        if self._rail._current_mode == "split":
            self._rail.switch_mode("gemini")
            return
        hwnd = self._rail._get_gemini_hwnd()
        if not hwnd:
            return
        wx, wy, ww, wh = get_work_area(hwnd)
        if self._rail._allows_full_left():
            full_rect = (wx, wy, ww, wh)
        else:
            _rx, _ry, actual_rail_w, _rh = get_window_visual_rect(int(self._rail.winId()))
            if actual_rail_w < RAIL_WIDTH:
                actual_rail_w = max(RAIL_WIDTH, round(RAIL_WIDTH * self.devicePixelRatioF()))
            full_rect = (wx + actual_rail_w, wy, max(480, ww - actual_rail_w), wh)
        cur = get_window_visual_rect(hwnd)
        is_filling = (
            abs(cur[0] - full_rect[0]) <= 6
            and abs(cur[1] - full_rect[1]) <= 6
            and abs(cur[2] - full_rect[2]) <= 12
            and abs(cur[3] - full_rect[3]) <= 12
        )
        if is_filling and self._pre_max_rect is not None:
            rx, ry, rw, rh = self._pre_max_rect
            place_window_visual_rect(hwnd, rx, ry, rw, rh, activate=True)
        else:
            if not is_filling and not is_window_maximized(hwnd):
                self._pre_max_rect = cur
            place_window_visual_rect(hwnd, *full_rect, activate=True)
        self._rail._snap_to_active_window()

    def mouseDoubleClickEvent(self, event) -> None:
        if self._hit_resize_edge(event.position().toPoint()):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_maximize()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._rail._resize_edge:
                return
            hwnd = self._rail._get_gemini_hwnd()
            if hwnd:
                gx, gy, _gw, _gh = get_window_visual_rect(hwnd)
                gp = event.globalPosition().toPoint()
                dpr = self.devicePixelRatioF()
                self._drag_offset = (round(gp.x() * dpr) - gx, round(gp.y() * dpr) - gy)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._rail._resize_edge:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._rail._update_target_resize()
                self._rail._snap_to_active_window()
            else:
                self._rail._end_target_resize()
            return
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            hwnd = self._rail._get_gemini_hwnd()
            if hwnd:
                gp = event.globalPosition().toPoint()
                dpr = self.devicePixelRatioF()
                nx = round(gp.x() * dpr) - self._drag_offset[0]
                ny = round(gp.y() * dpr) - self._drag_offset[1]
                wx, wy, _ww, _wh = get_work_area(hwnd)
                ny = max(wy, ny)
                if not self._rail._allows_full_left():
                    actual_rail_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))
                    if self._rail.isVisible():
                        _rx, _ry, cur_rw, _rh = get_window_visual_rect(int(self._rail.winId()))
                        if cur_rw >= RAIL_WIDTH:
                            actual_rail_w = cur_rw
                    nx = max(wx + actual_rail_w, nx)
                else:
                    nx = max(wx, nx)
                _gx, _gy, gw, gh = get_window_visual_rect(hwnd)
                place_window_visual_rect(hwnd, nx, ny, gw, gh, activate=False)
                self._rail._snap_to_active_window()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        self._rail._end_target_resize()
        super().mouseReleaseEvent(event)


class BottomResizeBar(QWidget):
    """Transparent 6px bottom-edge resize overlay so Gemini stays resizable above the taskbar."""

    def __init__(self, rail: "MixRailWindow") -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setObjectName("BottomResizeBar")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFixedHeight(6)
        self._rail = rail

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        painter.end()

    def _hit_resize_edge(self, x: int) -> str:
        corner_w = 14
        w = self.width()
        if x <= corner_w:
            return "bottom_left"
        if x >= w - corner_w:
            return "bottom_right"
        return "bottom"

    @staticmethod
    def _cursor_for_edge(edge: str) -> Qt.CursorShape:
        if edge == "bottom_left":
            return Qt.CursorShape.SizeBDiagCursor
        if edge == "bottom_right":
            return Qt.CursorShape.SizeFDiagCursor
        return Qt.CursorShape.SizeVerCursor

    def mouseMoveEvent(self, event) -> None:
        if self._rail._resize_edge:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._rail._update_target_resize()
                self._rail._snap_to_active_window()
            else:
                self._rail._end_target_resize()
            return
        edge = self._hit_resize_edge(round(event.position().x()))
        self.setCursor(self._cursor_for_edge(edge))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._hit_resize_edge(round(event.position().x()))
            self._rail._start_target_resize(edge)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._rail._end_target_resize()
        super().mouseReleaseEvent(event)


class EdgeSensorBar(QWidget):
    """Thin 4px left-edge sensor strip for Option 2 (auto-slide Mix rail on hover)."""

    def __init__(self, rail: "MixRailWindow") -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("EdgeSensorBar")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(0.55)
        self.setFixedWidth(4)
        self._rail = rail

    def enterEvent(self, event) -> None:
        self._rail._open_auto_rail()
        super().enterEvent(event)


class SettingsPopover(QFrame):
    """Floating settings popover anchored beside the bottom-left Settings button."""

    def __init__(self, rail: "MixRailWindow") -> None:
        super().__init__(
            rail,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("SettingsPopover")
        self._rail = rail
        self.last_hide_time: float = 0.0
        self.setFixedWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Gemini chat font size
        font_header = QHBoxLayout()
        self.font_title = QLabel(self)
        self.font_title.setObjectName("SectionTitle")
        self.font_badge = QLabel(f"{rail.config['font_size']} px", self)
        self.font_badge.setObjectName("FontValueBadge")
        self.font_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_badge.setFixedWidth(48)
        font_header.addWidget(self.font_title)
        font_header.addStretch()
        font_header.addWidget(self.font_badge)
        layout.addLayout(font_header)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(6)
        self.minus_btn = QPushButton("-", self)
        self.minus_btn.setObjectName("FontStepBtn")
        self.minus_btn.setFixedSize(28, 26)
        self.minus_btn.clicked.connect(lambda: rail._step_font_size(-1))

        self.font_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.font_slider.setMinimum(rail.config["min_font_size"])
        self.font_slider.setMaximum(rail.config["max_font_size"])
        self.font_slider.setValue(rail.config["font_size"])
        self.font_slider.valueChanged.connect(rail._set_font_size)

        self.plus_btn = QPushButton("+", self)
        self.plus_btn.setObjectName("FontStepBtn")
        self.plus_btn.setFixedSize(28, 26)
        self.plus_btn.clicked.connect(lambda: rail._step_font_size(1))

        self.reset_btn = QPushButton(self)
        self.reset_btn.setObjectName("ResetFontBtn")
        self.reset_btn.clicked.connect(lambda: rail._set_font_size(14))

        slider_row.addWidget(self.minus_btn)
        slider_row.addWidget(self.font_slider)
        slider_row.addWidget(self.plus_btn)
        slider_row.addWidget(self.reset_btn)
        layout.addLayout(slider_row)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(128, 128, 128, 0.25);")
        layout.addWidget(sep)

        # 2. Default startup mode
        self.mode_title = QLabel(self)
        self.mode_title.setObjectName("SectionTitle")
        layout.addWidget(self.mode_title)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.startup_group = QButtonGroup(self)
        self.startup_group.setExclusive(True)
        self._startup_btns: dict[str, QPushButton] = {}
        for idx, key in enumerate(["gemini", "split", "antigravity"]):
            btn = QPushButton(self)
            btn.setObjectName("SegBtn")
            btn.setCheckable(True)
            btn.setChecked(rail.config.get("mode", "gemini") == key)
            btn.clicked.connect(lambda _=False, k=key: rail._set_startup_mode(k))
            self.startup_group.addButton(btn, idx)
            self._startup_btns[key] = btn
            mode_row.addWidget(btn)
        layout.addLayout(mode_row)

        sep_edge = QFrame(self)
        sep_edge.setFrameShape(QFrame.Shape.HLine)
        sep_edge.setStyleSheet("color: rgba(128, 128, 128, 0.25);")
        layout.addWidget(sep_edge)

        # 3. Left edge behavior (Option 1 vs Option 2)
        self.edge_title = QLabel(self)
        self.edge_title.setObjectName("SectionTitle")
        layout.addWidget(self.edge_title)

        edge_row = QHBoxLayout()
        edge_row.setSpacing(6)
        self.edge_group = QButtonGroup(self)
        self.edge_group.setExclusive(True)
        self._edge_btns: dict[str, QPushButton] = {}
        for idx, key in enumerate(["push", "auto_hide", "top_pill"]):
            btn = QPushButton(self)
            btn.setObjectName("SegBtn")
            btn.setCheckable(True)
            btn.setChecked(rail.config.get("edge_mode", "top_pill") == key)
            btn.clicked.connect(lambda _=False, k=key: rail._set_edge_mode(k))
            self.edge_group.addButton(btn, idx)
            self._edge_btns[key] = btn
            edge_row.addWidget(btn)
        layout.addLayout(edge_row)

        sep_lang = QFrame(self)
        sep_lang.setFrameShape(QFrame.Shape.HLine)
        sep_lang.setStyleSheet("color: rgba(128, 128, 128, 0.25);")
        layout.addWidget(sep_lang)

        # 4. Interface Language
        self.lang_title = QLabel(self)
        self.lang_title.setObjectName("SectionTitle")
        layout.addWidget(self.lang_title)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(6)
        self.lang_group = QButtonGroup(self)
        self.lang_group.setExclusive(True)
        for idx, (code, label) in enumerate(
            [("zh-CN", "简中"), ("zh-TW", "繁中"), ("en", "EN")]
        ):
            btn = QPushButton(label, self)
            btn.setObjectName("SegBtn")
            btn.setCheckable(True)
            btn.setChecked(rail.config.get("language", "zh-CN") == code)
            btn.clicked.connect(lambda _=False, c=code: rail._set_language(c))
            self.lang_group.addButton(btn, idx)
            lang_row.addWidget(btn)
        layout.addLayout(lang_row)

        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(128, 128, 128, 0.25);")
        layout.addWidget(sep2)

        # 4. Shortcut hint
        self.hint_label = QLabel(self)
        self.hint_label.setObjectName("MutedLabel")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)
        self.apply_language(rail.config.get("language", "zh-CN"))

    def apply_language(self, lang: str) -> None:
        self.font_title.setText(tr(lang, "font_title"))
        self.reset_btn.setText(tr(lang, "reset"))
        self.mode_title.setText(tr(lang, "startup_title"))
        self._startup_btns["gemini"].setText(tr(lang, "gemini"))
        self._startup_btns["split"].setText(tr(lang, "split"))
        self._startup_btns["antigravity"].setText(tr(lang, "ag"))
        self.edge_title.setText(tr(lang, "edge_title"))
        self._edge_btns["push"].setText(tr(lang, "edge_push"))
        self._edge_btns["auto_hide"].setText(tr(lang, "edge_auto"))
        self._edge_btns["top_pill"].setText(tr(lang, "edge_pill"))
        self.lang_title.setText(tr(lang, "lang_title"))
        self.hint_label.setText(tr(lang, "shortcut_hint"))

    def sync_font_display(self, size: int) -> None:
        self.font_badge.setText(f"{size} px")
        self.font_slider.blockSignals(True)
        self.font_slider.setValue(size)
        self.font_slider.blockSignals(False)

    def hideEvent(self, event) -> None:
        self.last_hide_time = time.monotonic()
        super().hideEvent(event)

    def sync_edge_mode(self, edge_mode: str) -> None:
        btn = self._edge_btns.get(edge_mode)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)


class MixRailWindow(QWidget):
    """Persistent 68px left navigation rail controlling Gemini (--app) and Antigravity."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setWindowTitle("MixGemini")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.config = load_config()
        if "theme" not in self.config:
            self.config["theme"] = detect_windows_theme()
        self._ui_theme = self.config["theme"]
        self._current_mode = "gemini"
        self._pre_split_mode = "gemini"
        self._pre_split_rect: tuple[int, int, int, int] | None = None
        self._ag_running = False
        self._browser_proc: subprocess.Popen | None = None
        self._cdp_port = find_free_port()
        self._gemini_hwnd = 0
        self._ag_hwnd = 0
        self._pending_gemini_url = GEMINI_URL
        self._pending_launch_mode: str | None = None
        self._launch_polls = 0
        self._drag_pos = None
        self._rail_hidden = False
        self._auto_rail_open = False
        self._auto_hide_deadline = 0.0
        self._last_rail_rect: tuple[int, int, int, int] | None = None
        self._last_sensor_rect: tuple[int, int, int, int] | None = None
        self._last_pill_rect: tuple[int, int, int, int] | None = None
        self._last_titlebar_rect: tuple[int, int, int, int] | None = None
        self._last_bottom_bar_rect: tuple[int, int, int, int] | None = None
        self._last_target_probe: float = 0.0
        self._resize_edge: str = ""
        self._resize_hwnd: int = 0
        self._resize_start_cursor: tuple[int, int] = (0, 0)
        self._resize_start_rect: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._drag_clip_active: bool = False
        self._drag_clip_hwnd: int = 0
        self._drag_clip_min_x: int = 0

        self.setFixedWidth(RAIL_WIDTH)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(lambda: save_config(self.config))

        self._font_cdp_timer = QTimer(self)
        self._font_cdp_timer.setSingleShot(True)
        self._font_cdp_timer.setInterval(50)
        self._font_cdp_timer.timeout.connect(self._inject_font_only)

        self._launch_timer = QTimer(self)
        self._launch_timer.setInterval(400)
        self._launch_timer.timeout.connect(self._poll_launched_antigravity)

        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(1200)
        self._sync_timer.timeout.connect(self._background_sync)

        self._snap_timer = QTimer(self)
        self._snap_timer.setInterval(10)
        self._snap_timer.timeout.connect(self._snap_to_active_window)

        self._build_ui()
        self.settings_popover = SettingsPopover(self)
        self.titlebar = GeminiTitleBar(self)
        self.bottom_resize_bar = BottomResizeBar(self)
        self.edge_sensor = EdgeSensorBar(self)
        self.top_pill = TopPillBar(self)
        self._setup_tray()
        self._setup_shortcuts()
        self._apply_language(self.config.get("language", "zh-CN"), persist=False)
        self._apply_theme(self.config["theme"], persist=False)

        # Position rail on the left edge of the monitor work area
        wx, wy, _ww, wh = get_work_area(0)
        dpr = self.devicePixelRatioF()
        rail_phys_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))
        if not self._allows_full_left():
            self.show()
            set_window_rounded_corners(int(self.winId()))
            place_window_visual_rect(int(self.winId()), wx, wy, rail_phys_w, wh, activate=False)
        else:
            self.hide()
            place_window_visual_rect(int(self.winId()), wx, wy, rail_phys_w, wh, activate=False)
            self.hide()
        self._apply_topmost_all()

        self._launch_or_focus_gemini()
        startup_mode = self.config.get("mode", "gemini")
        if startup_mode in ("antigravity", "split"):
            QTimer.singleShot(250, lambda: self.switch_mode(startup_mode))
        self._sync_timer.start()
        self._snap_timer.start()

    def _build_ui(self) -> None:
        self.setObjectName("LeftRail")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 8, 5, 8)
        layout.setSpacing(3)

        self.brand_label = QLabel(self)
        self.brand_label.setObjectName("BrandBadge")
        self.brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_label.setFixedHeight(32)
        if APP_ICON_PNG.is_file():
            pm = QPixmap(str(APP_ICON_PNG)).scaled(
                56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            pm.setDevicePixelRatio(2)
            self.brand_label.setPixmap(pm)
        else:
            self.brand_label.setText("MIX")
        self.brand_label.setToolTip("按住可拖动导航栏")
        layout.addWidget(self.brand_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(4)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.gemini_btn = self._make_rail_btn("Gemini", "Ctrl+1 — Gemini 聊天")
        self.ag_btn = self._make_rail_btn("AG", "Ctrl+2 — 切换到 Antigravity")
        self.split_btn = self._make_rail_btn("分屏", "Ctrl+3 — 左右并排分屏（再次点击恢复原状态）")

        self.gemini_btn.setChecked(True)
        self.mode_group.addButton(self.gemini_btn, 0)
        self.mode_group.addButton(self.ag_btn, 1)
        self.mode_group.addButton(self.split_btn, 2)

        self.gemini_btn.clicked.connect(lambda: self.switch_mode("gemini"))
        self.ag_btn.clicked.connect(lambda: self.switch_mode("antigravity"))
        self.split_btn.clicked.connect(lambda: self.switch_mode("split"))

        layout.addWidget(self.gemini_btn)
        layout.addWidget(self.ag_btn)
        layout.addWidget(self.split_btn)

        self.ag_status_label = QLabel("○ 未启动", self)
        self.ag_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ag_status_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self.ag_status_label)

        layout.addStretch()

        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(128, 128, 128, 0.25);")
        layout.addWidget(sep2)

        self.pin_btn = self._make_rail_btn("置顶", "窗口置顶（同时置顶当前工作区窗口）")
        self.pin_btn.setChecked(bool(self.config.get("always_on_top", False)))
        self.pin_btn.toggled.connect(self._on_toggle_pin)

        self.theme_btn = self._make_rail_btn("主题", "切换深色 / 浅色主题", checkable=False)
        self.theme_btn.clicked.connect(self._toggle_theme)

        self.settings_btn = self._make_rail_btn("设置", "打开常用设置（字号、启动视图等）", checkable=False)
        self.settings_btn.clicked.connect(self._toggle_settings_popover)

        self.hide_btn = self._make_rail_btn(
            "隐藏", "收起左栏并切换为顶部胶囊模式", checkable=False
        )
        self.hide_btn.clicked.connect(self._collapse_rail_to_pill)

        self.close_btn = QPushButton("退出", self)
        self.close_btn.setObjectName("ResetFontBtn")
        self.close_btn.setFixedSize(56, 24)
        self.close_btn.setToolTip("关闭 MixGemini 与 Gemini 窗口")
        self.close_btn.clicked.connect(self.close)

        layout.addWidget(self.pin_btn)
        layout.addWidget(self.theme_btn)
        layout.addWidget(self.settings_btn)
        layout.addWidget(self.hide_btn)
        layout.addWidget(self.close_btn)

    def _make_rail_btn(self, text: str, tooltip: str, checkable: bool = True) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("RailBtn")
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(56, 48)
        return btn

    def _setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        if APP_ICON_ICO.is_file():
            self.tray_icon.setIcon(QIcon(str(APP_ICON_ICO)))
        elif APP_ICON_PNG.is_file():
            self.tray_icon.setIcon(QIcon(str(APP_ICON_PNG)))
        self.tray_icon.setToolTip("MixGemini")

        menu = QMenu()
        self.tray_toggle_action = QAction("隐藏 Mix 边栏", menu)
        self.tray_toggle_action.triggered.connect(self._toggle_rail_visibility)
        self.tray_gemini_action = QAction("Gemini", menu)
        self.tray_gemini_action.triggered.connect(lambda: self._tray_switch("gemini"))
        self.tray_ag_action = QAction("AG", menu)
        self.tray_ag_action.triggered.connect(lambda: self._tray_switch("antigravity"))
        self.tray_split_action = QAction("分屏", menu)
        self.tray_split_action.triggered.connect(lambda: self._tray_switch("split"))
        self.tray_quit_action = QAction("退出", menu)
        self.tray_quit_action.triggered.connect(self.close)

        menu.addAction(self.tray_toggle_action)
        menu.addSeparator()
        menu.addAction(self.tray_gemini_action)
        menu.addAction(self.tray_ag_action)
        menu.addAction(self.tray_split_action)
        menu.addSeparator()
        menu.addAction(self.tray_quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_rail_visibility()

    def _tray_switch(self, mode: str) -> None:
        self._show_rail()
        self.switch_mode(mode)

    def _is_auto_hide(self) -> bool:
        return self.config.get("edge_mode", "top_pill") == "auto_hide"

    def _is_top_pill(self) -> bool:
        return self.config.get("edge_mode", "top_pill") == "top_pill"

    def _allows_full_left(self) -> bool:
        return self._rail_hidden or self._is_auto_hide() or self._is_top_pill()

    def _adjust_windows_for_edge_mode(self, prev_rail_w: int = 0) -> None:
        """Reserve or reclaim left rail space when switching edge modes."""
        if self._current_mode == "split":
            if self._get_ag_hwnd() and self._get_gemini_hwnd():
                self._place_split()
            return
        hwnd = self._active_target_hwnd()
        if not hwnd or is_window_minimized(hwnd):
            return
        wx, wy, ww, wh = get_work_area(hwnd)
        dpr = self.devicePixelRatioF()
        actual_rail_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))
        rail_span = max(actual_rail_w, prev_rail_w)
        tx, ty, tw, th = get_window_visual_rect(hwnd)
        if self._allows_full_left():
            if (not is_window_maximized(hwnd)) and (wx < tx <= wx + rail_span + 24):
                nw = (tx + tw) - wx if (tx + tw >= wx + ww - 16) else tw
                place_window_visual_rect(hwnd, wx, ty, nw, th, activate=False)
        else:
            if is_window_maximized(hwnd):
                place_window_visual_rect(
                    hwnd, wx + actual_rail_w, wy, max(480, ww - actual_rail_w), wh, activate=False
                )
            elif tx < wx + actual_rail_w:
                nx = wx + actual_rail_w
                nw = min(tw, max(480, (wx + ww) - nx))
                ny = max(wy, ty)
                nh = min(th, max(320, (wy + wh) - ny))
                place_window_visual_rect(hwnd, nx, ny, nw, nh, activate=False)

    def _set_edge_mode(self, edge_mode: str) -> None:
        prev_rail_w = self._last_rail_rect[2] if self._last_rail_rect else 0
        if not prev_rail_w and self.isVisible():
            prev_rail_w = get_window_visual_rect(int(self.winId()))[2]
        self.config["edge_mode"] = edge_mode
        save_config(self.config)
        self.settings_popover.sync_edge_mode(edge_mode)
        self._last_rail_rect = None
        self._last_sensor_rect = None
        self._last_pill_rect = None
        self._last_titlebar_rect = None
        self._auto_rail_open = False
        self.edge_sensor.hide()
        self.top_pill.hide()
        self.titlebar.set_pill_visible(False)
        if edge_mode == "push":
            if not self._rail_hidden:
                self.show()
                set_window_rounded_corners(int(self.winId()))
        else:
            self.hide()
        self._adjust_windows_for_edge_mode(prev_rail_w)
        self._apply_topmost_all()
        self._snap_to_active_window()

    def _collapse_rail_to_pill(self) -> None:
        """Collapse left rail into TopPillBar and switch edge_mode to top_pill."""
        self.settings_popover.hide()
        self._rail_hidden = False
        self._set_edge_mode("top_pill")
        self._sync_tray_texts()

    def _expand_rail_from_pill(self) -> None:
        """Expand TopPillBar back into the docked left rail (push mode)."""
        self.settings_popover.hide()
        self._rail_hidden = False
        self._set_edge_mode("push")
        self._sync_tray_texts()

    def _open_auto_rail(self) -> None:
        if self._rail_hidden or not self._is_auto_hide():
            return
        self._auto_rail_open = True
        self._auto_hide_deadline = time.monotonic() + 0.35
        self.edge_sensor.hide()
        if not self.isVisible():
            self.show()
            set_window_rounded_corners(int(self.winId()))
        set_topmost(int(self.winId()), True)

    def _close_auto_rail(self) -> None:
        self._auto_rail_open = False
        set_topmost(int(self.winId()), bool(self.config.get("always_on_top", False)))
        if self.isVisible():
            self.hide()

    def _hide_rail(self) -> None:
        self._rail_hidden = True
        self._auto_rail_open = False
        self.settings_popover.hide()
        self.edge_sensor.hide()
        self.top_pill.hide()
        self.titlebar.set_pill_visible(False)
        self.hide()
        self._sync_tray_texts()

    def _show_rail(self) -> None:
        self._rail_hidden = False
        self._last_rail_rect = None
        self._last_pill_rect = None
        if self._is_auto_hide():
            self._open_auto_rail()
        elif not self._is_top_pill():
            self.edge_sensor.hide()
            self.show()
        self._snap_to_active_window()
        self._sync_tray_texts()

    def _toggle_rail_visibility(self) -> None:
        if self._rail_hidden or (
            not self.isVisible()
            and not self.top_pill.isVisible()
            and not self.titlebar.pill.isVisible()
        ):
            self._show_rail()
        else:
            self._hide_rail()

    def _sync_tray_texts(self) -> None:
        lang = self.config.get("language", "zh-CN")
        self.tray_toggle_action.setText(
            tr(lang, "tray_show") if self._rail_hidden else tr(lang, "tray_hide")
        )
        self.tray_gemini_action.setText(tr(lang, "gemini"))
        self.tray_ag_action.setText(tr(lang, "ag"))
        self.tray_split_action.setText(tr(lang, "split"))
        self.tray_quit_action.setText(tr(lang, "exit"))

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+1"), self).activated.connect(
            lambda: self.switch_mode("gemini")
        )
        QShortcut(QKeySequence("Ctrl+2"), self).activated.connect(
            lambda: self.switch_mode("antigravity")
        )
        QShortcut(QKeySequence("Ctrl+3"), self).activated.connect(
            lambda: self.switch_mode("split")
        )
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(
            lambda: self._step_font_size(-1)
        )
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(
            lambda: self._step_font_size(1)
        )
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(
            lambda: self._set_font_size(14)
        )

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._allows_full_left()
            and self._current_mode != "split"
        ):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint() - self._drag_pos
            geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
            cx = max(geo.left(), min(pos.x(), geo.right() - self.width() + 1))
            cy = max(geo.top(), min(pos.y(), geo.bottom() - self.height() + 1))
            self.move(cx, cy)
            hwnd = self._active_target_hwnd()
            if hwnd and not is_window_minimized(hwnd):
                rx, ry, rw, _rh = get_window_visual_rect(int(self.winId()))
                _tx, _ty, tw, th = get_window_visual_rect(hwnd)
                place_window_visual_rect(hwnd, rx + rw, ry, tw, th, activate=False)
                self._last_rail_rect = (rx, ry, rw, _rh)
                if self.titlebar.isVisible() and self._gemini_hwnd == hwnd:
                    wx, wy, _ww, _wh = get_work_area(hwnd)
                    dpr = self.devicePixelRatioF()
                    tb_h = max(TITLEBAR_HEIGHT, round(TITLEBAR_HEIGHT * dpr))
                    gx, gy, gw, _gh = get_window_visual_rect(hwnd)
                    tb_rect = (max(gx, rx + rw), max(wy, gy), max(200, gw), tb_h)
                    self._last_titlebar_rect = tb_rect
                    place_window_visual_rect(int(self.titlebar.winId()), *tb_rect, activate=False)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _apply_ui_stylesheet(self, ui_theme: str) -> None:
        self._ui_theme = ui_theme
        qss = build_stylesheet(ui_theme)
        self.setStyleSheet(qss)
        self.settings_popover.setStyleSheet(qss)
        self.titlebar.setStyleSheet(qss)
        self.edge_sensor.setStyleSheet(qss)
        self.top_pill.setStyleSheet(qss)
        self.titlebar.update_theme(ui_theme)
        self._refresh_icons()

    def _apply_theme(self, theme: str, persist: bool = True) -> None:
        self.config["theme"] = theme
        if persist:
            self._save_timer.start()
        self._apply_ui_stylesheet(theme)
        is_dark = theme == "dark"
        gem_hwnd = self._get_gemini_hwnd()
        if gem_hwnd:
            set_window_dark_titlebar(gem_hwnd, is_dark)
        ag_hwnd = self._get_ag_hwnd()
        if ag_hwnd:
            set_window_dark_titlebar(ag_hwnd, is_dark)
        port = self._resolve_cdp_port()
        if port:
            dispatch_cdp(set_color_scheme_on_gemini, port, theme)

    def _sync_ag_ui_theme(self) -> None:
        """Auto-match Mix UI theme to Antigravity's visual brightness while in AG mode."""
        if self._current_mode != "antigravity":
            return
        ag_hwnd = self._get_ag_hwnd()
        if not ag_hwnd or is_window_minimized(ag_hwnd):
            return
        fg = get_foreground_hwnd()
        if fg not in (ag_hwnd, int(self.winId()), int(self.top_pill.winId())):
            return
        detected = detect_window_theme(ag_hwnd, self.devicePixelRatioF())
        if detected and detected != self._ui_theme:
            self._apply_ui_stylesheet(detected)
            set_window_dark_titlebar(ag_hwnd, detected == "dark")

    def _toggle_theme(self) -> None:
        next_theme = "light" if self.config.get("theme") == "dark" else "dark"
        self._apply_theme(next_theme, persist=True)

    def _toggle_settings_popover(self, from_pill: bool = False) -> None:
        if self.settings_popover.isVisible():
            self.settings_popover.hide()
            return
        if time.monotonic() - self.settings_popover.last_hide_time < 0.2:
            return
        self.settings_popover.adjustSize()
        pop_w = self.settings_popover.width()
        pop_h = self.settings_popover.height()
        if from_pill and self.titlebar.isVisible() and self.titlebar.pill.isVisible():
            btn = self.titlebar.pill.settings_btn
            btn_bl = btn.mapToGlobal(btn.rect().bottomLeft())
            geo = (self.titlebar.screen() or self.screen()).availableGeometry()
            x = max(geo.left() + 8, min(btn_bl.x() - pop_w // 2, geo.right() - pop_w - 8))
            y = max(geo.top() + 8, min(btn_bl.y() + 8, geo.bottom() - pop_h - 8))
        elif from_pill and self.top_pill.isVisible():
            btn = self.top_pill.settings_btn
            btn_bl = btn.mapToGlobal(btn.rect().bottomLeft())
            geo = (self.top_pill.screen() or self.screen()).availableGeometry()
            x = max(geo.left() + 8, min(btn_bl.x() - pop_w // 2, geo.right() - pop_w - 8))
            y = max(geo.top() + 8, min(btn_bl.y() + 8, geo.bottom() - pop_h - 8))
        else:
            btn_top_right = self.settings_btn.mapToGlobal(self.settings_btn.rect().topRight())
            x = btn_top_right.x() + 8
            y = max(10, btn_top_right.y() + self.settings_btn.height() - pop_h)
        self.settings_popover.move(x, y)
        self.settings_popover.show()
        set_window_rounded_corners(int(self.settings_popover.winId()))

    def _set_startup_mode(self, mode: str) -> None:
        self.config["mode"] = mode
        save_config(self.config)

    def _set_language(self, lang: str) -> None:
        self._apply_language(lang, persist=True)
        port = self._resolve_cdp_port()
        if port:
            dispatch_cdp(set_language_on_gemini, port, lang)

    def _apply_language(self, lang: str, persist: bool = True) -> None:
        self.config["language"] = lang
        if persist:
            save_config(self.config)
        self.brand_label.setToolTip(tr(lang, "tip_brand"))
        self.gemini_btn.setText(tr(lang, "gemini"))
        self.gemini_btn.setToolTip(tr(lang, "tip_gemini"))
        self.ag_btn.setText(tr(lang, "ag"))
        self.ag_btn.setToolTip(tr(lang, "tip_ag"))
        self.split_btn.setText(tr(lang, "split"))
        self.split_btn.setToolTip(tr(lang, "tip_split"))
        self.pin_btn.setText(tr(lang, "pin"))
        self.pin_btn.setToolTip(tr(lang, "tip_pin"))
        self.theme_btn.setText(tr(lang, "theme"))
        self.theme_btn.setToolTip(tr(lang, "tip_theme"))
        self.settings_btn.setText(tr(lang, "settings"))
        self.settings_btn.setToolTip(tr(lang, "tip_settings"))
        self.hide_btn.setText(tr(lang, "hide"))
        self.hide_btn.setToolTip(tr(lang, "tip_collapse_to_pill"))
        self.close_btn.setText(tr(lang, "exit"))
        self.close_btn.setToolTip(tr(lang, "tip_exit"))
        self.settings_popover.apply_language(lang)
        self.top_pill.apply_language(lang)
        self.titlebar.pill.apply_language(lang)
        self._sync_tray_texts()
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        p = get_theme_palette(self._ui_theme)
        lang = self.config.get("language", "zh-CN")
        icon_color = p["icon"]
        active_color = p["icon_active"]

        show_theme_btn = self._current_mode != "antigravity"
        if self.theme_btn.isHidden() == show_theme_btn:
            self.theme_btn.setVisible(show_theme_btn)
        self.top_pill.set_theme_btn_visible(show_theme_btn)
        self.titlebar.pill.set_theme_btn_visible(show_theme_btn)

        mapping = {"gemini": self.gemini_btn, "antigravity": self.ag_btn, "split": self.split_btn}
        mapping.get(self._current_mode, self.gemini_btn).setChecked(True)

        self.gemini_btn.setIcon(
            make_svg_icon("gemini", active_color if self._current_mode == "gemini" else icon_color)
        )
        self.ag_btn.setIcon(
            make_svg_icon(
                "antigravity",
                active_color if self._current_mode == "antigravity" else icon_color,
            )
        )
        self.split_btn.setIcon(
            make_svg_icon("split", active_color if self._current_mode == "split" else icon_color)
        )
        self.pin_btn.setIcon(
            make_svg_icon("pin", active_color if self.pin_btn.isChecked() else icon_color)
        )
        self.theme_btn.setIcon(
            make_svg_icon("sun" if self._ui_theme == "dark" else "moon", icon_color)
        )
        self.settings_btn.setIcon(make_svg_icon("sliders", icon_color))
        self.hide_btn.setIcon(make_svg_icon("eye_off", icon_color))

        if self._ag_running:
            self.ag_status_label.setText(tr(lang, "online"))
            self.ag_status_label.setStyleSheet(
                f"font-size: 10px; color: {p['status_ok']}; font-weight: 600;"
            )
        else:
            self.ag_status_label.setText(tr(lang, "offline"))
            self.ag_status_label.setStyleSheet(f"font-size: 10px; color: {p['status_off']};")
        self.top_pill.sync_state(
            self._current_mode,
            self._ui_theme,
            self._ag_running,
            self.pin_btn.isChecked(),
        )
        self.titlebar.pill.sync_state(
            self._current_mode,
            self._ui_theme,
            self._ag_running,
            self.pin_btn.isChecked(),
        )

    def _get_ag_hwnd(self) -> int:
        cfg_path = self.config.get("antigravity_path", "")
        if self._ag_hwnd:
            if is_antigravity_hwnd(self._ag_hwnd, cfg_path):
                return self._ag_hwnd
            self._ag_hwnd = 0
        hwnd = find_antigravity_hwnd(exclude_hwnd=int(self.winId()), configured_path=cfg_path)
        if hwnd:
            self._ag_hwnd = hwnd
        return hwnd

    def _get_gemini_hwnd(self) -> int:
        profile_dir = str(BROWSER_PROFILE_DIR)
        browser_pid = self._get_browser_pid()
        if self._gemini_hwnd:
            if is_gemini_app_hwnd(
                self._gemini_hwnd, profile_dir=profile_dir, browser_pid=browser_pid
            ):
                return self._gemini_hwnd
            self._gemini_hwnd = 0
        hwnd = find_gemini_app_hwnd(browser_pid, profile_dir=profile_dir)
        if hwnd:
            self._gemini_hwnd = hwnd
        return hwnd

    def _apply_topmost_all(self) -> None:
        pinned = bool(self.config.get("always_on_top", False))
        set_topmost(int(self.winId()), pinned)
        set_topmost(int(self.top_pill.winId()), pinned)
        gem_hwnd = self._get_gemini_hwnd()
        ag_hwnd = self._get_ag_hwnd()
        if self._current_mode == "gemini":
            if gem_hwnd:
                set_topmost(gem_hwnd, pinned)
                set_topmost(int(self.titlebar.winId()), pinned)
                set_topmost(int(self.bottom_resize_bar.winId()), pinned)
        elif self._current_mode == "antigravity":
            if ag_hwnd:
                set_topmost(ag_hwnd, pinned)
        elif self._current_mode == "split":
            if gem_hwnd:
                set_topmost(gem_hwnd, pinned)
                set_topmost(int(self.titlebar.winId()), pinned)
                set_topmost(int(self.bottom_resize_bar.winId()), pinned)
            if ag_hwnd:
                set_topmost(ag_hwnd, pinned)

    def _on_toggle_pin(self, checked: bool) -> None:
        self.config["always_on_top"] = checked
        save_config(self.config)
        self._apply_topmost_all()
        self._refresh_icons()

    def _step_font_size(self, delta: int) -> None:
        self._set_font_size(self.config["font_size"] + delta)

    def _set_font_size(self, value: int) -> None:
        min_fs = int(self.config["min_font_size"])
        max_fs = int(self.config["max_font_size"])
        clamped = max(min_fs, min(max_fs, int(value)))
        self.config["font_size"] = clamped
        self.settings_popover.sync_font_display(clamped)
        self._save_timer.start()
        self._font_cdp_timer.start()

    def _resolve_cdp_port(self) -> int:
        live_port = find_browser_cdp_port(str(BROWSER_PROFILE_DIR))
        if live_port:
            if live_port != self._cdp_port:
                self._cdp_port = live_port
                self._save_cdp_port(live_port)
            return live_port
        return self._cdp_port

    def _inject_font_only(self) -> None:
        port = self._resolve_cdp_port()
        if not port:
            return
        js = build_injection_js(self.config["font_size"], self.config["theme"])
        dispatch_cdp(inject_js_into_gemini, port, js)

    def _inject_css_now(self) -> None:
        port = self._resolve_cdp_port()
        if not port:
            return
        js = build_injection_js(self.config["font_size"], self.config["theme"])
        dispatch_cdp(inject_js_into_gemini, port, js)
        dispatch_cdp(set_color_scheme_on_gemini, port, self.config["theme"])

    def _get_browser_pid(self) -> int:
        if self._browser_proc and self._browser_proc.poll() is None:
            return self._browser_proc.pid
        return 0

    def _read_saved_cdp_port(self) -> int:
        try:
            if CDP_PORT_FILE.exists():
                port = int(CDP_PORT_FILE.read_text(encoding="utf-8").strip())
                if list_page_targets(port):
                    return port
        except (OSError, ValueError):
            pass
        return 0

    def _save_cdp_port(self, port: int) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CDP_PORT_FILE.write_text(str(port), encoding="utf-8")
        except OSError:
            pass

    def _launch_or_focus_gemini(self, target_url: str = "") -> None:
        launch_url = target_url or self._pending_gemini_url or GEMINI_URL
        profile_dir = str(BROWSER_PROFILE_DIR)
        if (
            self._gemini_hwnd
            and find_gemini_app_hwnd(self._get_browser_pid(), profile_dir=profile_dir)
            == self._gemini_hwnd
        ):
            self._resolve_cdp_port()
            self._place_gemini_full()
            return

        # Reuse already-running MixGemini Chrome profile if present
        existing_port = find_browser_cdp_port(profile_dir) or self._read_saved_cdp_port()
        if existing_port and not target_url:
            self._cdp_port = existing_port
            self._save_cdp_port(existing_port)
            hwnd = find_gemini_app_hwnd(0, profile_dir=profile_dir)
            if hwnd:
                self._gemini_hwnd = hwnd
                if self._current_mode == "gemini":
                    self._place_gemini_full()
                elif self._current_mode == "split":
                    self._place_split()
                elif self._current_mode == "antigravity":
                    hide_window(hwnd)
                self._inject_css_now()
                return

        browser_exe = find_browser_executable()
        if not browser_exe:
            QMessageBox.warning(
                self,
                "未找到浏览器",
                "未检测到 Google Chrome 或 Microsoft Edge，无法启动 Gemini 窗口。",
            )
            return

        BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        if not self._browser_proc or self._browser_proc.poll() is not None:
            self._cdp_port = find_free_port()
            self._save_cdp_port(self._cdp_port)
            args = [
                browser_exe,
                f"--app={launch_url}",
                f"--user-data-dir={BROWSER_PROFILE_DIR}",
                f"--remote-debugging-port={self._cdp_port}",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            self._browser_proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        QTimer.singleShot(700, self._attach_launched_gemini)

    def _attach_launched_gemini(self, attempt: int = 0) -> None:
        hwnd = find_gemini_app_hwnd(self._get_browser_pid(), profile_dir=str(BROWSER_PROFILE_DIR))
        if hwnd:
            self._gemini_hwnd = hwnd
            set_window_dark_titlebar(hwnd, self.config.get("theme") == "dark")
            if self._current_mode == "gemini":
                self._place_gemini_full()
            elif self._current_mode == "split":
                self._place_split()
            elif self._current_mode == "antigravity":
                hide_window(hwnd)
            self._inject_css_now()
            return
        if attempt < 15:
            QTimer.singleShot(350, lambda: self._attach_launched_gemini(attempt + 1))

    def _active_target_hwnd(self) -> int:
        now = time.monotonic()
        if self._current_mode in ("gemini", "split"):
            if self._gemini_hwnd and is_window_valid(self._gemini_hwnd):
                return self._gemini_hwnd
            if now - self._last_target_probe >= 0.35:
                self._last_target_probe = now
                hwnd = self._get_gemini_hwnd()
                if hwnd and self._current_mode == "gemini":
                    QTimer.singleShot(0, self._place_gemini_full)
                return hwnd
            return 0
        if self._ag_hwnd and is_window_valid(self._ag_hwnd):
            return self._ag_hwnd
        if now - self._last_target_probe >= 0.35:
            self._last_target_probe = now
            return self._get_ag_hwnd()
        return 0

    def _start_target_resize(self, edge: str, hwnd: int = 0) -> bool:
        target = hwnd or self._get_gemini_hwnd()
        if not target or is_window_minimized(target):
            return False
        self._resize_edge = edge
        self._resize_hwnd = target
        self._resize_start_cursor = get_cursor_pos()
        self._resize_start_rect = get_window_visual_rect(target)
        return True

    def _update_target_resize(self) -> None:
        if (
            not self._resize_edge
            or not self._resize_hwnd
            or not is_window_valid(self._resize_hwnd)
        ):
            self._end_target_resize()
            return
        cx, cy = get_cursor_pos()
        cx0, cy0 = self._resize_start_cursor
        gx0, gy0, gw0, gh0 = self._resize_start_rect
        dx = cx - cx0
        dy = cy - cy0

        wx, wy, ww, wh = get_work_area(self._resize_hwnd)
        dpr = self.devicePixelRatioF()
        min_w = max(480, round(480 * dpr))
        min_h = max(320, round(320 * dpr))
        min_x = wx
        if not self._allows_full_left() and self.isVisible():
            actual_rail_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))
            _rx, _ry, cur_rw, _rh = get_window_visual_rect(int(self.winId()))
            if cur_rw >= RAIL_WIDTH:
                actual_rail_w = cur_rw
            min_x = wx + actual_rail_w

        nx, ny, nw, nh = gx0, gy0, gw0, gh0
        if "top" in self._resize_edge:
            bottom0 = gy0 + gh0
            ny = max(wy, min(bottom0 - min_h, gy0 + dy))
            nh = bottom0 - ny
        if "bottom" in self._resize_edge:
            new_bottom = max(gy0 + min_h, min(wy + wh, gy0 + gh0 + dy))
            nh = new_bottom - gy0
        if "left" in self._resize_edge:
            right0 = gx0 + gw0
            nx = max(min_x, min(right0 - min_w, gx0 + dx))
            nw = right0 - nx
        if "right" in self._resize_edge:
            new_right = max(gx0 + min_w, min(wx + ww, gx0 + gw0 + dx))
            nw = new_right - gx0

        place_window_visual_rect(self._resize_hwnd, nx, ny, nw, nh, activate=False)

    def _end_target_resize(self) -> None:
        self._resize_edge = ""
        self._resize_hwnd = 0

    def _release_drag_clip(self) -> None:
        if self._drag_clip_active:
            unclip_cursor()
            self._drag_clip_active = False
            self._drag_clip_hwnd = 0
            self._drag_clip_min_x = 0

    def _snap_to_active_window(self) -> None:
        """Continuously glue the rail / top pill, titlebar, and Z-order layer."""
        if self._drag_pos is not None:
            return
        if self._resize_edge:
            if is_left_mouse_down():
                self._update_target_resize()
            else:
                self._end_target_resize()
        if self._drag_clip_active and (not is_left_mouse_down() or self._allows_full_left()):
            self._release_drag_clip()
        fg = get_foreground_hwnd()
        if (
            self._current_mode == "antigravity"
            and self._gemini_hwnd
            and fg == self._gemini_hwnd
            and is_window_visible(self._gemini_hwnd)
        ):
            self.switch_mode("gemini")
            return
        if (
            self._current_mode == "gemini"
            and self._ag_hwnd
            and fg == self._ag_hwnd
            and is_window_visible(self._ag_hwnd)
        ):
            self.switch_mode("antigravity")
            return
        hwnd = self._active_target_hwnd()
        if not hwnd:
            self._release_drag_clip()
            self.titlebar.set_pill_visible(False)
            if self.titlebar.isVisible():
                self.titlebar.hide()
            if self.bottom_resize_bar.isVisible():
                self.bottom_resize_bar.hide()
                self._last_bottom_bar_rect = None
            if self.edge_sensor.isVisible():
                self.edge_sensor.hide()
            if self._rail_hidden:
                if self.isVisible():
                    self.hide()
                if self.top_pill.isVisible():
                    self.top_pill.hide()
            elif self._is_top_pill():
                if self.isVisible():
                    self.hide()
                if not self.top_pill.isVisible():
                    wx, wy, ww, _wh = get_work_area(0)
                    dpr = self.devicePixelRatioF()
                    self.top_pill.adjustSize()
                    pw = max(240, round(self.top_pill.width() * dpr))
                    ph = max(32, round(self.top_pill.height() * dpr))
                    px = max(wx + 8, wx + (ww - pw) // 2)
                    py = wy + max(4, round(4 * dpr))
                    self.top_pill.show()
                    set_window_rounded_corners(int(self.top_pill.winId()))
                    place_window_visual_rect(int(self.top_pill.winId()), px, py, pw, ph, activate=False)
            elif not self._is_auto_hide() and not self.isVisible():
                self.show()
            return
        if is_window_minimized(hwnd):
            self._release_drag_clip()
            self.titlebar.set_pill_visible(False)
            if self.titlebar.isVisible():
                self.titlebar.hide()
            if self.bottom_resize_bar.isVisible():
                self.bottom_resize_bar.hide()
                self._last_bottom_bar_rect = None
            if self.edge_sensor.isVisible():
                self.edge_sensor.hide()
            if self.isVisible() and not self.settings_popover.isVisible():
                self.hide()
            if self.top_pill.isVisible() and not self.settings_popover.isVisible():
                self.top_pill.hide()
            return

        tx, ty, tw, th = get_window_visual_rect(hwnd)
        wx, wy, ww, wh = get_work_area(hwnd)
        dpr = self.devicePixelRatioF()
        actual_rail_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))
        if self.isVisible():
            _rx, _ry, cur_rw, _rh = get_window_visual_rect(int(self.winId()))
            if cur_rw >= RAIL_WIDTH:
                actual_rail_w = cur_rw
        gem_hwnd = self._gemini_hwnd if is_window_valid(self._gemini_hwnd) else 0

        if self._rail_hidden:
            self.titlebar.set_pill_visible(False)
            if self.isVisible():
                self.hide()
            if self.edge_sensor.isVisible():
                self.edge_sensor.hide()
            if self.top_pill.isVisible():
                self.top_pill.hide()
        elif self._is_auto_hide():
            self.titlebar.set_pill_visible(False)
            if self.top_pill.isVisible():
                self.top_pill.hide()
            # Option 2: Edge sensor + hover slide-out (window can touch x=0 / full width)
            rail_y = max(wy, ty)
            rail_h = min(wh - (rail_y - wy), max(320, th))
            cx, cy = get_cursor_pos()
            in_left_trigger = wx <= cx <= wx + max(8, round(6 * dpr)) and rail_y <= cy <= rail_y + rail_h
            in_open_rail = (
                self._auto_rail_open
                and wx <= cx <= wx + actual_rail_w + round(14 * dpr)
                and rail_y <= cy <= rail_y + rail_h
            )
            if in_left_trigger or in_open_rail or self.settings_popover.isVisible():
                self._auto_hide_deadline = time.monotonic() + 0.24
                if not self._auto_rail_open:
                    self._open_auto_rail()
            elif self._auto_rail_open and time.monotonic() >= self._auto_hide_deadline:
                self._close_auto_rail()

            if self._auto_rail_open:
                if self.edge_sensor.isVisible():
                    self.edge_sensor.hide()
                target_rect = (wx, rail_y, actual_rail_w, rail_h)
                if not self.isVisible():
                    self.show()
                    set_window_rounded_corners(int(self.winId()))
                    set_topmost(int(self.winId()), True)
                if target_rect != self._last_rail_rect:
                    self._last_rail_rect = target_rect
                    place_window_visual_rect(
                        int(self.winId()), wx, rail_y, actual_rail_w, rail_h, activate=False
                    )
            else:
                if self.isVisible():
                    self.hide()
                sensor_w = max(4, round(4 * dpr))
                sensor_rect = (wx, rail_y + 18, sensor_w, max(120, rail_h - 36))
                if not self.edge_sensor.isVisible():
                    self.edge_sensor.show()
                if sensor_rect != self._last_sensor_rect:
                    self._last_sensor_rect = sensor_rect
                    place_window_visual_rect(
                        int(self.edge_sensor.winId()),
                        sensor_rect[0],
                        sensor_rect[1],
                        sensor_rect[2],
                        sensor_rect[3],
                        activate=False,
                    )
        elif self._is_top_pill():
            # Option 3: Always hide 68px left rail and present compact top pill
            if self.edge_sensor.isVisible():
                self.edge_sensor.hide()
            if self.isVisible():
                self.hide()
                self._last_rail_rect = None
            use_inline_pill = (
                self._current_mode in ("gemini", "split")
                and bool(gem_hwnd)
                and (not is_window_minimized(gem_hwnd))
                and (tw >= round(540 * dpr))
            )
            if use_inline_pill:
                if self.top_pill.isVisible():
                    self.top_pill.hide()
                    self._last_pill_rect = None
                self.titlebar.set_pill_visible(True, narrow=(tw < round(620 * dpr)))
            else:
                self.titlebar.set_pill_visible(False)
                self.top_pill.adjustSize()
                pw = max(240, round(self.top_pill.width() * dpr))
                ph = max(32, round(self.top_pill.height() * dpr))
                center_x, center_w = (wx, ww) if self._current_mode == "split" else (tx, tw)
                base_y = wy if self._current_mode == "split" else ty
                px = max(wx + 8, min(center_x + (center_w - pw) // 2, wx + ww - pw - 8))
                py = max(wy, base_y + max(2, round(2 * dpr)))
                pill_rect = (px, py, pw, ph)
                if not self.top_pill.isVisible():
                    self.top_pill.show()
                    set_window_rounded_corners(int(self.top_pill.winId()))
                    self._last_pill_rect = None
                if pill_rect != self._last_pill_rect:
                    self._last_pill_rect = pill_rect
                    place_window_visual_rect(
                        int(self.top_pill.winId()), px, py, pw, ph, activate=False
                    )
        else:
            # Option 1: Left-edge anti-collision push-back + persistent docked rail
            self.titlebar.set_pill_visible(False)
            if self.edge_sensor.isVisible():
                self.edge_sensor.hide()
            if self.top_pill.isVisible():
                self.top_pill.hide()
            if not self.isVisible():
                self.show()

            if is_window_maximized(hwnd):
                self._release_drag_clip()
                fx, fy, fw, fh = wx + actual_rail_w, wy, max(480, ww - actual_rail_w), wh
                place_window_visual_rect(hwnd, fx, fy, fw, fh, activate=False)
                tx, ty, tw, th = fx, fy, fw, fh
            else:
                in_movesize = (
                    is_left_mouse_down()
                    and not self._resize_edge
                    and is_window_in_movesize(hwnd)
                )
                if in_movesize:
                    cx, cy = get_cursor_pos()
                    if not self._drag_clip_active or self._drag_clip_hwnd != hwnd:
                        is_right_resize = cx >= tx + tw - round(16 * dpr) and cy > ty + round(36 * dpr)
                        is_bottom_only = cy >= ty + th - round(16 * dpr) and cx > tx + round(16 * dpr)
                        is_top_only = cy <= ty + round(6 * dpr) and cx > tx + round(16 * dpr)
                        if not (is_right_resize or is_bottom_only or is_top_only):
                            min_cx = max(wx, min(wx + ww - 8, (wx + actual_rail_w) + (cx - tx)))
                            clip_cursor_min_x(min_cx, max_x=wx + ww, max_y=wy + wh)
                            self._drag_clip_active = True
                            self._drag_clip_hwnd = hwnd
                            self._drag_clip_min_x = min_cx
                    if tx < wx + actual_rail_w:
                        delta_x = (wx + actual_rail_w) - tx
                        min_cx = max(wx, min(wx + ww - 8, max(self._drag_clip_min_x, cx) + delta_x))
                        clip_cursor_min_x(min_cx, max_x=wx + ww, max_y=wy + wh)
                        self._drag_clip_active = True
                        self._drag_clip_hwnd = hwnd
                        self._drag_clip_min_x = min_cx
                        nx = wx + actual_rail_w
                        nw = min(tw, max(480, (wx + ww) - nx))
                        ny = max(wy, ty)
                        nh = min(th, max(320, (wy + wh) - ny))
                        place_window_visual_rect(hwnd, nx, ny, nw, nh, activate=False)
                        tx, ty, tw, th = nx, ny, nw, nh
                else:
                    self._release_drag_clip()
                    if tx < wx + actual_rail_w and not is_left_mouse_down():
                        nx = wx + actual_rail_w
                        nw = min(tw, max(480, (wx + ww) - nx))
                        ny = max(wy, ty)
                        nh = min(th, max(320, (wy + wh) - ny))
                        place_window_visual_rect(hwnd, nx, ny, nw, nh, activate=False)
                        tx, ty, tw, th = nx, ny, nw, nh

            rail_x = max(wx, tx - actual_rail_w)
            rail_y = max(wy, ty)
            rail_h = min(wh - (rail_y - wy), max(320, th))
            target_rect = (rail_x, rail_y, actual_rail_w, rail_h)
            if target_rect != self._last_rail_rect:
                self._last_rail_rect = target_rect
                place_window_visual_rect(
                    int(self.winId()), rail_x, rail_y, actual_rail_w, rail_h, activate=False
                )

        if self._current_mode in ("gemini", "split") and gem_hwnd and not is_window_minimized(gem_hwnd):
            gx, gy, gw, gh = get_window_visual_rect(gem_hwnd)
            tb_h = max(TITLEBAR_HEIGHT, round(TITLEBAR_HEIGHT * dpr))
            tb_left = gx
            tb_w = max(200, gw)
            if self.isVisible() and not self._allows_full_left() and gx < wx + actual_rail_w:
                tb_left = wx + actual_rail_w
                tb_w = max(200, gw - (tb_left - gx))
            tb_rect = (tb_left, max(wy, gy), tb_w, tb_h)
            if not self.titlebar.isVisible():
                self.titlebar.show()
                set_window_rounded_corners(int(self.titlebar.winId()))
            if tb_rect != self._last_titlebar_rect:
                self._last_titlebar_rect = tb_rect
                place_window_visual_rect(
                    int(self.titlebar.winId()), tb_rect[0], tb_rect[1], tb_rect[2], tb_rect[3], activate=False
                )

            br_h = max(6, round(6 * dpr))
            br_rect = (tb_left, max(wy, gy + gh - br_h), tb_w, br_h)
            if not self.bottom_resize_bar.isVisible():
                self.bottom_resize_bar.show()
            if br_rect != self._last_bottom_bar_rect:
                self._last_bottom_bar_rect = br_rect
                place_window_visual_rect(
                    int(self.bottom_resize_bar.winId()),
                    br_rect[0],
                    br_rect[1],
                    br_rect[2],
                    br_rect[3],
                    activate=False,
                )
        else:
            if self.titlebar.isVisible():
                self.titlebar.set_pill_visible(False)
                self.titlebar.hide()
                self._last_titlebar_rect = None
            if self.bottom_resize_bar.isVisible():
                self.bottom_resize_bar.hide()
                self._last_bottom_bar_rect = None

        # Keep MixRail / TopPill strictly above GeminiTitleBar and active target window
        rail_hwnd = (
            int(self.winId())
            if (not self._rail_hidden and not self._is_auto_hide() and self.isVisible())
            else 0
        )
        pill_hwnd = (
            int(self.top_pill.winId())
            if (not self._rail_hidden and self._is_top_pill() and self.top_pill.isVisible())
            else 0
        )
        dock_hwnd = pill_hwnd or rail_hwnd
        tb_hwnd = int(self.titlebar.winId()) if self.titlebar.isVisible() else 0
        br_hwnd = int(self.bottom_resize_bar.winId()) if self.bottom_resize_bar.isVisible() else 0
        ag_hwnd = self._ag_hwnd if is_window_valid(self._ag_hwnd) else 0
        fg = get_foreground_hwnd()

        if dock_hwnd and fg in (dock_hwnd, tb_hwnd, br_hwnd):
            followers: list[int] = []
            if tb_hwnd:
                followers.append(tb_hwnd)
            if br_hwnd:
                followers.append(br_hwnd)
            followers.append(hwnd)
            if self._current_mode == "split" and ag_hwnd and ag_hwnd != hwnd:
                followers.append(ag_hwnd)
            sync_group_below(dock_hwnd, followers)
        elif tb_hwnd and fg == tb_hwnd:
            followers = ([br_hwnd] if br_hwnd else []) + [hwnd]
            if self._current_mode == "split" and ag_hwnd and ag_hwnd != hwnd:
                followers.append(ag_hwnd)
            sync_group_below(tb_hwnd, followers)
        elif br_hwnd and fg == br_hwnd:
            followers = ([tb_hwnd] if tb_hwnd else []) + [hwnd]
            if self._current_mode == "split" and ag_hwnd and ag_hwnd != hwnd:
                followers.append(ag_hwnd)
            sync_group_below(br_hwnd, followers)
        else:
            z_target = hwnd
            if self._current_mode == "split":
                if ag_hwnd and fg == ag_hwnd:
                    z_target = ag_hwnd
                    if gem_hwnd and not is_window_minimized(gem_hwnd):
                        sync_group_below(ag_hwnd, [gem_hwnd])
                elif gem_hwnd and fg == gem_hwnd and ag_hwnd and not is_window_minimized(ag_hwnd):
                    z_target = gem_hwnd
                    sync_group_below(gem_hwnd, [ag_hwnd])
            overlays = (
                ([pill_hwnd] if pill_hwnd else [])
                + ([rail_hwnd] if rail_hwnd else [])
                + ([tb_hwnd] if tb_hwnd else [])
                + ([br_hwnd] if br_hwnd else [])
            )
            if overlays:
                sync_z_order_above(z_target, overlays)

    def _content_area(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) in physical pixels matching the active right-hand area."""
        if self._pre_split_rect is not None and self._current_mode in ("gemini", "antigravity"):
            rect = self._pre_split_rect
            self._pre_split_rect = None
            if rect[2] >= 480 and rect[3] >= 320:
                return rect

        wx, wy, ww, wh = get_work_area(int(self.winId()))
        dpr = self.devicePixelRatioF()
        rail_phys_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))

        # If there is an active visible non-split right window, preserve its current size/position
        if self._current_mode in ("gemini", "antigravity"):
            other_hwnd = (
                self._get_ag_hwnd()
                if self._current_mode == "gemini"
                else self._get_gemini_hwnd()
            )
            if other_hwnd and is_window_visible(other_hwnd) and not is_window_minimized(other_hwnd):
                ox, oy, ow, oh = get_window_visual_rect(other_hwnd)
                if ow >= 480 and oh >= 320:
                    if not self._allows_full_left() and ox < wx + rail_phys_w:
                        ox = wx + rail_phys_w
                        ow = min(ow, max(480, (wx + ww) - ox))
                    elif self._allows_full_left() and wx < ox <= wx + rail_phys_w + 16:
                        if ox + ow >= wx + ww - 16:
                            ow = (ox + ow) - wx
                        ox = wx
                    return ox, oy, ow, oh

        if self._allows_full_left():
            return wx, wy, max(480, ww), wh
        return wx + rail_phys_w, wy, max(480, ww - rail_phys_w), wh

    def _place_gemini_full(self) -> None:
        hwnd = self._get_gemini_hwnd()
        if not hwnd:
            self._launch_or_focus_gemini()
            return
        show_window(hwnd)
        cx, cy, cw, ch = self._content_area()
        place_window_visual_rect(hwnd, cx, cy, cw, ch, activate=True)
        activate_window(hwnd)
        ag_hwnd = self._get_ag_hwnd()
        if ag_hwnd:
            set_topmost(ag_hwnd, False)
            hide_window(ag_hwnd)
        self._apply_topmost_all()
        self._snap_to_active_window()

    def _place_antigravity_full(self) -> None:
        ag_hwnd = self._get_ag_hwnd()
        if not ag_hwnd:
            return
        show_window(ag_hwnd)
        cx, cy, cw, ch = self._content_area()
        place_window_visual_rect(ag_hwnd, cx, cy, cw, ch, activate=True)
        activate_window(ag_hwnd)
        gem_hwnd = self._get_gemini_hwnd()
        if gem_hwnd:
            set_topmost(gem_hwnd, False)
            hide_window(gem_hwnd)
        self._apply_topmost_all()
        self._snap_to_active_window()
        self._sync_ag_ui_theme()
        QTimer.singleShot(160, self._sync_ag_ui_theme)

    def _place_split(self) -> None:
        ag_hwnd = self._get_ag_hwnd()
        gem_hwnd = self._get_gemini_hwnd()
        if not ag_hwnd or not gem_hwnd:
            return
        show_window(gem_hwnd)
        show_window(ag_hwnd)
        wx, wy, ww, wh = get_work_area(int(self.winId()))
        if self._allows_full_left():
            cx = wx
            cw = max(640, ww)
        else:
            dpr = self.devicePixelRatioF()
            rail_phys_w = max(RAIL_WIDTH, round(RAIL_WIDTH * dpr))
            cx = wx + rail_phys_w
            cw = max(640, ww - rail_phys_w)
        left_w = cw // 2
        place_window_visual_rect(gem_hwnd, cx, wy, left_w, wh, activate=False)
        place_window_visual_rect(ag_hwnd, cx + left_w, wy, cw - left_w, wh, activate=False)
        activate_window(gem_hwnd)
        sync_group_below(gem_hwnd, [ag_hwnd])
        self._apply_topmost_all()
        self._snap_to_active_window()

    def _background_sync(self) -> None:
        ag_running = bool(self._get_ag_hwnd())
        if ag_running != self._ag_running:
            self._ag_running = ag_running
            self._refresh_icons()

        if self._current_mode == "split" and not ag_running:
            self.switch_mode("gemini")
            return

        was_gem = self._gemini_hwnd if is_window_valid(self._gemini_hwnd) else 0
        gem_hwnd = self._get_gemini_hwnd()
        if gem_hwnd and not was_gem:
            if self._current_mode == "gemini":
                self._place_gemini_full()
                self._inject_css_now()
            elif self._current_mode == "split":
                self._place_split()
                self._inject_css_now()
            elif self._current_mode == "antigravity":
                if get_foreground_hwnd() == gem_hwnd:
                    self.switch_mode("gemini")
                else:
                    hide_window(gem_hwnd)
        self._sync_ag_ui_theme()

        port = self._resolve_cdp_port()
        if port:
            js = build_injection_js(self.config["font_size"], self.config["theme"])
            dispatch_cdp(
                sync_gemini_if_navigated,
                port,
                js,
                self.config["theme"],
            )

    def _ensure_antigravity_or_launch(self, target_mode: str) -> bool:
        if self._get_ag_hwnd():
            return True

        if not launch_antigravity(self.config.get("antigravity_path", "")):
            QMessageBox.warning(
                self,
                "启动失败",
                "未找到 Antigravity.exe，请先手动打开 Antigravity。",
            )
            return False

        self.ag_status_label.setText("● 启动中")
        self._pending_launch_mode = target_mode
        self._launch_polls = 0
        self._launch_timer.start()
        return False

    def _poll_launched_antigravity(self) -> None:
        self._launch_polls += 1
        if find_antigravity_hwnd(
            exclude_hwnd=int(self.winId()),
            configured_path=self.config.get("antigravity_path", ""),
        ):
            self._launch_timer.stop()
            mode = self._pending_launch_mode or "antigravity"
            self._pending_launch_mode = None
            self.switch_mode(mode)
        elif self._launch_polls >= 25:
            self._launch_timer.stop()
            self._pending_launch_mode = None
            QMessageBox.information(
                self,
                "等待超时",
                "Antigravity 仍在启动中，窗口就绪后可再次点击切换。",
            )

    def switch_mode(self, mode: str) -> None:
        """Switch instantly between Gemini, Antigravity, and Split modes with zero flicker."""
        self._release_drag_clip()
        if mode == "split" and self._current_mode == "split":
            mode = self._pre_split_mode if self._pre_split_mode in ("gemini", "antigravity") else "gemini"

        if mode in ("antigravity", "split"):
            if not self._ensure_antigravity_or_launch(mode):
                self._refresh_icons()
                return

        if mode == "split" and self._current_mode != "split":
            self._pre_split_mode = self._current_mode
            active = (
                self._get_gemini_hwnd()
                if self._current_mode == "gemini"
                else self._get_ag_hwnd()
            )
            if active and not is_window_minimized(active):
                self._pre_split_rect = get_window_visual_rect(active)

        self._current_mode = mode
        if mode != "antigravity" and self._ui_theme != self.config["theme"]:
            self._apply_ui_stylesheet(self.config["theme"])
        else:
            self._refresh_icons()

        if mode == "gemini":
            self._place_gemini_full()
        elif mode == "antigravity":
            self._place_antigravity_full()
        elif mode == "split":
            self._place_split()

    def closeEvent(self, event) -> None:
        self._release_drag_clip()
        self._snap_timer.stop()
        self._sync_timer.stop()
        self._launch_timer.stop()
        self.tray_icon.hide()
        self.edge_sensor.close()
        self.top_pill.close()
        self.titlebar.close()
        self.bottom_resize_bar.close()
        save_config(self.config)
        if is_window_valid(self._ag_hwnd):
            show_window(self._ag_hwnd)
        port = self._resolve_cdp_port()
        if port:
            close_browser_via_cdp(port)
        if self._browser_proc and self._browser_proc.poll() is None:
            try:
                self._browser_proc.terminate()
            except OSError:
                pass
        try:
            if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass
        super().closeEvent(event)
        QApplication.instance().quit()


def _ensure_single_instance() -> None:
    """Terminate any stale MixGemini process before launching a new one."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            allowed_names = {"pythonw.exe", "python.exe", Path(sys.executable).name.lower()}
            if old_pid != os.getpid() and get_process_name(old_pid) in allowed_names:
                terminate_pid(old_pid)
        except (OSError, ValueError):
            pass
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    _ensure_single_instance()
    app = QApplication(sys.argv)
    app.setApplicationName("MixGemini")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    if APP_ICON_ICO.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON_ICO)))

    window = MixRailWindow()
    if not window._allows_full_left():
        window.show()
    else:
        window._snap_to_active_window()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
