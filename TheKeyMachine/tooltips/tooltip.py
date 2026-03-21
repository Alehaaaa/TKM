from __future__ import annotations
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
    )
    from PySide6.QtCore import (  # type: ignore
        Qt,
        QSize,
        QPoint,
        QPointF,
        QTimer,
        QRect,
    )
except ImportError:
    from PySide2.QtWidgets import (
        QWidget,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QFrame,
        QMenu,
        QApplication,
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
    )
    from PySide2.QtCore import (
        Qt,
        QSize,
        QPoint,
        QPointF,
        QTimer,
        QRect,
    )

from TheKeyMachine.widgets import util as wutil


class QFlatTooltip(QWidget):
    """A floating tooltip with an arrow pointing to its source."""

    BG_COLOR = "#333333"
    HEADER_COLOR = "#282828"
    TEXT_COLOR = "#bbbbbb"
    ACCENT_COLOR = "#e0e0e0"

    ARROW_W = 12
    ARROW_H = 8
    BORDER_RADIUS = 8

    MAX_WIDTH = 320
    MIN_WIDTH = 220

    IS_MAC = sys.platform == "darwin"
    KEY_MAP = {
        Qt.Key_Alt: "⌥" if IS_MAC else "Alt",
        Qt.Key_Shift: "⇧" if IS_MAC else "Shift",
        Qt.Key_Control: "⌘" if IS_MAC else "Ctrl",
    }
    KEY_ORDER = [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift]

    def __init__(self, text="", anchor_widget=None, icon=None, shortcuts=None, description=None, template=None, icon_obj=None):
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

        # 1. Build the base template
        if template is None:
            if text and ("<" in text or ">" in text or "<br" in text.lower()):
                template = text
            else:
                template = ""
                if icon:
                    template += f"<img src='{icon}'>"
                if text:
                    template += f"<b>{text.strip()}</b>"

            # Always append description if provided
            if description:
                # Ensure we have a separator if there was already content
                prefix = "<br><br>" if template else ""
                template = f"{template}{prefix}{description.strip()}"

        self.template = template

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
        keys_set = set(keys_list)
        parts = [self.KEY_MAP[k] for k in self.KEY_ORDER if k in keys_set]

        if len(parts) < len(keys_list):
            for k in keys_list:
                if k not in self.KEY_MAP:
                    parts.append(str(k))

        return ("" if self.IS_MAC else "+").join(parts) + "+Click"

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.main_layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self.setStyleSheet(
            "QFlatTooltip > QFrame#BgFrame {{ background-color: {}; border-radius: {}px; }}".format(self.BG_COLOR, wutil.DPI(self.BORDER_RADIUS))
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
        parts = re.split(r"<br\s*/?>", self.template, maxsplit=1, flags=re.IGNORECASE)
        header_candidate = parts[0] if parts else self.template

        # Look for <b>Title</b> or <title>Title</title> in the header line
        title_match = re.search(r"<(b|title)>(.*?)</\1>", header_candidate, re.IGNORECASE)
        if title_match:
            extracted_title = title_match.group(2).strip()

        # Look for <img src='...'> in the header line
        img_match = re.search(r"<img[^>]*src=['\"](.*?)['\"]", header_candidate, re.IGNORECASE)
        if img_match:
            extracted_icon_path = img_match.group(1)

        # 2. Determine Header Content - Fallback to self.text if extraction failed
        header_title = extracted_title or self.text
        header_pixmap = self.icon_obj if self.icon_obj and not self.icon_obj.isNull() else None

        if not header_pixmap and extracted_icon_path:
            header_pixmap = QPixmap(extracted_icon_path)

        # 3. Build Header Section if we have a title or icon
        if header_title or header_pixmap:
            header_frame, header_layout = self._create_section_frame("")
            if header_pixmap:
                lbl = self._create_icon_label(header_pixmap, dim=29)
                header_layout.addWidget(lbl)
            if header_title:
                title_lbl = self._create_text_label(header_title, size=18, bold=True, elide=True)
                header_layout.addWidget(title_lbl)

            header_layout.addStretch()
            self.bg_layout.addWidget(header_frame)
            self.has_header = True

        # 4. Clean up the template for the body
        # We remove the first 'header' line if it contains the title/icon to avoid duplication
        body_html = self.template

        if self.has_header and len(parts) > 1:
            header_line = parts[0]
            cleaned_first = re.sub(r"<[^>]*>", "", header_line).strip()

            # If the extracted title is in the first line, we assume it's the header to remove
            is_header_line = False
            if not cleaned_first:
                is_header_line = True
            elif extracted_title and extracted_title.lower() in cleaned_first.lower():
                # Ensure it's not a long paragraph that just happens to contain the title
                if len(cleaned_first) < len(extracted_title) + 30:
                    is_header_line = True

            if is_header_line:
                # Discard the first line and EVERY following <br> to start at real content
                body_html = parts[1].strip()
                while True:
                    next_br = re.match(r"^\s*<br\s*/?>", body_html, re.IGNORECASE)
                    if next_br:
                        body_html = body_html[next_br.end() :].strip()
                    else:
                        break
        elif self.has_header and len(parts) == 1:
            # If there's no <br>, and we extracted everything into the header, body should be empty
            cleaned_all = re.sub(r"<[^>]*>", "", body_html).strip()
            if not cleaned_all or (extracted_title and extracted_title.lower() == cleaned_all.lower()):
                body_html = ""

        content_layout = QVBoxLayout()
        top_margin = wutil.DPI(0) if self.has_header else wutil.DPI(12)
        content_layout.setContentsMargins(wutil.DPI(12), top_margin, wutil.DPI(12), wutil.DPI(8))

        if body_html.strip():
            raw_lbl = QLabel(body_html)
            raw_lbl.setWordWrap(True)
            raw_lbl.setOpenExternalLinks(True)
            raw_lbl.setTextFormat(Qt.RichText)
            raw_lbl.setMaximumWidth(wutil.DPI(self.MAX_WIDTH))
            raw_lbl.setStyleSheet("color: {}; background: transparent;".format(self.TEXT_COLOR))
            content_layout.addWidget(raw_lbl)
            self.bg_layout.addLayout(content_layout)
            self.bg_layout.addSpacing(wutil.DPI(4))
        self.bg_layout.addSpacing(wutil.DPI(4))

        # 5. Shortcuts detection
        # Logic: If the word "Shortcuts" (or similar consistent pattern) is in the HTML,
        # we skip building the auto-section because it's already in the HTML.
        # User said "Shortcuts title will always be the same text in the helpers"
        if self.shortcuts and "Shortcuts" not in self.template:
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

        self.bg_layout.addSpacing(wutil.DPI(10))
        self.bg_layout.addWidget(frame)
        self.bg_layout.addSpacing(wutil.DPI(12))

        for sh in self.shortcuts:
            row = QHBoxLayout()
            row.setContentsMargins(wutil.DPI(12), 0, wutil.DPI(12), 0)
            row.setSpacing(wutil.DPI(20))

            icon_path = sh.get("icon", "default")
            pix = QPixmap(icon_path)
            row.addWidget(self._create_icon_label(pix, dim=17))

            name = QLabel(sh.get("label", ""))
            name.setStyleSheet("color: {}; font-size: {}px;".format(self.TEXT_COLOR, wutil.DPI(10.5)))
            row.addWidget(name)
            row.addStretch()

            command = sh.get("keys", "")
            if isinstance(command, list):
                command = self._format_keys(command)
            keys = QLabel(command)
            keys.setStyleSheet("color: {}; font-size: {}px;".format(self.TEXT_COLOR, wutil.DPI(10.5)))
            row.addWidget(keys)
            self.bg_layout.addLayout(row)
            self.bg_layout.addSpacing(wutil.DPI(4))

        self.bg_layout.addSpacing(wutil.DPI(16))

    def _create_icon_label(self, source, dim=16):
        lbl = QLabel()
        px_dim = wutil.DPI(dim)
        if hasattr(source, "pixmap"):
            pix = source.pixmap(px_dim, px_dim)
        elif isinstance(source, QPixmap):
            pix = source
        else:
            pix = QPixmap()

        if not pix.isNull():
            lbl.setPixmap(pix.scaled(px_dim, px_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return lbl

    def _create_text_label(self, text, size=11, bold=False, elide=False, align=None):
        lbl = QLabel(text)
        lbl.setObjectName("text_label")
        lbl.setToolTip(text)
        lbl.setWordWrap(True)

        style = "#text_label {{ color: {0}; font-size: {1}px; {2}}}".format(self.TEXT_COLOR, wutil.DPI(size), "font-weight: bold;" if bold else "")
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

    def _create_media_label(self, path, is_gif=False):
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setContentsMargins(wutil.DPI(12), wutil.DPI(4), wutil.DPI(12), wutil.DPI(4))
        if is_gif or path.endswith(".gif"):
            movie = QMovie(path)
            movie.setScaledSize(QSize(wutil.DPI(300), wutil.DPI(150)))
            movie.start()
            lbl.setMovie(movie)
        else:
            pix = QPixmap(path)
            if not pix.isNull():
                if pix.width() > wutil.DPI(300):
                    pix = pix.scaledToWidth(wutil.DPI(300), Qt.SmoothTransformation)
                lbl.setPixmap(pix)
        return lbl

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
            poly = QPolygonF([QPointF(ax, self.height()), QPointF(ax - aw / 2, self.height() - ah - 1), QPointF(ax + aw / 2, self.height() - ah - 1)])
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

        pos = QPoint(target_x - w // 2, self._global_anc.top() - h - wutil.DPI(2))

        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        if pos.y() < geo.top() + wutil.DPI(5):
            # Not enough room above, flip to BELOW the widget (arrow on top)
            self.side = "top"
            self.main_layout.setContentsMargins(0, ah, 0, 0)
            self.main_layout.activate()
            self.adjustSize()
            w, h = self.width(), self.height()
            pos.setY(self._global_anc.bottom() + 1 + wutil.DPI(2))

        final_x = max(geo.left() + wutil.DPI(5), min(pos.x(), geo.right() - w - wutil.DPI(5)))
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
        template=None,
        action_rect=None,
        icon_obj=None,
        target_rect=None,
    ):
        if not cls.enabled:
            return
        if cls._timer:
            cls._timer.stop()
        # Guard: if anchor_widget has been deleted by the time we show, bail out
        if anchor_widget is not None and not wutil.is_valid_widget(anchor_widget):
            return
        cls.hide()
        cls._current_tooltip = QFlatTooltip(
            text=text,
            anchor_widget=anchor_widget,
            icon=icon,
            shortcuts=shortcuts,
            description=description,
            template=template,
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
