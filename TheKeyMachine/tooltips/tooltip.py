import sys
import re

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
    )
    try:
        from PySide6.QtSvg import QSvgRenderer  # type: ignore
    except ImportError:
        QSvgRenderer = None  # type: ignore
except ImportError:
    from PySide2.QtWidgets import (
        QWidget,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QFrame,
        QMenu,
        QApplication,
        QSizePolicy,
    )
    from PySide2.QtGui import (
        QColor,
        QPixmap,
        QPainter,
        QPolygonF,
        QCursor,
        QGuiApplication,
        QMovie,
        QFontMetrics,
        QIcon,
    )
    from PySide2.QtCore import (
        Qt,
        QSize,
        QPoint,
        QPointF,
        QTimer,
        QRect,
    )
    try:
        from PySide2.QtSvg import QSvgRenderer  # type: ignore
    except ImportError:
        QSvgRenderer = None  # type: ignore

from TheKeyMachine.widgets import util as wutil


TOOLTIP_TITLE_FONT_SIZE = "{}px".format(wutil.DPI(35))
TOOLTIP_BODY_FONT_SIZE = "{}px".format(wutil.DPI(10.5))


# Pre-compiled regular expressions for high-performance tooltip parsing
RE_BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)
RE_TITLE_EXTRACT = re.compile(r"<(b|title)>(.*?)</\1>", re.IGNORECASE)
RE_IMG_EXTRACT = re.compile(r"<img[^>]*src=['\"](.*?)['\"]", re.IGNORECASE)
RE_HR_TAG = re.compile(r"<hr\s*/?>", re.IGNORECASE)
RE_BODY_TOKEN = re.compile(r"(<img[^>]*src=['\"].*?['\"][^>]*>|<hr\s*/?>)", re.IGNORECASE)
RE_FONT_TAG = re.compile(r"</?font[^>]*>", re.IGNORECASE)
RE_TAG_STRIP = re.compile(r"<[^>]*>")
RE_LEADING_BR = re.compile(r"^\s*<br\s*/?>", re.IGNORECASE)
RE_TRAILING_BR = re.compile(r"(<br\s*/?>\s*)+$", re.IGNORECASE)

IS_MAC = sys.platform == "darwin"
SHORTCUT_KEY_MAP = {
    Qt.Key_Alt: "⌥" if IS_MAC else "Alt",
    Qt.Key_Shift: "⇧" if IS_MAC else "Shift",
    Qt.Key_Control: "⌘" if IS_MAC else "Ctrl",
    Qt.MiddleButton: "Click" if IS_MAC else "MidClick",
}
SHORTCUT_KEY_ORDER = [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.MiddleButton]


class TooltipTemplate(str):
    def __new__(cls, html, title="", body_lines=(), icon=None, icon_width=30):
        obj = str.__new__(cls, html)
        obj.title = title
        obj.body_lines = tuple(line for line in body_lines if line)
        obj.icon = icon
        obj.icon_width = icon_width
        return obj

    @property
    def first_line(self):
        return self.body_lines[0] if self.body_lines else ""


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


def tool_tooltip(title, body, icon=None, icon_width=30):
    body_lines = tooltip_body(*(body if isinstance(body, (list, tuple)) else [body]))
    icon_html = f"<img src='{icon}' width='{icon_width}'>" if icon else ""
    body_parts = []
    for item in body_lines:
        if item is separator:
            body_parts.append("<hr>")
        elif isinstance(item, TooltipMedia):
            body_parts.append(f"<img src='{item.path}'>")
        else:
            body_parts.append(item)
    body_html = "<br><br>".join(body_parts)
    html = (
        f"<font style='color: #cccccc; font-size:{TOOLTIP_TITLE_FONT_SIZE};'><b>{title}</b></font>{icon_html}<br><br>"
        f"<font style='color: #cccccc; font-size:{TOOLTIP_BODY_FONT_SIZE};'>{body_html}</font>"
    )
    return TooltipTemplate(html, title=title, body_lines=body_lines, icon=icon, icon_width=icon_width)


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

        # 1. Build base template if not provided
        if not tooltip_template:
            # If text has HTML-like markers, use it directly
            if text and ("<" in text or ">" in text or "<br" in text.lower()):
                tooltip_template = text
            else:
                tooltip_template = ""
                if icon:
                    tooltip_template += "<img src='{}'>".format(icon)
                if text:
                    tooltip_template += "<b>{}</b>".format(text.strip())

        # 2. Add description if missing from template body
        if description:
            # Check if template already has a body break
            has_body = tooltip_template and ("<br" in tooltip_template.lower() or "\n" in tooltip_template)
            if not has_body:
                prefix = "<br><br>" if tooltip_template else ""
                tooltip_template = "{}{}{}".format(tooltip_template, prefix, description.strip())

        self.tooltip_template = tooltip_template or ""

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

    def _format_keys(self, keys_list):
        return format_tooltip_shortcut(keys_list, include_click_suffix=True)

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
        # Treatment for raw HTML (standard helperMod format)
        self.has_header = False

        # 1. Try to extract Title and Icon from the template if not explicitly provided
        extracted_title = ""
        extracted_icon_path = ""

        # Split by first <br> to restrict extraction to the "header line"
        parts = RE_BR_SPLIT.split(self.tooltip_template, maxsplit=1)
        header_candidate = parts[0] if parts else self.tooltip_template

        # Look for <b>Title</b> or <title>Title</title> in the header line
        title_match = RE_TITLE_EXTRACT.search(header_candidate)
        if title_match:
            extracted_title = title_match.group(2).strip()

        # Look for <img src='...'> in the header line
        img_match = RE_IMG_EXTRACT.search(header_candidate)
        if img_match:
            extracted_icon_path = img_match.group(1)

        # 2. Determine Header Content - Fallback to self.text if extraction failed
        header_title = extracted_title or self.text
        header_pixmap = self.icon_obj if self.icon_obj and not self.icon_obj.isNull() else None

        if not header_pixmap:
            if extracted_icon_path:
                header_pixmap = QIcon(extracted_icon_path)
            elif self.icon_path and isinstance(self.icon_path, (str, bytes)):
                header_pixmap = QIcon(self.icon_path)

        # 3. Build Header Section if we have a title or icon
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

        # 4. Clean up the template for the body
        # We remove the first 'header' line if it contains the title/icon to avoid duplication
        body_html = self.tooltip_template

        if self.has_header and len(parts) > 1:
            header_line = parts[0]
            cleaned_first = RE_TAG_STRIP.sub("", header_line).strip()

            # If the extracted title is in the first line, we assume it's the header to remove
            is_header_line = False
            if not cleaned_first:
                is_header_line = True
            elif header_title and header_title.lower() in cleaned_first.lower():
                # Ensure it's not a long paragraph that just happens to contain the title
                if len(cleaned_first) < len(header_title) + 30:
                    is_header_line = True

            if is_header_line:
                # Discard the first line and EVERY following <br> to start at real content
                body_html = parts[1].strip()

                while True:
                    next_br = RE_LEADING_BR.match(body_html)
                    if next_br:
                        body_html = body_html[next_br.end() :].strip()
                    else:
                        break
        elif self.has_header and len(parts) == 1:
            # If there's no <br>, and we extracted everything into the header, body should be empty
            cleaned_all = re.sub(r"<[^>]*>", "", body_html).strip()
            if not cleaned_all or (header_title and header_title.lower() == cleaned_all.lower()):
                body_html = ""

        content_layout = QVBoxLayout()
        content_layout.setSpacing(wutil.DPI(6))
        top_margin = wutil.DPI(0) if self.has_header else wutil.DPI(12)
        content_layout.setContentsMargins(wutil.DPI(12), top_margin, wutil.DPI(12), wutil.DPI(8))
        self.content_layout = content_layout

        if not body_html.strip() and self.description:
            body_html = self.description

        if body_html.strip():
            self._populate_body_content(content_layout, body_html)
            self.bg_layout.addLayout(content_layout)
            if self.shortcuts and "Shortcuts" not in self.tooltip_template:
                self.bg_layout.addSpacing(wutil.DPI(14))
            else:
                self.bg_layout.addSpacing(wutil.DPI(18))

        # 5. Shortcuts detection
        if self.shortcuts and "Shortcuts" not in self.tooltip_template:
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
                command = self._format_keys(command)
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
            lbl = TooltipMovieLabel()
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

    def _create_body_text_label(self, html):
        raw_lbl = QLabel(html)
        raw_lbl.setWordWrap(True)
        raw_lbl.setOpenExternalLinks(True)
        raw_lbl.setTextFormat(Qt.RichText)
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

    def _normalize_body_text(self, html):
        html = RE_FONT_TAG.sub("", html or "")
        html = RE_LEADING_BR.sub("", html)
        html = RE_TRAILING_BR.sub("", html)
        return html.strip()

    def _iter_body_blocks(self, body_html):
        for part in RE_BODY_TOKEN.split(body_html):
            part = (part or "").strip()
            if not part:
                continue

            if RE_HR_TAG.fullmatch(part):
                yield ("separator", None)
                continue

            img_match = RE_IMG_EXTRACT.search(part)
            if img_match:
                yield ("media", img_match.group(1))
                continue

            text_html = self._normalize_body_text(part)
            if text_html:
                yield ("text", text_html)

    def _populate_body_content(self, layout, body_html):
        for block_type, value in self._iter_body_blocks(body_html):
            if block_type == "separator":
                layout.addSpacing(wutil.DPI(6))
                layout.addWidget(self._create_separator())
                continue

            if block_type == "media":
                layout.addWidget(self._create_media_label(value))
                continue

            layout.addWidget(self._create_body_text_label(value))

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

        try:
            cls._timer.timeout.disconnect()
        except Exception:
            pass

        anchor = kwargs.get("anchor_widget")

        def _safe_show():
            if anchor is not None and not wutil.is_valid_widget(anchor):
                return
            cls.show(**kwargs)

        cls._timer.timeout.connect(_safe_show)
        cls._timer.setInterval(delay)
        cls._timer.start()


def parse_tt(html):
    """
    Parses TKM HTML tooltips into (Header, Description).
    Preserves HTML formatting for rich tooltips.
    """
    if not html:
        return "", ""

    # Split by double break (common TKM separator)
    parts = re.split(r"<br\s*/?>\s*<br\s*/?>", html, maxsplit=1, flags=re.IGNORECASE)
    header = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ""

    return header, description
