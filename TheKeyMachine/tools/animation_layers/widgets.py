"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Modified by: Alehaaaa / alehaaaa.github.io



"""

"""The Animation Layers window.

A floating, list-based tool window (same shell family as Selection Sets and
Attribute Switcher) showing every animation layer and group in the scene as
one flat, indented, drag-reorderable list -- mirroring how Maya's own
Animation Layer Editor presents nested layers. Groups are just animation
layers used purely as parent containers (see ``controller.create_group``),
so the same row widget renders both; nesting depth drives indentation only.
"""

from maya import cmds  # type: ignore

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.core import runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.tools.animation_layers import api as animationLayersApi
from TheKeyMachine.tools.animation_layers import controller
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets import customWidgets as cw
from TheKeyMachine.ui.widgets import util as wutil


WINDOW_NAME = "animation_layers_window"
ROW_HEIGHT = wutil.DPI(24)
INDENT_WIDTH = wutil.DPI(14)
BASE_COLOR_EVEN = "#2b2b2b"
BASE_COLOR_ODD = "#2e2e2e"
SELECTED_COLOR = "#5f88a8"
ARROW_COLUMN_WIDTH = wutil.DPI(14)
BORDER_WIDTH_INHERITED = wutil.DPI(3)
TOGGLE_BUTTON_SIZE = wutil.DPI(20)


# ---------------------------------------------------------------------------
# Small painted icons -- kept local rather than shared, matching how
# tools.workspaces.widgets and tools.hotkeys.controller each keep their own
# copy of the same kind of tiny presentation helper (see ARCHITECTURE.md:
# feature-specific widgets stay inside their own tools/<feature> package).
# ---------------------------------------------------------------------------


def _grip_icon(size, color="#8a8a8a"):
    """2x3 dot-grid pixmap used as the row drag handle."""
    dim = max(1, int(size))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    radius = max(0.75, dim / 9.0)
    for x_ratio in (0.3, 0.75):
        for y_ratio in (0.2, 0.5, 0.8):
            painter.drawEllipse(QtCore.QPointF(dim * x_ratio, dim * y_ratio), radius, radius)
    painter.end()
    return pixmap


def _text_badge_icon(text, size, color="#1a1a1a", background="#787878"):
    """A small filled circle with a bold letter -- used for the Additive/
    Override type badge, matching ``workspaces.widgets._text_badge_qicon``'s
    approach of a painted badge instead of a static icon file."""
    dim = max(1, int(size))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(background))
    painter.drawEllipse(pixmap.rect().adjusted(1, 1, -1, -1))
    painter.setPen(QtGui.QColor(color))
    font = QtGui.QFont()
    font.setBold(True)
    font.setPixelSize(max(1, int(dim * 0.58)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, text or "")
    painter.end()
    return QtGui.QIcon(pixmap)


def _tinted_pixmap(icon_path, size, color):
    """Recolor a flat-fill svg/icon file, same SourceIn-composite trick
    ``AttributeItem._refresh_pill_style`` uses to tint the rotate-order globe
    icon -- there's no shared tint helper in ``ui.widgets.util`` to call
    instead, so this stays a small local copy of that idiom.

    Loads via a plain ``QPixmap(path)`` + ``.scaled(..., SmoothTransformation)``
    rather than ``QIcon(path).pixmap(dim, dim)`` -- the latter lets Qt fetch a
    HiDPI-scaled render tagged with its own devicePixelRatio, which then gets
    silently dropped by the plain ``QPixmap(pixmap.size())`` below (it always
    starts at devicePixelRatio 1), leaving the tinted result reporting a
    logical size roughly double what it should be and rendering into only
    the top-left quarter of the icon slot it's placed in.
    """
    dim = max(1, int(size))
    if not icon_path:
        return QtGui.QPixmap()
    pixmap = QtGui.QPixmap(icon_path)
    if pixmap.isNull():
        return pixmap
    pixmap = pixmap.scaled(dim, dim, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    tinted = QtGui.QPixmap(pixmap.size())
    tinted.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QtGui.QColor(color))
    painter.end()
    return tinted


def _color_swatch_icon(size, color):
    """A plain filled circle -- used for entries in the group color menu."""
    dim = max(1, int(size))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    painter.drawEllipse(pixmap.rect().adjusted(1, 1, -1, -1))
    painter.end()
    return QtGui.QIcon(pixmap)


def _arrow_icon(size, expanded, color="#c0c0c0"):
    """Small triangle -- right when collapsed, down when expanded -- for the
    group row's collapse/expand toggle."""
    dim = max(1, int(size))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    inset = dim * 0.22
    if expanded:
        triangle = QtGui.QPolygonF([
            QtCore.QPointF(inset, dim * 0.35),
            QtCore.QPointF(dim - inset, dim * 0.35),
            QtCore.QPointF(dim / 2.0, dim - inset),
        ])
    else:
        triangle = QtGui.QPolygonF([
            QtCore.QPointF(dim * 0.35, inset),
            QtCore.QPointF(dim * 0.35, dim - inset),
            QtCore.QPointF(dim - inset, dim / 2.0),
        ])
    painter.drawPolygon(triangle)
    painter.end()
    return QtGui.QIcon(pixmap)


def _lock_icon(size, color):
    """Padlock glyph -- shackle arc over a rounded body -- for the Lock toggle."""
    dim = max(1, int(size))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    pen_width = max(1.0, dim * 0.13)
    painter.setPen(QtGui.QPen(QtGui.QColor(color), pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
    painter.setBrush(QtCore.Qt.NoBrush)
    shackle_rect = QtCore.QRectF(dim * 0.27, dim * 0.06, dim * 0.46, dim * 0.5)
    painter.drawArc(shackle_rect, 0, 180 * 16)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    body_rect = QtCore.QRectF(dim * 0.16, dim * 0.44, dim * 0.68, dim * 0.44)
    painter.drawRoundedRect(body_rect, dim * 0.08, dim * 0.08)
    painter.end()
    return QtGui.QIcon(pixmap)


def _mute_icon(size, color):
    """Speaker-with-slash glyph for the Mute toggle."""
    dim = max(1, int(size))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    speaker = QtGui.QPolygonF([
        QtCore.QPointF(dim * 0.10, dim * 0.38),
        QtCore.QPointF(dim * 0.32, dim * 0.38),
        QtCore.QPointF(dim * 0.54, dim * 0.16),
        QtCore.QPointF(dim * 0.54, dim * 0.84),
        QtCore.QPointF(dim * 0.32, dim * 0.62),
        QtCore.QPointF(dim * 0.10, dim * 0.62),
    ])
    painter.drawPolygon(speaker)
    pen_width = max(1.0, dim * 0.12)
    painter.setPen(QtGui.QPen(QtGui.QColor(color), pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
    painter.drawLine(QtCore.QPointF(dim * 0.64, dim * 0.32), QtCore.QPointF(dim * 0.90, dim * 0.68))
    painter.drawLine(QtCore.QPointF(dim * 0.90, dim * 0.32), QtCore.QPointF(dim * 0.64, dim * 0.68))
    painter.end()
    return QtGui.QIcon(pixmap)


def _contrast_color(hex_color):
    """Pick black or off-white text/icon color for readability over ``hex_color``."""
    color = QtGui.QColor(hex_color)
    luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255.0
    return "#1a1a1a" if luminance > 0.55 else "#f0f0f0"


# ---------------------------------------------------------------------------
# List + drag/drop
# ---------------------------------------------------------------------------


class _DropIndicator(QtWidgets.QFrame):
    """Line marking where a dragged row will land -- drawn over the
    viewport ourselves, since rows here are opaque item widgets that sit on
    top of (and hide) the view's own native drop-indicator painting. See
    ``tools.workspaces.widgets._DropIndicator`` for the original of this
    pattern."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(wutil.DPI(2))
        self.setStyleSheet("background-color: %s;" % SELECTED_COLOR)
        self.hide()


class LayerListWidget(QtWidgets.QListWidget):
    """A flat, indented, drag-reorderable list of animation layer rows.

    Reordering stays a plain, native ``InternalMove`` drag on a
    ``QListWidget`` -- nesting is expressed only by each row's own
    indentation (mirroring Maya's own Animation Layer Editor), not by a real
    ``QTreeWidget``, which does not combine item widgets and drag-reordering
    as cleanly. A drag only ever starts from a row's own grip handle (see
    ``LayerRowWidget``/``_DragHandle``) -- ordinary clicks on the row itself
    (buttons, name, weight field) never trigger one.
    """

    layerDropped = QtCore.Signal(str)
    emptyAreaClicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setDropIndicatorShown(False)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            "QListWidget{background:#242424;border:none;outline:none;}"
            "QListWidget::item{margin:0px;padding:0px;border:none;}"
        )
        self._indicator = _DropIndicator(self.viewport())
        self._dragging_name = None

    def mousePressEvent(self, event):
        # Rows are opaque item widgets that fill their item rect entirely,
        # so itemAt() returning None here means the click landed on genuinely
        # empty space (below the last row, or in side padding) -- clear the
        # window's selection the way clicking empty list space normally does.
        if self.itemAt(event.pos()) is None:
            self.emptyAreaClicked.emit()
        super().mousePressEvent(event)

    def start_drag_for_item(self, item):
        widget = self.itemWidget(item)
        if widget is None:
            return
        self.setCurrentItem(item)
        self._dragging_name = widget.layer_name
        rect = self.visualItemRect(item)
        drag = QtGui.QDrag(self)
        drag.setMimeData(self.model().mimeData([self.indexFromItem(item)]))
        drag.setPixmap(widget.grab())
        drag.setHotSpot(QtCore.QPoint(wutil.DPI(10), max(0, rect.height() // 2)))
        drag.exec_(QtCore.Qt.MoveAction, QtCore.Qt.MoveAction)
        self._dragging_name = None

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        self._update_indicator(event.pos())

    def dragLeaveEvent(self, event):
        self._indicator.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._indicator.hide()
        dragging_name = self._dragging_name
        super().dropEvent(event)
        if dragging_name:
            self.layerDropped.emit(dragging_name)

    def _update_indicator(self, pos):
        if not self.count():
            self._indicator.hide()
            return
        item = self.itemAt(pos)
        if item is None:
            y = self.visualItemRect(self.item(self.count() - 1)).bottom()
        else:
            rect = self.visualItemRect(item)
            y = rect.top() if pos.y() < rect.center().y() else rect.bottom()
        self._indicator.setGeometry(0, max(0, y - 1), self.viewport().width(), self._indicator.height())
        self._indicator.show()
        self._indicator.raise_()


class _DragHandle(QtWidgets.QLabel):
    """The grip at the start of a row -- the only place a reorder drag starts."""

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self._row = row
        self.setFixedSize(wutil.DPI(16), ROW_HEIGHT)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setPixmap(_grip_icon(wutil.DPI(10)))
        self.setCursor(QtCore.Qt.OpenHandCursor)
        self.setToolTip("Drag to reorder")
        self.setStyleSheet("background:transparent;")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._row.begin_drag()
            event.accept()
            return
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Row widget
# ---------------------------------------------------------------------------


class LayerRowWidget(QtWidgets.QWidget):
    clicked = QtCore.Signal(str, object)
    muteToggled = QtCore.Signal(str, bool)
    lockToggled = QtCore.Signal(str, bool)
    overrideToggled = QtCore.Signal(str, bool)
    weightEdited = QtCore.Signal(str, float)
    renamed = QtCore.Signal(str, str)
    contextRequested = QtCore.Signal(str, QtCore.QPoint)
    collapseToggled = QtCore.Signal(str, bool)
    colorChosen = QtCore.Signal(str, object)

    def __init__(self, node, depth, row_index, collapsed=False, parent=None):
        super().__init__(parent)
        self.layer_name = node["name"]
        self.is_root = bool(node.get("is_root"))
        self.is_group = bool(node.get("is_group"))
        self._override = bool(node.get("override"))
        self._list_widget = None
        self._item = None
        self._selected = False
        self._collapsed = bool(collapsed)

        border_suffix = node.get("_border_color")
        self._border_hex = COLORS.selection.get(border_suffix).hex if border_suffix else None
        self._is_color_owner = bool(node.get("_is_color_owner"))

        base_color = BASE_COLOR_EVEN if row_index % 2 == 0 else BASE_COLOR_ODD
        self.setObjectName("AnimLayerRow")
        self.setProperty("rowSelected", False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#AnimLayerRow{background:%s;}"
            "#AnimLayerRow[rowSelected='true']{background:%s;}"
            % (base_color, SELECTED_COLOR)
        )
        self.setFixedHeight(ROW_HEIGHT)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(3), 0, wutil.DPI(4), 0)
        layout.setSpacing(wutil.DPI(2))

        # Gutter column: the collapse arrow and the color border share this
        # one reserved slot instead of stacking a separate painted strip next
        # to a separate arrow button. A group paints the whole gutter in its
        # own color with the arrow drawn on top of it; a plain layer nested
        # under a colored group gets a thinner bar of that inherited color;
        # the root row and an ungrouped top-level layer get a blank gutter.
        self.collapse_button = None
        gutter = QtWidgets.QWidget(self)
        gutter.setFixedSize(ARROW_COLUMN_WIDTH, ROW_HEIGHT)
        gutter_layout = QtWidgets.QHBoxLayout(gutter)
        gutter_layout.setContentsMargins(0, 0, 0, 0)
        gutter_layout.setSpacing(0)
        if self.is_group:
            self.collapse_button = QtWidgets.QToolButton(gutter)
            self.collapse_button.setAutoRaise(True)
            self.collapse_button.setFixedSize(ARROW_COLUMN_WIDTH, ROW_HEIGHT)
            self.collapse_button.setIconSize(QtCore.QSize(wutil.DPI(8), wutil.DPI(8)))
            self.collapse_button.setCursor(QtCore.Qt.PointingHandCursor)
            self.collapse_button.setStyleSheet(
                "QToolButton{background-color:%s;border:none;}"
                "QToolButton:hover{background-color:%s;}" % (self._border_hex, self._border_hex)
            )
            self.collapse_button.clicked.connect(self._on_collapse_clicked)
            self._refresh_collapse_icon()
            gutter_layout.addWidget(self.collapse_button)
        elif self._border_hex and not self.is_root:
            bar = QtWidgets.QWidget(gutter)
            bar.setFixedWidth(BORDER_WIDTH_INHERITED)
            bar.setStyleSheet("background:%s;" % self._border_hex)
            gutter_layout.addWidget(bar, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(gutter)

        # The root/BaseAnimation row can't be reordered -- no drag handle.
        if self.is_root:
            handle_spacer = QtWidgets.QWidget(self)
            handle_spacer.setFixedSize(wutil.DPI(16), ROW_HEIGHT)
            handle_spacer.setStyleSheet("background:transparent;")
            layout.addWidget(handle_spacer)
        else:
            self.handle = _DragHandle(self, self)
            layout.addWidget(self.handle)

        self.lock_button = self._make_icon_toggle(
            _lock_icon, node.get("lock"), "#c9a76b", "Lock -- prevents keying this layer"
        )
        self.lock_button.toggled.connect(lambda checked: self.lockToggled.emit(self.layer_name, checked))
        layout.addWidget(self.lock_button)

        self.mute_button = self._make_icon_toggle(
            _mute_icon, node.get("mute"), "#c96b68", "Mute -- disables this layer's effect"
        )
        self.mute_button.toggled.connect(lambda checked: self.muteToggled.emit(self.layer_name, checked))
        layout.addWidget(self.mute_button)

        # Indent only pushes the name over -- lock/mute stay aligned in one
        # column across every row regardless of nesting depth.
        if depth:
            indent = QtWidgets.QWidget(self)
            indent.setFixedWidth(INDENT_WIDTH * depth)
            indent.setStyleSheet("background:transparent;")
            layout.addWidget(indent)

        self.name_button = cw.InlineRenameButton(
            node["name"], self,
            rename_alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            rename_margins=(wutil.DPI(2), wutil.DPI(2), wutil.DPI(6), wutil.DPI(2)),
        )
        self.name_button.setFlat(True)
        self.name_button.setFixedHeight(ROW_HEIGHT)
        self.name_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.name_button.setProperty("tkm_text_color", "#ffffff")
        self.name_button.set_rename_target(node["name"], node["name"], self._on_renamed)
        self.name_button.clicked.connect(self._emit_clicked)
        layout.addWidget(self.name_button, 1)

        self.weight_spin = cw.QFlatDoubleSpinBox(
            decimals=0,
            minimum=0.0,
            maximum=100.0,
            value=round(float(node.get("weight", 1.0)) * 100.0),
            single_step=5.0,
        )
        self.weight_spin.setFixedWidth(wutil.DPI(46))
        self.weight_spin.setFixedHeight(wutil.DPI(18))
        self.weight_spin.setSuffix("%")
        self.weight_spin.setAlignment(QtCore.Qt.AlignCenter)
        self.weight_spin.setToolTip("Layer weight")
        self.weight_spin.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.weight_spin.valueChanged.connect(self._on_weight_changed)
        if self.is_root:
            # BaseAnimation has no meaningful override weight to blend.
            self.weight_spin.setEnabled(False)
        layout.addWidget(self.weight_spin)

        # Type indicator, at the very end of the row: for a group this is a
        # clickable folder icon that opens the color menu; for an ordinary
        # layer it's the clickable Additive/Override badge; the root row gets
        # neither (just a same-size blank spacer, for column alignment).
        if self.is_group:
            self._own_color_hex = self._border_hex if self._is_color_owner else None
            self.type_button = QtWidgets.QToolButton(self)
            self.type_button.setAutoRaise(True)
            self.type_button.setFixedSize(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE)
            self.type_button.setIconSize(QtCore.QSize(wutil.DPI(16), wutil.DPI(16)))
            self.type_button.setCursor(QtCore.Qt.PointingHandCursor)
            self._refresh_group_icon()
            self.type_button.setToolTip("Group -- click to set its color.")
            self.type_button.clicked.connect(self._open_color_menu)
            layout.addWidget(self.type_button)
        elif not self.is_root:
            badge = "O" if self._override else "A"
            badge_color = "#c9a76b" if self._override else "#689d85"
            self.type_button = QtWidgets.QToolButton(self)
            self.type_button.setAutoRaise(True)
            self.type_button.setFixedSize(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE)
            self.type_button.setIconSize(QtCore.QSize(wutil.DPI(16), wutil.DPI(16)))
            self.type_button.setIcon(_text_badge_icon(badge, wutil.DPI(16), background=badge_color))
            self.type_button.setToolTip(
                "Override layer -- replaces the value below it. Click to switch to Additive."
                if self._override else
                "Additive layer -- adds on top of the value below it. Click to switch to Override."
            )
            self.type_button.setCursor(QtCore.Qt.PointingHandCursor)
            self.type_button.clicked.connect(self._on_type_clicked)
            layout.addWidget(self.type_button)
        else:
            self.type_button = None
            end_spacer = QtWidgets.QWidget(self)
            end_spacer.setFixedSize(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE)
            end_spacer.setStyleSheet("background:transparent;")
            layout.addWidget(end_spacer)

        self.set_selected(bool(node.get("selected")))

    # ------------------------------------------------------------ helpers

    def _make_icon_toggle(self, icon_fn, checked, active_color, tooltip):
        button = QtWidgets.QToolButton(self)
        button.setCheckable(True)
        button.setChecked(bool(checked))
        button.setAutoRaise(True)
        button.setFixedSize(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE)
        icon_dim = int(TOGGLE_BUTTON_SIZE * 0.8)
        button.setIconSize(QtCore.QSize(icon_dim, icon_dim))
        button.setToolTip(tooltip)
        button.setCursor(QtCore.Qt.PointingHandCursor)

        def _refresh(is_checked):
            button.setIcon(icon_fn(icon_dim, active_color if is_checked else "#8a8a8a"))

        button.toggled.connect(_refresh)
        _refresh(button.isChecked())
        return button

    def _apply_name_style(self, selected):
        if self.name_button.is_renaming():
            return
        color = "#ffffff" if selected else ("#eaeaea" if self.is_group else "#d0d0d0")
        weight = "bold" if self.is_group else "normal"
        self.name_button.setStyleSheet(
            "QPushButton{background:transparent;color:%s;border:none;text-align:left;"
            "padding-left:4px;font-weight:%s;}" % (color, weight)
        )

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("rowSelected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self._apply_name_style(self._selected)

    def bind_to_item(self, list_widget, item):
        self._list_widget = list_widget
        self._item = item

    def item(self):
        return self._item

    def begin_drag(self):
        if self._list_widget is not None and self._item is not None:
            self._list_widget.start_drag_for_item(self._item)

    def _refresh_collapse_icon(self):
        arrow_color = _contrast_color(self._border_hex) if self._border_hex else "#c0c0c0"
        self.collapse_button.setIcon(_arrow_icon(wutil.DPI(9), expanded=not self._collapsed, color=arrow_color))
        self.collapse_button.setToolTip("Expand group" if self._collapsed else "Collapse group")

    def _on_collapse_clicked(self, *_args):
        self._collapsed = not self._collapsed
        self._refresh_collapse_icon()
        self.collapseToggled.emit(self.layer_name, self._collapsed)

    def _refresh_group_icon(self):
        group_icon_path = icons.get("layer_group")
        color = self._own_color_hex or "#bdbdbd"
        icon_dim = wutil.DPI(16)
        pixmap = _tinted_pixmap(group_icon_path, icon_dim, color)
        self.type_button.setIcon(QtGui.QIcon(pixmap) if not pixmap.isNull() else QtGui.QIcon())
        self.type_button.setIconSize(QtCore.QSize(icon_dim, icon_dim))

    def _open_color_menu(self, *_args):
        menu = QtWidgets.QMenu(self)
        swatch_size = wutil.DPI(12)
        default_hex = COLORS.selection.get(controller.DEFAULT_GROUP_COLOR_SUFFIX).hex
        default_action = menu.addAction(_color_swatch_icon(swatch_size, default_hex), "Default (Light Gray)")
        default_action.triggered.connect(lambda *_: self.colorChosen.emit(self.layer_name, None))
        menu.addSeparator()
        for color in COLORS.selection.all:
            action = menu.addAction(_color_swatch_icon(swatch_size, color.hex), color.label)
            action.triggered.connect(lambda *_, s=color.suffix: self.colorChosen.emit(self.layer_name, s))
        exec_fn = getattr(menu, "exec", None) or getattr(menu, "exec_", None)
        if exec_fn:
            exec_fn(QtGui.QCursor.pos())

    # ------------------------------------------------------------ events

    def mousePressEvent(self, event):
        # Clicking anywhere on the row's own background (not a child
        # control) still selects the layer.
        self._emit_clicked()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        self.contextRequested.emit(self.layer_name, event.globalPos())

    def _emit_clicked(self, *_args):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        self.clicked.emit(self.layer_name, modifiers)

    def _on_weight_changed(self, value):
        self.weightEdited.emit(self.layer_name, value / 100.0)

    def _on_renamed(self, _payload, new_name):
        self.renamed.emit(self.layer_name, new_name)

    def _on_type_clicked(self, *_args):
        self.overrideToggled.emit(self.layer_name, not self._override)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class AnimationLayersWindow(FloatingToolWindowMixin, customDialogs.QFlatPinnableToolBarPopupDialog):
    """Floating manager for the scene's animation layers and groups.

    Uses the same shell every other toolbar popup shares (see
    ``QFlatPinnableToolBarPopupDialog``): opens as a transient popup that
    pins into a normal window (native bottom-bar Close button) once dragged
    or opened non-transiently, with the icon+title header built the same way
    for every tool -- ``QFlatToolBarDialog`` renders it from ``self.title`` /
    ``self.icon``, matching Bake Custom Interval and Attribute Switcher's own
    selection header exactly rather than re-implementing it here.
    """

    REFRESH_KEY = "animation_layers_window_refresh"

    def __init__(self, parent=None, popup=False):
        self.title = "Animation Layers"
        self.icon = icons.get("animation_layers")

        super().__init__(
            parent=parent,
            popup=popup,
            bottom_bar_kwargs={"margins": 0, "spacing": 2},
        )
        self.setObjectName(WINDOW_NAME)
        self.title_label.setText(self.title)
        # 3:5 (height:width) aspect ratio, horizontal.
        self.resize(wutil.DPI(500), wutil.DPI(300))
        self.setMinimumSize(wutil.DPI(360), wutil.DPI(216))
        self.mainLayout.setContentsMargins(0, 0, 0, wutil.DPI(4))

        self._rows = {}
        self._selected_names = set()
        self._last_anchor = None
        self._collapsed_groups = set()

        self._build_ui()
        self._init_floating_window_behavior()
        self.adjustSize()
        self._restore_saved_geometry()
        self.apply_stay_on_top_setting()
        self.update_transparency_state(False)
        self._connect_runtime()
        self._install_click_outside_filter()
        self.refresh()

    # ------------------------------------------------------------ layout

    def _build_ui(self):
        # A plain toolbar row under the title -- unlike Selection Sets, this
        # window has no user-customizable/hideable button set, so it skips
        # QFlatSectionWidget and just lays the buttons out directly.
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(6), wutil.DPI(6))
        toolbar_layout.setSpacing(wutil.DPI(2))

        self.new_layer_button = self._create_toolbar_button(
            icons.add, "New Layer From Selected",
            self._create_layer_from_selection,
            description="Create a new animation layer from the current selection.",
        )
        self.new_group_button = self._create_toolbar_button(
            icons.get("layer_group"), "New Group", self._create_group,
            description="Group the selected layers under a new layer with its own weight.",
        )
        self.merge_button = self._create_toolbar_button(
            icons.get("layer_merge"), "Smart Merge Selected", self._merge_selected,
            description="Bake the selected layers together, sampling only the frames where they actually have weight.",
        )
        self.delete_button = self._create_toolbar_button(
            icons.trash, "Delete Selected", self._delete_selected,
            description="Delete the selected layers or groups.",
        )
        for button in (self.new_layer_button, self.new_group_button, self.merge_button, self.delete_button):
            toolbar_layout.addWidget(button)

        toolbar_layout.addStretch(1)

        self.refresh_button = self._create_toolbar_button(
            icons.refresh, "Refresh", self.refresh,
            description="Reload the layer list from the current scene.",
        )
        self.export_button = self._create_toolbar_button(
            icons.get("export"), "Export Selected", self._export_selected,
            description="Export the selected layers (and their animation) to a file.",
        )
        self.import_button = self._create_toolbar_button(
            icons.get("import"), "Import Layers", self._import_layers,
            description="Import previously exported animation layers.",
        )
        for button in (self.refresh_button, self.export_button, self.import_button):
            toolbar_layout.addWidget(button)

        self.mainLayout.addLayout(toolbar_layout)

        self.list_widget = LayerListWidget(self)
        self.list_widget.layerDropped.connect(self._on_layer_dropped)
        self.list_widget.emptyAreaClicked.connect(self._on_empty_area_clicked)
        self.mainLayout.addWidget(self.list_widget, 1)

        self.empty_label = QtWidgets.QLabel("No animation layers in this scene.", self)
        self.empty_label.setAlignment(QtCore.Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color:#7b7b7b;background:transparent;padding:12px;")
        self.empty_label.setVisible(False)
        self.mainLayout.addWidget(self.empty_label)

    def _create_toolbar_button(self, icon, tooltip, callback, description=None):
        button = cw.create_tool_button_from_data(
            {"label": tooltip, "icon": icon, "tooltip": tooltip, "description": description},
            callback=None,
        )
        button.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        button.setIconSize(QtCore.QSize(wutil.DPI(17), wutil.DPI(17)))
        button.connect_tool(callback)
        return button

    # ------------------------------------------------------------ refresh

    def refresh(self, *_args):
        if not wutil.is_valid_widget(self):
            return
        tree = controller.layer_tree()
        selection_before = set(self._selected_names)
        self.list_widget.clear()
        self._rows = {}

        # Show BaseAnimation by itself once it exists, even with zero real
        # layers under it yet -- only truly nothing (no root at all) falls
        # back to the empty-state message.
        if tree is None:
            self.empty_label.setVisible(True)
            self.list_widget.setVisible(False)
            self._selected_names = set()
            return

        self.empty_label.setVisible(False)
        self.list_widget.setVisible(True)

        flat = self._filter_visible(controller.flatten_tree(tree))
        for row_index, node in enumerate(flat):
            item = QtWidgets.QListWidgetItem(self.list_widget)
            item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT))
            row = LayerRowWidget(
                node, node.get("_depth", 0), row_index,
                collapsed=node["name"] in self._collapsed_groups,
                parent=self.list_widget,
            )
            row.bind_to_item(self.list_widget, item)
            row.clicked.connect(self._on_row_clicked)
            row.lockToggled.connect(self._on_lock_toggled)
            row.muteToggled.connect(self._on_mute_toggled)
            row.overrideToggled.connect(self._on_override_toggled)
            row.weightEdited.connect(self._on_weight_edited)
            row.renamed.connect(self._on_renamed)
            row.contextRequested.connect(self._on_row_context_menu)
            row.collapseToggled.connect(self._on_group_collapse_toggled)
            row.colorChosen.connect(self._on_group_color_chosen)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
            self._rows[node["name"]] = row
            row.set_selected(node["name"] in selection_before)

        self._selected_names = {name for name in selection_before if name in self._rows}

    def _filter_visible(self, flat):
        """Drop every node nested under a collapsed group.

        ``flatten_tree`` is a depth-first pre-order walk, so a collapsed
        group's descendants are exactly the contiguous run right after it
        whose depth is greater than its own -- once depth drops back to (or
        below) that level, we've left the collapsed subtree.
        """
        visible = []
        skip_depth = None
        for node in flat:
            depth = node.get("_depth", 0)
            if skip_depth is not None:
                if depth > skip_depth:
                    continue
                skip_depth = None
            visible.append(node)
            if node.get("is_group") and node["name"] in self._collapsed_groups:
                skip_depth = depth
        return visible

    # ------------------------------------------------------------ selection

    def _set_selection(self, names):
        self._selected_names = set(names)
        for name, row in self._rows.items():
            row.set_selected(name in self._selected_names)

    def _on_empty_area_clicked(self):
        self._set_selection(set())
        self._last_anchor = None

    def _on_row_clicked(self, layer_name, modifiers):
        flat_names = list(self._rows.keys())
        if modifiers & QtCore.Qt.ControlModifier:
            selected = set(self._selected_names)
            if layer_name in selected:
                selected.discard(layer_name)
            else:
                selected.add(layer_name)
            self._set_selection(selected)
            self._last_anchor = layer_name
        elif modifiers & QtCore.Qt.ShiftModifier and self._last_anchor in self._rows:
            try:
                start = flat_names.index(self._last_anchor)
                end = flat_names.index(layer_name)
            except ValueError:
                start = end = flat_names.index(layer_name)
            lo, hi = sorted((start, end))
            self._set_selection(flat_names[lo:hi + 1])
        else:
            self._set_selection({layer_name})
            self._last_anchor = layer_name

        controller.select_layer(layer_name, weight_attribute=True)

    # ------------------------------------------------------------ per-row mutations

    def _on_lock_toggled(self, layer_name, checked):
        # Refresh afterwards, not just on this one row -- a group cascades
        # its lock state onto every child's row, and an unlock blocked by a
        # still-locked ancestor group needs this row's own checkbox reverted
        # back to checked rather than left showing the click that didn't
        # actually take effect.
        with toolCommon.tool_operation(tool_id="animation_layers_lock", label="Lock Animation Layer", undo=True, progress=False):
            controller.set_lock(layer_name, checked)
        self.refresh()

    def _on_mute_toggled(self, layer_name, checked):
        with toolCommon.tool_operation(tool_id="animation_layers_mute", label="Mute Animation Layer", undo=True, progress=False):
            controller.set_mute(layer_name, checked)

    def _on_override_toggled(self, layer_name, override):
        with toolCommon.tool_operation(tool_id="animation_layers_override", label="Change Layer Type", undo=True, progress=False):
            controller.set_override(layer_name, override)
        self.refresh()

    def _on_weight_edited(self, layer_name, weight):
        with toolCommon.tool_operation(tool_id="animation_layers_weight", label="Set Layer Weight", undo=True, progress=False):
            controller.set_weight(layer_name, weight)

    def _on_renamed(self, layer_name, new_name):
        with toolCommon.tool_operation(tool_id="animation_layers_rename", label="Rename Animation Layer", undo=True, progress=False):
            renamed = controller.rename_layer(layer_name, new_name)
        if layer_name in self._selected_names:
            self._selected_names.discard(layer_name)
            self._selected_names.add(renamed)
        self.refresh()

    def _on_layer_dropped(self, layer_name):
        row = self._rows.get(layer_name)
        if row is None or row.item() is None:
            return
        index = self.list_widget.row(row.item())
        previous_item = self.list_widget.item(index - 1) if index > 0 else None
        next_item = self.list_widget.item(index + 1) if index < self.list_widget.count() - 1 else None
        previous_widget = self.list_widget.itemWidget(previous_item) if previous_item is not None else None
        next_widget = self.list_widget.itemWidget(next_item) if next_item is not None else None

        with toolCommon.tool_operation(tool_id="animation_layers_reorder", label="Reorder Animation Layers", undo=True, progress=False):
            if previous_widget is not None:
                controller.move_layer_to_parent(layer_name, controller.get_parent(previous_widget.layer_name))
                controller.reorder_layer(layer_name, previous_widget.layer_name, before=False)
            elif next_widget is not None:
                controller.move_layer_to_parent(layer_name, controller.get_parent(next_widget.layer_name))
                controller.reorder_layer(layer_name, next_widget.layer_name, before=True)
        self.refresh()

    def _on_group_collapse_toggled(self, layer_name, collapsed):
        if collapsed:
            self._collapsed_groups.add(layer_name)
        else:
            self._collapsed_groups.discard(layer_name)
        self.refresh()

    def _on_group_color_chosen(self, layer_name, suffix):
        with toolCommon.tool_operation(tool_id="animation_layers_color", label="Set Group Color", undo=True, progress=False):
            controller.set_group_color(layer_name, suffix)
        self.refresh()

    # ------------------------------------------------------------ toolbar actions

    def _create_layer_from_selection(self, *_args):
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_new", label="Create Animation Layer", undo=True, progress=False):
                controller.create_layer_from_selection()
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))
            return
        self.refresh()

    def _create_group(self, *_args):
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_new_group", label="Group Animation Layers", undo=True, progress=False):
                controller.create_group(member_names=list(self._selected_names))
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))
            return
        self.refresh()

    def _merge_selected(self, *_args):
        selected = list(self._selected_names)
        if len(selected) < 2:
            wutil.make_inViewMessage("Select two or more animation layers to merge")
            return
        try:
            with toolCommon.tool_operation(
                tool_id="animation_layers_merge",
                label="Smart Merge Animation Layers",
                undo=True,
                progress=True,
            ) as operation:
                operation.start()
                controller.smart_merge_layers(selected, operation=operation)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))
            return
        self._selected_names = set()
        self.refresh()

    def _delete_selected(self, *_args):
        selected = list(self._selected_names)
        if not selected:
            wutil.make_inViewMessage("Select one or more layers to delete")
            return
        clicked = customDialogs.QFlatConfirmDialog.question(
            self,
            "Delete Animation Layers",
            "Delete {} animation layer(s)?".format(len(selected)),
            buttons=[customDialogs.QFlatConfirmDialog.Yes, customDialogs.QFlatConfirmDialog.Cancel],
            highlight=customDialogs.QFlatConfirmDialog.Yes,
            title="Delete layers?",
            icon=icons.warning,
        )
        if clicked != customDialogs.QFlatConfirmDialog.Yes:
            return
        with toolCommon.tool_operation(tool_id="animation_layers_delete", label="Delete Animation Layers", undo=True, progress=False):
            for name in selected:
                controller.delete_layer(name, recursive=False)
        self._selected_names = set()
        self.refresh()

    def _export_selected(self, *_args):
        selected = list(self._selected_names)
        if not selected:
            wutil.make_inViewMessage("Select one or more layers to export")
            return
        with toolCommon.tool_operation(tool_id="animation_layers_export", label="Export Animation Layers", undo=False) as operation:
            try:
                controller.export_selected(selected, operation=operation)
            except RuntimeError as exc:
                wutil.make_inViewMessage(str(exc))

    def _import_layers(self, *_args):
        with toolCommon.tool_operation(tool_id="animation_layers_import", label="Import Animation Layers", undo=True) as operation:
            controller.import_from_file(operation=operation)
        self.refresh()

    # ------------------------------------------------------------ context menu

    def _on_row_context_menu(self, layer_name, global_pos):
        if layer_name not in self._selected_names:
            self._set_selection({layer_name})
        menu = cw.OpenMenuWidget(self)
        selected = list(self._selected_names)

        menu.addAction(
            QtGui.QIcon(icons.add), "New Layer From Selected Objects",
            description="Create a new animation layer from the current scene selection.",
            callback=lambda *_: self._create_layer_from_selection(),
        )
        group_icon = icons.get("layer_group")
        menu.addAction(
            QtGui.QIcon(group_icon) if group_icon else QtGui.QIcon(), "Group Selected Layers",
            description="Group the selected layers under a new layer with its own weight.",
            callback=lambda *_: self._create_group(),
        )
        if len(selected) >= 2:
            merge_icon = icons.get("layer_merge")
            menu.addAction(
                QtGui.QIcon(merge_icon) if merge_icon else QtGui.QIcon(), "Smart Merge",
                description="Bake the selected layers together, sampling only where they have weight.",
                callback=lambda *_: self._merge_selected(),
            )
        menu.addSeparator()
        menu.addAction(
            QtGui.QIcon(icons.rename), "Rename",
            description="Rename this layer.",
            callback=lambda *_: self._start_rename(layer_name),
        )
        menu.addAction(
            "Select Objects",
            description="Select this layer's member objects.",
            callback=lambda *_: self._select_layer_objects(layer_name),
        )
        menu.addAction(
            "Add Selected Objects",
            description="Add the current scene selection to this layer.",
            callback=lambda *_: self._add_selected_to_layer(layer_name),
        )
        menu.addAction(
            "Remove Selected Objects",
            description="Remove the current scene selection from this layer.",
            callback=lambda *_: self._remove_selected_from_layer(layer_name),
        )
        menu.addSeparator()
        menu.addAction(
            "Remove From Group",
            description="Move the selected layers back to the top level.",
            callback=lambda *_: self._ungroup_selected(),
        )
        menu.addSeparator()
        menu.addAction(
            QtGui.QIcon(icons.trash), "Delete",
            description="Delete the selected layers.",
            callback=lambda *_: self._delete_selected(),
        )
        exec_fn = getattr(menu, "exec", None) or getattr(menu, "exec_", None)
        if exec_fn:
            exec_fn(global_pos)

    def _start_rename(self, layer_name):
        row = self._rows.get(layer_name)
        if row is not None:
            row.name_button.start_inline_rename()

    def _select_layer_objects(self, layer_name):
        try:
            controller.select_layer_objects(layer_name)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))

    def _add_selected_to_layer(self, layer_name):
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_add_members", label="Add To Animation Layer", undo=True, progress=False):
                controller.add_selected_to_layer(layer_name)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))

    def _remove_selected_from_layer(self, layer_name):
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_remove_members", label="Remove From Animation Layer", undo=True, progress=False):
                controller.remove_selected_from_layer(layer_name)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))

    def _ungroup_selected(self, *_args):
        with toolCommon.tool_operation(tool_id="animation_layers_ungroup", label="Remove From Group", undo=True, progress=False):
            for name in list(self._selected_names):
                controller.move_layer_to_parent(name, None)
        self.refresh()

    # ------------------------------------------------------------ floating window hooks

    def _auto_transparency_setting_enabled(self):
        return animationLayersApi.is_auto_transparency_enabled()

    def _stays_on_top_setting_enabled(self):
        return animationLayersApi.is_stay_on_top()

    def _geometry_settings_key(self):
        return "animation_layers_geometry"

    def _geometry_settings_namespace(self):
        return animationLayersApi.SETTINGS_NAMESPACE

    # ------------------------------------------------------------ live sync

    def _connect_runtime(self):
        manager = runtime.get_runtime_manager()
        # "Undo"/"Redo" so an undone/redone layer create/delete/reorder/etc.
        # is reflected immediately, same as a live scene edit -- all four
        # share one key so closeEvent()'s single disconnect_callbacks() call
        # tears them all down together.
        for event_name in ("animLayerRebuild", "animLayerRefresh", "Undo", "Redo"):
            manager.add_scriptjob(event=event_name, key=self.REFRESH_KEY, callback=self._on_scene_layers_changed)

    def _on_scene_layers_changed(self, *_args):
        if wutil.is_valid_widget(self) and self.isVisible():
            self.refresh()

    # ------------------------------------------------------------ focus handling

    def _install_click_outside_filter(self):
        # Same app-level installEventFilter/removeEventFilter idiom
        # ``core.runtime``'s modifier-state watcher uses -- the weight
        # spinbox needs "strong" focus so scrolling/typing works while it's
        # focused, but that alone doesn't make an unrelated click elsewhere
        # release it (QAbstractSpinBox only loses focus to a *focusable*
        # sibling); this makes any outside click do that explicitly.
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.installEventFilter(self)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                focus_widget = QtWidgets.QApplication.focusWidget()
                if (
                    isinstance(focus_widget, QtWidgets.QAbstractSpinBox)
                    and self.isAncestorOf(focus_widget)
                    and obj is not focus_widget
                    and not (isinstance(obj, QtWidgets.QWidget) and focus_widget.isAncestorOf(obj))
                ):
                    focus_widget.clearFocus()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        return False

    # ------------------------------------------------------------ lifecycle

    def closeEvent(self, event):
        try:
            runtime.get_runtime_manager().disconnect_callbacks(self.REFRESH_KEY)
        except Exception:
            pass
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.removeEventFilter(self)
        except Exception:
            pass
        animationLayersApi._emit_animation_layers_window_state(False)
        super().closeEvent(event)

    def hideEvent(self, event):
        animationLayersApi._emit_animation_layers_window_state(False)
        super().hideEvent(event)
