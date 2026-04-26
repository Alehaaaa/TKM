import sys
from TheKeyMachine.tools import common as toolCommon

try:
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QFrame,
        QMenu,
        QApplication,
        QSizePolicy,
    )
    from PySide6.QtGui import (  # type: ignore
        QColor,
        QPixmap,
        QPainter,
        QPainterPath,
        QRegion,
        QPolygonF,
        QCursor,
        QGuiApplication,
        QMovie,
        QFontMetrics,
        QIcon,
    )
    from PySide6.QtCore import (  # type: ignore
        Qt,
        QSize,
        QPoint,
        QPointF,
        QTimer,
        QRect,
        QRectF,
    )
    try:
        from PySide6.QtSvg import QSvgRenderer  # type: ignore
    except ImportError:
        QSvgRenderer = None  # type: ignore
except ImportError:
    from PySide2.QtWidgets import (  # type: ignore
        QWidget,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QFrame,
        QMenu,
        QApplication,
        QSizePolicy,
    )
    from PySide2.QtGui import (  # type: ignore
        QColor,
        QPixmap,
        QPainter,
        QPainterPath,
        QRegion,
        QPolygonF,
        QCursor,
        QGuiApplication,
        QMovie,
        QFontMetrics,
        QIcon,
    )
    from PySide2.QtCore import (  # type: ignore
        Qt,
        QSize,
        QPoint,
        QPointF,
        QTimer,
        QRect,
        QRectF,
    )
    try:
        from PySide2.QtSvg import QSvgRenderer  # type: ignore
    except ImportError:
        QSvgRenderer = None  # type: ignore

from TheKeyMachine.widgets import util as wutil


IS_MAC = sys.platform == "darwin"
SHORTCUT_KEY_MAP = {
    Qt.Key_Alt: "⌥" if IS_MAC else "Alt",
    Qt.Key_Shift: "⇧" if IS_MAC else "Shift",
    Qt.Key_Control: "⌘" if IS_MAC else "Ctrl",
    Qt.MiddleButton: "Click" if IS_MAC else "MidClick",
}
SHORTCUT_KEY_ORDER = [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.MiddleButton]


class TooltipTemplate(str):
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


class TooltipMedia:
    def __init__(self, path):
        self.path = str(path)


class _TooltipSeparator:
    pass


separator = _TooltipSeparator()


def tooltip_media(path):
    return TooltipMedia(path)


def tooltip_body(*paragraphs):
    lines = []
    for paragraph in paragraphs:
        if paragraph is separator:
            lines.append(paragraph)
            continue
        if isinstance(paragraph, TooltipMedia):
            lines.append(paragraph)
            continue
        if paragraph and str(paragraph).strip():
            lines.append(str(paragraph).strip())
    return tuple(lines)


def _tooltip_template_from_data(raw, fallback_title="", fallback_description="", fallback_icon=None):
    if isinstance(raw, TooltipTemplate):
        return raw

    if isinstance(raw, (list, tuple)):
        title = raw[0] if len(raw) > 0 else fallback_title
        body = raw[1] if len(raw) > 1 else fallback_description
        icon = raw[2] if len(raw) > 2 else fallback_icon
        return tool_tooltip(title, body, icon=icon)

    if raw:
        title = toolCommon.clean_tool_text(fallback_title or raw)
        lines = list(_string_body_lines(raw))
        if title and lines and lines[0].lower() == title.lower():
            lines = lines[1:]
        return TooltipTemplate(str(raw), title=title, body_lines=lines, icon=fallback_icon)

    if fallback_title or fallback_description or fallback_icon:
        return tool_tooltip(fallback_title, fallback_description, icon=fallback_icon)

    return TooltipTemplate("", title="", body_lines=(), icon=None)


def tool_tooltip(title, body, icon=None):
    body_lines = tooltip_body(*(body if isinstance(body, (list, tuple)) else [body]))
    text_lines = [toolCommon.clean_tool_text(title)] if title else []
    for item in body_lines:
        if item is separator:
            text_lines.append("---")
        elif isinstance(item, TooltipMedia):
            text_lines.append(item.path)
        else:
            text_lines.append(str(item))
    return TooltipTemplate("\n\n".join(line for line in text_lines if line), title=title, body_lines=body_lines, icon=icon)


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


class TooltipMovieLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._movie = None
        self._display_size = None
        self.setAlignment(Qt.AlignCenter)

    def set_tooltip_movie(self, movie, display_size=None):
        self._movie = movie
        self._display_size = display_size if display_size and display_size.isValid() else None
        if self._display_size is not None:
            self.setFixedSize(self._display_size)
        elif movie is not None:
            frame_rect = movie.frameRect()
            if frame_rect.isValid():
                self.setFixedSize(frame_rect.size())
        if movie is not None:
            movie.frameChanged.connect(self._update_frame)
            self._update_frame()

    def _update_frame(self, *_):
        if self._movie is None:
            return
        frame = self._movie.currentPixmap()
        if frame.isNull():
            return
        if self._display_size is not None and frame.size() != self._display_size:
            frame = frame.scaled(self._display_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(frame)


class TooltipMovieWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._movie = None
        self._display_size = None
        self._corner_radius = wutil.DPI(10)

        self._movie_label = TooltipMovieLabel(self)
        self._progress_track = QFrame(self._movie_label)
        self._progress_fill = QFrame(self._progress_track)

        self.setObjectName("tooltip_movie_widget")
        self.setStyleSheet(
            "#tooltip_movie_widget { background: transparent; border: none; border-radius: %dpx; }" % self._corner_radius
        )
        self._movie_label.setStyleSheet("background: transparent; border: none;")
        self._progress_track.setStyleSheet("background: transparent; border: none;")
        self._progress_fill.setStyleSheet("background-color: rgba(192, 192, 192, 0.5); border: none;")
        self._progress_track.setFixedHeight(wutil.DPI(2))
        self._progress_fill.setFixedHeight(wutil.DPI(2))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._movie_label)

    def set_tooltip_movie(self, movie, display_size=None):
        self._movie = movie
        self._display_size = display_size if display_size and display_size.isValid() else None
        self._movie_label.set_tooltip_movie(movie, display_size=display_size)
        if self._display_size is not None:
            self.setFixedWidth(self._display_size.width())
        else:
            self.setMinimumWidth(self._movie_label.width())
        if movie is not None:
            movie.frameChanged.connect(self._update_progress)
            self._update_progress()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_rounded_mask()
        self._layout_overlay()
        self._update_progress()

    def _apply_rounded_mask(self):
        rect = self.rect()
        if not rect.isValid():
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), self._corner_radius, self._corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
        self._movie_label.setMask(region.translated(-self._movie_label.x(), -self._movie_label.y()))

    def _layout_overlay(self):
        track_height = self._progress_track.height()
        self._progress_track.setGeometry(
            0,
            max(0, self._movie_label.height() - track_height),
            self._movie_label.width(),
            track_height,
        )
        self._progress_track.raise_()
        self._progress_fill.raise_()

    def _update_progress(self, *_):
        if self._movie is None:
            self._progress_fill.setFixedWidth(0)
            return

        track_width = max(0, self._progress_track.width())
        if track_width <= 0:
            self._progress_fill.setFixedWidth(0)
            return

        frame_count = self._movie.frameCount()
        current_frame = self._movie.currentFrameNumber()
        if frame_count and frame_count > 1 and current_frame >= 0:
            progress = float(current_frame) / float(frame_count - 1)
        else:
            progress = 0.0
        fill_width = max(0, min(track_width, int(round(track_width * progress))))
        self._progress_fill.setGeometry(0, 0, fill_width, self._progress_track.height())


class QFlatTooltip(QWidget):
    """A floating tooltip with an arrow pointing to its source."""

    BG_COLOR = "#333333"
    HEADER_COLOR = "#282828"
    TEXT_COLOR = "#bbbbbb"
    ARROW_W = 12
    ARROW_H = 8
    BORDER_RADIUS = 8

    MAX_WIDTH = 320
    MIN_WIDTH = 220

    def __init__(self, text="", anchor_widget=None, icon=None, shortcuts=None, description=None, tooltip_template=None, icon_obj=None):
        QWidget.__init__(self, wutil.get_maya_qt())
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.anchor_widget = anchor_widget
        self.shortcuts = shortcuts or []
        self.icon_obj = icon_obj
        self.text = text
        self.description = description
        self.icon_path = icon  # Store for reference
        self._shortcut_min_width = 0

        self.tooltip_template = _tooltip_template_from_data(
            tooltip_template,
            fallback_title=text.strip() if text else "",
            fallback_description=description.strip() if isinstance(description, str) else description,
            fallback_icon=icon,
        )

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setInterval(200)
        self._auto_close_timer.timeout.connect(self._check_auto_close)

        self._setup_ui()

    def _check_auto_close(self):
        """Strictly manages tooltip visibility based on cursor location."""
        if not self.isVisible():
            self._auto_close_timer.stop()
            return

        cursor_pos = QCursor.pos()
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
            anc_geo.moveTo(self.anchor_widget.mapToGlobal(QPoint(0, 0)))
        else:
            self.close()
            return

        if anc_geo.contains(cursor_pos):
            return

        if isinstance(self.anchor_widget, QMenu):
            active_popup = QApplication.activePopupWidget()
            if active_popup and active_popup.geometry().contains(cursor_pos):
                return

        bridge_l = max(anc_geo.left(), tt_geo.left())
        bridge_r = min(anc_geo.right(), tt_geo.right())

        if side == "top":
            bridge_top, bridge_bot = anc_geo.bottom() - 1, tt_geo.top() + 1
        else:
            bridge_top, bridge_bot = tt_geo.bottom() - 1, anc_geo.top() + 1

        bridge = QRect(bridge_l, bridge_top, bridge_r - bridge_l, bridge_bot - bridge_top)
        if bridge.contains(cursor_pos):
            return

        self.close()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.main_layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self.setStyleSheet(
            "QFlatTooltip > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(
                self.BG_COLOR, wutil.DPI(self.BORDER_RADIUS)
            )
        )

        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("BgFrame")
        self.bg_frame.setMinimumWidth(wutil.DPI(self.MIN_WIDTH))
        self.bg_frame.setMaximumWidth(wutil.DPI(self.MAX_WIDTH))
        self.bg_layout = QVBoxLayout(self.bg_frame)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_layout.setSpacing(0)
        self.main_layout.addWidget(self.bg_frame)

        self._build_content()

    def _build_content(self):
        self.has_header = False
        header_title = getattr(self.tooltip_template, "title", "") or self.text
        header_pixmap = self.icon_obj if self.icon_obj and not self.icon_obj.isNull() else None

        if not header_pixmap:
            template_icon = getattr(self.tooltip_template, "icon", None)
            if template_icon:
                header_pixmap = QIcon(template_icon)
            elif self.icon_path and isinstance(self.icon_path, (str, bytes)):
                header_pixmap = QIcon(self.icon_path)

        if header_title or header_pixmap:
            header_frame, header_layout = self._create_section_frame("")
            if header_pixmap:
                lbl = self._create_icon_label(header_pixmap, dim=22.5)
                header_layout.addWidget(lbl)
            if header_title:
                title_lbl = self._create_text_label(header_title, size=18, bold=True, elide=True)
                header_layout.addWidget(title_lbl)

            header_layout.addStretch()
            self.bg_layout.addWidget(header_frame)
            self.has_header = True

        content_layout = QVBoxLayout()
        content_layout.setSpacing(wutil.DPI(6))
        top_margin = wutil.DPI(0) if self.has_header else wutil.DPI(12)
        content_layout.setContentsMargins(wutil.DPI(12), top_margin, wutil.DPI(12), wutil.DPI(8))
        self.content_layout = content_layout

        body_items = tuple(getattr(self.tooltip_template, "body_lines", ()) or ())
        if not body_items and self.description:
            body_items = tooltip_body(self.description)

        if body_items:
            self._populate_body_content(content_layout, body_items)
            self.bg_layout.addLayout(content_layout)
            if self.shortcuts:
                self.bg_layout.addSpacing(wutil.DPI(14))
            else:
                self.bg_layout.addSpacing(wutil.DPI(18))

        if self.shortcuts:
            self._build_shortcuts_section()

    def _create_section_frame(self, color):
        frame = QFrame()
        frame.setStyleSheet("background-color: {};".format(color))
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(wutil.DPI(12), wutil.DPI(12), wutil.DPI(12), wutil.DPI(12))
        layout.setSpacing(wutil.DPI(8))
        return frame, layout

    def _build_shortcuts_section(self):
        frame, layout = self._create_section_frame(self.HEADER_COLOR)
        layout.setContentsMargins(0, wutil.DPI(4), 0, wutil.DPI(4))

        title_lbl = self._create_text_label("Shortcuts", size=16, bold=True, elide=True, align=Qt.AlignCenter)
        title_lbl.setMinimumHeight(wutil.DPI(20))
        layout.addWidget(title_lbl)

        self.bg_layout.addSpacing(0)
        self.bg_layout.addWidget(frame)
        self.bg_layout.addSpacing(wutil.DPI(12))

        max_row_width = 0
        shortcut_font = self.font()
        shortcut_font.setPixelSize(wutil.DPI(10.5))
        shortcut_metrics = QFontMetrics(shortcut_font)
        shortcut_icon_dim = 11.25

        for sh in self.shortcuts:
            row = QHBoxLayout()
            row.setContentsMargins(wutil.DPI(12), 0, wutil.DPI(12), 0)
            row.setSpacing(wutil.DPI(20))

            icon_path = sh.get("icon", "default")
            row.addWidget(self._create_icon_label(icon_path, dim=shortcut_icon_dim))

            label_text = sh.get("label", "")
            name = QLabel(label_text)
            name.setWordWrap(False)
            name.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            name.setMinimumWidth(shortcut_metrics.horizontalAdvance(label_text))
            name.setStyleSheet("color: {}; font-size: {}px;".format(self.TEXT_COLOR, wutil.DPI(10.5)))
            row.addWidget(name)
            row.addStretch()

            command = sh.get("keys", "")
            if isinstance(command, list):
                command = format_tooltip_shortcut(command, include_click_suffix=True)
            keys = QLabel(command)
            keys.setWordWrap(False)
            keys.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
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
        lbl = QLabel()
        target_size = self._icon_target_size(dim)
        if hasattr(source, "pixmap"):
            pix = source.pixmap(target_size)
        elif isinstance(source, (str, bytes)):
            icon_path = source.decode() if isinstance(source, bytes) else source
            pix = self._load_icon_pixmap(icon_path, target_size)
        elif isinstance(source, QPixmap):
            pix = source.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pix = QPixmap()

        if not pix.isNull():
            lbl.setPixmap(pix)
        return lbl

    def _icon_target_size(self, dim):
        px_dim = max(1, int(wutil.DPI(dim * 2)))
        return QSize(px_dim, px_dim)

    def _load_icon_pixmap(self, path, target_size):
        if not path:
            return QPixmap()

        if path.lower().endswith(".svg") and QSvgRenderer:
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                pixmap = QPixmap(target_size)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return pixmap
        return pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _create_text_label(self, text, size=11, bold=False, elide=False, align=None):
        lbl = QLabel(text)
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
            fm = QFontMetrics(f)
            limit = wutil.DPI(self.MAX_WIDTH - 80)
            if fm.horizontalAdvance(text) > limit:
                lbl.setText(fm.elidedText(text, Qt.ElideLeft, limit))
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
        return QSize(max_width, max(1, int(size.height() * scale)))

    def _create_media_label(self, path):
        max_media_width = self._body_max_width()

        if path.lower().endswith(".gif"):
            lbl = TooltipMovieWidget()
            lbl.setMaximumWidth(max_media_width)
            movie = QMovie(path)
            movie.setCacheMode(QMovie.CacheAll)
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
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMaximumWidth(max_media_width)
            pix = QPixmap(path)
            if not pix.isNull():
                contained_size = self._contain_size(max_media_width, pix.size())
                if contained_size is not None and pix.size() != contained_size:
                    pix = pix.scaled(contained_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl.setPixmap(pix)
        return lbl

    def _create_body_text_label(self, text):
        raw_lbl = QLabel(text)
        raw_lbl.setWordWrap(True)
        raw_lbl.setOpenExternalLinks(False)
        raw_lbl.setTextFormat(Qt.PlainText)
        raw_lbl.setMaximumWidth(self._body_max_width())
        raw_lbl.setStyleSheet(
            "color: {}; background: transparent; font-size: {}px; margin: 0; padding: 0;".format(self.TEXT_COLOR, wutil.DPI(10.5))
        )
        return raw_lbl

    def _create_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        side = getattr(self, "side", "bottom")
        painter.setBrush(QColor(self.BG_COLOR))

        aw = wutil.DPI(self.ARROW_W)
        ah = wutil.DPI(self.ARROW_H)
        ax = getattr(self, "arrow_x", self.width() / 2)

        if side == "top":
            poly = QPolygonF([QPointF(ax, 0), QPointF(ax - aw / 2, ah + 1), QPointF(ax + aw / 2, ah + 1)])
            painter.drawPolygon(poly)
        else:
            poly = QPolygonF(
                [QPointF(ax, self.height()), QPointF(ax - aw / 2, self.height() - ah - 1), QPointF(ax + aw / 2, self.height() - ah - 1)]
            )
            painter.drawPolygon(poly)

    def show_around(self, widget, action_rect=None, target_rect=None):
        self.action_rect = action_rect
        self.target_rect = target_rect
        self.anchor_widget = widget

        cursor_pos = QCursor.pos()
        ah = wutil.DPI(self.ARROW_H)

        if target_rect:
            self._global_anc = target_rect
        elif action_rect:
            try:
                self._global_anc = QRect(widget.mapToGlobal(action_rect.topLeft()), action_rect.size())
            except RuntimeError:
                return
            self.target_rect = self._global_anc
        else:
            try:
                target_global = widget.mapToGlobal(QPoint(0, 0))
            except RuntimeError:
                return
            self._global_anc = QRect(target_global, widget.size())
            self.target_rect = self._global_anc

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
        pos = QPoint(target_x - w // 2, self._global_anc.top() - h - gap)

        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
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


class QFlatTooltipManager(object):
    """Manages global state for QFlatTooltips ensuring only one exists at a time."""

    _current_tooltip = None
    _timer = None
    enabled = True

    @classmethod
    def is_active(cls):
        return (cls._current_tooltip and cls._current_tooltip.isVisible()) or (cls._timer and cls._timer.isActive())

    @classmethod
    def cancel_timer(cls):
        if cls._timer:
            cls._timer.stop()

    @classmethod
    def hide(cls):
        cls.cancel_timer()
        if cls._current_tooltip:
            try:
                cls._current_tooltip.close()
            except Exception:
                pass
            cls._current_tooltip = None

    @classmethod
    def show(
        cls,
        text="",
        anchor_widget=None,
        icon=None,
        shortcuts=None,
        description=None,
        tooltip_template=None,
        action_rect=None,
        icon_obj=None,
        target_rect=None,
        **kwargs,
    ):
        if not cls.enabled:
            return
        if cls._timer:
            cls._timer.stop()
        if anchor_widget is not None and not wutil.is_valid_widget(anchor_widget):
            return

        if icon and not isinstance(icon, (str, bytes)):
            icon_obj = icon
            icon = None

        cls.hide()
        cls._current_tooltip = QFlatTooltip(
            text=text,
            anchor_widget=anchor_widget,
            icon=icon,
            shortcuts=shortcuts,
            description=description,
            tooltip_template=tooltip_template,
            icon_obj=icon_obj,
        )
        cls._current_tooltip.show_around(anchor_widget, action_rect, target_rect=target_rect)

    @classmethod
    def delayed_show(cls, delay=800, **kwargs):
        if not cls.enabled:
            return
        if cls._timer and cls._timer.isActive():
            cls._timer.stop()

        if not cls._timer:
            cls._timer = QTimer()
            cls._timer.setSingleShot(True)

        anchor = kwargs.get("anchor_widget")

        def _safe_show():
            if anchor is not None and not wutil.is_valid_widget(anchor):
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


def parse_tt(template):
    if not template:
        return "", ""
    normalized = _tooltip_template_from_data(template)
    header = toolCommon.clean_tool_text(getattr(normalized, "title", ""))
    description = toolCommon.clean_tool_text(getattr(normalized, "first_line", ""))
    return header, description
