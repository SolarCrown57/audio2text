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
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QIcon, QAction

from event_bus import event_bus


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

        font = self.font()
        text = self.text()

        if not text:
            return

        rect = self.rect()
        painter.setFont(font)
        painter.setPen(self.outline_color)

        # Draw outline
        for dx in range(-self.outline_width, self.outline_width + 1):
            for dy in range(-self.outline_width, self.outline_width + 1):
                if dx != 0 or dy != 0:
                    offset_rect = rect.translated(dx, dy)
                    painter.drawText(
                        offset_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        text
                    )

        # Draw main text
        painter.setPen(self.text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class TabSubtitleWidget(QFrame):
    """Single tab subtitle display widget"""

    def __init__(self, tab_id: str, tab_title: str = "", parent=None):
        super().__init__(parent)
        self.tab_id = tab_id
        self.tab_title = tab_title or f"Tab {tab_id}"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)

        # Tab title label
        self.title_label = QLabel(self.tab_title)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet("color: #aaa;")
        self.title_label.setMaximumHeight(20)

        # Subtitle label
        self.subtitle_label = SubtitleLabel()
        self.subtitle_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        self.subtitle_label.setMinimumHeight(40)
        self.subtitle_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        self.setStyleSheet("""
            TabSubtitleWidget {
                background-color: rgba(0, 0, 0, 100);
                border-radius: 8px;
                margin: 2px;
            }
        """)

    def update_subtitle(self, text: str, is_final: bool = False):
        self.subtitle_label.setText(text)
        if is_final:
            self.subtitle_label.text_color = QColor(255, 255, 255, 255)
        else:
            self.subtitle_label.text_color = QColor(200, 200, 200, 255)
        self.subtitle_label.update()

    def set_title(self, title: str):
        self.tab_title = title
        self.title_label.setText(title)


class SubtitleWindow(QWidget):
    """Multi-tab subtitle window"""

    def __init__(self):
        super().__init__()
        self.drag_position: Optional[QPoint] = None
        self.is_locked = False
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
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

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
        # Calculate needed height based on number of tabs
        base_height = 60
        per_tab_height = 80
        tab_count = len(self.tab_widgets)
        new_height = base_height + (tab_count if tab_count > 0 else 0) * per_tab_height
        new_height = min(new_height, 400)  # Max height
        self.resize(self.width(), new_height)

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
