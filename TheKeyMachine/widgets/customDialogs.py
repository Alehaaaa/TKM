import sys

import re
import xml.etree.ElementTree as ET
from functools import partial

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtGui import QRegularExpressionValidator
    from PySide6.QtCore import QRegularExpression

    try:
        from PySide6.QtSvg import QSvgRenderer  # type: ignore
    except ImportError:
        QSvgRenderer = None  # type: ignore

    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtGui import QRegExpValidator
    from PySide2.QtCore import QRegExp

    try:
        from PySide2.QtSvg import QSvgRenderer  # type: ignore
    except ImportError:
        QSvgRenderer = None  # type: ignore

    PYSIDE_VERSION = 2

    QRegularExpression = QRegExp
    QRegularExpressionValidator = QRegExpValidator

from TheKeyMachine.widgets.util import DPI, get_maya_qt, get_selected_objects, is_valid_widget
from TheKeyMachine.tooltips.tooltip import QFlatTooltipManager

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.widgets.customWidgets as cw


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


class QFlatDialog(QtWidgets.QDialog):
    # Button Preconfigurations
    Yes = QFlatDialogButton("Yes", positive=True, icon=media.apply_image)
    Ok = QFlatDialogButton("Ok", positive=True, icon=media.apply_image)

    No = QFlatDialogButton("No", positive=False, icon=media.cancel_image)
    Cancel = QFlatDialogButton("Cancel", positive=False, icon=media.cancel_image)
    Close = QFlatDialogButton("Close", positive=False, icon=media.close_image)

    CustomButton = QFlatDialogButton

    def __init__(self, parent=None, buttons=None, highlight=None, closeButton=False, **kwargs):
        if parent is None:
            parent = get_maya_qt()

        QtWidgets.QDialog.__init__(self, parent)
        if sys.platform != "win32":
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        self.setProperty("tkm_floating_widget", True)
        self.root_layout = QtWidgets.QVBoxLayout(self)
        self.root_layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
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

            btn = cw.QFlatButton(
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
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self._default_button:
                self._default_button.click()
                return
        QtWidgets.QDialog.keyPressEvent(self, event)

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
            self.bottomBar = cw.QFlatBottomBar(buttons=created_buttons, margins=margins, spacing=spacing, parent=self)
            self.root_layout.addWidget(self.bottomBar)

    def _ensure_close_button(self):
        if not self.bottomBar:
            # No bottom bar yet → just create one with close
            self.setBottomBar(closeButton=True)
            return

        # Check if a close button already exists (avoid duplicates)
        for btn in self.bottomBar.findChildren(QtWidgets.QPushButton):
            if btn.text().lower() in ("close", "cancel"):
                return

        # Create close config
        close_cfg = self.Close.copy()
        if not close_cfg.get("callback"):
            close_cfg["callback"] = self.close

        # Build button using same pipeline
        new_btns = self._defineButtons([close_cfg])

        for btn in new_btns:
            self.bottomBar.layout().addWidget(btn)


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
        **kwargs,
    ):
        QFlatDialog.__init__(self, parent=parent, buttons=buttons, highlight=highlight, closeButton=closeButton, **kwargs)

        new_flags = self.windowFlags() | QtCore.Qt.Dialog
        if parent and (parent.windowFlags() & QtCore.Qt.Tool):
            new_flags |= QtCore.Qt.Tool

        self.setWindowFlags(new_flags)
        if parent:
            self.setParent(parent)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setWindowTitle(window or "Confirm")
        self.clicked_button = None

        self._exclusive = exclusive
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(25), DPI(20), DPI(25), DPI(20))

        if icon:
            icon_label = QtWidgets.QLabel()
            pix = QtGui.QPixmap(icon)
            if not pix.isNull():
                icon_dim = DPI(80)
                icon_label.setPixmap(pix.scaled(icon_dim, icon_dim, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                icon_label.setFixedSize(icon_dim, icon_dim)
                content_layout.addWidget(icon_label, 0, QtCore.Qt.AlignTop)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(DPI(5))
        content_layout.addLayout(text_layout, 1)

        if title:
            self.title_label = QtWidgets.QLabel(title)
            self.title_label.setWordWrap(True)
            self.title_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
            self.title_label.setStyleSheet("font-size: %spx; color: %s; font-weight: bold;" % (DPI(18), self.TEXT_COLOR))
            text_layout.addWidget(self.title_label)

        self.message_label = QtWidgets.QLabel(message)
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
            return self.exec_() == QtWidgets.QDialog.Accepted

        self.show()
        self.raise_()
        self.activateWindow()
        loop = QtCore.QEventLoop()
        self.finished.connect(loop.quit)
        loop.exec_()
        return self.result() == QtWidgets.QDialog.Accepted


class QFlatTooltipConfirm(QFlatDialog):
    """
    A hybrid widget combining the visual style of a QFlatTooltip (arrow, rounded, dark, XML tooltip_template)
    with the logic and button handling of a QFlatConfirmDialog.
    """

    BG_COLOR = "#333333"
    TEXT_COLOR = "#bbbbbb"
    BORDER_RADIUS = 8
    ARROW_W = 12
    ARROW_H = 8

    def __init__(self, parent=None, title="", message="", buttons=None, icon=None, tooltip_template=None, highlight=None, **kwargs):
        tooltip_template = tooltip_template or kwargs.get("template")
        QFlatDialog.__init__(self, parent=parent, buttons=buttons, highlight=highlight, **kwargs)

        # Tooltip-like window setup
        self.setWindowFlags(QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.clicked_button = None

        # Build tooltip_template if not provided (compatibility with standard title/message/icon)
        if tooltip_template is None:
            tooltip_template = ""
            if icon:
                tooltip_template += "<icon>{}</icon>".format(icon)
            if title:
                tooltip_template += "<title>{}</title>".format(title)
            if message:
                tooltip_template += "<text>{}</text>".format(message)
        else:
            # If tooltip_template provided, ensure icon/title are included if passed as args and missing in xml
            if icon and "<icon>" not in tooltip_template:
                tooltip_template = "<icon>{}</icon>{}".format(icon, tooltip_template)
            if title and "<title>" not in tooltip_template:
                tooltip_template = "<title>{}</title>{}".format(title, tooltip_template)
        self.tooltip_template = tooltip_template

        # Style the frame
        self.setStyleSheet(
            "QFlatTooltipConfirm > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(self.BG_COLOR, DPI(self.BORDER_RADIUS))
        )

        self.bg_frame = QtWidgets.QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.bg_layout = QtWidgets.QVBoxLayout(self.bg_frame)
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
        """Parses the XML tooltip_template and builds the body, same as QFlatTooltip."""
        try:
            # Basic sanitization
            safe_tooltip_template = self.tooltip_template.replace("&", "&amp;")
            if "<br>" in safe_tooltip_template.lower():
                safe_tooltip_template = re.sub(r"(?i)<br\s*>", "<br/>", safe_tooltip_template)

            root = ET.fromstring("<root>{}</root>".format(safe_tooltip_template))
        except Exception as e:
            root = ET.fromstring("<root><text>Invalid XML: {}</text></root>".format(e))

        # 1. Header Area (Icon + Title)
        header_frame = QtWidgets.QFrame()
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        header_layout.setContentsMargins(DPI(18), DPI(15), DPI(18), DPI(10))
        header_layout.setSpacing(DPI(12))

        has_header = False
        for child in root:
            if child.tag == "icon":
                pix = QtGui.QPixmap(child.text)
                if not pix.isNull():
                    lbl = QtWidgets.QLabel()
                    dim = DPI(80)
                    lbl.setPixmap(pix.scaled(dim, dim, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                    header_layout.addWidget(lbl)
                    has_header = True
            elif child.tag == "title":
                inner_text = (child.text or "") + "".join(
                    ET.tostring(c, encoding="utf-8").decode("utf-8") if sys.version_info[0] < 3 else ET.tostring(c, encoding="unicode") for c in child
                )
                lbl = QtWidgets.QLabel(inner_text)
                lbl.setStyleSheet("color: {}; font-size: {}px; font-weight: bold; background: transparent;".format(self.TEXT_COLOR, DPI(18)))
                lbl.setWordWrap(True)
                header_layout.addWidget(lbl)
                has_header = True

        if has_header:
            header_layout.addStretch()
            self.bg_layout.addWidget(header_frame)

        # 2. Main Content Area (Text, Separators, Images)
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setContentsMargins(DPI(18), 0, DPI(18), 0)
        content_layout.setSpacing(DPI(6))

        in_content = False
        for child in root:
            if not in_content and child.tag not in ["title", "icon"]:
                in_content = True
            if not in_content:
                continue

            if child.tag == "text":
                inner_text = (child.text or "") + "".join(
                    ET.tostring(c, encoding="utf-8").decode("utf-8") if sys.version_info[0] < 3 else ET.tostring(c, encoding="unicode") for c in child
                )
                lbl = QtWidgets.QLabel(inner_text)
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: {}; font-size: {}px; background: transparent;".format(self.TEXT_COLOR, DPI(11.5)))
                content_layout.addWidget(lbl)
            elif child.tag == "separator":
                sep = QtWidgets.QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background-color: rgba(255,255,255,10); margin: {}px 0px;".format(DPI(4)))
                content_layout.addWidget(sep)
            elif child.tag in ["image", "gif"]:
                lbl = QtWidgets.QLabel()
                lbl.setAlignment(QtCore.Qt.AlignCenter)
                pix = QtGui.QPixmap(child.text)
                if not pix.isNull():
                    if pix.width() > DPI(280):
                        pix = pix.scaledToWidth(DPI(280), QtCore.Qt.SmoothTransformation)
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
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(self.BG_COLOR))

        side = getattr(self, "side", "top")
        aw = DPI(self.ARROW_W)
        ah = DPI(self.ARROW_H)
        ax = getattr(self, "arrow_x", self.width() / 2)

        if side == "top":
            poly = QtGui.QPolygonF([QtCore.QPointF(ax, 0), QtCore.QPointF(ax - aw / 2, ah + 1), QtCore.QPointF(ax + aw / 2, ah + 1)])
            painter.drawPolygon(poly)
        else:
            poly = QtGui.QPolygonF(
                [
                    QtCore.QPointF(ax, self.height()),
                    QtCore.QPointF(ax - aw / 2, self.height() - ah - 1),
                    QtCore.QPointF(ax + aw / 2, self.height() - ah - 1),
                ]
            )
            painter.drawPolygon(poly)

    def _show_around(self, widget, target_rect=None):
        ah = DPI(self.ARROW_H)
        cursor_pos = QtGui.QCursor.pos()

        if target_rect:
            self._global_anc = target_rect
        elif is_valid_widget(widget):
            # 1. Handle QtWidgets.QMenu (ui.version_bar) inside a QtWidgets.QMenuBar
            if hasattr(widget, "menuAction"):
                action = widget.menuAction()
                parent_mb = widget.parent()
                if not isinstance(parent_mb, QtWidgets.QMenuBar):
                    win = widget.window()
                    parent_mb = win.findChild(QtWidgets.QMenuBar) if win else None

                if isinstance(parent_mb, QtWidgets.QMenuBar):
                    geom = parent_mb.actionGeometry(action)
                    self._global_anc = QtCore.QRect(parent_mb.mapToGlobal(geom.topLeft()), geom.size())
                else:
                    self._global_anc = QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())

            # 2. Handle QtWidgets.QMenuBar itself (point to last item)
            elif isinstance(widget, QtWidgets.QMenuBar):
                actions = widget.actions()
                if actions:
                    geom = widget.actionGeometry(actions[-1])
                    self._global_anc = QtCore.QRect(widget.mapToGlobal(geom.topLeft()), geom.size())
                else:
                    self._global_anc = QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())

            # 3. Standard Widget
            else:
                self._global_anc = QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())
        else:
            # Final fallback: point to cursor if widget is dead
            self._global_anc = QtCore.QRect(cursor_pos, QtCore.QSize(0, 0))

        self.side = "bottom"
        self.root_layout.setContentsMargins(0, 0, 0, ah)
        self.root_layout.activate()
        self.adjustSize()
        w, h = self.width(), self.height()

        target_x = self._global_anc.left()
        pos = QtCore.QPoint(target_x - w // 2, self._global_anc.top() - h - DPI(2))

        screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        if pos.y() < geo.top():
            self.side = "top"
            self.root_layout.setContentsMargins(0, ah, 0, 0)
            self.root_layout.activate()
            self.adjustSize()
            w, h = self.width(), self.height()
            pos.setY(self._global_anc.bottom() + DPI(2))

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


class QFlatFloatingWidget(QFlatDialog):
    """
    A draggable, frameless, rounded widget wrapper.
    Can be instantiated as a temporary popup or a pinned window.
    """

    BORDER_RADIUS = DPI(5)

    TEXT_COLOR = "#bbbbbb"
    COLOR_BG_TRACK = "#444444"
    DARK_BG_COLOR = "#333333"

    def __init__(self, popup=False, closeButton=False, parent=None):
        QFlatDialog.__init__(self, parent)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setMouseTracking(True)

        self._popup = popup
        self._closeButton = closeButton

        self._is_dragging = False
        self._drag_offset = QtCore.QPoint()
        self._drag_start_pos = QtCore.QPoint()

        self._setup_ui()

    def _setup_ui(self):
        self.mainContent = QtWidgets.QWidget(self)
        self.mainLayout = QtWidgets.QVBoxLayout(self.mainContent)
        self.mainLayout.setContentsMargins(DPI(6), DPI(8), DPI(6), DPI(8))
        self.mainLayout.setSpacing(2)

        self.root_layout.insertWidget(0, self.mainContent, 1)

        self.grip = QtWidgets.QSizeGrip(self)
        self.grip.setCursor(QtCore.Qt.SizeBDiagCursor)

    def paintEvent(self, event):
        if not self.isVisible():
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(self.COLOR_BG_TRACK))

        # Use drawRoundedRect for clean, all-around rounded corners
        rect = self.rect()
        r = self.BORDER_RADIUS
        p.drawRoundedRect(rect, r, r)

    def place_near_cursor(self):
        self.adjustSize()
        w, h = self.width(), self.height()
        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        # Vertical Placement: Prefer Above. If not enough space, place Below.
        # We add an offset (DPI(30)) to avoid sitting exactly on the cursor
        v_offset = DPI(30)
        y = cursor_pos.y() - h - v_offset

        if y < geo.top():
            # Flip to below cursor
            y = cursor_pos.y() + v_offset

        # Horizontal Placement: Centered on cursor
        x = cursor_pos.x() - w // 2

        # Screen boundary clamping
        x = max(geo.left(), min(x, geo.right() - w))
        y = max(geo.top(), min(y, geo.bottom() - h))

        self.move(x, y)
        self.show()
        self.raise_()

    def resizeEvent(self, event):
        s = self.grip.sizeHint()
        self.grip.setFixedSize(s)
        self.grip.move(self.width() - s.width(), 0)
        self.grip.raise_()
        QFlatDialog.resizeEvent(self, event)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._is_dragging = True
            if PYSIDE_VERSION < 6:
                global_position = e.globalPos()
            else:
                global_position = e.globalPosition().toPoint()
            self._drag_start_pos = global_position
            self._drag_offset = global_position - self.frameGeometry().topLeft()
        QFlatDialog.mousePressEvent(self, e)

    def mouseMoveEvent(self, e):
        if self._is_dragging and (e.buttons() & QtCore.Qt.LeftButton):
            if PYSIDE_VERSION < 6:
                global_position = e.globalPos()
            else:
                global_position = e.globalPosition().toPoint()
            self.move(global_position - self._drag_offset)
        QFlatDialog.mouseMoveEvent(self, e)

    def mouseReleaseEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            if self._popup and self._closeButton:
                self._ensure_close_button()
        QFlatDialog.mouseReleaseEvent(self, e)


class QFlatCloseableFloatingWidget(QFlatFloatingWidget):
    """
    A default floating widget with a right close button, no titles, normal main layout.
    """

    def __init__(self, popup=False, parent=None):
        super().__init__(popup=popup, closeButton=False, parent=parent)

        # Header row. Subclasses can optionally populate:
        # - left content via set_header_left_widget(...)
        # - right-side widgets via add_header_right_widget(...), placed before close.
        self.top_bar_layout = QtWidgets.QHBoxLayout()
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setSpacing(0)

        self.header_left_container = QtWidgets.QWidget()
        self.header_left_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.header_left_layout = QtWidgets.QHBoxLayout(self.header_left_container)
        self.header_left_layout.setContentsMargins(0, 0, 0, 0)
        self.header_left_layout.setSpacing(0)

        self._header_left_spacing = QtWidgets.QWidget()
        self._header_left_spacing.setFixedWidth(DPI(8))
        self._header_left_spacing.setVisible(False)

        self.header_separator = QtWidgets.QFrame()
        self.header_separator.setFrameShape(QtWidgets.QFrame.VLine)
        self.header_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.header_separator.setStyleSheet("QFrame { background-color: #3d3d3d; border: none; }")
        self.header_separator.setFixedWidth(max(1, DPI(2)))
        self.header_separator.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self.header_separator.setVisible(False)

        self._header_right_spacing = QtWidgets.QWidget()
        self._header_right_spacing.setFixedWidth(DPI(8))
        self._header_right_spacing.setVisible(False)

        self.header_right_container = QtWidgets.QWidget()
        self.header_right_container.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Expanding)
        self.header_right_layout = QtWidgets.QHBoxLayout(self.header_right_container)
        self.header_right_layout.setContentsMargins(0, 0, 0, 0)
        self.header_right_layout.setSpacing(DPI(2))
        self.header_right_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.close_button = QtWidgets.QToolButton()
        self.close_button.setAutoRaise(True)
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_button.setIcon(QtGui.QIcon(media.close_image))
        self.close_button.setIconSize(QtCore.QSize(DPI(18), DPI(18)))
        # Orbit (and other floating tools) expect a compact close button.
        self.close_button.setFixedSize(DPI(20), DPI(20))
        self.close_button.setStyleSheet(
            """
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QToolButton:pressed {
                background-color: rgba(0, 0, 0, 0.45);
            }
            """
        )
        self.close_button.clicked.connect(self.close)

        self.header_right_layout.addWidget(self.close_button)

        self.top_bar_layout.addWidget(self.header_left_container, 1)
        self.top_bar_layout.addWidget(self._header_left_spacing, 0)
        self.top_bar_layout.addWidget(self.header_separator, 0)
        self.top_bar_layout.addWidget(self._header_right_spacing, 0)
        self.top_bar_layout.addWidget(self.header_right_container, 0)

        self.mainLayout.insertLayout(0, self.top_bar_layout)

    def _set_header_divider_visible(self, visible):
        self._header_left_spacing.setVisible(bool(visible))
        self.header_separator.setVisible(bool(visible))
        self._header_right_spacing.setVisible(bool(visible))

    def set_header_left_widget(self, widget, stretch=1):
        while self.header_left_layout.count():
            item = self.header_left_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        if widget:
            self.header_left_layout.addWidget(widget, stretch)
            self._set_header_divider_visible(True)

    def clear_header_right_widgets(self):
        # Keep the close button; remove any extra widgets.
        for i in reversed(range(self.header_right_layout.count())):
            item = self.header_right_layout.itemAt(i)
            w = item.widget()
            if w and w is not self.close_button:
                self.header_right_layout.takeAt(i)
                w.setParent(None)

    def add_header_right_widget(self, widget, before_close=True):
        if not widget:
            return
        self._set_header_divider_visible(True)
        if before_close:
            idx = max(0, self.header_right_layout.indexOf(self.close_button))
            self.header_right_layout.insertWidget(idx, widget)
        else:
            self.header_right_layout.addWidget(widget)


class QFlatToolBarDialog(QFlatFloatingWidget):
    """
    A modern successor to the Maya tool bar.
    """

    title = "Dialog"
    icon_path = None

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)
        self.setWindowTitle(self.title)
        self.setMinimumWidth(DPI(230))
        self.setMinimumHeight(DPI(300))

        self._opened = False

        # Header
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setContentsMargins(DPI(6), DPI(10), 0, DPI(4))
        title_layout.setSpacing(DPI(6))

        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("title_label")
        self.title_label.setStyleSheet(
            "#title_label{font-size: %spx; color: %s; font-weight: bold; background: transparent;}" % (DPI(24), self.TEXT_COLOR)
        )
        self.title_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.title_label.setWordWrap(False)
        title_layout.addWidget(self.title_label)

        if self.icon_path:
            icon_label = QtWidgets.QLabel()
            icon_size = DPI(30)

            icon = QtGui.QIcon(self.icon_path)
            pixmap = icon.pixmap(icon_size, icon_size)

            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(icon_size, icon_size)
            icon_label.setAlignment(QtCore.Qt.AlignCenter)

            title_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignVCenter)

        self.mainLayout.addLayout(title_layout)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange:
            if self._opened:
                self.close()
            self._opened = True
            return
        super().changeEvent(event)


class QFlatSelectorDialog(QFlatToolBarDialog):
    """
    A modern successor to the Maya textScrollList selector.
    Displays a list of currently selected objects, allowing for quick
    re-selection and focus.
    """

    def __init__(self, parent=None):
        self.title = "Selector"
        self.icon_path = media.selector_image
        super().__init__(parent=parent)
        self.title_label.setText("0")

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.reload_objects)
        self._suppress_next_refresh = False
        self._pending_objects = []
        self._refreshing = False

        # List
        self._list_model = QtCore.QStringListModel(self)
        self.list_widget = QtWidgets.QListView()
        self.list_widget.setModel(self._list_model)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.selectionModel().selectionChanged.connect(self._on_list_selection_changed)

        self.mainLayout.addWidget(self.list_widget, 1)

        # Auto-refresh with Maya selection changes (no manual reload button).
        try:
            import TheKeyMachine.core.runtime_manager as runtime  # type: ignore

            runtime.get_runtime_manager().selection_changed.connect(self._schedule_reload)
        except Exception:
            pass

        self.reload_objects()

    def _schedule_reload(self, *_args):
        if self._suppress_next_refresh:
            self._suppress_next_refresh = False
            return
        if not self._refresh_timer.isActive():
            self._refresh_timer.start(0)

    def _sort_selected_objects_for_display(self, objects):
        return sorted(objects or [], key=lambda obj: (obj.rsplit("|", 1)[-1].lower(), obj.lower()))

    def _select_all_rows(self):
        selection_model = self.list_widget.selectionModel()
        if not selection_model or not self._pending_objects:
            return
        top_left = self._list_model.index(0, 0)
        bottom_right = self._list_model.index(len(self._pending_objects) - 1, 0)
        selection_model.select(
            QtCore.QItemSelection(top_left, bottom_right),
            QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows,
        )

    def reload_objects(self):
        """Fills the list with current selection names and preserves active selection in the UI."""
        self._refreshing = True
        self.list_widget.blockSignals(True)
        selected = self._sort_selected_objects_for_display(get_selected_objects(long=True))
        self._pending_objects = selected
        item_labels = [obj.rsplit("|", 1)[-1] for obj in selected]
        self.title_label.setText(str(len(selected)))
        self._list_model.setStringList(item_labels)
        self._select_all_rows()
        self._refreshing = False
        self.list_widget.blockSignals(False)

    def _on_list_selection_changed(self):
        """Syncs the dialog selection back to the Maya scene."""
        import maya.cmds as cmds

        if self._refreshing:
            return

        names = []
        for index in self.list_widget.selectionModel().selectedIndexes():
            row = index.row()
            if 0 <= row < len(self._pending_objects):
                names.append(self._pending_objects[row])

        valid_names = [n for n in names if n and cmds.objExists(n)]

        if names and not valid_names:
            self.reload_objects()
            return

        if valid_names:
            self._suppress_next_refresh = True
            cmds.select(valid_names, replace=True)
        else:
            self._suppress_next_refresh = True
            cmds.select(clear=True)


class QFlatBugReportDialog(QFlatDialog):
    """
    Modern bug report dialog that reuses QFlatDialog styling.
    """

    MAX_TEXT_CHARS = 1200

    def __init__(self, parent=None, submit_callback=None, dialog_title="Sorry, you found a bug!", prefill_name="", prefill_explanation="", prefill_script_error=""):
        self._submit_callback = submit_callback
        self._send_button = None
        QFlatDialog.__init__(self, parent)
        self.setWindowTitle(dialog_title)
        # More horizontal / less tall default footprint.
        self.setMinimumSize(DPI(600), DPI(450))

        self._info_color = "#9bbbca"
        self._error_color = "#CA6161"
        self._status_placeholder = " "

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(24), DPI(20), DPI(24), DPI(10))
        content_layout.setSpacing(DPI(12))

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(DPI(12))

        icon_label = QtWidgets.QLabel()
        icon_size = QtCore.QSize(DPI(72), DPI(72))
        icon_label.setFixedSize(icon_size)
        icon_label.setScaledContents(False)
        bug_pixmap = self._bug_icon_pixmap(icon_size)
        if not bug_pixmap.isNull():
            icon_label.setPixmap(bug_pixmap)
        header_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignTop)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(DPI(4))

        self.title_label = QtWidgets.QLabel("<b>{}</b>".format(dialog_title))
        self.title_label.setAlignment(QtCore.Qt.AlignLeft)
        self.title_label.setStyleSheet("color: #CA6161; font-size: %spx;" % DPI(18))
        text_layout.addWidget(self.title_label)

        subtitle = QtWidgets.QLabel("Have you found a bug? Please fill the report and I will do my best to fix it in the next update.")
        subtitle.setAlignment(QtCore.Qt.AlignLeft)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #cccccc; font-size: %spx;" % DPI(11))
        text_layout.addWidget(subtitle)

        header_layout.addLayout(text_layout, stretch=1)
        content_layout.addLayout(header_layout)

        self.status_label = QtWidgets.QLabel(self._status_placeholder)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.status_label.setMinimumHeight(self._status_row_height())
        self.status_label.setStyleSheet("color: %s;" % self._info_color)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("* Your name")
        self.name_input.setMaxLength(50)
        if prefill_name:
            self.name_input.setText(prefill_name)

        self.explanation_textbox = QtWidgets.QTextEdit()
        self.explanation_textbox.setPlaceholderText(
            "* Describe what happened, what you expected, and the steps to reproduce it."
        )
        self.explanation_textbox.setAcceptRichText(False)
        self.explanation_textbox.setMinimumHeight(DPI(110))
        self.explanation_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.explanation_textbox.textChanged.connect(lambda: self._enforce_text_limit(self.explanation_textbox))
        if prefill_explanation:
            self.explanation_textbox.setPlainText(prefill_explanation)

        self.script_error_textbox = QtWidgets.QTextEdit()
        self.script_error_textbox.setPlaceholderText(
            "Paste the last Script Editor lines here. Include the traceback or exact error if you have it."
        )
        self.script_error_textbox.setAcceptRichText(False)
        self.script_error_textbox.setMinimumHeight(DPI(80))
        self.script_error_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.script_error_textbox.textChanged.connect(lambda: self._enforce_text_limit(self.script_error_textbox))
        if prefill_script_error:
            self.script_error_textbox.setPlainText(prefill_script_error)

        self.name_input.setStyleSheet(self._input_style())
        self.name_input.textChanged.connect(self._clear_status_message)

        for widget in (self.explanation_textbox, self.script_error_textbox):
            widget.setStyleSheet(self._textedit_style())
            widget.textChanged.connect(self._clear_status_message)

        # Keep fields in a single vertical column for faster scanning/filling.
        content_layout.addWidget(self.name_input)
        self.details_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.details_splitter.setChildrenCollapsible(False)
        self.details_splitter.setOpaqueResize(True)
        self.details_splitter.setHandleWidth(DPI(6))
        self.details_splitter.addWidget(self.explanation_textbox)
        self.details_splitter.addWidget(self.script_error_textbox)
        self.details_splitter.setStretchFactor(0, 2)
        self.details_splitter.setStretchFactor(1, 1)
        content_layout.addWidget(self.details_splitter, 1)
        content_layout.addWidget(self.status_label)

        self.root_layout.addWidget(content_widget, 1)

        send_cfg = QFlatDialogButton("Send bug", highlight=True, icon=media.apply_image)
        send_cfg["callback"] = self._on_send_clicked
        self.setBottomBar([send_cfg], closeButton=True, highlight="Send bug")
        self._send_button = self._find_button("Send bug")

        # Keep a horizontal rectangle feel even with vertical fields.
        self.resize(DPI(680), DPI(500))
        QtCore.QTimer.singleShot(0, self._init_splitter_sizes)

    def _input_style(self):
        return (
            "QLineEdit {background-color: #2d2d2d;border: 1px solid #393939;border-radius: %spx;color: #cccccc;padding: %spx;font-size: %spx;}"
        ) % (DPI(4), DPI(6), DPI(11))

    def _textedit_style(self):
        return (
            "QTextEdit {background-color: #2d2d2d;border: 1px solid #393939;border-radius: %spx;color: #cccccc;padding: %spx;font-size: %spx;}"
        ) % (DPI(4), DPI(6), DPI(11))

    def _bug_icon_pixmap(self, size):
        path = media.report_a_bug_image
        if not path:
            return QtGui.QPixmap()

        lower = path.lower()
        if lower.endswith(".svg") and QSvgRenderer:
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                screen = QtGui.QGuiApplication.primaryScreen()
                dpr = screen.devicePixelRatio() if screen else 1.0
                width = max(1, int(size.width() * dpr))
                height = max(1, int(size.height() * dpr))
                pixmap = QtGui.QPixmap(width, height)
                pixmap.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(pixmap)
                renderer.render(painter, QtCore.QRectF(0, 0, width, height))
                painter.end()
                pixmap.setDevicePixelRatio(dpr)
                return pixmap

        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            return pixmap
        return pixmap.scaled(size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    def _find_button(self, name):
        if not self.bottomBar:
            return None
        for btn in self.bottomBar.findChildren(QtWidgets.QPushButton):
            if btn.text().strip().lower() == name.lower():
                return btn
        return None

    def apply_prefill(self, dialog_title=None, name="", explanation="", script_error=""):
        if dialog_title:
            self.setWindowTitle(dialog_title)
            self.title_label.setText("<b>{}</b>".format(dialog_title))
        self.name_input.setText(name or "")
        self.explanation_textbox.setPlainText(explanation or "")
        self.script_error_textbox.setPlainText(script_error or "")
        self._set_send_enabled(True)
        self._clear_status_message()

    def _status_row_height(self):
        metrics = self.status_label.fontMetrics() if hasattr(self, "status_label") else self.fontMetrics()
        return max(DPI(10), metrics.lineSpacing() + DPI(1))

    def _init_splitter_sizes(self):
        if not hasattr(self, "details_splitter"):
            return
        total = max(DPI(240), self.details_splitter.size().height())
        upper = max(DPI(130), int(total * 0.68))
        lower = max(DPI(90), total - upper)
        self.details_splitter.setSizes([upper, lower])

    def _set_send_enabled(self, enabled):
        if self._send_button:
            self._send_button.setEnabled(bool(enabled))

    def _required_values(self):
        return (
            self.name_input.text().strip(),
            self.explanation_textbox.toPlainText().strip(),
        )

    def _optional_values(self):
        return {
            "script_error": self.script_error_textbox.toPlainText().strip(),
        }

    def _validate(self):
        name, explanation = self._required_values()
        if not name or not explanation:
            self._set_status("Please fill in the required fields.", error=True)
            return None
        return {
            "name": name,
            "explanation": explanation,
            **self._optional_values(),
        }

    def _set_status(self, message, error=False):
        color = self._error_color if error else self._info_color
        self.status_label.setStyleSheet("color: %s;" % color)
        self.status_label.setText(message or self._status_placeholder)

    def _clear_status_message(self):
        if self._send_button and not self._send_button.isEnabled():
            return
        self.status_label.setText(self._status_placeholder)

    def _enforce_text_limit(self, widget):
        text = widget.toPlainText()
        if len(text) <= self.MAX_TEXT_CHARS:
            return
        cursor = widget.textCursor()
        pos = cursor.position()
        widget.blockSignals(True)
        widget.setPlainText(text[: self.MAX_TEXT_CHARS])
        cursor.setPosition(min(pos, self.MAX_TEXT_CHARS))
        widget.setTextCursor(cursor)
        widget.blockSignals(False)

    def _on_send_clicked(self):
        payload = self._validate()
        if not payload:
            return

        if not self._submit_callback:
            self._set_status("Bug reporting is unavailable right now.", error=True)
            return

        self._set_status("Sending bug report...", error=False)
        self._set_send_enabled(False)

        success = False
        try:
            success = bool(self._submit_callback(**payload))
        except Exception as exc:
            print("[TheKeyMachine] Bug report submission failed:", exc)

        if success:
            self._set_status("Report sent successfully. Thanks!", error=False)
            QtCore.QTimer.singleShot(3100, self.close)
        else:
            self._set_status("Failed to send the report. Try again later.", error=True)
            self._set_send_enabled(True)

    def show_centered(self):
        # Avoid adjustSize() here: it tends to make this dialog overly tall based on content hints.
        self.resize(DPI(680), DPI(500))
        parent = self.parentWidget() or get_maya_qt()
        if parent:
            geo = parent.frameGeometry()
            x = geo.x() + (geo.width() - self.width()) / 2
            y = geo.y() + (geo.height() - self.height()) / 2
        else:
            geo = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            x = geo.x() + (geo.width() - self.width()) / 2
            y = geo.y() + (geo.height() - self.height()) / 2

        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()


class TKMAboutDialog(QFlatDialog):
    def __init__(self, parent=None):
        QFlatDialog.__init__(self, parent)
        self.setWindowTitle("About TheKeyMachine")

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(20), DPI(20), DPI(20), 0)
        content_layout.setSpacing(DPI(12))

        # Logo
        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignCenter)
        logo_pixmap = QtGui.QPixmap(media.TheKeyMachine_logo_250_image)
        logo_label.setPixmap(logo_pixmap)
        content_layout.addWidget(logo_label)

        TheKeyMachine_stage_version = general.get_thekeymachine_stage_version()
        TheKeyMachine_version = general.get_thekeymachine_version()
        TheKeyMachine_build_version = general.get_thekeymachine_build_version()
        TheKeyMachine_codename = general.get_thekeymachine_codename()

        # Tool Name & Title
        tool_name = QtWidgets.QLabel("Animation toolset for Maya Animators")
        tool_name.setAlignment(QtCore.Qt.AlignCenter)
        tool_name.setStyleSheet("font-size: %spx; font-weight: bold; color: #ececec;" % DPI(16))
        content_layout.addWidget(tool_name)

        # Version Badge
        version_btn = QtWidgets.QPushButton(f"v{TheKeyMachine_version} {TheKeyMachine_stage_version}")

        if general.config["INTERNET_CONNECTION"]:
            version_btn.setCursor(QtCore.Qt.PointingHandCursor)

            clickable_style = """
                QPushButton:hover {
                    background-color: #498042;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #3a5a3d;
                    color: #98ae97;
                }
                """

            def _check_updates():
                import TheKeyMachine.mods.updater as updater

                try:
                    from importlib import reload
                except ImportError:
                    from imp import reload
                except ImportError:
                    pass

                reload(updater)

                updater.check_for_updates(force=True)

            version_btn.clicked.connect(_check_updates)
        else:
            clickable_style = ""

        version_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(76, 175, 80, 0.15);
                border: 1px solid #4CAF50;
                color: #81C784;
                border-radius: %spx;
                padding: %spx %spx;
                font-size: %spx;
                font-weight: bold;
            }
            %s
            """
            % (DPI(4), DPI(4), DPI(8), DPI(12), clickable_style)
        )
        content_layout.addWidget(version_btn, alignment=QtCore.Qt.AlignCenter)

        build_label = QtWidgets.QLabel(f"Build: {TheKeyMachine_build_version} | {TheKeyMachine_codename}")
        build_label.setAlignment(QtCore.Qt.AlignCenter)
        build_label.setStyleSheet("font-size: %spx; color: #888888;" % DPI(11))
        content_layout.addWidget(build_label)

        info_text = """
            <div style='text-align: center; color: #888888; font-size: %spx;'>
                <p>This tool is licensed under the <a href='https://www.gnu.org/licenses/gpl-3.0.en.html' style='color: #67b9e0; text-decoration: none;'>GNU GPL 3.0</a>.</p>
                <div style='margin-top: 10px;'>
                    Developed by <a href='http://rodritorres.com' style='color: #67b9e0; text-decoration: none;'>Rodrigo Torres</a>
                </div>
                <div style='margin-top: 5px;'>
                    Modified by <a href='http://alehaaaa.github.io' style='color: #67b9e0; text-decoration: none;'>Alehaaaa</a>
                </div>
            </div>
        """ % (DPI(11))

        info_label = QtWidgets.QLabel(info_text)
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_label.setTextFormat(QtCore.Qt.RichText)
        info_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        info_label.setOpenExternalLinks(True)
        info_label.setStyleSheet("background: transparent;")
        content_layout.addWidget(info_label)

        self.root_layout.addWidget(content_widget)
        self.setBottomBar(closeButton=True)
        self.adjustSize()


class QFlatNumberInput(QFlatToolBarDialog):
    """
    Flat floating dialog with:
        - title
        - optional icon
        - numeric input (spinbox)
        - action button
    """

    def __init__(
        self,
        callback=None,
        width=DPI(230),
        popup=True,
        closeButton=True,
        parent=None,
    ):
        self.title = "Bake Custom Interval"
        self.icon_path = media.bake_animation_custom_image
        self.start_value = 1.0

        self.COLOR_BG_TRACK = self.DARK_BG_COLOR

        super().__init__(parent=parent, popup=popup, closeButton=closeButton)

        self.setMinimumWidth(width)
        self.title_label.setText(self.title)

        self._callback = callback

        # Spinbox (replaces line edit)
        self.spinbox = cw.QFlatSpinBox()
        self.spinbox.setFixedHeight(DPI(30))

        # Configure behavior
        self.spinbox.setValue(self.start_value)
        self.spinbox.setSingleStep(1.0)  # step size

        # Enter key support (depends on your widget internals)
        if hasattr(self.spinbox, "lineEdit"):
            self.spinbox.lineEdit().returnPressed.connect(self._on_accept)

        self.mainLayout.addWidget(self.spinbox)

        bake_button = QFlatDialogButton(
            "Bake",
            icon=media.apply_image,
            callback=self._on_accept,
            highlight=True,
        )

        self.setBottomBar([bake_button], margins=0, spacing=2)

        self.spinbox.setFocus()

    # --- Value helpers ---
    def value(self):
        return self.spinbox.value()

    def int_value(self):
        return int(self.spinbox.value())

    def float_value(self):
        return float(self.spinbox.value())

    # --- Action ---
    def _on_accept(self, *args):
        if self._callback:
            self._callback(self.value(), self)
