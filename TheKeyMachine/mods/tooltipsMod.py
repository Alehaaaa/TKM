import sys
from TheKeyMachine.tools import common as toolCommon

from TheKeyMachine.core.Qt import QtCore, QtGui, QtSvg, QtWidgets  # type: ignore

QSvgRenderer = getattr(QtSvg, "QSvgRenderer", None)

from TheKeyMachine.widgets import util as wutil
from TheKeyMachine.data import icons
from TheKeyMachine.data.movies import TooltipMedia
from TheKeyMachine.widgets.tooltip_media import TooltipMovieWidget
import TheKeyMachine.mods.settingsMod as settings


IS_MAC = sys.platform == "darwin"
SHORTCUT_KEY_MAP = {
    QtCore.Qt.Key_Alt: "⌥" if IS_MAC else "Alt",
    QtCore.Qt.Key_Shift: "⇧" if IS_MAC else "Shift",
    QtCore.Qt.Key_Control: "⌘" if IS_MAC else "Ctrl",
    QtCore.Qt.MiddleButton: "Click" if IS_MAC else "MidClick",
}
SHORTCUT_KEY_ORDER = [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift, QtCore.Qt.MiddleButton]


class Tooltip(str):
    def __new__(cls, text, title="", body_lines=(), icon=None):
        obj = str.__new__(cls, text)
        obj.title = title
        obj.body_lines = tuple(line for line in body_lines if line)
        obj.icon = icon
        return obj

    @property
    def first_line(self):
        for line in self.body_lines:
            if isinstance(line, str) and line.strip():
                return line
        return ""


def _string_body_lines(raw):
    lines = []
    for line in str(raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        clean_line = toolCommon.clean_tool_text(line)
        if clean_line:
            lines.append(clean_line)
    return tuple(lines)


separator = object()


def tooltip_body(*paragraphs):
    lines = []
    def _append(paragraph):
        if paragraph is separator:
            lines.append(paragraph)
            return
        if isinstance(paragraph, TooltipMedia):
            lines.append(paragraph)
            return
        if isinstance(paragraph, (list, tuple)):
            for item in paragraph:
                _append(item)
            return
        if paragraph and str(paragraph).strip():
            lines.append(str(paragraph).strip())

    for paragraph in paragraphs:
        _append(paragraph)
    return tuple(lines)


def _tooltip_from_body(body):
    body_lines = tooltip_body(*(body if isinstance(body, (list, tuple)) else [body]))
    text_lines = []
    for item in body_lines:
        if item is separator:
            text_lines.append("---")
        elif isinstance(item, TooltipMedia):
            text_lines.append(item.path)
        else:
            text_lines.append(str(item))
    return Tooltip("\n\n".join(line for line in text_lines if line), title="", body_lines=body_lines, icon=None)


def _tooltip_from_data(raw, fallback_title="", fallback_description="", fallback_icon=None):
    if isinstance(raw, Tooltip):
        return Tooltip(
            str(raw),
            title="",
            body_lines=getattr(raw, "body_lines", ()),
            icon=None,
        )

    if isinstance(raw, (list, tuple)):
        return _tooltip_from_body(raw)

    # Fallback: plain string passed directly as tooltip content.
    if isinstance(raw, str) and raw:
        lines = list(_string_body_lines(raw))
        if fallback_title and lines and lines[0].lower() == fallback_title.lower():
            lines = lines[1:]
        return Tooltip(raw, title="", body_lines=lines, icon=None)

    if fallback_description:
        return _tooltip_from_body(fallback_description)

    return Tooltip("", title="", body_lines=(), icon=None)


def format_tooltip_shortcut(keys_list, include_click_suffix=False):
    keys_list = list(keys_list or [])
    if not keys_list:
        return ""

    keys_set = set(keys_list)
    parts = [SHORTCUT_KEY_MAP[key] for key in SHORTCUT_KEY_ORDER if key in keys_set]
    seen_labels = set(parts)

    if len(parts) < len(keys_set):
        for key in keys_list:
            if key in SHORTCUT_KEY_MAP:
                continue
            label = str(key)
            if label in seen_labels:
                continue
            parts.append(label)
            seen_labels.add(label)

    if not parts:
        return ""

    separator = "" if IS_MAC else "+"
    result = separator.join(parts)
    if include_click_suffix:
        return result + "+Click"
    return result


class QFlatTooltip(QtWidgets.QWidget):
    """A floating tooltip with an arrow pointing to its source."""

    BG_COLOR = "#333333"
    HEADER_COLOR = "#282828"
    TEXT_COLOR = "#bbbbbb"
    ARROW_W = 12
    ARROW_H = 8
    BORDER_RADIUS = 8

    MAX_WIDTH = 320
    MIN_WIDTH = 220

    def __init__(
        self,
        text="",
        anchor_widget=None,
        icon=None,
        shortcuts=None,
        description=None,
        tooltip=None,
        icon_obj=None,
        command_id=None,
        command_label=None,
        command_icon=None,
        from_menu=False,
    ):
        QtWidgets.QWidget.__init__(self, wutil.get_maya_qt())
        window_type = QtCore.Qt.ToolTip if from_menu else QtCore.Qt.Tool
        self.setWindowFlags(window_type | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_NoMouseReplay)

        self.anchor_widget = anchor_widget
        self.shortcuts = shortcuts or []
        self.icon_obj = icon_obj
        self.command_id = command_id
        self.command_label = command_label
        self.command_icon = command_icon
        self.text = text
        self.description = description
        self.icon = icon  # Store for reference
        self._shortcut_min_width = 0

        self.tooltip = _tooltip_from_data(
            tooltip,
            fallback_title=text.strip() if text else "",
            fallback_description=description.strip() if isinstance(description, str) else description,
            fallback_icon=icon,
        )

        self._auto_close_timer = QtCore.QTimer(self)
        self._auto_close_timer.setInterval(200)
        self._auto_close_timer.timeout.connect(self._check_auto_close)

        self._setup_ui()

    def _check_auto_close(self):
        """Strictly manages tooltip visibility based on cursor location."""
        if not self.isVisible():
            self._auto_close_timer.stop()
            return

        cursor_pos = QtGui.QCursor.pos()
        tt_geo = self.frameGeometry()
        side = getattr(self, "side", "bottom")

        buffer = wutil.DPI(30)
        if side == "top":
            tt_safety = tt_geo.adjusted(-buffer, 0, buffer, buffer)
        else:
            tt_safety = tt_geo.adjusted(-buffer, -buffer, buffer, 0)

        if tt_safety.contains(cursor_pos):
            return

        if getattr(self, "target_rect", None):
            anc_geo = self.target_rect
        elif self.anchor_widget and wutil.is_valid_widget(self.anchor_widget) and self.anchor_widget.isVisible():
            anc_geo = self.anchor_widget.rect()
            anc_geo.moveTo(self.anchor_widget.mapToGlobal(QtCore.QPoint(0, 0)))
        else:
            self.close()
            return

        if anc_geo.contains(cursor_pos):
            return

        if isinstance(self.anchor_widget, QtWidgets.QMenu):
            active_popup = QtWidgets.QApplication.activePopupWidget()
            if active_popup and active_popup.geometry().contains(cursor_pos):
                return

        bridge_l = max(anc_geo.left(), tt_geo.left())
        bridge_r = min(anc_geo.right(), tt_geo.right())

        if side == "top":
            bridge_top, bridge_bot = anc_geo.bottom() - 1, tt_geo.top() + 1
        else:
            bridge_top, bridge_bot = tt_geo.bottom() - 1, anc_geo.top() + 1

        bridge = QtCore.QRect(bridge_l, bridge_top, bridge_r - bridge_l, bridge_bot - bridge_top)
        if bridge.contains(cursor_pos):
            return

        self.close()

    def _setup_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.main_layout.setSizeConstraint(QtWidgets.QVBoxLayout.SetMinAndMaxSize)
        self.setStyleSheet(
            "QFlatTooltip > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(
                self.BG_COLOR, wutil.DPI(self.BORDER_RADIUS)
            )
        )

        self.bg_frame = QtWidgets.QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.bg_frame.setMinimumWidth(wutil.DPI(self.MIN_WIDTH))
        self.bg_frame.setMaximumWidth(wutil.DPI(self.MAX_WIDTH))
        self.bg_layout = QtWidgets.QVBoxLayout(self.bg_frame)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_layout.setSpacing(0)
        self.main_layout.addWidget(self.bg_frame)

        self._build_content()

    def _build_content(self):
        self.has_header = False
        header_title = getattr(self.tooltip, "title", "") or self.text
        header_pixmap = self.icon_obj if self.icon_obj and not self.icon_obj.isNull() else None
        body_items = tuple(getattr(self.tooltip, "body_lines", ()) or ())
        if not body_items and self.description:
            body_items = tooltip_body(self.description)
        has_body = bool(body_items)
        header_only = bool(header_title or header_pixmap) and not has_body and not self.shortcuts

        if not header_pixmap:
            if self.icon and isinstance(self.icon, (str, bytes)):
                header_pixmap = QtGui.QIcon(self.icon)

        if header_title or header_pixmap:
            header_frame, header_layout = self._create_section_frame(
                self.HEADER_COLOR,
                rounded_top=True,
                rounded_bottom=header_only,
            )
            if header_pixmap:
                lbl = self._create_icon_label(header_pixmap, dim=22.5)
                header_layout.addWidget(lbl)
            if header_title:
                title_lbl = self._create_text_label(header_title, size=18, bold=True, elide=True)
                header_layout.addWidget(title_lbl)

            header_layout.addStretch()
            self._add_header_action_buttons(header_layout, header_title)
            self.bg_layout.addWidget(header_frame)
            self.has_header = True

        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setSpacing(wutil.DPI(6))
        top_margin = wutil.DPI(12)
        content_layout.setContentsMargins(wutil.DPI(12), top_margin, wutil.DPI(12), wutil.DPI(8))
        self.content_layout = content_layout

        if has_body:
            self._populate_body_content(content_layout, body_items)
            self.bg_layout.addLayout(content_layout)
            if self.shortcuts:
                self.bg_layout.addSpacing(wutil.DPI(14))
            else:
                self.bg_layout.addSpacing(wutil.DPI(18))

        if self.shortcuts:
            self._build_shortcuts_section()

    def _create_section_frame(self, color, rounded_top=False, rounded_bottom=False):
        frame = QtWidgets.QFrame()
        if rounded_top or rounded_bottom:
            frame.setObjectName("TooltipHeaderFrame")
            frame.setStyleSheet(
                (
                    "QFrame#TooltipHeaderFrame {{ background-color: {}; "
                    "border-top-left-radius: {}px; border-top-right-radius: {}px; "
                    "border-bottom-left-radius: {}px; border-bottom-right-radius: {}px; }}"
                ).format(
                    color,
                    wutil.DPI(self.BORDER_RADIUS) if rounded_top else 0,
                    wutil.DPI(self.BORDER_RADIUS) if rounded_top else 0,
                    wutil.DPI(self.BORDER_RADIUS) if rounded_bottom else 0,
                    wutil.DPI(self.BORDER_RADIUS) if rounded_bottom else 0,
                )
            )
        else:
            frame.setObjectName("TooltipSectionFrame")
            frame.setStyleSheet("QFrame#TooltipSectionFrame {{ background-color: {}; }}".format(color))
        layout = QtWidgets.QHBoxLayout(frame)
        if rounded_top:
            layout.setContentsMargins(wutil.DPI(10), wutil.DPI(8), wutil.DPI(8), wutil.DPI(8))
            layout.setSpacing(wutil.DPI(6))
        else:
            layout.setContentsMargins(wutil.DPI(12), wutil.DPI(12), wutil.DPI(12), wutil.DPI(12))
            layout.setSpacing(wutil.DPI(8))
        return frame, layout

    def _add_header_action_buttons(self, layout, header_title):
        if not self.command_id:
            return
        actions = QtWidgets.QWidget(self)
        actions.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        actions_layout = QtWidgets.QVBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(wutil.DPI(1))

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(wutil.DPI(2))
        if self.command_id:
            buttons_layout.addWidget(self._create_header_button(icons.hotkeys, "Edit hotkey", self._open_hotkey_editor))
        buttons_layout.addWidget(self._create_header_button(icons.add_to_shelf, "Add to shelf", lambda: self._add_to_shelf(header_title)))
        actions_layout.addLayout(buttons_layout)

        shortcut_text = self._command_shortcut_text()
        if shortcut_text:
            command_lbl = self._create_command_shortcut_label(shortcut_text, buttons_layout.sizeHint().width())
            actions_layout.addWidget(command_lbl)

        layout.addWidget(actions, 0, QtCore.Qt.AlignVCenter)

    def _command_shortcut_text(self):
        if not self.command_id:
            return ""
        try:
            from TheKeyMachine.mods import hotkeysMod

            return hotkeysMod.shortcut_for_command(self.command_id) or ""
        except Exception:
            return ""

    def _create_command_shortcut_label(self, shortcut_text, width):
        label = QtWidgets.QLabel(shortcut_text)
        label.setObjectName("TooltipCommandShortcutLabel")
        label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        label.setContentsMargins(0, 0, wutil.DPI(3), 0)
        label.setWordWrap(False)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        label.setToolTip(self.command_id or "")
        font = label.font()
        font.setPixelSize(wutil.DPI(9.5))
        label.setFont(font)
        label.setStyleSheet(
            "#TooltipCommandShortcutLabel { color: #8c8c8c; background: transparent; padding: 0px; margin: 0px; }"
        )
        metrics = QtGui.QFontMetrics(label.font())
        available_width = max(1, int(width or label.sizeHint().width()))
        label.setFixedWidth(available_width)
        label.setText(metrics.elidedText(shortcut_text, QtCore.Qt.ElideMiddle, available_width))
        return label

    def _create_header_button(self, icon_path, tooltip, callback):
        btn = QtWidgets.QToolButton(self)
        btn.setObjectName("TooltipHeaderButton")
        btn.setAutoRaise(True)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setIconSize(QtCore.QSize(wutil.DPI(22), wutil.DPI(22)))
        btn.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        btn.setStyleSheet(
            "QToolButton#TooltipHeaderButton { background-color: transparent; border: none; border-radius: 0px; padding: 0px; }"
            "QToolButton#TooltipHeaderButton:pressed { background-color: #1f1f1f; border: none; border-radius: 0px; }"
        )
        btn.clicked.connect(lambda _checked=False: callback())
        return btn

    def _open_hotkey_editor(self):
        if not self.command_id:
            return
        command_id = self.command_id
        QFlatTooltipManager.hide()
        try:
            from TheKeyMachine.mods import hotkeysMod

            hotkeysMod.show_hotkeys_window_for_command(command_id)
        except Exception:
            pass

    def _add_to_shelf(self, header_title):
        if not self.command_id:
            return
        command_id = self.command_id
        command_label = self.command_label or header_title
        command_icon = self.command_icon or self.icon
        QFlatTooltipManager.hide()
        try:
            from TheKeyMachine.mods import shelfMod

            shelfMod.create_tool_shelf_button(command_id, command_label, icon=command_icon)
        except Exception:
            pass

    def _build_shortcuts_section(self):
        frame, layout = self._create_section_frame(self.HEADER_COLOR)
        layout.setContentsMargins(0, wutil.DPI(4), 0, wutil.DPI(4))

        title_lbl = self._create_text_label("Shortcuts", size=16, bold=True, elide=True, align=QtCore.Qt.AlignCenter)
        title_lbl.setMinimumHeight(wutil.DPI(20))
        layout.addWidget(title_lbl)

        self.bg_layout.addSpacing(0)
        self.bg_layout.addWidget(frame)
        self.bg_layout.addSpacing(wutil.DPI(12))

        max_row_width = 0
        shortcut_font = self.font()
        shortcut_font.setPixelSize(wutil.DPI(10.5))
        shortcut_metrics = QtGui.QFontMetrics(shortcut_font)
        shortcut_icon_dim = 11.25

        for sh in self.shortcuts:
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(wutil.DPI(12), 0, wutil.DPI(12), 0)
            row.setSpacing(wutil.DPI(20))

            icon = sh.get("icon", "default")
            row.addWidget(self._create_icon_label(icon, dim=shortcut_icon_dim))

            label_text = sh.get("label", "")
            name = QtWidgets.QLabel(label_text)
            name.setWordWrap(False)
            name.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
            name.setMinimumWidth(shortcut_metrics.horizontalAdvance(label_text))
            name.setStyleSheet("color: {}; font-size: {}px;".format(self.TEXT_COLOR, wutil.DPI(10.5)))
            row.addWidget(name)
            row.addStretch()

            command = sh.get("keys", "")
            if isinstance(command, list):
                command = format_tooltip_shortcut(command, include_click_suffix=True)
            keys = QtWidgets.QLabel(command)
            keys.setWordWrap(False)
            keys.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
            keys.setMinimumWidth(shortcut_metrics.horizontalAdvance(command))
            keys.setStyleSheet("color: {}; font-size: {}px;".format(self.TEXT_COLOR, wutil.DPI(10.5)))
            row.addWidget(keys)
            self.bg_layout.addLayout(row)
            self.bg_layout.addSpacing(wutil.DPI(4))

            row_width = (
                wutil.DPI(shortcut_icon_dim)
                + wutil.DPI(20)
                + shortcut_metrics.horizontalAdvance(label_text)
                + wutil.DPI(20)
                + shortcut_metrics.horizontalAdvance(command)
                + wutil.DPI(shortcut_icon_dim)
            )
            max_row_width = max(max_row_width, row_width)

        self.bg_layout.addSpacing(wutil.DPI(18))
        if max_row_width:
            self._shortcut_min_width = min(max_row_width, wutil.DPI(460))
            self.bg_frame.setMinimumWidth(max(self.bg_frame.minimumWidth(), self._shortcut_min_width))
            self.bg_frame.setMaximumWidth(max(wutil.DPI(self.MAX_WIDTH), self._shortcut_min_width))

    def _create_icon_label(self, source, dim=32):
        lbl = QtWidgets.QLabel()
        target_size = self._icon_target_size(dim)
        if hasattr(source, "pixmap"):
            pix = source.pixmap(target_size)
        elif isinstance(source, (str, bytes)):
            icon = source.decode() if isinstance(source, bytes) else source
            pix = self._load_icon_pixmap(icon, target_size)
        elif isinstance(source, QtGui.QPixmap):
            pix = source.scaled(target_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        else:
            pix = QtGui.QPixmap()

        if not pix.isNull():
            lbl.setPixmap(pix)
        return lbl

    def _icon_target_size(self, dim):
        px_dim = max(1, int(wutil.DPI(dim * 2)))
        return QtCore.QSize(px_dim, px_dim)

    def _load_icon_pixmap(self, path, target_size):
        if not path:
            return QtGui.QPixmap()

        if path.lower().endswith(".svg") and QSvgRenderer:
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                pixmap = QtGui.QPixmap(target_size)
                pixmap.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap

        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            return pixmap
        return pixmap.scaled(target_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    def _create_text_label(self, text, size=11, bold=False, elide=False, align=None):
        lbl = QtWidgets.QLabel(text)
        lbl.setObjectName("text_label")
        lbl.setToolTip(text)
        lbl.setWordWrap(True)

        style = "#text_label {{ color: {0}; font-size: {1}px; {2}}}".format(
            self.TEXT_COLOR, wutil.DPI(size), "font-weight: bold;" if bold else ""
        )
        lbl.setStyleSheet(style)
        if align:
            lbl.setAlignment(align)

        if elide and " " not in text:
            f = lbl.font()
            f.setPixelSize(wutil.DPI(size))
            f.setBold(bold)
            fm = QtGui.QFontMetrics(f)
            limit = wutil.DPI(self.MAX_WIDTH - 80)
            if fm.horizontalAdvance(text) > limit:
                lbl.setText(fm.elidedText(text, QtCore.Qt.ElideLeft, limit))
                lbl.setWordWrap(False)
        return lbl

    def _body_max_width(self):
        margins = self.content_layout.contentsMargins() if hasattr(self, "content_layout") else self.bg_layout.contentsMargins()
        return max(1, self.bg_frame.maximumWidth() - margins.left() - margins.right())

    def _contain_size(self, max_width, size):
        if not size.isValid() or size.width() <= 0:
            return None

        if size.width() <= max_width:
            return size

        scale = float(max_width) / float(size.width())
        return QtCore.QSize(max_width, max(1, int(size.height() * scale)))

    def _create_media_label(self, path):
        max_media_width = self._body_max_width()

        if path.lower().endswith(".gif"):
            lbl = TooltipMovieWidget()
            lbl.setMaximumWidth(max_media_width)
            movie = QtGui.QMovie(path)
            movie.setCacheMode(QtGui.QMovie.CacheAll)
            movie.jumpToFrame(0)
            frame_size = movie.currentImage().size()
            if not frame_size.isValid():
                frame_size = movie.frameRect().size()
            contained_size = self._contain_size(max_media_width, frame_size)
            movie.finished.connect(movie.start)
            lbl.set_tooltip_movie(movie, display_size=contained_size)
            movie.start()
            lbl._movie = movie
        else:
            lbl = QtWidgets.QLabel()
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setMaximumWidth(max_media_width)
            pix = QtGui.QPixmap(path)
            if not pix.isNull():
                contained_size = self._contain_size(max_media_width, pix.size())
                if contained_size is not None and pix.size() != contained_size:
                    pix = pix.scaled(contained_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                lbl.setPixmap(pix)
        return lbl

    def _create_body_text_label(self, text):
        raw_lbl = QtWidgets.QLabel(text)
        raw_lbl.setWordWrap(True)
        raw_lbl.setOpenExternalLinks(False)
        raw_lbl.setTextFormat(QtCore.Qt.PlainText)
        raw_lbl.setMaximumWidth(self._body_max_width())
        raw_lbl.setStyleSheet(
            "color: {}; background: transparent; font-size: {}px; margin: 0; padding: 0;".format(self.TEXT_COLOR, wutil.DPI(10.5))
        )
        return raw_lbl

    def _create_separator(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Plain)
        line.setStyleSheet("background-color: #4a4a4a; color: #4a4a4a; border: none; min-height: 1px; max-height: 1px; margin: 0; padding: 0;")
        return line

    def _populate_body_content(self, layout, body_items):
        for item in body_items:
            if item is separator:
                layout.addSpacing(wutil.DPI(6))
                layout.addWidget(self._create_separator())
                continue

            if isinstance(item, TooltipMedia):
                layout.addWidget(self._create_media_label(item.path))
                continue

            layout.addWidget(self._create_body_text_label(str(item)))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)

        side = getattr(self, "side", "bottom")
        painter.setBrush(QtGui.QColor(self.BG_COLOR))

        aw = wutil.DPI(self.ARROW_W)
        ah = wutil.DPI(self.ARROW_H)
        ax = getattr(self, "arrow_x", self.width() / 2)

        if side == "top":
            poly = QtGui.QPolygonF([QtCore.QPointF(ax, 0), QtCore.QPointF(ax - aw / 2, ah + 1), QtCore.QPointF(ax + aw / 2, ah + 1)])
            painter.drawPolygon(poly)
        else:
            poly = QtGui.QPolygonF(
                [QtCore.QPointF(ax, self.height()), QtCore.QPointF(ax - aw / 2, self.height() - ah - 1), QtCore.QPointF(ax + aw / 2, self.height() - ah - 1)]
            )
            painter.drawPolygon(poly)

    def show_around(self, widget, action_rect=None, target_rect=None, target_pos=None):
        self.action_rect = action_rect
        self.target_rect = target_rect
        self.anchor_widget = widget

        ah = wutil.DPI(self.ARROW_H)

        if target_rect:
            self._global_anc = target_rect
            cursor_pos = target_pos or QtGui.QCursor.pos()
        elif action_rect:
            try:
                self._global_anc = QtCore.QRect(widget.mapToGlobal(action_rect.topLeft()), action_rect.size())
            except RuntimeError:
                return
            self.target_rect = self._global_anc
            cursor_pos = target_pos or QtGui.QCursor.pos()
        else:
            try:
                target_global = widget.mapToGlobal(QtCore.QPoint(0, 0))
            except RuntimeError:
                return
            self._global_anc = QtCore.QRect(target_global, widget.size())
            self.target_rect = self._global_anc
            cursor_pos = target_pos or QtGui.QCursor.pos()

        # Calculate target_x based on cursor position, clamped to the anchor's horizontal bounds.
        # This makes the tooltip (and arrow) "grow" from exactly where the user is hovering.
        tx = cursor_pos.x()
        if tx < self._global_anc.left():
            tx = self._global_anc.left()
        elif tx > self._global_anc.right():
            tx = self._global_anc.right()
        target_x = tx

        # Default to placing tooltip ON TOP (above) the widget (arrow on bottom)
        self.side = "bottom"
        self.main_layout.setContentsMargins(0, 0, 0, ah)
        self.main_layout.activate()
        self.adjustSize()
        w, h = self.width(), self.height()

        gap = wutil.DPI(2)
        edge_padding = wutil.DPI(5)
        pos = QtCore.QPoint(target_x - w // 2, self._global_anc.top() - h - gap)

        screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        available_top = self._global_anc.top() - geo.top() - gap
        available_bottom = geo.bottom() - self._global_anc.bottom() - gap

        if pos.y() < geo.top() + edge_padding and available_bottom > available_top:
            # If the tooltip does not fit above, only flip below when there is more room there.
            self.side = "top"
            self.main_layout.setContentsMargins(0, ah, 0, 0)
            self.main_layout.activate()
            self.adjustSize()
            w, h = self.width(), self.height()
            pos.setY(self._global_anc.bottom() + 1 + gap)

        final_x = max(geo.left() + edge_padding, min(pos.x(), geo.right() - w - edge_padding))
        pos.setX(final_x)
        self.move(pos)

        arrow_x = target_x - final_x
        aw = wutil.DPI(self.ARROW_W)
        self.arrow_x = max(wutil.DPI(6) + aw / 2, min(arrow_x, w - wutil.DPI(6) - aw / 2))
        self.update()

        self._auto_close_timer.start()
        self.show()


class _TooltipMouseFilter(QtCore.QObject):
    def __init__(self, manager):
        QtCore.QObject.__init__(self)
        self.manager = manager
        self._pressed_button = None

    def eventFilter(self, obj, event):
        event_type = event.type()
        unavailable_events = (QtCore.QEvent.Hide, QtCore.QEvent.Close, QtCore.QEvent.Destroy)
        if event_type == QtCore.QEvent.ApplicationDeactivate or event_type in unavailable_events:
            if event_type == QtCore.QEvent.ApplicationDeactivate:
                self.manager.hide()
            else:
                self.manager.source_left(anchor_widget=obj, anchor_unavailable=True)
            return False

        if event_type in (QtCore.QEvent.MouseMove, QtCore.QEvent.HoverMove, QtCore.QEvent.Leave):
            self.manager.validate_pointer()

        tooltip = self.manager._current_tooltip
        if not tooltip or not tooltip.isVisible():
            self._pressed_button = None
            return False

        if event_type not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.MouseButtonDblClick):
            return False

        global_pos = self._event_global_pos(event)
        if global_pos is None or not tooltip.frameGeometry().contains(global_pos):
            self._pressed_button = None
            return False

        button = self._tooltip_button_at(tooltip, global_pos)
        if event_type == QtCore.QEvent.MouseButtonPress:
            self._pressed_button = button
            if button:
                button.setDown(True)
            return True

        if event_type == QtCore.QEvent.MouseButtonRelease:
            pressed_button = self._pressed_button
            self._pressed_button = None
            if pressed_button:
                pressed_button.setDown(False)
                if pressed_button is button and pressed_button.isEnabled():
                    pressed_button.click()
            return True

        return True

    @staticmethod
    def _event_global_pos(event):
        if hasattr(event, "globalPos"):
            return event.globalPos()
        if hasattr(event, "globalPosition"):
            pos = event.globalPosition()
            return QtCore.QPoint(int(pos.x()), int(pos.y()))
        return None

    @staticmethod
    def _tooltip_button_at(tooltip, global_pos):
        widget = tooltip.childAt(tooltip.mapFromGlobal(global_pos))
        while widget and widget is not tooltip:
            if isinstance(widget, QtWidgets.QToolButton):
                return widget
            widget = widget.parentWidget()
        return None


class QFlatTooltipManager(object):
    """Manages global state for QFlatTooltips ensuring only one exists at a time."""

    _current_tooltip = None
    _timer = None
    _mouse_filter = None
    _current_source_key = None
    _pending_source_key = None
    _pending_request = None
    _request_serial = 0
    # Initialize from persistence here so every tooltip-enabled surface starts
    # with the same state, even when the main toolbar/settings button is absent.
    enabled = bool(settings.get_setting("show_tooltips", True))

    @classmethod
    def is_active(cls):
        return (cls._current_tooltip and cls._current_tooltip.isVisible()) or (cls._timer and cls._timer.isActive())

    @classmethod
    def is_current_source(cls, source_key):
        if source_key is None:
            return False
        if cls._current_tooltip and cls._current_tooltip.isVisible() and cls._current_source_key == source_key:
            return True
        if cls._timer and cls._timer.isActive() and cls._pending_source_key == source_key:
            return True
        return False

    @classmethod
    def _clear_pending(cls):
        cls._pending_source_key = None
        cls._pending_request = None

    @classmethod
    def _ensure_mouse_filter(cls):
        app = QtWidgets.QApplication.instance()
        if not app:
            return
        if cls._mouse_filter is None:
            cls._mouse_filter = _TooltipMouseFilter(cls)
            app.installEventFilter(cls._mouse_filter)

    @classmethod
    def cancel_timer(cls):
        cls._request_serial += 1
        if cls._timer:
            cls._timer.stop()
        cls._clear_pending()

    @classmethod
    def _global_widget_rect(cls, widget):
        if widget is None or not wutil.is_valid_widget(widget) or not widget.isVisible():
            return None
        try:
            rect = widget.rect()
            rect.moveTo(widget.mapToGlobal(QtCore.QPoint(0, 0)))
            return rect
        except (RuntimeError, ValueError, TypeError, AttributeError):
            return None

    @classmethod
    def _request_contains_cursor(cls, request):
        if not request:
            return False
        cursor_pos = QtGui.QCursor.pos()
        target_rect = request.get("target_rect")
        if callable(target_rect):
            try:
                target_rect = target_rect()
            except Exception:
                target_rect = None
        if target_rect is not None:
            try:
                return bool(target_rect.contains(cursor_pos))
            except (RuntimeError, ValueError, TypeError, AttributeError):
                return False
        anchor_rect = cls._global_widget_rect(request.get("anchor_widget"))
        return bool(anchor_rect and anchor_rect.contains(cursor_pos))

    @classmethod
    def validate_pointer(cls):
        if cls._timer and cls._timer.isActive() and not cls._request_contains_cursor(cls._pending_request):
            cls.cancel_timer()
        tooltip = cls._current_tooltip
        if tooltip and tooltip.isVisible():
            check_auto_close = getattr(tooltip, "_check_auto_close", None)
            if callable(check_auto_close):
                QtCore.QTimer.singleShot(0, check_auto_close)
            else:
                cls._current_tooltip = None
                cls._current_source_key = None

    @classmethod
    def source_left(cls, source_key=None, anchor_widget=None, anchor_unavailable=False):
        pending = cls._pending_request or {}
        pending_matches = (
            (source_key is not None and cls._pending_source_key == source_key)
            or (anchor_widget is not None and pending.get("anchor_widget") is anchor_widget)
        )
        if pending_matches:
            cls.cancel_timer()

        tooltip = cls._current_tooltip
        current_matches = bool(
            tooltip
            and (
                (source_key is not None and cls._current_source_key == source_key)
                or (
                    anchor_widget is not None
                    and getattr(tooltip, "anchor_widget", None) is anchor_widget
                )
            )
        )
        if not current_matches:
            return
        if anchor_unavailable:
            cls.hide()
            return
        check_auto_close = getattr(tooltip, "_check_auto_close", None)
        if callable(check_auto_close):
            QtCore.QTimer.singleShot(0, check_auto_close)
        else:
            cls._current_tooltip = None
            cls._current_source_key = None

    @classmethod
    def hide(cls):
        cls.cancel_timer()
        if cls._current_tooltip:
            try:
                cls._current_tooltip.close()
            except Exception:
                pass
            cls._current_tooltip = None
        cls._current_source_key = None

    @classmethod
    def show(
        cls,
        text="",
        anchor_widget=None,
        icon=None,
        shortcuts=None,
        description=None,
        tooltip=None,
        action_rect=None,
        icon_obj=None,
        target_rect=None,
        target_pos=None,
        source_key=None,
        command_id=None,
        command_label=None,
        command_icon=None,
        **kwargs,
    ):
        if not cls.enabled:
            return
        if cls._timer:
            cls._timer.stop()
            cls._clear_pending()
        if anchor_widget is not None and not wutil.is_valid_widget(anchor_widget):
            return

        cls._ensure_mouse_filter()

        if not icon and command_icon:
            icon = command_icon
        if icon and not isinstance(icon, (str, bytes)):
            icon_obj = icon
            icon = None

        if callable(target_pos):
            target_pos = target_pos()

        cls.hide()
        cls._current_source_key = source_key
        cls._current_tooltip = QFlatTooltip(
            text=text,
            anchor_widget=anchor_widget,
            icon=icon,
            shortcuts=shortcuts,
            description=description,
            tooltip=tooltip,
            icon_obj=icon_obj,
            command_id=command_id,
            command_label=command_label,
            command_icon=command_icon,
            from_menu=isinstance(anchor_widget, QtWidgets.QMenu),
        )
        cls._current_tooltip.show_around(anchor_widget, action_rect, target_rect=target_rect, target_pos=target_pos)

    @classmethod
    def delayed_show(cls, delay=1200, **kwargs):
        if not cls.enabled:
            return
        cls._ensure_mouse_filter()
        source_key = kwargs.get("source_key")
        if cls.is_current_source(source_key):
            return
        cls.cancel_timer()

        if not cls._timer:
            cls._timer = QtCore.QTimer()
            cls._timer.setSingleShot(True)

        anchor = kwargs.get("anchor_widget")
        cls._pending_source_key = source_key
        cls._pending_request = dict(kwargs)
        request_serial = cls._request_serial

        def _safe_show():
            if request_serial != cls._request_serial:
                return
            if anchor is not None and not wutil.is_valid_widget(anchor):
                cls._clear_pending()
                return
            if not cls._request_contains_cursor(kwargs):
                cls._clear_pending()
                return
            cls.show(**kwargs)

        toolCommon.replace_tracked_connection(
            cls,
            "_timer_connection",
            cls._timer.timeout,
            _safe_show,
            parent=cls._timer,
        )
        cls._timer.setInterval(delay)
        cls._timer.start()


def parse_tt(tooltip):
    if not tooltip:
        return "", ""
    normalized = _tooltip_from_data(tooltip)
    header = toolCommon.clean_tool_text(getattr(normalized, "title", ""))
    description = toolCommon.clean_tool_text(getattr(normalized, "first_line", ""))
    return header, description
