"""
Subtitle Window - Multi-tab support
Transparent, always-on-top, draggable subtitle windows
"""

import sys
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QSystemTrayIcon, QMenu,
    QScrollArea, QFrame
)
from PyQt6.QtCore import (
    Qt, QPoint, pyqtSignal, QObject, QTimer,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QIcon, QAction

from event_bus import event_bus


WRAP_CHARS = 25  # 每行最多字符数，超出自动换行


def wrap_text(text: str, width: int = WRAP_CHARS) -> str:
    """按字符数硬换行：每 width 个字符插一个换行符"""
    if not text:
        return text
    return "\n".join(text[i:i + width] for i in range(0, len(text), width))


class SubtitleSignals(QObject):
    """Cross-thread signal passing"""
    update_subtitle = pyqtSignal(dict)
    remove_tab = pyqtSignal(str)


class SubtitleLabel(QLabel):
    """Subtitle label with outline effect"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outline_color = QColor(0, 0, 0, 200)
        self.text_color = QColor(255, 255, 255, 255)
        self.outline_width = 2

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        text = self.text()
        if not text:
            return

        painter.setFont(self.font())
        painter.setClipRect(self.rect())

        # 按 \n 分行，每行单独绘制（含描边）
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lines = text.split("\n")
        line_h = self.height() // max(1, len(lines))

        for i, line in enumerate(lines):
            line_rect = self.rect().adjusted(0, i * line_h, 0, 0)
            line_rect.setHeight(line_h)

            # 单行内若仍溢出，向左偏移让末尾贴右
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(line)
            usable = line_rect.width() - 2 * self.outline_width
            overflow = text_width - usable
            draw_rect = line_rect.adjusted(-overflow, 0, 0, 0) if overflow > 0 else line_rect

            painter.setPen(self.outline_color)
            for dx in range(-self.outline_width, self.outline_width + 1):
                for dy in range(-self.outline_width, self.outline_width + 1):
                    if dx != 0 or dy != 0:
                        painter.drawText(draw_rect.translated(dx, dy), flags, line)

            painter.setPen(self.text_color)
            painter.drawText(draw_rect, flags, line)


class SmoothScrollArea(QScrollArea):
    """支持平滑滚轮的 QScrollArea"""

    WHEEL_DURATION = 160         # 滚轮动画时长(ms)
    PIXELS_PER_NOTCH = 90        # 一格滚轮(120 delta)对应像素

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(self.WHEEL_DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._target: Optional[int] = None
        # 用户滚轮时回调，可用于打断外部正在进行的自动动画
        self.on_user_wheel = None  # type: ignore[assignment]

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        if bar.maximum() <= 0:
            event.accept()
            return

        if callable(self.on_user_wheel):
            self.on_user_wheel()

        # 累加到现有目标，连续快速滚轮也能叠加
        running = self._anim.state() == QPropertyAnimation.State.Running
        base = self._target if (running and self._target is not None) else bar.value()

        delta = event.angleDelta().y()
        step = int(delta / 120.0 * self.PIXELS_PER_NOTCH)
        target = base - step
        target = max(bar.minimum(), min(bar.maximum(), target))
        self._target = target

        self._anim.stop()
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(target)
        self._anim.start()
        event.accept()

    def stop_smooth(self):
        self._anim.stop()
        self._target = None


class TabSubtitleWidget(QFrame):
    """单 tab 字幕显示：新句子从下方滑入，旧句子向上滑出"""

    LINE_HEIGHT = 40           # 单行字幕高度
    EXPANDED_LINES = 10        # 展开模式可见行数（按 LINE_HEIGHT 计）
    SCROLL_DURATION = 220      # 滚动动画时长(ms)

    def __init__(self, tab_id: str, tab_title: str = "", parent=None):
        super().__init__(parent)
        self.tab_id = tab_id
        self.tab_title = tab_title or f"Tab {tab_id}"
        self.expanded = False
        self._scroll_anim: Optional[QPropertyAnimation] = None
        self._last_interim_lines = 1     # 当前 interim 行数，用于折叠模式高度
        self._last_history_height = 0    # 上一次插入历史 label 的高度，用于动画起点
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)

        self.title_label = QLabel(self.tab_title)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet("color: #aaa;")
        self.title_label.setMaximumHeight(20)

        # 滚动区：默认单行高，展开后多行高（支持平滑滚轮）
        self.history_scroll = SmoothScrollArea()
        self.history_scroll.on_user_wheel = self._on_user_wheel
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFixedHeight(self.LINE_HEIGHT)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.history_scroll.setStyleSheet("background: transparent; border: none;")
        self.history_scroll.viewport().setStyleSheet("background: transparent;")

        self.history_container = QWidget()
        self.history_container.setStyleSheet("background: transparent;")
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(0)
        self.history_layout.addStretch(1)  # 内容贴底

        self.history_scroll.setWidget(self.history_container)

        # 当前正在识别中的（interim）行
        self.subtitle_label = SubtitleLabel()
        self.subtitle_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        self.subtitle_label.setMinimumHeight(self.LINE_HEIGHT)
        self.subtitle_label.setFixedHeight(self.LINE_HEIGHT)
        self.history_layout.addWidget(self.subtitle_label)

        layout.addWidget(self.title_label)
        layout.addWidget(self.history_scroll)

        self.setStyleSheet("""
            TabSubtitleWidget {
                background-color: rgba(0, 0, 0, 100);
                border-radius: 8px;
                margin: 2px;
            }
        """)

    def _make_history_label(self, wrapped_text: str) -> "SubtitleLabel":
        lbl = SubtitleLabel()
        lbl.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        lines = max(1, wrapped_text.count("\n") + 1)
        lbl.setFixedHeight(self.LINE_HEIGHT * lines)
        lbl.setText(wrapped_text)
        return lbl

    def _apply_interim(self, wrapped_text: str):
        """更新 interim label 的内容与高度，并按折叠模式调整滚动区高度"""
        lines = max(1, wrapped_text.count("\n") + 1) if wrapped_text else 1
        self._last_interim_lines = lines
        self.subtitle_label.setFixedHeight(self.LINE_HEIGHT * lines)
        self.subtitle_label.setText(wrapped_text)
        self.subtitle_label.update()

        # 折叠模式：滚动区高度 = 当前 interim 的实际高度（最多 EXPANDED_LINES）
        if not self.expanded:
            visible_lines = min(lines, self.EXPANDED_LINES)
            self.history_scroll.setFixedHeight(self.LINE_HEIGHT * visible_lines)
            # 通知外层窗口同步调整高度
            self._notify_height_changed()

    def _notify_height_changed(self):
        parent = self.parent()
        while parent is not None and not isinstance(parent, SubtitleWindow):
            parent = parent.parent()
        if isinstance(parent, SubtitleWindow):
            parent.adjust_height()

    def _on_user_wheel(self):
        """用户主动滚轮时，打断自动滑入动画，把控制权交给用户"""
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
            self._scroll_anim = None

    def _anim_running(self) -> bool:
        return (
            self._scroll_anim is not None
            and self._scroll_anim.state() == QPropertyAnimation.State.Running
        )

    def update_subtitle(self, text: str, is_final: bool = False):
        wrapped = wrap_text(text, WRAP_CHARS)

        if is_final:
            # interim 行先定型为最终样式
            self.subtitle_label.text_color = QColor(255, 255, 255, 255)
            self._apply_interim(wrapped)

            # 复制为一条历史，插在 stretch 之后、当前行之前
            idx = self.history_layout.indexOf(self.subtitle_label)
            history_label = self._make_history_label(wrapped)
            self.history_layout.insertWidget(idx, history_label)
            self._last_history_height = history_label.height()

            # 清空当前行，等待下一句（恢复到 1 行高）
            self.subtitle_label.text_color = QColor(200, 200, 200, 255)
            self._apply_interim("")

            # 强制立刻完成布局，拿到准确的 maximum 再启动动画
            self.history_container.adjustSize()
            self.history_layout.activate()
            self._start_slide_in_anim()
        else:
            self.subtitle_label.text_color = QColor(200, 200, 200, 255)
            self._apply_interim(wrapped)
            # interim 不打断正在进行的滑入动画；否则贴底
            if not self._anim_running():
                self._snap_to_bottom()

    def _snap_to_bottom(self):
        bar = self.history_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _start_slide_in_anim(self):
        """从上一句尾部位置平滑滚到新底部，让整段新历史从下方滑入"""
        bar = self.history_scroll.verticalScrollBar()
        end_value = bar.maximum()
        # 起点 = 新底部 - 新历史条的高度，让整条历史从视口下沿滑入
        slide_distance = max(self.LINE_HEIGHT, self._last_history_height)
        start_value = max(0, end_value - slide_distance)

        if end_value <= 0 or start_value >= end_value:
            bar.setValue(end_value)
            return

        # 停掉旧动画
        if self._scroll_anim is not None:
            self._scroll_anim.stop()

        bar.setValue(start_value)
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(self.SCROLL_DURATION)
        anim.setStartValue(start_value)
        anim.setEndValue(end_value)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._scroll_anim = anim

    def set_expanded(self, expanded: bool):
        """切换单行/多行显示模式"""
        self.expanded = expanded
        # 切换时打断进行中的滚动动画，避免遗留状态
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
            self._scroll_anim = None

        if expanded:
            self.history_scroll.setFixedHeight(self.LINE_HEIGHT * self.EXPANDED_LINES)
            self.history_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
        else:
            # 折叠模式：高度跟随当前 interim 行数
            visible = min(self._last_interim_lines, self.EXPANDED_LINES)
            self.history_scroll.setFixedHeight(self.LINE_HEIGHT * visible)
            self.history_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

        # 强制立刻完成布局，再分两帧 snap，确保 maximum 已稳定
        self.history_container.adjustSize()
        self.history_layout.activate()
        self._snap_to_bottom()
        QTimer.singleShot(0, self._snap_to_bottom)
        QTimer.singleShot(30, self._snap_to_bottom)

    def content_height(self) -> int:
        """返回当前 tab 实际所需高度（标题 + 滚动区 + 边距）"""
        m = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        return (
            m.top() + m.bottom()
            + self.title_label.sizeHint().height()
            + spacing
            + self.history_scroll.height()
        )

    def set_title(self, title: str):
        self.tab_title = title
        self.title_label.setText(title)


class SubtitleWindow(QWidget):
    """Multi-tab subtitle window"""

    def __init__(self):
        super().__init__()
        self.drag_position: Optional[QPoint] = None
        self.is_locked = False
        self.expanded = False  # 展开模式：多行历史
        self.tab_widgets: Dict[str, TabSubtitleWidget] = {}
        self.init_ui()

    def init_ui(self):
        # Window properties
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 6, 10, 10)
        self.main_layout.setSpacing(4)

        # 顶部工具栏：展开/收起按钮
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(4)
        toolbar.addStretch(1)

        self.expand_btn = QPushButton("▼")
        self.expand_btn.setFixedSize(22, 22)
        self.expand_btn.setToolTip("展开历史字幕（多行）")
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.setStyleSheet(
            "QPushButton { color: #ddd; background: rgba(255,255,255,30);"
            " border: none; border-radius: 11px; font-size: 12px; }"
            "QPushButton:hover { background: rgba(255,255,255,60); }"
        )
        self.expand_btn.clicked.connect(self.toggle_expanded)
        toolbar.addWidget(self.expand_btn)

        self.main_layout.addLayout(toolbar)

        # Container for tab subtitles
        self.tabs_container = QWidget()
        self.tabs_layout = QVBoxLayout(self.tabs_container)
        self.tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_layout.setSpacing(5)

        # Placeholder label when no tabs
        self.placeholder_label = SubtitleLabel()
        self.placeholder_label.setFont(QFont("Microsoft YaHei", 18))
        self.placeholder_label.setText("Waiting for audio input...")
        self.placeholder_label.setMinimumHeight(50)
        self.tabs_layout.addWidget(self.placeholder_label)

        self.main_layout.addWidget(self.tabs_container)

        # Set initial size and position
        self.resize(900, 120)
        self.move_to_bottom_center()

    def move_to_bottom_center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 80
        self.move(x, y)

    def add_or_update_tab(self, tab_id: str, text: str, is_final: bool = False, tab_title: str = ""):
        # Hide placeholder when we have active tabs
        if self.placeholder_label.isVisible() and tab_id:
            self.placeholder_label.hide()

        if tab_id not in self.tab_widgets:
            # Create new tab widget
            widget = TabSubtitleWidget(tab_id, tab_title)
            widget.set_expanded(self.expanded)
            self.tab_widgets[tab_id] = widget
            self.tabs_layout.addWidget(widget)
            # Adjust window height
            self.adjust_height()

        widget = self.tab_widgets[tab_id]
        if tab_title:
            widget.set_title(tab_title)
        widget.update_subtitle(text, is_final)

    def remove_tab(self, tab_id: str):
        if tab_id in self.tab_widgets:
            widget = self.tab_widgets[tab_id]
            self.tabs_layout.removeWidget(widget)
            widget.deleteLater()
            del self.tab_widgets[tab_id]
            self.adjust_height()

            # Show placeholder if no tabs left
            if len(self.tab_widgets) == 0:
                self.placeholder_label.show()

    def adjust_height(self):
        # 窗口顶部工具栏（按钮）+ 主布局上下边距
        m = self.main_layout.contentsMargins()
        toolbar_h = 22 + self.main_layout.spacing()
        base = m.top() + m.bottom() + toolbar_h

        # 累加每个 tab 的真实高度；无 tab 时给 placeholder 留位
        if self.tab_widgets:
            tabs_spacing = self.tabs_layout.spacing()
            widgets = list(self.tab_widgets.values())
            tabs_total = sum(w.content_height() for w in widgets)
            tabs_total += tabs_spacing * max(0, len(widgets) - 1)
        else:
            tabs_total = self.placeholder_label.sizeHint().height() + 10

        new_height = base + tabs_total + 8
        new_height = max(60, min(new_height, 700))

        # 清除可能残留的最小/最大高度约束，确保能向下缩
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

        # 让子 widget 的新尺寸先生效，再 resize 父窗口
        self.tabs_container.updateGeometry()
        self.tabs_container.adjustSize()
        self.main_layout.activate()

        # 以原底边为锚点，缩放后仍贴底
        old_bottom = self.y() + self.height()
        self.resize(self.width(), new_height)
        new_y = old_bottom - new_height
        screen = QApplication.primaryScreen().geometry()
        new_y = max(0, min(new_y, screen.height() - new_height))
        self.move(self.x(), new_y)

    def toggle_expanded(self):
        self.expanded = not self.expanded
        self.expand_btn.setText("▲" if self.expanded else "▼")
        self.expand_btn.setToolTip(
            "收起为单行模式" if self.expanded else "展开历史字幕（多行）"
        )
        for w in self.tab_widgets.values():
            w.set_expanded(self.expanded)
        # 立刻调一次，再延后一帧补一次：覆盖布局异步生效的情况
        self.adjust_height()
        QTimer.singleShot(0, self.adjust_height)

    def set_locked(self, locked: bool):
        self.is_locked = locked
        if locked:
            self.setWindowFlags(
                self.windowFlags() |
                Qt.WindowType.WindowTransparentForInput
            )
        else:
            self.setWindowFlags(
                self.windowFlags() &
                ~Qt.WindowType.WindowTransparentForInput
            )
        self.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.is_locked:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position and not self.is_locked:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.fillPath(path, QColor(0, 0, 0, 140))


class SubtitleApp:
    """Subtitle application manager"""

    def __init__(self):
        self.signals = SubtitleSignals()
        self.window: Optional[SubtitleWindow] = None
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.tab_titles: Dict[str, str] = {}

        self.init_window()
        self.init_tray_icon()
        self.connect_events()

    def init_window(self):
        self.window = SubtitleWindow()
        self.window.show()

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon()

        menu = QMenu()

        show_action = QAction("Show Subtitles", menu)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)

        hide_action = QAction("Hide Subtitles", menu)
        hide_action.triggered.connect(self.hide_window)
        menu.addAction(hide_action)

        menu.addSeparator()

        lock_action = QAction("Lock Position (Click-through)", menu)
        lock_action.setCheckable(True)
        lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(lock_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("Audio2Text Subtitles")
        self.tray_icon.show()

    def connect_events(self):
        self.signals.update_subtitle.connect(self._handle_subtitle_update)
        self.signals.remove_tab.connect(self._handle_remove_tab)

        event_bus.on('subtitle_update', self._on_subtitle_event)
        event_bus.on('tab_closed', self._on_tab_closed)

    def _on_subtitle_event(self, data: dict):
        self.signals.update_subtitle.emit(data)

    def _on_tab_closed(self, data: dict):
        tab_id = data.get('tab_id', '')
        if tab_id:
            self.signals.remove_tab.emit(str(tab_id))

    def _handle_subtitle_update(self, data: dict):
        tab_id = str(data.get('tab_id', 'default'))
        text = data.get('text', '')
        is_final = data.get('is_final', False)
        tab_title = data.get('tab_title', '')

        # Store tab title
        if tab_title:
            self.tab_titles[tab_id] = tab_title

        if self.window:
            self.window.add_or_update_tab(
                tab_id,
                text,
                is_final,
                self.tab_titles.get(tab_id, f"Tab {tab_id}")
            )

    def _handle_remove_tab(self, tab_id: str):
        if self.window:
            self.window.remove_tab(tab_id)
        if tab_id in self.tab_titles:
            del self.tab_titles[tab_id]

    def show_window(self):
        if self.window:
            self.window.show()

    def hide_window(self):
        if self.window:
            self.window.hide()

    def toggle_lock(self, locked: bool):
        if self.window:
            self.window.set_locked(locked)
