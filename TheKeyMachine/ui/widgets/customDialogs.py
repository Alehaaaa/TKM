import sys

import re
import xml.etree.ElementTree as ET
from functools import partial

from TheKeyMachine.core.Qt import IsPyQt6, IsPySide6, QtCore, QtGui, QtSvg, QtWidgets

QRegularExpression = getattr(QtCore, "QRegularExpression", None) or getattr(QtCore, "QRegExp")
QRegularExpressionValidator = getattr(QtGui, "QRegularExpressionValidator", None) or getattr(QtGui, "QRegExpValidator")
QSvgRenderer = getattr(QtSvg, "QSvgRenderer", None)
PYSIDE_VERSION = 6 if (IsPySide6 or IsPyQt6) else 2

from TheKeyMachine.maya.selection import get_valid_selected_objects
from TheKeyMachine.ui.widgets.util import DPI, event_global_pos, get_maya_qt, is_valid_widget
from TheKeyMachine.ui.tooltips import QFlatTooltipManager

from TheKeyMachine.data import icons
from TheKeyMachine.tools.update import changelog
import TheKeyMachine.core.application as general
import TheKeyMachine.ui.widgets.customWidgets as cw


def _prepare_modal_wait():
    """Remove tool progress before waiting for user input."""
    try:
        from TheKeyMachine.tools import common as toolCommon

        toolCommon.finish_active_progress()
    except Exception:
        pass


def _parent_widget_for_layout(layout, fallback=None):
    parent = layout.parentWidget() if layout is not None and hasattr(layout, "parentWidget") else None
    return parent or fallback


# Standard dialog-button vocabulary, reused verbatim across the whole app --
# both via the QFlatDialog.Yes/No/Ok/Cancel/Close presets below and as plain
# literal strings passed straight into QFlatDialogButton() by individual
# dialogs (e.g. an "Apply" or "Close" button built ad hoc in some tool's own
# bottom bar). Every one of those still funnels through _defineButtons(), so
# resolving the translation there -- keyed by the literal English name -- is
# the single place this vocabulary translates for every dialog in the app.
# Feature-specific button words ("Save As", "Import Hotkeys", "Send bug", ...)
# are not reused across contexts and are translated at their own call site.
_STANDARD_BUTTON_I18N_IDS = {
    "Yes": "dialog_button_yes",
    "No": "dialog_button_no",
    "Ok": "dialog_button_ok",
    "Cancel": "dialog_button_cancel",
    "Close": "close",  # reuse the existing "Close" menu-action translation
    "Apply": "dialog_button_apply",
    "Save": "dialog_button_save",
}


def _translate_button_name(name, i18n_key=None):
    """Resolve a dialog button's displayed text for the current language.

    ``i18n_key`` is the same opt-in used by declared menu items
    (``widgets.toolbar_menus._declared_item_text``): a caller with a feature-
    specific button word (e.g. "Send bug") passes its own key instead of
    growing this module's standard-word table. Without one, ``name`` falls
    back to the shared Yes/No/Ok/Cancel/Close/Apply vocabulary above.
    """
    if i18n_key:
        from TheKeyMachine.core import i18n

        return i18n.tr(i18n_key, name)

    key = _STANDARD_BUTTON_I18N_IDS.get(name)
    if not key:
        return name
    from TheKeyMachine.core import i18n

    return i18n.tr(key, name)


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


class QFlatWindowMixin:
    """Shared header and footer helpers for QFlat windows."""

    TEXT_COLOR = "#bbbbbb"
    WINDOW_HEADER_MARGINS = (0, 4, 0, 6)
    WINDOW_HEADER_SPACING = 7
    WINDOW_HEADER_ICON_SIZE = 51
    WINDOW_HEADER_TITLE_SIZE = 20

    def _windowIconPixmap(self, icon, size):
        if not icon:
            return QtGui.QPixmap()

        icon_size = size if isinstance(size, QtCore.QSize) else QtCore.QSize(int(size), int(size))
        if isinstance(icon, QtGui.QIcon):
            if icon.isNull():
                return QtGui.QPixmap()
            return icon.pixmap(icon_size)
        if isinstance(icon, QtGui.QPixmap):
            if icon.isNull():
                return icon
            return icon.scaled(icon_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        lower_path = str(icon).lower()
        if lower_path.endswith(".svg") and QSvgRenderer:
            renderer = QSvgRenderer(icon)
            if renderer.isValid():
                screen = QtGui.QGuiApplication.primaryScreen()
                dpr = screen.devicePixelRatio() if screen else 1.0
                width = max(1, int(icon_size.width() * dpr))
                height = max(1, int(icon_size.height() * dpr))
                pixmap = QtGui.QPixmap(width, height)
                pixmap.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(pixmap)
                renderer.render(painter, QtCore.QRectF(0, 0, width, height))
                painter.end()
                pixmap.setDevicePixelRatio(dpr)
                return pixmap

        qicon = QtGui.QIcon(icon)
        if not qicon.isNull():
            return qicon.pixmap(icon_size)

        pixmap = QtGui.QPixmap(icon)
        if pixmap.isNull():
            return pixmap
        return pixmap.scaled(icon_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        self.setWindowHeaderTitle(title)

    def windowHeader(self):
        return getattr(self, "qflat_window_header", None)

    def windowHeaderLayout(self):
        return getattr(self, "qflat_window_header_layout", None)

    def addWindowHeader(
        self,
        parentLayout=None,
        text="",
        icon=None,
        textColor=None,
    ):
        layout = parentLayout or getattr(self, "root_layout", None)
        if layout is None:
            return None

        margins = tuple(DPI(value) for value in self.WINDOW_HEADER_MARGINS)
        spacing = DPI(self.WINDOW_HEADER_SPACING)
        icon_size = DPI(self.WINDOW_HEADER_ICON_SIZE)
        title_size = DPI(self.WINDOW_HEADER_TITLE_SIZE)
        if textColor is None:
            textColor = getattr(self, "TEXT_COLOR", "#bbbbbb")
        if icon is None:
            icon = getattr(self, "_window_header_icon", None)
        else:
            self._window_header_icon = icon
        text = text or self.windowTitle()

        header = QtWidgets.QWidget(_parent_widget_for_layout(layout, self))
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(*margins)
        header_layout.setSpacing(spacing)

        self.window_icon = QtWidgets.QLabel(header)
        self.window_icon.setFixedSize(icon_size, icon_size)
        self.window_icon.setAlignment(QtCore.Qt.AlignCenter)
        pixmap = self._windowIconPixmap(icon, QtCore.QSize(icon_size, icon_size))
        if not pixmap.isNull():
            self.window_icon.setPixmap(pixmap)
        self.window_icon.setVisible(bool(icon and not pixmap.isNull()))
        header_layout.addWidget(self.window_icon, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.window_title = QtWidgets.QLabel(text or "", header)
        self.window_title.setObjectName("qflat_window_title")
        self.window_title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.window_title.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.window_title.setWordWrap(False)
        self.window_title.setStyleSheet(
            "#qflat_window_title{color:%s;font-size:%spx;font-weight:bold;background:transparent;}" % (textColor, title_size)
        )
        header_layout.addWidget(self.window_title, 1, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.qflat_window_header = header
        self.qflat_window_header_layout = header_layout
        self.title_label = self.window_title

        layout.addWidget(header)
        return header

    def setWindowHeaderTitle(self, title):
        label = getattr(self, "window_title", None)
        if label:
            label.setText(title or "")

    def setWindowHeaderIcon(self, icon):
        self._window_header_icon = icon
        label = getattr(self, "window_icon", None)
        if not label:
            return
        icon_size = label.width() or DPI(self.WINDOW_HEADER_ICON_SIZE)
        pixmap = self._windowIconPixmap(icon, QtCore.QSize(icon_size, icon_size))
        label.setPixmap(pixmap)
        label.setVisible(bool(icon and not pixmap.isNull()))


class QFlatDialog(QFlatWindowMixin, QtWidgets.QDialog):
    # Button Preconfigurations
    Yes = QFlatDialogButton("Yes", positive=True, icon=icons.apply)
    Ok = QFlatDialogButton("Ok", positive=True, icon=icons.apply)

    No = QFlatDialogButton("No", positive=False, icon=icons.cancel)
    Cancel = QFlatDialogButton("Cancel", positive=False, icon=icons.cancel)
    Close = QFlatDialogButton("Close", positive=False, icon=icons.close)

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

    def exec_(self):
        _prepare_modal_wait()
        return QtWidgets.QDialog.exec_(self)

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

            canonical_name = config.get("name", "Button")
            btn = cw.QFlatButton(
                text=_translate_button_name(canonical_name, config.get("i18n_key")),
                background=config.get("background", "#5D5D5D"),
                icon=config.get("icon"),
                highlight=is_highlighted,
            )
            # Recognize this button by its untranslated English name later
            # (see _ensure_close_button()) -- btn.text() itself is translated
            # and can no longer be compared against literal words like "close".
            btn.setProperty("tkm_dialog_button_name", canonical_name)

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

        # Check if a close button already exists (avoid duplicates). Matched
        # by the untranslated English name stashed in _defineButtons(), since
        # btn.text() is translated and no longer comparable to "close".
        for btn in self.bottomBar.findChildren(QtWidgets.QPushButton):
            if str(btn.property("tkm_dialog_button_name") or btn.text()).lower() in ("close", "cancel"):
                return

        # Create close config
        close_cfg = self.Close.copy()
        if not close_cfg.get("callback"):
            close_cfg["callback"] = self.close

        # Build button using same pipeline
        new_btns = self._defineButtons([close_cfg])

        for btn in new_btns:
            self.bottomBar.layout().addWidget(btn)


class QFlatTooltipContent(QFlatWindowMixin, QtWidgets.QWidget):
    TEXT_COLOR = "#bbbbbb"
    HEADER_ICON_SIZE = 60

    def __init__(self, tooltip, icon=None, title="", parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.tooltip = tooltip or ""
        if icon and "<icon>" not in self.tooltip:
            self.tooltip = "<icon>{}</icon>{}".format(icon, self.tooltip)
        if title and "<title>" not in self.tooltip:
            self.tooltip = "<title>{}</title>{}".format(title, self.tooltip)

        self.content_layout = QtWidgets.QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self._build_content()

    def _build_content(self):
        try:
            safe_tooltip = self.tooltip.replace("&", "&amp;")
            if "<br>" in safe_tooltip.lower():
                safe_tooltip = re.sub(r"(?i)<br\s*>", "<br/>", safe_tooltip)
            root = ET.fromstring("<root>{}</root>".format(safe_tooltip))
        except Exception as e:
            root = ET.fromstring("<root><text>Invalid XML: {}</text></root>".format(e))

        header_frame = QtWidgets.QFrame(self)
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        header_layout.setContentsMargins(DPI(18), DPI(15), DPI(18), DPI(10))
        header_layout.setSpacing(DPI(12))

        has_header = False
        for child in root:
            if child.tag == "icon":
                dim = DPI(self.HEADER_ICON_SIZE)
                pix = self._windowIconPixmap(child.text, QtCore.QSize(dim, dim))
                if not pix.isNull():
                    lbl = QtWidgets.QLabel(header_frame)
                    lbl.setFixedSize(dim, dim)
                    lbl.setAlignment(QtCore.Qt.AlignCenter)
                    lbl.setPixmap(pix)
                    header_layout.addWidget(lbl)
                    has_header = True
            elif child.tag == "title":
                lbl = QtWidgets.QLabel(self._element_inner_text(child), header_frame)
                lbl.setStyleSheet(
                    "color: {}; font-size: {}px; font-weight: bold; background: transparent;".format(self.TEXT_COLOR, DPI(18))
                )
                lbl.setWordWrap(True)
                header_layout.addWidget(lbl)
                has_header = True

        if has_header:
            header_layout.addStretch()
            self.content_layout.addWidget(header_frame)

        body_layout = QtWidgets.QVBoxLayout()
        body_layout.setContentsMargins(DPI(18), 0, DPI(18), 0)
        body_layout.setSpacing(DPI(6))

        in_content = False
        for child in root:
            if not in_content and child.tag not in ["title", "icon"]:
                in_content = True
            if not in_content:
                continue
            self._add_content_element(body_layout, child)

        if body_layout.count() > 0:
            self.content_layout.addLayout(body_layout)

    def _element_inner_text(self, element):
        return (element.text or "") + "".join(
            ET.tostring(c, encoding="unicode")
            for c in element
        )

    def _add_content_element(self, layout, element):
        if element.tag == "text":
            lbl = QtWidgets.QLabel(self._element_inner_text(element), self)
            lbl.setWordWrap(True)
            lbl.setTextFormat(QtCore.Qt.RichText)
            lbl.setStyleSheet("color: {}; font-size: {}px; background: transparent;".format(self.TEXT_COLOR, DPI(11.5)))
            layout.addWidget(lbl)
        elif element.tag == "separator":
            try:
                margin = int(element.attrib.get("margin", 4))
            except (TypeError, ValueError):
                margin = 4
            if margin > 0:
                layout.addSpacing(DPI(margin))
            sep = QtWidgets.QFrame(self)
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: rgba(255,255,255,10);")
            layout.addWidget(sep)
            if margin > 0:
                layout.addSpacing(DPI(margin))
        elif element.tag == "spacing":
            try:
                size = int(element.attrib.get("size", 6))
            except (TypeError, ValueError):
                size = 6
            layout.addSpacing(DPI(size))
        elif element.tag in ["image", "gif"]:
            lbl = QtWidgets.QLabel(self)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            pix = QtGui.QPixmap(element.text)
            if not pix.isNull():
                if pix.width() > DPI(280):
                    pix = pix.scaledToWidth(DPI(280), QtCore.Qt.SmoothTransformation)
                lbl.setPixmap(pix)
                layout.addWidget(lbl)
        elif element.tag == "scroll":
            self._add_scroll_content(layout, element)

    def _add_scroll_content(self, layout, element):
        max_height = element.attrib.get("max_height", "")
        try:
            max_height = DPI(int(max_height))
        except (TypeError, ValueError):
            max_height = DPI(240)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setMaximumHeight(max_height)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QtWidgets.QWidget()
        content.setStyleSheet("background: transparent;")
        scroll_layout = QtWidgets.QVBoxLayout(content)
        scroll_layout.setContentsMargins(0, 0, DPI(8), 0)
        scroll_layout.setSpacing(DPI(6))

        for child in element:
            self._add_content_element(scroll_layout, child)

        scroll_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll)


class QFlatConfirmDialog(QFlatDialog):
    TEXT_COLOR = "#bbbbbb"

    def __init__(
        self,
        window="Confirm",
        title="",
        message="",
        buttons=[],
        closeButton=True,
        highlight=None,
        icon=None,
        tooltip=None,
        exclusive=True,
        parent=None,
        **kwargs,
    ):
        if not buttons and not closeButton:
            buttons = ["Ok"]
        QFlatDialog.__init__(self, parent=parent, buttons=buttons, highlight=highlight, closeButton=closeButton, **kwargs)

        new_flags = self.windowFlags() | QtCore.Qt.Dialog
        if parent and (parent.windowFlags() & QtCore.Qt.Tool):
            new_flags |= QtCore.Qt.Tool

        self.setWindowFlags(new_flags)
        if parent:
            self.setParent(parent)

        self._exclusive = exclusive
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setWindowTitle(window or "Confirm")

        self.clicked_button = None

        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)

        if tooltip:
            self.root_layout.addWidget(QFlatTooltipContent(tooltip, icon=icon, title=title, parent=self))
        else:
            content_widget = QtWidgets.QWidget(self)
            content_layout = QtWidgets.QHBoxLayout(content_widget)
            content_layout.setContentsMargins(DPI(25), DPI(20), DPI(25), DPI(20))

            if icon:
                icon_label = QtWidgets.QLabel(content_widget)
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
                self.title_label = QtWidgets.QLabel(title, content_widget)
                self.title_label.setWordWrap(True)
                self.title_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
                self.title_label.setStyleSheet("font-size: %spx; color: %s; font-weight: bold;" % (DPI(18), self.TEXT_COLOR))
                text_layout.addWidget(self.title_label)

            if isinstance(message, (list, tuple)):
                message = "<br><br>".join(message)

            self.message_label = QtWidgets.QLabel(message, content_widget)
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

    def _on_button_clicked(self, config, *_args):
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
        icon=None,
        **kwargs,
    ):
        if buttons is None:
            closeButton = True
        dlg = cls(
            window=window,
            icon=icon,
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
        icon=None,
        title="Are you sure?",
        **kwargs,
    ):
        if buttons is None and not closeButton:
            buttons = [cls.Yes, cls.No]
        dlg = cls(
            window=window,
            icon=icon,
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

        _prepare_modal_wait()
        self.show()
        self.raise_()
        self.activateWindow()
        loop = QtCore.QEventLoop()
        self.finished.connect(loop.quit)
        loop.exec_()
        return self.result() == QtWidgets.QDialog.Accepted


class QFlatTooltipConfirm(QFlatDialog):
    """
    A hybrid widget combining the visual style of a QFlatTooltip (arrow, rounded, dark, XML tooltip)
    with the logic and button handling of a QFlatConfirmDialog.
    """

    BG_COLOR = "#333333"
    TEXT_COLOR = "#bbbbbb"
    BORDER_RADIUS = 8
    ARROW_W = 12
    ARROW_H = 8
    HEADER_ICON_SIZE = 60

    def __init__(self, parent=None, title="", message="", buttons=None, icon=None, tooltip=None, highlight=None, **kwargs):
        tooltip = tooltip
        QFlatDialog.__init__(self, parent=parent, buttons=buttons, highlight=highlight, **kwargs)

        # Tooltip-like window setup
        self.setWindowFlags(QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.clicked_button = None

        # Build tooltip if not provided (compatibility with standard title/message/icon)
        if tooltip is None:
            tooltip = ""
            if icon:
                tooltip += "<icon>{}</icon>".format(icon)
            if title:
                tooltip += "<title>{}</title>".format(title)
            if message:
                tooltip += "<text>{}</text>".format(message)
        else:
            # If tooltip provided, ensure icon/title are included if passed as args and missing in xml
            if icon and "<icon>" not in tooltip:
                tooltip = "<icon>{}</icon>{}".format(icon, tooltip)
            if title and "<title>" not in tooltip:
                tooltip = "<title>{}</title>{}".format(title, tooltip)
        self.tooltip = tooltip

        # Style the frame
        self.setStyleSheet(
            "QFlatTooltipConfirm > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(
                self.BG_COLOR, DPI(self.BORDER_RADIUS)
            )
        )

        self.bg_frame = QtWidgets.QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.bg_layout = QtWidgets.QVBoxLayout(self.bg_frame)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_layout.setSpacing(0)
        self.root_layout.addWidget(self.bg_frame)

        self.bg_layout.addWidget(QFlatTooltipContent(self.tooltip, parent=self.bg_frame))

        # Add the interactive buttons at the bottom
        self.setBottomBar(buttons, margins=12, spacing=DPI(6), highlight=highlight)
        if self.bottomBar:
            self.root_layout.removeWidget(self.bottomBar)
            # Add a small separator before buttons if there was content
            self.bg_layout.addSpacing(DPI(8))
            self.bg_layout.addWidget(self.bottomBar)
            self.bg_layout.addSpacing(DPI(4))

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

    def _on_button_clicked(self, config, *_args):
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

        try:
            dlg._show_around(anchor_widget, target_rect=kwargs.get("target_rect"))
            dlg.exec_()
            return dlg.clicked_button
        finally:
            dlg.setParent(None)
            dlg.deleteLater()
            app = QtWidgets.QApplication.instance()
            if app is not None:
                QtWidgets.QApplication.sendPostedEvents(dlg, QtCore.QEvent.DeferredDelete)

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


class QFlatAutoHideMessage(QFlatDialog):
    """A borderless, buttonless notification popup -- the same dark rounded
    XML-tooltip look ``QFlatTooltipConfirm`` uses (arrow included, same
    ``paintEvent``/margin-reservation approach), minus its buttons (nothing
    to confirm): it just states its piece and closes itself after
    *duration* milliseconds. A thin ``QProgressBar`` along the bottom of
    the inner layout counts down visibly so the user can see how long is
    left to read it before it auto-hides -- use ``show_message`` rather
    than the constructor directly, which also keeps the instance alive (it
    isn't parented to anything modal, so nothing else would)."""

    BG_COLOR = "#333333"
    TEXT_COLOR = "#bbbbbb"
    BORDER_RADIUS = 8
    ARROW_W = 12
    ARROW_H = 8
    PROGRESS_INTERVAL_MS = 50

    _live_instances = []

    def __init__(self, tooltip="", duration=5000, parent=None):
        QFlatDialog.__init__(self, parent=parent)

        self.setWindowFlags(QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        # None until show_message anchors this to a real widget -- no
        # arrow drawn (see paintEvent) for the no-anchor cursor fallback,
        # since there's nothing for it to point at there.
        self.side = None
        self.arrow_x = None

        self.setStyleSheet(
            "QFlatAutoHideMessage > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(
                self.BG_COLOR, DPI(self.BORDER_RADIUS)
            )
        )

        self.bg_frame = QtWidgets.QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.bg_frame.setMinimumWidth(DPI(240))
        self.bg_frame.setMaximumWidth(DPI(360))
        self.bg_layout = QtWidgets.QVBoxLayout(self.bg_frame)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_layout.setSpacing(0)
        self.root_layout.addWidget(self.bg_frame)

        self.bg_layout.addWidget(QFlatTooltipContent(tooltip, parent=self.bg_frame))
        self.bg_layout.addSpacing(DPI(8))

        radius = DPI(self.BORDER_RADIUS)
        self.progress_bar = QtWidgets.QProgressBar(self.bg_frame)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, max(1, duration))
        self.progress_bar.setValue(duration)
        self.progress_bar.setFixedHeight(DPI(4))
        self.progress_bar.setStyleSheet(
            "QProgressBar {{ background: #222222; border: none; "
            "border-bottom-left-radius: {r}px; border-bottom-right-radius: {r}px; }} "
            # The chunk (the actual fill, not just the track) needs both
            # bottom corners rounded too, not just the left one -- it
            # starts at full width, so its right edge sits flush against
            # the track's rounded bottom-right corner and was squaring it
            # off, poking a sharp corner out past bg_frame's rounded shape
            # instead of sitting flush inside it.
            "QProgressBar::chunk {{ background: #8a8a8a; border-bottom-left-radius: {r}px; "
            "border-bottom-right-radius: {r}px; }}".format(r=radius)
        )
        self.bg_layout.addWidget(self.progress_bar)

        self._remaining_ms = duration
        self._tick_timer = QtCore.QTimer(self)
        self._tick_timer.setInterval(self.PROGRESS_INTERVAL_MS)
        self._tick_timer.timeout.connect(self._on_tick)

    def _on_tick(self):
        self._remaining_ms -= self.PROGRESS_INTERVAL_MS
        self.progress_bar.setValue(max(0, self._remaining_ms))
        if self._remaining_ms <= 0:
            self._tick_timer.stop()
            self.close()

    def closeEvent(self, event):
        self._tick_timer.stop()
        if self in QFlatAutoHideMessage._live_instances:
            QFlatAutoHideMessage._live_instances.remove(self)
        QFlatDialog.closeEvent(self, event)

    def paintEvent(self, event):
        # Same arrow-triangle painting QFlatTooltipConfirm.paintEvent does --
        # the rounded dark frame itself is drawn by bg_frame's own
        # stylesheet, this just adds the little pointer in the margin
        # root_layout reserved for it (see show_message). No anchor ->
        # self.side is None -> nothing to draw, no arrow.
        if not self.side:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(self.BG_COLOR))

        aw = DPI(self.ARROW_W)
        ah = DPI(self.ARROW_H)
        ax = self.arrow_x if self.arrow_x is not None else self.width() / 2

        if self.side == "top":
            poly = QtGui.QPolygonF([QtCore.QPointF(ax, 0), QtCore.QPointF(ax - aw / 2, ah + 1), QtCore.QPointF(ax + aw / 2, ah + 1)])
        else:
            poly = QtGui.QPolygonF(
                [
                    QtCore.QPointF(ax, self.height()),
                    QtCore.QPointF(ax - aw / 2, self.height() - ah - 1),
                    QtCore.QPointF(ax + aw / 2, self.height() - ah - 1),
                ]
            )
        painter.drawPolygon(poly)

    @classmethod
    def show_message(cls, tooltip, duration=5000, anchor_widget=None, parent=None):
        """Build, position, show, and start counting down one of these --
        the usual entry point instead of the constructor.

        With *anchor_widget* (a still-valid, visible widget -- typically
        the toolbar button that triggered whatever's being reported on),
        this lands just under it, arrow pointing up at it, like a tooltip
        would -- flipping above (arrow pointing down) if there's no room
        below. Without one (or if it's gone/hidden by the time this
        fires), it falls back to centered near the top of the cursor's own
        screen, with no arrow (nothing to point at there)."""
        msg = cls(tooltip=tooltip, duration=duration, parent=parent)
        cls._live_instances.append(msg)

        ah = DPI(cls.ARROW_H)
        aw = DPI(cls.ARROW_W)

        if anchor_widget is not None and is_valid_widget(anchor_widget) and anchor_widget.isVisible():
            anchor_rect = QtCore.QRect(anchor_widget.mapToGlobal(QtCore.QPoint(0, 0)), anchor_widget.size())
            screen = QtGui.QGuiApplication.screenAt(anchor_rect.center()) or QtGui.QGuiApplication.primaryScreen()
            geo = screen.availableGeometry()

            # Box below the anchor: the arrow sits on the box's *top* edge,
            # pointing up at the anchor above it -- that's paintEvent's
            # "top" branch (apex at y=0), so self.side is "top" here even
            # though the box itself is below the anchor. Margin reserves
            # room for it the same way QFlatTooltipConfirm._show_around does.
            msg.side = "top"
            msg.root_layout.setContentsMargins(0, ah, 0, 0)
            msg.root_layout.activate()
            msg.adjustSize()

            x = anchor_rect.center().x() - msg.width() // 2
            y = anchor_rect.bottom() + DPI(2)
            if y + msg.height() > geo.bottom():
                # Flipped above the anchor instead: arrow moves to the
                # box's *bottom* edge, pointing down at the anchor below it.
                msg.side = "bottom"
                msg.root_layout.setContentsMargins(0, 0, 0, ah)
                msg.root_layout.activate()
                msg.adjustSize()
                y = anchor_rect.top() - msg.height() - DPI(2)
        else:
            msg.adjustSize()
            cursor_pos = QtGui.QCursor.pos()
            screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
            geo = screen.availableGeometry()
            x = geo.center().x() - msg.width() // 2
            y = geo.top() + DPI(60)

        final_x = max(geo.left() + DPI(5), min(x, geo.right() - msg.width() - DPI(5)))
        final_y = max(geo.top() + DPI(5), min(y, geo.bottom() - msg.height() - DPI(5)))
        msg.move(final_x, final_y)

        if msg.side:
            arrow_x = anchor_rect.center().x() - final_x
            msg.arrow_x = max(DPI(6) + aw / 2, min(arrow_x, msg.width() - DPI(6) - aw / 2))

        msg.show()
        msg.raise_()
        msg._tick_timer.start()
        return msg


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
        self.header_left_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
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
        self.header_separator.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.header_separator.setVisible(False)

        self._header_right_spacing = QtWidgets.QWidget()
        self._header_right_spacing.setFixedWidth(DPI(8))
        self._header_right_spacing.setVisible(False)

        self.header_right_container = QtWidgets.QWidget()
        self.header_right_container.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        self.header_right_layout = QtWidgets.QHBoxLayout(self.header_right_container)
        self.header_right_layout.setContentsMargins(0, 0, 0, 0)
        self.header_right_layout.setSpacing(DPI(2))
        self.header_right_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.close_button = QtWidgets.QToolButton()
        self.close_button.setAutoRaise(True)
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_button.setIcon(QtGui.QIcon(icons.close))
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
    icon = None

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)
        self.setWindowTitle(self.title)
        self.setMinimumWidth(DPI(230))
        self.setMinimumHeight(DPI(300))

        # Header. Matches AttributeSwitcherWindow's selection header exactly:
        # icon first (fixed size, centered), then an expanding bold title
        # label -- the one icon/title system every toolbar popup shares.
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setContentsMargins(DPI(6), DPI(10), DPI(6), DPI(4))
        title_layout.setSpacing(DPI(6))

        if self.icon:
            icon_size = DPI(25)
            icon_label = QtWidgets.QLabel()
            icon_label.setFixedSize(icon_size, icon_size)
            icon_label.setPixmap(QtGui.QIcon(self.icon).pixmap(icon_size, icon_size))
            icon_label.setAlignment(QtCore.Qt.AlignCenter)
            title_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignVCenter)

        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("title_label")
        self.title_label.setStyleSheet(
            "#title_label{font-size: %spx; color: %s; font-weight: bold; background: transparent;}" % (DPI(18), self.TEXT_COLOR)
        )
        self.title_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.title_label.setWordWrap(False)
        title_layout.addWidget(self.title_label, 1)
        # Kept as an attribute so subclasses can append persistent header
        # affordances (e.g. a "+" create button) without re-building the header.
        self.title_layout = title_layout

        self.mainLayout.addLayout(title_layout)


class ActivationAutoCloseMixin:
    """Close a transient window only after it has genuinely been active.

    Qt can emit ``ActivationChange`` while window flags are being configured
    and while a hidden widget is being constructed.  Those events are not
    user-driven deactivation and must never arm auto-close.
    """

    _activation_auto_close_enabled = True

    def showEvent(self, event):
        self._activation_auto_close_armed = False
        super().showEvent(event)

    def changeEvent(self, event):
        if (
            self._activation_auto_close_enabled
            and event.type() == QtCore.QEvent.ActivationChange
        ):
            should_close = False
            if self.isVisible():
                if self.isActiveWindow():
                    self._activation_auto_close_armed = True
                else:
                    should_close = getattr(
                        self, "_activation_auto_close_armed", False
                    )

            super().changeEvent(event)
            if should_close:
                self.close()
            return

        super().changeEvent(event)


class QFlatToolBarPopupDialog(ActivationAutoCloseMixin, QFlatToolBarDialog):
    """
    Toolbar-style popup dialog that closes after activation changes.
    """

    def __init__(self, parent=None, native_popup=False, *args, **kwargs):
        self._native_popup = bool(native_popup)
        self._activation_auto_close_enabled = not self._native_popup
        self._activation_auto_close_armed = False
        super().__init__(parent=parent, *args, **kwargs)
        if self._native_popup:
            self.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)


class QFlatPinnableToolBarPopupDialog(QFlatToolBarPopupDialog):
    """A toolbar popup that turns into a normal pinned window once dragged.

    Opens as a transient popup with no bottom bar (unless ``persistent_buttons``
    are supplied), closing itself the moment Maya's UI steals window activation
    -- the same behavior ``QFlatToolBarPopupDialog`` gives every other transient
    popup. Dragging it promotes the window to "pinned": activation changes stop
    closing it, and a Close button appears in the bottom bar alongside any
    persistent buttons. This is the one place that owns that pin/unpin quirk;
    subclasses only describe their own persistent buttons and reuse it instead
    of re-implementing drag detection and activation-change handling.
    """

    DRAG_PIN_DISTANCE = None  # falls back to DPI(10) if left unset

    def __init__(self, parent=None, popup=True, persistent_buttons=None, bottom_bar_kwargs=None, **kwargs):
        self._pinned = not popup
        self._persistent_buttons = list(persistent_buttons or [])
        self._bottom_bar_kwargs = dict(bottom_bar_kwargs or {})
        super().__init__(parent=parent, popup=popup, closeButton=False, **kwargs)
        self._refresh_action_bar()

    def _refresh_action_bar(self):
        self.setBottomBar(
            buttons=list(self._persistent_buttons),
            closeButton=self._pinned,
            **self._bottom_bar_kwargs,
        )

    def set_persistent_buttons(self, buttons):
        """Replace the always-visible bottom-bar buttons (Close is managed separately)."""
        self._persistent_buttons = list(buttons or [])
        self._refresh_action_bar()

    def set_popup_mode(self, popup):
        """Restore transient or pinned presentation when reusing the window."""
        self._popup = bool(popup)
        self._pinned = not popup
        self._activation_auto_close_armed = False
        self._refresh_action_bar()

    def _pin_after_reposition(self):
        if self._pinned:
            return
        self._pinned = True
        self._popup = False
        self._refresh_action_bar()

    def mouseReleaseEvent(self, event):
        was_dragging = self._is_dragging
        drag_start = QtCore.QPoint(self._drag_start_pos)
        global_position = event_global_pos(event)
        super().mouseReleaseEvent(event)
        threshold = self.DRAG_PIN_DISTANCE if self.DRAG_PIN_DISTANCE is not None else DPI(10)
        if was_dragging and (global_position - drag_start).manhattanLength() > threshold:
            self._pin_after_reposition()

    def changeEvent(self, event):
        if self._pinned:
            QFlatToolBarDialog.changeEvent(self, event)
            return
        super().changeEvent(event)


class QFlatBugReportDialog(QFlatDialog):
    """
    Modern bug report dialog that reuses QFlatDialog styling.
    """

    MAX_TEXT_CHARS = 1200
    MAX_SCRIPT_ERROR_CHARS = 12000

    def __init__(
        self,
        parent=None,
        submit_callback=None,
        prepare_callback=None,
        worker_class=None,
        dialog_title=None,
        prefill_name="",
        prefill_explanation="",
        prefill_script_error="",
    ):
        from TheKeyMachine.core import i18n

        self._submit_callback = submit_callback
        self._prepare_callback = prepare_callback
        self._worker_class = worker_class
        self._submit_worker = None
        self._submitted_successfully = False
        self._send_button = None
        super().__init__(parent=parent)
        self.setWindowTitle(dialog_title or i18n.tr("bug_report_title", "Report a Bug"))
        # More horizontal / less tall default footprint.
        self.setMinimumSize(DPI(600), DPI(450))

        self._info_color = "#9bbbca"
        self._error_color = "#CA6161"
        self._status_placeholder = " "

        content_widget = QtWidgets.QWidget(self)
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(12), DPI(12), DPI(12), 0)
        content_layout.setSpacing(DPI(8))

        self.addWindowHeader(
            parentLayout=content_layout,
            icon=icons.bug,
            textColor="#CA6161",
        )

        subtitle = QtWidgets.QLabel(
            i18n.tr(
                "bug_report_subtitle",
                "Have you found a bug? Please fill the report and I will do my best to fix it in the next update.",
            ),
            content_widget,
        )
        subtitle.setAlignment(QtCore.Qt.AlignLeft)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #cccccc; font-size: %spx;" % DPI(11))
        content_layout.addWidget(subtitle)

        self.status_label = QtWidgets.QLabel(self._status_placeholder, content_widget)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.status_label.setMinimumHeight(self._status_row_height())
        self.status_label.setStyleSheet("color: %s;" % self._info_color)
        self.status_label.setVisible(False)

        self.name_input = QtWidgets.QLineEdit(content_widget)
        self.name_input.setPlaceholderText(i18n.tr("bug_report_name_placeholder", "* Your name"))
        self.name_input.setMaxLength(50)
        if prefill_name:
            self.name_input.setText(prefill_name)

        self.explanation_textbox = QtWidgets.QTextEdit(content_widget)
        self.explanation_textbox.setPlaceholderText(
            i18n.tr(
                "bug_report_explanation_placeholder",
                "* Describe what happened, what you expected, and the steps to reproduce it.",
            )
        )
        self.explanation_textbox.setAcceptRichText(False)
        self.explanation_textbox.setMinimumHeight(DPI(110))
        self.explanation_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.explanation_textbox.textChanged.connect(lambda: self._enforce_text_limit(self.explanation_textbox))
        if prefill_explanation:
            self.explanation_textbox.setPlainText(prefill_explanation)

        self.script_error_textbox = QtWidgets.QTextEdit(content_widget)
        self.script_error_textbox.setPlaceholderText(
            i18n.tr(
                "bug_report_script_error_placeholder",
                "Paste the last Script Editor lines here. Include the traceback or exact error if you have it.",
            )
        )
        self.script_error_textbox.setAcceptRichText(False)
        self.script_error_textbox.setMinimumHeight(DPI(80))
        self.script_error_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.script_error_textbox.textChanged.connect(
            lambda: self._enforce_text_limit(self.script_error_textbox, limit=self.MAX_SCRIPT_ERROR_CHARS)
        )
        if prefill_script_error:
            self.script_error_textbox.setPlainText(prefill_script_error)

        self.name_input.setStyleSheet(self._input_style())
        self.name_input.textChanged.connect(self._clear_status_message)

        for widget in (self.explanation_textbox, self.script_error_textbox):
            widget.setStyleSheet(self._textedit_style())
            widget.textChanged.connect(self._clear_status_message)

        left_fields = QtWidgets.QWidget(content_widget)
        left_fields_layout = QtWidgets.QVBoxLayout(left_fields)
        left_fields_layout.setContentsMargins(0, 0, 0, 0)
        left_fields_layout.setSpacing(DPI(8))
        left_fields_layout.addWidget(self.name_input)
        left_fields_layout.addWidget(self.explanation_textbox, 1)

        self.details_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, content_widget)
        self.details_splitter.setChildrenCollapsible(False)
        self.details_splitter.setOpaqueResize(True)
        self.details_splitter.setHandleWidth(DPI(6))
        self.details_splitter.addWidget(left_fields)
        self.details_splitter.addWidget(self.script_error_textbox)
        self.details_splitter.setStretchFactor(0, 2)
        self.details_splitter.setStretchFactor(1, 1)
        content_layout.addWidget(self.details_splitter, 1)
        content_layout.addWidget(self.status_label)

        self.root_layout.addWidget(content_widget, 1)

        send_cfg = QFlatDialogButton(
            "Send bug", highlight=True, icon=icons.apply, i18n_key="bug_report_send_button"
        )
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

    def _find_button(self, name):
        if not self.bottomBar:
            return None
        for btn in self.bottomBar.findChildren(QtWidgets.QPushButton):
            # Match by the untranslated English name stashed in
            # _defineButtons() -- btn.text() is translated and no longer
            # comparable to a literal English name like "Send bug".
            stored_name = btn.property("tkm_dialog_button_name")
            candidate = str(stored_name) if stored_name else btn.text()
            if candidate.strip().lower() == name.lower():
                return btn
        return None

    def apply_prefill(self, dialog_title=None, name="", explanation="", script_error=""):
        if dialog_title:
            self.setWindowTitle(dialog_title)
        self.name_input.setText(name or "")
        self.explanation_textbox.setPlainText(explanation or "")
        self.script_error_textbox.setPlainText(script_error or "")
        self._submitted_successfully = False
        self._set_send_enabled(True)
        self._clear_status_message()

    def _status_row_height(self):
        metrics = self.status_label.fontMetrics() if hasattr(self, "status_label") else self.fontMetrics()
        return max(DPI(10), metrics.lineSpacing() + DPI(1))

    def _init_splitter_sizes(self):
        if not hasattr(self, "details_splitter"):
            return
        total = max(DPI(420), self.details_splitter.size().width())
        left = max(DPI(260), int(total * 0.62))
        right = max(DPI(180), total - left)
        self.details_splitter.setSizes([left, right])

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
        from TheKeyMachine.core import i18n

        name, explanation = self._required_values()
        if not name or not explanation:
            self._set_status(
                i18n.tr("bug_report_status_missing_fields", "Please fill in the required fields."),
                error=True,
            )
            return None
        return {
            "name": name,
            "explanation": explanation,
            **self._optional_values(),
        }

    def _set_status(self, message, error=False):
        color = self._error_color if error else self._info_color
        self.status_label.setStyleSheet("color: %s;" % color)
        self.status_label.setText(message or "")
        self.status_label.setVisible(bool(message))

    def _clear_status_message(self):
        if self._submitted_successfully:
            return
        if self._send_button and not self._send_button.isEnabled():
            return
        self.status_label.setText("")
        self.status_label.setVisible(False)

    def _enforce_text_limit(self, widget, limit=None):
        limit = int(limit or self.MAX_TEXT_CHARS)
        text = widget.toPlainText()
        if len(text) <= limit:
            return
        cursor = widget.textCursor()
        pos = cursor.position()
        widget.blockSignals(True)
        widget.setPlainText(text[:limit])
        cursor.setPosition(min(pos, limit))
        widget.setTextCursor(cursor)
        widget.blockSignals(False)

    def _on_send_clicked(self):
        from TheKeyMachine.core import i18n

        payload = self._validate()
        if not payload:
            return

        unavailable_message = i18n.tr(
            "bug_report_status_unavailable", "Bug reporting is unavailable right now."
        )

        if not self._submit_callback:
            self._set_status(unavailable_message, error=True)
            return

        if self._submit_worker and self._submit_worker.isRunning():
            return

        if self._prepare_callback:
            try:
                payload = self._prepare_callback(**payload)
            except Exception as exc:
                print("[TheKeyMachine] Bug report preparation failed:", exc)
                self._set_status(
                    i18n.tr("bug_report_status_prepare_failed", "Failed to prepare the report."),
                    error=True,
                )
                return

        self._set_status(i18n.tr("bug_report_status_sending", "Sending bug report..."), error=False)
        self._set_send_enabled(False)

        if self._worker_class is None:
            self._set_status(unavailable_message, error=True)
            self._set_send_enabled(True)
            return

        self._submit_worker = self._worker_class(self._submit_callback, payload, parent=self)
        self._submit_worker.result_ready.connect(self._on_submit_finished)
        self._submit_worker.finished.connect(self._submit_worker.deleteLater)
        self._submit_worker.start()

    def _on_submit_finished(self, success, error):
        from TheKeyMachine.core import i18n

        if success:
            self._submitted_successfully = True
            self._set_status(
                i18n.tr("bug_report_status_success", "Report sent successfully. Thanks!"), error=False
            )
            self._set_send_enabled(False)
        else:
            if error:
                print("[TheKeyMachine] Bug report submission failed:", error)
            self._set_status(
                i18n.tr("bug_report_status_failed", "Failed to send the report. Try again later."),
                error=True,
            )
            self._set_send_enabled(True)
        self._submit_worker = None

    def closeEvent(self, event):
        if self._submit_worker and self._submit_worker.isRunning():
            from TheKeyMachine.core import i18n

            self._set_status(
                i18n.tr("bug_report_status_sending_wait", "Sending bug report. Please wait..."),
                error=False,
            )
            event.ignore()
            return
        QFlatDialog.closeEvent(self, event)

    def show_centered(self):
        # Avoid adjustSize() here: it tends to make this dialog overly tall based on content hints.
        self.resize(DPI(680), DPI(500))
        parent = self.parentWidget() or get_maya_qt()
        if isinstance(parent, QtWidgets.QWidget) and hasattr(parent, "frameGeometry"):
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
