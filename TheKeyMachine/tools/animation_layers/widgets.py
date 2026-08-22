"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Modified by: Alehaaaa / alehaaaa.github.io



"""

"""The Animation Layers window: a floating, indented, drag-reorderable list of the scene's animation layers and groups."""

from TheKeyMachine.core.Qt import QtCore, QtGui, QtSvg, QtWidgets  # type: ignore
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
ICON_BUTTON_RADIUS = wutil.DPI(4)
DRAG_HANDLE_WIDTH = wutil.DPI(16)
WEIGHT_COLUMN_WIDTH = wutil.DPI(46)
TYPE_ICON_SIZE = wutil.DPI(16)
COLLAPSE_ICON_SIZE = wutil.DPI(9)
# Qt5/6 renamed QMenu.exec_() to exec(); fall back to whichever exists.
_STALE_WIDGET_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)


def _popup_menu(menu, pos):
    exec_fn = getattr(menu, "exec", None) or getattr(menu, "exec_", None)
    if exec_fn:
        exec_fn(pos)


# ---------------------------------------------------------------------------
# Small painted icons
# ---------------------------------------------------------------------------


def _screen_dpr():
    screen = QtGui.QGuiApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0


def _rasterize_svg(icon_path, pixel_dim):
    """Render an SVG file into an untagged QPixmap of exactly pixel_dim x
    pixel_dim device pixels (devicePixelRatio left at the default 1).

    Callers set the pixmap's real devicePixelRatio themselves, as the very
    last step after any further painting (e.g. _tinted_pixmap's SourceIn
    recolor) -- tagging it *before* that would make Qt mix logical and
    physical coordinates for the remaining painter calls on this pixmap,
    silently shrinking the result into one corner of its own buffer. Matches
    ``customDialogs``'s own svg icon loader.
    """
    if not icon_path:
        return QtGui.QPixmap()
    renderer = QtSvg.QSvgRenderer(icon_path)
    if not renderer.isValid():
        return QtGui.QPixmap()
    pixmap = QtGui.QPixmap(pixel_dim, pixel_dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    renderer.render(painter, QtCore.QRectF(0, 0, pixel_dim, pixel_dim))
    painter.end()
    return pixmap


def _flat_pixmap(icon_path, size):
    """Load an icon file as-is, no runtime tint -- for icons that only ever
    appear in one fixed, baked-into-the-file color. Rendered at the screen's
    device pixel ratio (see _rasterize_svg) so it stays crisp on HiDPI displays,
    instead of the flat 1x a plain QPixmap(path) load would give."""
    dim = max(1, int(size))
    dpr = _screen_dpr()
    pixmap = _rasterize_svg(icon_path, max(1, int(dim * dpr)))
    if not pixmap.isNull():
        pixmap.setDevicePixelRatio(dpr)
    return pixmap


def _grip_icon(size):
    """2x3 dot-grid pixmap for the row drag handle (single fixed color, baked into grip.svg)."""
    return _flat_pixmap(icons.get("grip"), size)


def _text_badge_icon(is_override, size):
    """Additive/Override type badge -- each variant is a fixed letter+color
    baked into its own file (badge_additive.svg/badge_override.svg), same as _grip_icon."""
    return QtGui.QIcon(_flat_pixmap(icons.get("badge_override" if is_override else "badge_additive"), size))


def _tinted_pixmap(icon_path, size, color):
    """Recolor a flat-fill SVG icon via SourceIn compositing, rendered at the
    screen's device pixel ratio (see _rasterize_svg) so tinted icons stay
    crisp on HiDPI displays instead of the softer 1x a plain QPixmap(path)
    load would give."""
    dim = max(1, int(size))
    dpr = _screen_dpr()
    pixel_dim = max(1, int(dim * dpr))
    pixmap = _rasterize_svg(icon_path, pixel_dim)
    if pixmap.isNull():
        return pixmap
    tinted = QtGui.QPixmap(pixmap.size())
    tinted.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QtGui.QColor(color))
    painter.end()
    tinted.setDevicePixelRatio(dpr)
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
    """Group row collapse/expand triangle."""
    return QtGui.QIcon(_tinted_pixmap(icons.get("arrow_down" if expanded else "arrow_right"), size, color))


def _lock_icon(size, color, locked=True):
    """Padlock glyph for the Lock toggle; *locked* picks open vs closed shackle."""
    return QtGui.QIcon(_tinted_pixmap(icons.get("lock" if locked else "lock_open"), size, color))


def _mute_icon(size, color, muted=True):
    """Speaker-with-slash glyph for the Mute toggle. *muted* is unused (only
    one glyph exists, unlike _lock_icon) -- kept so _make_icon_toggle can
    call either icon_fn the same way."""
    return QtGui.QIcon(_tinted_pixmap(icons.get("mute"), size, color))


def _contrast_color(hex_color):
    """Pick black or off-white text/icon color for readability over ``hex_color``."""
    color = QtGui.QColor(hex_color)
    luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255.0
    return "#1a1a1a" if luminance > 0.55 else "#f0f0f0"


def _shade(hex_color, factor):
    """Darken (factor > 100) or lighten (factor < 100) a hex color."""
    return QtGui.QColor(hex_color).darker(int(factor)).name()


NEUTRAL_BUTTON_BG = "#3c3c3c"
NEUTRAL_BUTTON_BORDER = "#525252"
NEUTRAL_BUTTON_HOVER_BG = "#484848"
NEUTRAL_BUTTON_HOVER_BORDER = "#606060"


def _row_icon_button_stylesheet(accent_color, filled=False):
    """Shared chip stylesheet for row icon buttons. ``filled`` tints indicator
    buttons (badge/folder) by accent color; toggles stay neutral until checked."""
    idle_bg = _shade(accent_color, 260) if filled else NEUTRAL_BUTTON_BG
    idle_border = accent_color if filled else NEUTRAL_BUTTON_BORDER
    hover_bg = _shade(accent_color, 200) if filled else NEUTRAL_BUTTON_HOVER_BG
    hover_border = accent_color if filled else NEUTRAL_BUTTON_HOVER_BORDER
    checked_bg = _shade(accent_color, 220)
    checked_hover_bg = _shade(accent_color, 170)
    return (
        "QToolButton{background:%s;border:1px solid %s;border-radius:%dpx;}"
        "QToolButton:hover{background:%s;border:1px solid %s;}"
        "QToolButton:checked{background:%s;border:1px solid %s;}"
        "QToolButton:checked:hover{background:%s;}"
    ) % (idle_bg, idle_border, ICON_BUTTON_RADIUS, hover_bg, hover_border, checked_bg, accent_color, checked_hover_bg)


# ---------------------------------------------------------------------------
# List + drag/drop
# ---------------------------------------------------------------------------


class _DropIndicator(QtWidgets.QFrame):
    """Line marking where a dragged row will land, painted manually since rows are opaque widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(wutil.DPI(2))
        self.setStyleSheet("background-color: %s;" % SELECTED_COLOR)
        self.hide()


class LayerListWidget(QtWidgets.QListWidget):
    """A flat, indented, drag-reorderable list of animation layer rows. Nesting is
    expressed via indentation, not QTreeWidget; drags start only from the row's grip handle."""

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
        # itemAt() None means the click landed on empty list space.
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
        self.setFixedSize(DRAG_HANDLE_WIDTH, ROW_HEIGHT)
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

        # Gutter: group shows arrow on its own color; nested layer gets an inherited color bar; root/ungrouped is blank.
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
            self.collapse_button.setIconSize(QtCore.QSize(COLLAPSE_ICON_SIZE, COLLAPSE_ICON_SIZE))
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
            layout.addWidget(self._spacer(DRAG_HANDLE_WIDTH, ROW_HEIGHT))
        else:
            self.handle = _DragHandle(self, self)
            layout.addWidget(self.handle)

        self.lock_button = self._make_icon_toggle(
            _lock_icon, node.get("lock"), "#c9a76b", "Lock -- prevents keying this layer"
        )
        self.lock_button.toggled.connect(lambda checked: self.lockToggled.emit(self.layer_name, checked))
        layout.addWidget(self.lock_button)

        if self.is_root:
            # BaseAnimation can't be muted -- hidden, not disabled; spacer keeps columns aligned.
            self.mute_button = None
            layout.addWidget(self._spacer(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE))
        else:
            self.mute_button = self._make_icon_toggle(
                _mute_icon, node.get("mute"), "#c96b68", "Mute -- disables this layer's effect"
            )
            self.mute_button.toggled.connect(lambda checked: self.muteToggled.emit(self.layer_name, checked))
            layout.addWidget(self.mute_button)

        # Indent pushes the name only; lock/mute stay column-aligned.
        if depth:
            indent = QtWidgets.QWidget(self)
            indent.setFixedWidth(INDENT_WIDTH * depth)
            indent.setStyleSheet("background:transparent;")
            layout.addWidget(indent)

        self.name_button = cw.InlineRenameButton(
            node["name"], self,
            rename_alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            rename_margins=(wutil.DPI(2), wutil.DPI(2), wutil.DPI(6), wutil.DPI(2)),
            rename_style_extra=(
                "QPushButton{background-color:%s;border:1px solid %s;border-radius:%dpx;}"
                % (NEUTRAL_BUTTON_BG, NEUTRAL_BUTTON_BORDER, ICON_BUTTON_RADIUS)
            ),
        )
        self.name_button.setFlat(True)
        self.name_button.setFixedHeight(ROW_HEIGHT)
        self.name_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.name_button.setProperty("tkm_text_color", "#ffffff")
        self.name_button.set_rename_target(node["name"], node["name"], self._on_renamed)
        self.name_button.clicked.connect(self._emit_clicked)
        layout.addWidget(self.name_button, 1)

        if self.is_root:
            # BaseAnimation has no weight; spacer keeps columns aligned.
            self.weight_spin = None
            layout.addWidget(self._spacer(WEIGHT_COLUMN_WIDTH, ROW_HEIGHT))
        else:
            self.weight_spin = cw.QFlatDoubleSpinBox(
                decimals=0,
                minimum=0.0,
                maximum=100.0,
                value=round(float(node.get("weight", 1.0)) * 100.0),
                single_step=5.0,
            )
            self.weight_spin.setFixedWidth(WEIGHT_COLUMN_WIDTH)
            self.weight_spin.setFixedHeight(wutil.DPI(18))
            self.weight_spin.setSuffix("%")
            self.weight_spin.setAlignment(QtCore.Qt.AlignCenter)
            self.weight_spin.setToolTip("Layer weight")
            self.weight_spin.setFocusPolicy(QtCore.Qt.StrongFocus)
            # Avoids flooding the undo stack with one entry per keystroke.
            self.weight_spin.setKeyboardTracking(False)
            self.weight_spin.valueChanged.connect(self._on_weight_changed)
            layout.addWidget(self.weight_spin)

        # End-of-row: group -> color-menu folder icon; layer -> Additive/Override badge; root -> spacer.
        if self.is_group:
            self._own_color_hex = self._border_hex if self._is_color_owner else None
            self.type_button = self._make_type_button(self._own_color_hex or "#8a8a8a")
            self._refresh_group_icon()
            self.type_button.setToolTip("Group -- click to set its color.")
            self.type_button.clicked.connect(self._open_color_menu)
            layout.addWidget(self.type_button)
        elif not self.is_root:
            badge_color = "#c9a76b" if self._override else "#689d85"
            self.type_button = self._make_type_button(badge_color)
            self.type_button.setIcon(_text_badge_icon(self._override, TYPE_ICON_SIZE))
            self.type_button.setToolTip(
                "Override layer -- replaces the value below it. Click to switch to Additive."
                if self._override else
                "Additive layer -- adds on top of the value below it. Click to switch to Override."
            )
            self.type_button.clicked.connect(self._on_type_clicked)
            layout.addWidget(self.type_button)
        else:
            self.type_button = None
            layout.addWidget(self._spacer(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE))

        self.set_selected(bool(node.get("selected")))

    # ------------------------------------------------------------ helpers

    def _spacer(self, width, height):
        """Blank placeholder filling a column a root row has no real widget for."""
        widget = QtWidgets.QWidget(self)
        widget.setFixedSize(width, height)
        widget.setStyleSheet("background:transparent;")
        return widget

    def _make_type_button(self, accent_color):
        """Shared chip setup for the end-of-row group-folder/Additive-Override-badge button."""
        button = QtWidgets.QToolButton(self)
        button.setAutoRaise(False)
        button.setStyleSheet(_row_icon_button_stylesheet(accent_color, filled=True))
        button.setFixedSize(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE)
        button.setIconSize(QtCore.QSize(TYPE_ICON_SIZE, TYPE_ICON_SIZE))
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _make_icon_toggle(self, icon_fn, checked, active_color, tooltip):
        button = QtWidgets.QToolButton(self)
        button.setCheckable(True)
        button.setChecked(bool(checked))
        # autoRaise off; explicit stylesheet draws its own chip instead of platform chrome.
        button.setAutoRaise(False)
        button.setStyleSheet(_row_icon_button_stylesheet(active_color))
        button.setFixedSize(TOGGLE_BUTTON_SIZE, TOGGLE_BUTTON_SIZE)
        icon_dim = int(TOGGLE_BUTTON_SIZE * 0.8)
        button.setIconSize(QtCore.QSize(icon_dim, icon_dim))
        button.setToolTip(tooltip)
        button.setCursor(QtCore.Qt.PointingHandCursor)

        def _refresh(is_checked):
            button.setIcon(icon_fn(icon_dim, active_color if is_checked else "#8a8a8a", is_checked))

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

    def begin_drag(self):
        if self._list_widget is not None and self._item is not None:
            self._list_widget.start_drag_for_item(self._item)

    def _refresh_collapse_icon(self):
        arrow_color = _contrast_color(self._border_hex) if self._border_hex else "#c0c0c0"
        self.collapse_button.setIcon(_arrow_icon(COLLAPSE_ICON_SIZE, expanded=not self._collapsed, color=arrow_color))
        self.collapse_button.setToolTip("Expand group" if self._collapsed else "Collapse group")

    def _on_collapse_clicked(self, *_args):
        self._collapsed = not self._collapsed
        self._refresh_collapse_icon()
        self.collapseToggled.emit(self.layer_name, self._collapsed)

    def _refresh_group_icon(self):
        color = self._own_color_hex or "#bdbdbd"
        pixmap = _tinted_pixmap(icons.get("layer_group"), TYPE_ICON_SIZE, color)
        self.type_button.setIcon(QtGui.QIcon(pixmap) if not pixmap.isNull() else QtGui.QIcon())

    def _open_color_menu(self, *_args):
        # Parented to the window, not the row -- refresh() can delete this row while the menu is open.
        menu = QtWidgets.QMenu(self.window())
        swatch_size = wutil.DPI(12)
        default_hex = COLORS.selection.get(controller.DEFAULT_GROUP_COLOR_SUFFIX).hex
        default_action = menu.addAction(_color_swatch_icon(swatch_size, default_hex), "Default (Light Gray)")
        default_action.triggered.connect(lambda *_: self.colorChosen.emit(self.layer_name, None))
        menu.addSeparator()
        for color in COLORS.selection.all:
            action = menu.addAction(_color_swatch_icon(swatch_size, color.hex), color.label)
            action.triggered.connect(lambda *_, s=color.suffix: self.colorChosen.emit(self.layer_name, s))
        _popup_menu(menu, QtGui.QCursor.pos())

    # ------------------------------------------------------------ events

    def mousePressEvent(self, event):
        # Clicking the row background also selects it.
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
    """Floating manager window for the scene's animation layers and groups."""

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
        self.setMinimumSize(wutil.DPI(380), wutil.DPI(140))
        self.mainLayout.setContentsMargins(0, 0, 0, wutil.DPI(4))

        self._rows = {}
        self._selected_names = set()
        self._last_anchor = None
        self._collapsed_groups = set()

        self._build_ui()
        self._init_floating_window_behavior()
        # Explicit resize after _build_ui() to set a fixed wide-and-short default shape.
        self.resize(wutil.DPI(560), wutil.DPI(190))
        self._restore_saved_geometry()
        self.apply_stay_on_top_setting()
        self.update_transparency_state(False)
        self._runtime_connected = False
        self._click_outside_filter_installed = False
        self._refreshing = False
        self.refresh()

    def _preferred_floating_size(self):
        # Fixed shape set in __init__ (resize()/_restore_saved_geometry()) --
        # see FloatingToolWindowMixin._preferred_floating_size()'s docstring
        # for why this beats the mixin's default adjustSize().
        return self.size()

    # ------------------------------------------------------------ layout

    def _build_ui(self):
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(6), wutil.DPI(6))
        toolbar_layout.setSpacing(wutil.DPI(2))

        # Left: pinnable section, same treatment Selection Sets' header
        # buttons get (see its QFlatSectionWidget usage) -- each button here
        # is individually hideable via a right-click "manage pinned tools"
        # menu. The right-side group below is plain/always-visible instead.
        self.toolbar_section = cw.QFlatSectionWidget(
            spacing=wutil.DPI(2),
            hiddeable=True,
            settings_namespace=animationLayersApi.SETTINGS_NAMESPACE,
        )
        section_layout = self.toolbar_section.layout()
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(wutil.DPI(2))

        self.new_layer_button = self._create_toolbar_button(
            icons.add, "New Layer From Selected",
            self._create_layer_from_selection,
            key="animation_layers_new_layer_btn",
            description="Create a new animation layer from the current selection.",
        )
        self.new_group_button = self._create_toolbar_button(
            icons.get("layer_group"), "New Group", self._create_group,
            key="animation_layers_new_group_btn",
            description="Group the selected layers under a new layer with its own weight.",
        )
        self.delete_button = self._create_toolbar_button(
            icons.trash, "Delete Selected", self._delete_selected,
            key="animation_layers_delete_btn",
            description="Delete the selected layers or groups.",
        )
        self.refresh_button = self._create_toolbar_button(
            icons.refresh, "Refresh", self.refresh,
            key="animation_layers_refresh_btn", default=False,
            description="Reload the layer list from the current scene.",
        )

        toolbar_layout.addWidget(self.toolbar_section)
        self._install_toolbar_context_menu()

        toolbar_layout.addStretch(1)

        # Right: plain, non-hideable actions (see toolbar_section comment above).
        self.merge_button = self._create_plain_toolbar_button(
            icons.get("layer_merge"), "Smart Merge Selected", self._merge_selected,
            description="Bake the selected layers together, sampling only the frames where they actually have weight.",
        )
        self.export_button = self._create_plain_toolbar_button(
            icons.get("export"), "Export Selected", self._export_selected,
            description="Export the selected layers (and their animation) to a file.",
        )
        self.import_button = self._create_plain_toolbar_button(
            icons.get("import"), "Import Layers", self._import_layers,
            description="Import previously exported animation layers.",
        )
        for button in (self.merge_button, self.export_button, self.import_button):
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

    def _create_toolbar_button(self, icon, tooltip, callback, key, default=True, description=None):
        button = self._make_toolbar_button(icon, tooltip, callback, description)
        self.toolbar_section.addWidget(
            button, label=tooltip, key=key, default=default,
            description=description or tooltip, tooltip=tooltip,
        )
        return button

    def _create_plain_toolbar_button(self, icon, tooltip, callback, description=None):
        # Same button, just not routed through the pinnable section.
        return self._make_toolbar_button(icon, tooltip, callback, description)

    def _make_toolbar_button(self, icon, tooltip, callback, description=None):
        button = cw.create_tool_button_from_data(
            {"label": tooltip, "icon": icon, "tooltip": tooltip, "description": description},
            callback=None,
        )
        button.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        button.setIconSize(QtCore.QSize(wutil.DPI(17), wutil.DPI(17)))
        button.connect_tool(callback)
        return button

    # ------------------------------------------------------------ toolbar pin menu

    def _install_toolbar_context_menu(self):
        # Right-clicking any left-side toolbar button (not just empty section
        # background) opens the same "manage pinned tools" menu -- mirrors
        # Selection Sets' own header pin-menu wiring. The right-side group
        # (Merge/Export/Import) isn't registered -- plain/non-hideable.
        self._toolbar_menu_targets = []
        self._register_toolbar_menu_target(self.toolbar_section)
        for button in (
            self.new_layer_button, self.new_group_button, self.delete_button, self.refresh_button,
        ):
            self._register_toolbar_menu_target(button)

    def _register_toolbar_menu_target(self, widget):
        if not widget:
            return
        widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(lambda pos, w=widget: self._open_toolbar_section_menu(pos, w))
        widget.installEventFilter(self)
        self._toolbar_menu_targets.append(widget)

    def _open_toolbar_section_menu(self, pos=None, widget=None):
        global_pos = widget.mapToGlobal(pos) if widget is not None and pos is not None else QtGui.QCursor.pos()
        self.toolbar_section.open_menu(global_pos)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.ContextMenu and obj in getattr(self, "_toolbar_menu_targets", []):
            self._open_toolbar_section_menu(event.pos(), obj)
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------ refresh

    def refresh(self, *_args):
        if not wutil.is_valid_widget(self):
            return
        # Guard against reentrant refresh (rebuild isn't safe to nest).
        if getattr(self, "_refreshing", False):
            return
        self._refreshing = True
        try:
            tree = controller.layer_tree()
            selection_before = set(self._selected_names)
            self.list_widget.clear()
            self._rows = {}

            # Empty state only when there's no root at all.
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
                # Qt's InternalMove drag-drop for QListWidget doesn't actually move the
                # dragged QListWidgetItem -- it removes it and decodes a brand-new item
                # from the drag's mime data at the drop position, which orphans that row's
                # cached bind_to_item() reference and drops its setItemWidget() association.
                # Tagging the item with its layer name (which mime encoding preserves) lets
                # _on_layer_dropped() re-locate the dropped row by scanning current items
                # instead of trusting a now-stale row.item().
                item.setData(QtCore.Qt.UserRole, node["name"])
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
        finally:
            self._refreshing = False

    def _filter_visible(self, flat):
        """Drop nodes nested under a collapsed group (relies on flatten_tree's depth-first pre-order)."""
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
        # Empty list space isn't focusable, so it never steals focus from an
        # active rename editor the way clicking another row/widget naturally
        # does -- commit it explicitly (a no-op if nothing's being renamed).
        for row in self._rows.values():
            row.name_button.commit_inline_rename()
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

        # Single selection uses select_layer() for Channel-Box convenience; multi writes the full Maya selection.
        if len(self._selected_names) == 1:
            controller.select_layer(next(iter(self._selected_names)), weight_attribute=True)
        elif self._selected_names:
            controller.set_selected_layers(self._selected_names)

    # ------------------------------------------------------------ per-row mutations

    def _on_lock_toggled(self, layer_name, checked):
        # Refresh: lock cascades to children/ancestors, so this row's checkbox may need reverting.
        with toolCommon.tool_operation(tool_id="animation_layers_lock", label="Lock Animation Layer", undo=True, progress=False):
            controller.set_lock(layer_name, checked)
        self.refresh()

    def _on_mute_toggled(self, layer_name, checked):
        # Refresh: set_mute() also toggles lock, cascading to children.
        with toolCommon.tool_operation(tool_id="animation_layers_mute", label="Mute Animation Layer", undo=True, progress=False):
            controller.set_mute(layer_name, checked)
        self.refresh()

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
        if layer_name in self._collapsed_groups:
            self._collapsed_groups.discard(layer_name)
            self._collapsed_groups.add(renamed)
        self.refresh()

    def _on_layer_dropped(self, layer_name):
        # Don't trust self._rows[layer_name].item() here -- QListWidget's InternalMove
        # drop rebuilds the dragged item from mime data rather than moving the original
        # object, so that cached reference is already stale by the time this runs. Find
        # the row's real post-drop position by scanning the list's own current items
        # instead (see the matching UserRole tag set in refresh()).
        index = -1
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item is not None and item.data(QtCore.Qt.UserRole) == layer_name:
                index = i
                break
        if index < 0:
            self.refresh()
            return
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
        # Iterate self._rows (ordered) rather than the set, to preserve visible order.
        ordered_selected = [name for name in self._rows.keys() if name in self._selected_names]
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_new_group", label="Group Animation Layers", undo=True, progress=False):
                controller.create_group(member_names=ordered_selected)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))
            return
        self.refresh()

    def _merge_selected(self, *_args):
        selected = list(self._selected_names)
        if not selected:
            wutil.make_inViewMessage("Select one or more animation layers to merge")
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
            controller.delete_layers(selected, recursive=False)
        self._selected_names = set()
        self._collapsed_groups -= set(selected)
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
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_import", label="Import Animation Layers", undo=True) as operation:
                controller.import_from_file(operation=operation)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))
            return
        self.refresh()

    # ------------------------------------------------------------ context menu

    def _on_row_context_menu(self, layer_name, global_pos):
        if layer_name not in self._selected_names:
            self._set_selection({layer_name})
        menu = cw.OpenMenuWidget(self)
        selected = list(self._selected_names)
        root_name = controller.root_layer_name()

        menu.addAction(
            QtGui.QIcon(icons.add), "New Layer From Selected",
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
        menu.addAction(
            "Extract to New Layer",
            description="Move the current scene selection's animation off this layer into a new one.",
            callback=lambda *_: self._extract_to_new_layer(layer_name),
        ).setEnabled(len(selected) == 1 and layer_name != root_name and not controller.is_group(layer_name))
        menu.addSeparator()
        can_ungroup = any(controller.get_parent(name) not in (None, root_name) for name in selected)
        menu.addAction(
            "Remove From Group",
            description="Move the selected layers back to the top level.",
            callback=lambda *_: self._ungroup_selected(),
        ).setEnabled(can_ungroup)
        menu.addSeparator()
        menu.addAction(
            QtGui.QIcon(icons.trash), "Delete",
            description="Delete the selected layers.",
            callback=lambda *_: self._delete_selected(),
        )
        _popup_menu(menu, global_pos)

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

    def _extract_to_new_layer(self, layer_name):
        try:
            with toolCommon.tool_operation(tool_id="animation_layers_extract", label="Extract To New Animation Layer", undo=True, progress=False):
                controller.extract_to_new_layer(layer_name)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))
            return
        self.refresh()

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
        # Bumped key so an old tall/vertical saved geometry doesn't override the new default shape.
        return "animation_layers_geometry_v2"

    def _geometry_settings_namespace(self):
        return animationLayersApi.SETTINGS_NAMESPACE

    # ------------------------------------------------------------ live sync

    def showEvent(self, event):
        super().showEvent(event)
        # Window is reused across close/reopen; reconnect since closeEvent() tears these down.
        if not getattr(self, "_runtime_connected", False):
            self._connect_runtime()
            self._runtime_connected = True
        if not getattr(self, "_click_outside_filter_installed", False):
            self._install_click_outside_filter()
            self._click_outside_filter_installed = True

    def _connect_runtime(self):
        manager = runtime.get_runtime_manager()
        # Undo/Redo included so layer changes stay in sync; one key for easy teardown.
        for event_name in ("animLayerRebuild", "animLayerRefresh", "Undo", "Redo"):
            manager.add_scriptjob(event=event_name, key=self.REFRESH_KEY, callback=self._on_scene_layers_changed)

    def _on_scene_layers_changed(self, *_args):
        if wutil.is_valid_widget(self) and self.isVisible():
            self.refresh()

    # ------------------------------------------------------------ focus handling

    def _install_click_outside_filter(self):
        # Delegated through the shared RuntimeManager (one app-level
        # QApplication.installEventFilter() backs every watcher) instead of a
        # self-managed installEventFilter/removeEventFilter pair. Reuses
        # REFRESH_KEY so closeEvent()'s disconnect_callbacks() already tears
        # this down -- no separate cleanup needed.
        try:
            runtime.get_runtime_manager().add_event_filter_watcher(self.REFRESH_KEY, self._handle_app_event)
        except _STALE_WIDGET_ERRORS:
            pass

    def _handle_app_event(self, obj, event):
        # Weight spinbox needs strong focus, which doesn't auto-release on an outside click; this forces it.
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
        except _STALE_WIDGET_ERRORS:
            pass

    # ------------------------------------------------------------ lifecycle

    def closeEvent(self, event):
        try:
            runtime.get_runtime_manager().disconnect_callbacks(self.REFRESH_KEY)
        except _STALE_WIDGET_ERRORS:
            pass
        # Reset so showEvent() reconnects on next reshow.
        self._runtime_connected = False
        self._click_outside_filter_installed = False
        animationLayersApi._emit_animation_layers_window_state(False)
        super().closeEvent(event)

    def hideEvent(self, event):
        animationLayersApi._emit_animation_layers_window_state(False)
        super().hideEvent(event)
