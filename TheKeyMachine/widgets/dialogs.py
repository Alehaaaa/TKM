import sys
import os
import re
import xml.etree.ElementTree as ET
from functools import partial

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from TheKeyMachine.widgets.util import DPI, get_maya_qt, is_valid_widget
from TheKeyMachine.widgets.customWidgets import QFlatHoverableIcon
import TheKeyMachine.mods.mediaMod as media
from TheKeyMachine.tooltips.tooltip import QFlatTooltipManager

def return_icon_path(name):
    if name.endswith('.png') or name.endswith('.svg'):
        return media.getImage(name)
    png_path = media.getImage(name + ".png")
    if os.path.exists(png_path):
        return png_path
    return media.getImage(name + ".svg")

# Compatibility with aleha_tools imports
QWidget = QtWidgets.QWidget
QHBoxLayout = QtWidgets.QHBoxLayout
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QDialog = QtWidgets.QDialog
QFrame = QtWidgets.QFrame
QSizePolicy = QtWidgets.QSizePolicy
QLayout = QtWidgets.QLayout
QMenu = QtWidgets.QMenu
QMenuBar = QtWidgets.QMenuBar
QApplication = QtWidgets.QApplication

QIcon = QtGui.QIcon
QColor = QtGui.QColor
QPixmap = QtGui.QPixmap
QPainter = QtGui.QPainter
QPolygonF = QtGui.QPolygonF
QCursor = QtGui.QCursor
QGuiApplication = QtGui.QGuiApplication
QMovie = QtGui.QMovie
QFontMetrics = QtGui.QFontMetrics

Qt = QtCore.Qt
QSize = QtCore.QSize
QEventLoop = QtCore.QEventLoop
QPoint = QtCore.QPoint
QPointF = QtCore.QPointF
QTimer = QtCore.QTimer
QRect = QtCore.QRect

class QFlatDialogButton(dict):
    """A dictionary subclass that supports the | operator to return a list of buttons."""

    def __init__(self, name_or_dict=None, **kwargs):
        if name_or_dict is not None:
            if isinstance(name_or_dict, (str, bytes)):
                kwargs["name"] = name_or_dict
                dict.__init__(self, **kwargs)
            elif isinstance(name_or_dict, dict):
                dict.__init__(self, name_or_dict, **kwargs)
            else:
                dict.__init__(self, **kwargs)
        else:
            dict.__init__(self, **kwargs)

    def copy(self):
        return QFlatDialogButton(dict.copy(self))

    def __eq__(self, other):
        if isinstance(other, (str, bytes)):
            return self.get("name") == other
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)


class QFlatButton(QPushButton):
    """A customizable, flat-styled button for the bottom bar."""

    STYLE_SHEET = """
        QPushButton {
            color: %s;
            background-color: %s;
            border-radius: %spx;
            padding: %spx %spx;
            font-weight: %s;
            font-size: %spx;
        }
        QPushButton:hover {
            background-color: %s;
        }
        QPushButton:pressed {
            background-color: %s;
        }
    """

    DEFAULT_COLOR = "#ffffff"
    DEFAULT_BACKGROUND = "#5D5D5D"
    DEFAULT_HOVER_BACKGROUND = "#707070"
    DEFAULT_PRESSED_BACKGROUND = "#252525"

    HIGHLIGHT_COLOR = "#282828"
    HIGHLIGHT_BACKGROUND = "#bdbdbd"
    HIGHLIGHT_HOVER_BACKGROUND = "#cfcfcf"
    HIGHLIGHT_PRESSED_BACKGROUND = "#707070"

    DEFAULT_FONT_SIZE = DPI(12)
    HIGHLIGHT_FONT_SIZE = DPI(15)

    BUTTON_BORDER_RADIUS = DPI(9)

    def __init__(
        self,
        text,
        color=DEFAULT_COLOR,
        background=DEFAULT_BACKGROUND,
        icon_path=None,
        border=BUTTON_BORDER_RADIUS,
        highlight=False,
        parent=None,
    ):
        QPushButton.__init__(self, text, parent)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(DPI(34))

        # Consistent Icon Size
        self.setIconSize(QSize(DPI(19), DPI(19)))
        if icon_path:
            QFlatHoverableIcon.apply(self, icon_path, highlight=highlight)

        v_padding = 2  # Tight padding since height is fixed

        if highlight:
            color = self.HIGHLIGHT_COLOR
            background = self.HIGHLIGHT_BACKGROUND
            hover_background = self.HIGHLIGHT_HOVER_BACKGROUND
            pressed_background = self.HIGHLIGHT_PRESSED_BACKGROUND
            font_size = self.HIGHLIGHT_FONT_SIZE
            weight = "bold"
        elif background != self.DEFAULT_BACKGROUND:
            try:
                base_background = int(background.lstrip("#"), 16)
                r, g, b = (
                    (base_background >> 16) & 0xFF,
                    (base_background >> 8) & 0xFF,
                    base_background & 0xFF,
                )
            except Exception:
                r, g, b = 93, 93, 93
            hover_background = "#%02x%02x%02x" % (min(r + 10, 255), min(g + 10, 255), min(b + 10, 255))
            pressed_background = "#%02x%02x%02x" % (max(r - 10, 0), max(g - 10, 0), max(b - 10, 0))
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"
        else:
            hover_background = self.DEFAULT_HOVER_BACKGROUND
            pressed_background = self.DEFAULT_PRESSED_BACKGROUND
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"

        actual_border = min(int(border), int(DPI(34)) // 2)

        self.setStyleSheet(
            self.STYLE_SHEET
            % (
                color,
                background,
                actual_border,
                int(DPI(v_padding)),
                int(DPI(12)),
                weight,
                int(font_size),
                hover_background,
                pressed_background,
            )
        )


class QFlatBottomBar(QFrame):
    """
    A container widget for arranging QFlatButtons horizontally.
    """

    def __init__(self, buttons=[], margins=8, spacing=6, parent=None):
        QFrame.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(DPI(margins), DPI(margins), DPI(margins), DPI(margins))
        layout.setSpacing(DPI(spacing))

        for button in buttons:
            layout.addWidget(button)


class QFlatDialog(QDialog):
    # Button Preconfigurations
    Yes = QFlatDialogButton("Yes", positive=True, icon=return_icon_path("apply"))
    Ok = QFlatDialogButton("Ok", positive=True, icon=return_icon_path("apply"))

    No = QFlatDialogButton("No", positive=False, icon=return_icon_path("cancel"))
    Cancel = QFlatDialogButton("Cancel", positive=False, icon=return_icon_path("cancel"))
    Close = QFlatDialogButton("Close", positive=False, icon=return_icon_path("close"))

    CustomButton = QFlatDialogButton

    def __init__(self, parent=None, buttons=None, highlight=None, closeButton=False):
        if parent is None:
            parent = get_maya_qt()

        QDialog.__init__(self, parent)
        if sys.platform != "win32":
            self.setWindowFlags(self.windowFlags() | Qt.Tool)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.bottomBar = None

        self._highlighted = highlight
        self._buttons_to_init = buttons
        self._default_button = None

    def _buttonConfigHook(self, index, config):
        return config

    def _defineButtons(self, buttons):
        created_buttons = []
        for i, btn_data in enumerate(buttons):
            if isinstance(btn_data, (str, bytes)):
                config = QFlatDialogButton(btn_data)
            else:
                config = btn_data.copy()

            config = self._buttonConfigHook(i, config)

            is_highlighted = config.get("highlight", False)
            if self._highlighted:
                if btn_data == self._highlighted or config.get("name") == self._highlighted:
                    is_highlighted = True

            btn = QFlatButton(
                text=config.get("name", "Button"),
                background=config.get("background", "#5D5D5D"),
                icon_path=config.get("icon"),
                highlight=is_highlighted,
            )

            callback = config.get("callback")
            if callback and callable(callback):
                btn.clicked.connect(callback)

            if is_highlighted:
                btn.setAutoDefault(True)
                btn.setDefault(True)
                self._default_button = btn

            created_buttons.append(btn)
        return created_buttons

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._default_button:
                self._default_button.click()
                return
        QDialog.keyPressEvent(self, event)

    def setBottomBar(self, buttons=None, margins=8, spacing=6, closeButton=False, highlight=None):
        if self.bottomBar:
            self.root_layout.removeWidget(self.bottomBar)
            self.bottomBar.setParent(None)
            self.bottomBar.deleteLater()
            self.bottomBar = None

        if highlight:
            self._highlighted = highlight

        btn_data = []
        if buttons:
            if isinstance(buttons, (list, tuple)):
                btn_data.extend(buttons)
            else:
                btn_data.append(buttons)

        if closeButton:
            close_cfg = self.Close.copy()
            if not close_cfg.get("callback"):
                close_cfg["callback"] = self.close
            btn_data.append(close_cfg)

        created_buttons = self._defineButtons(btn_data)

        if created_buttons:
            self.bottomBar = QFlatBottomBar(buttons=created_buttons, margins=margins, spacing=spacing, parent=self)
            self.root_layout.addWidget(self.bottomBar)


class QFlatConfirmDialog(QFlatDialog):
    TEXT_COLOR = "#bbbbbb"

    def __init__(
        self,
        window="Confirm",
        title="",
        message="",
        buttons=["Ok"],
        closeButton=True,
        highlight=None,
        icon=None,
        exclusive=True,
        parent=None,
    ):
        QFlatDialog.__init__(self, parent=parent, buttons=buttons, highlight=highlight, closeButton=closeButton)

        new_flags = self.windowFlags() | Qt.Dialog
        if parent and (parent.windowFlags() & Qt.Tool):
            new_flags |= Qt.Tool

        self.setWindowFlags(new_flags)
        if parent:
            self.setParent(parent)

        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowTitle(window or "Confirm")
        self.clicked_button = None

        self._exclusive = exclusive
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(25), DPI(20), DPI(25), DPI(20))

        if icon:
            icon_label = QLabel()
            pix = QPixmap(icon)
            if not pix.isNull():
                icon_dim = DPI(80)
                icon_label.setPixmap(pix.scaled(icon_dim, icon_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                icon_label.setFixedSize(icon_dim, icon_dim)
                content_layout.addWidget(icon_label, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(DPI(5))
        content_layout.addLayout(text_layout, 1)

        if title:
            self.title_label = QLabel(title)
            self.title_label.setWordWrap(True)
            self.title_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
            self.title_label.setStyleSheet("font-size: %spx; color: %s; font-weight: bold;" % (DPI(18), self.TEXT_COLOR))
            text_layout.addWidget(self.title_label)

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: %spx; color: %s;" % (DPI(11.5), self.TEXT_COLOR))
        text_layout.addWidget(self.message_label)

        self.root_layout.addWidget(content_widget)

        self.setBottomBar(buttons, closeButton=closeButton, highlight=highlight)
        self.adjustSize()

    def _buttonConfigHook(self, index, config):
        if isinstance(config, (str, bytes)):
            name = config
            is_pos = index == 0
            original_config = QFlatDialogButton(name, positive=is_pos)
        else:
            name = config.get("name", "Button")
            is_pos = config.get("positive", index == 0)
            original_config = config.copy()

        config["callback"] = partial(self._on_button_clicked, original_config)
        return config

    def _on_button_clicked(self, config):
        self.clicked_button = config
        if config.get("positive", False):
            self.accept()
        else:
            self.reject()

    @classmethod
    def information(
        cls,
        parent,
        window,
        message,
        buttons=None,
        highlight=None,
        closeButton=True,
        title=None,
        **kwargs,
    ):
        if buttons is None and not closeButton:
            buttons = [cls.Close]
        dlg = cls(
            window=window,
            title=title,
            message=message,
            buttons=buttons,
            highlight=highlight,
            closeButton=closeButton,
            parent=parent,
            **kwargs,
        )
        dlg.exec_()
        return dlg.clicked_button

    @classmethod
    def question(
        cls,
        parent,
        window,
        message,
        buttons=None,
        highlight=None,
        closeButton=False,
        title="Are you sure?",
        **kwargs,
    ):
        if buttons is None and not closeButton:
            buttons = [cls.Yes, cls.No]
        dlg = cls(
            window=window,
            title=title,
            message=message,
            buttons=buttons,
            highlight=highlight,
            closeButton=closeButton,
            parent=parent,
            **kwargs,
        )
        dlg.exec_()
        return dlg.clicked_button

    def confirm(self):
        if self._exclusive:
            return self.exec_() == QDialog.Accepted

        self.show()
        self.raise_()
        self.activateWindow()
        loop = QEventLoop()
        self.finished.connect(loop.quit)
        loop.exec_()
        return self.result() == QDialog.Accepted


class QFlatTooltipConfirm(QFlatDialog):
    """
    A hybrid widget combining the visual style of a QFlatTooltip (arrow, rounded, dark, XML template)
    with the logic and button handling of a QFlatConfirmDialog.
    """

    BG_COLOR = "#333333"
    TEXT_COLOR = "#bbbbbb"
    BORDER_RADIUS = 8
    ARROW_W = 12
    ARROW_H = 8

    def __init__(self, parent=None, title="", message="", buttons=None, icon=None, template=None, highlight=None):
        QFlatDialog.__init__(self, parent=parent, buttons=buttons, highlight=highlight)

        # Tooltip-like window setup
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.clicked_button = None

        # Build template if not provided (compatibility with standard title/message/icon)
        if template is None:
            template = ""
            if icon:
                template += "<icon>{}</icon>".format(icon)
            if title:
                template += "<title>{}</title>".format(title)
            if message:
                template += "<text>{}</text>".format(message)
        else:
            # If template provided, ensure icon/title are included if passed as args and missing in xml
            if icon and "<icon>" not in template:
                template = "<icon>{}</icon>{}".format(icon, template)
            if title and "<title>" not in template:
                template = "<title>{}</title>{}".format(title, template)
        self.template = template

        # Style the frame
        self.setStyleSheet(
            "QFlatTooltipConfirm > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(self.BG_COLOR, DPI(self.BORDER_RADIUS))
        )

        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.bg_layout = QVBoxLayout(self.bg_frame)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_layout.setSpacing(0)
        self.root_layout.addWidget(self.bg_frame)

        self._build_content()

        # Add the interactive buttons at the bottom
        self.setBottomBar(buttons, margins=12, spacing=DPI(6), highlight=highlight)
        if self.bottomBar:
            self.root_layout.removeWidget(self.bottomBar)
            # Add a small separator before buttons if there was content
            self.bg_layout.addSpacing(DPI(8))
            self.bg_layout.addWidget(self.bottomBar)
            self.bg_layout.addSpacing(DPI(4))

    def _build_content(self):
        """Parses the XML template and builds the body, same as QFlatTooltip."""
        try:
            # Basic sanitization
            safe_template = self.template.replace("&", "&amp;")
            if "<br>" in safe_template.lower():
                safe_template = re.sub(r"(?i)<br\s*>", "<br/>", safe_template)

            root = ET.fromstring("<root>{}</root>".format(safe_template))
        except Exception as e:
            root = ET.fromstring("<root><text>Invalid XML: {}</text></root>".format(e))

        # 1. Header Area (Icon + Title)
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(DPI(18), DPI(15), DPI(18), DPI(10))
        header_layout.setSpacing(DPI(12))

        has_header = False
        for child in root:
            if child.tag == "icon":
                pix = QPixmap(child.text)
                if not pix.isNull():
                    lbl = QLabel()
                    dim = DPI(80)
                    lbl.setPixmap(pix.scaled(dim, dim, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    header_layout.addWidget(lbl)
                    has_header = True
            elif child.tag == "title":
                inner_text = (child.text or "") + "".join(ET.tostring(c, encoding="utf-8").decode("utf-8") if sys.version_info[0] < 3 else ET.tostring(c, encoding="unicode") for c in child)
                lbl = QLabel(inner_text)
                lbl.setStyleSheet("color: {}; font-size: {}px; font-weight: bold; background: transparent;".format(self.TEXT_COLOR, DPI(18)))
                lbl.setWordWrap(True)
                header_layout.addWidget(lbl)
                has_header = True

        if has_header:
            header_layout.addStretch()
            self.bg_layout.addWidget(header_frame)

        # 2. Main Content Area (Text, Separators, Images)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(DPI(18), 0, DPI(18), 0)
        content_layout.setSpacing(DPI(6))

        in_content = False
        for child in root:
            if not in_content and child.tag not in ["title", "icon"]:
                in_content = True
            if not in_content:
                continue

            if child.tag == "text":
                inner_text = (child.text or "") + "".join(ET.tostring(c, encoding="utf-8").decode("utf-8") if sys.version_info[0] < 3 else ET.tostring(c, encoding="unicode") for c in child)
                lbl = QLabel(inner_text)
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: {}; font-size: {}px; background: transparent;".format(self.TEXT_COLOR, DPI(11.5)))
                content_layout.addWidget(lbl)
            elif child.tag == "separator":
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background-color: rgba(255,255,255,10); margin: {}px 0px;".format(DPI(4)))
                content_layout.addWidget(sep)
            elif child.tag in ["image", "gif"]:
                lbl = QLabel()
                lbl.setAlignment(Qt.AlignCenter)
                pix = QPixmap(child.text)
                if not pix.isNull():
                    if pix.width() > DPI(280):
                        pix = pix.scaledToWidth(DPI(280), Qt.SmoothTransformation)
                    lbl.setPixmap(pix)
                    content_layout.addWidget(lbl)

        if content_layout.count() > 0:
            self.bg_layout.addLayout(content_layout)

    def _buttonConfigHook(self, index, config):
        if isinstance(config, (str, bytes)):
            name = config
            is_pos = index == 0
            original_config = QFlatDialogButton(name, positive=is_pos)
        else:
            name = config.get("name", "Button")
            is_pos = config.get("positive", index == 0)
            original_config = config.copy()

        config["callback"] = partial(self._on_button_clicked, original_config)
        return config

    def _on_button_clicked(self, config):
        self.clicked_button = config
        if config.get("positive", False):
            self.accept()
        else:
            self.reject()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.BG_COLOR))

        side = getattr(self, "side", "top")
        aw = DPI(self.ARROW_W)
        ah = DPI(self.ARROW_H)
        ax = getattr(self, "arrow_x", self.width() / 2)

        if side == "top":
            poly = QPolygonF([QPointF(ax, 0), QPointF(ax - aw / 2, ah + 1), QPointF(ax + aw / 2, ah + 1)])
            painter.drawPolygon(poly)
        else:
            poly = QPolygonF([QPointF(ax, self.height()), QPointF(ax - aw / 2, self.height() - ah - 1), QPointF(ax + aw / 2, self.height() - ah - 1)])
            painter.drawPolygon(poly)

    def _show_around(self, widget, target_rect=None):
        ah = DPI(self.ARROW_H)
        cursor_pos = QCursor.pos()

        if target_rect:
            self._global_anc = target_rect
        elif is_valid_widget(widget):
            # 1. Handle QMenu (ui.version_bar) inside a QMenuBar
            if hasattr(widget, "menuAction"):
                action = widget.menuAction()
                parent_mb = widget.parent()
                if not isinstance(parent_mb, QMenuBar):
                    win = widget.window()
                    parent_mb = win.findChild(QMenuBar) if win else None

                if isinstance(parent_mb, QMenuBar):
                    geom = parent_mb.actionGeometry(action)
                    self._global_anc = QRect(parent_mb.mapToGlobal(geom.topLeft()), geom.size())
                else:
                    self._global_anc = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())

            # 2. Handle QMenuBar itself (point to last item)
            elif isinstance(widget, QMenuBar):
                actions = widget.actions()
                if actions:
                    geom = widget.actionGeometry(actions[-1])
                    self._global_anc = QRect(widget.mapToGlobal(geom.topLeft()), geom.size())
                else:
                    self._global_anc = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())

            # 3. Standard Widget
            else:
                self._global_anc = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
        else:
            # Final fallback: point to cursor if widget is dead
            self._global_anc = QRect(cursor_pos, QSize(0, 0))

        self.side = "top"
        self.root_layout.setContentsMargins(0, ah, 0, 0)
        self.root_layout.activate()
        self.adjustSize()
        w, h = self.width(), self.height()

        target_x = self._global_anc.left()
        pos = QPoint(target_x - w // 2, self._global_anc.bottom() + DPI(2))

        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        if pos.y() + h > geo.bottom():
            self.side = "bottom"
            self.root_layout.setContentsMargins(0, 0, 0, ah)
            self.root_layout.activate()
            self.adjustSize()
            w, h = self.width(), self.height()
            pos.setY(self._global_anc.top() - h - DPI(2))

        # Horizontal screen safety (keep it within screen bounds while trying to stay centered on target_x)
        final_x = max(geo.left() + DPI(5), min(pos.x(), geo.right() - w - DPI(5)))
        pos.setX(final_x)
        self.move(pos)

        # Arrow points exactly to the widget's left corner (clamped to tooltip edges)
        arrow_x = target_x - final_x
        aw = DPI(self.ARROW_W)
        self.arrow_x = max(DPI(6) + aw / 2, min(arrow_x, w - DPI(6) - aw / 2))
        self.update()
        self.show()

    @classmethod
    def _run(cls, anchor_widget, **kwargs):
        """Central instantiation and execution logic."""
        # Handle cases where the anchor widget might be deleted (common in menus/maya)
        if not is_valid_widget(anchor_widget):
            anchor_widget = get_maya_qt()

        # Close existing tooltips/confirmations
        QFlatTooltipManager.hide()

        parent = kwargs.pop("parent", None) or anchor_widget.window()
        dlg = cls(parent=parent, **kwargs)

        # Register with TooltipManager so it can be managed/cleared
        QFlatTooltipManager._current_tooltip = dlg

        dlg._show_around(anchor_widget, target_rect=kwargs.get("target_rect"))
        dlg.exec_()

        # Clean up registration
        if QFlatTooltipManager._current_tooltip == dlg:
            QFlatTooltipManager._current_tooltip = None

        return dlg.clicked_button

    show_around = _show_around

    @classmethod
    def question(cls, anchor_widget, title="Are you sure?", message="", buttons=None, **kwargs):
        if buttons is None:
            buttons = [cls.Yes, cls.No]
        return cls._run(anchor_widget, title=title, message=message, buttons=buttons, **kwargs)

    @classmethod
    def information(cls, anchor_widget, title="Information", message="", buttons=None, **kwargs):
        if buttons is None:
            buttons = [cls.Ok]
        return cls._run(anchor_widget, title=title, message=message, buttons=buttons, **kwargs)
