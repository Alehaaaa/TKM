"""The Temporal Controls Panel.

Opens from the Temporal Controls right-click menu's "Temporal Controls Panel"
item (``api.open_temp_controls_panel``). Two lists on the left: every "rig"
in the scene (a target object plus every Temporal Control that traces back
to it -- see ``api.list_rigs``), and, once a rig is picked, that rig's
individual controls. Selecting a *control* (not just a rig) enables a
detail sidebar on the right: independent Position/Orientation space
pickers with a lock tying Orientation to follow Position, a size nudge
slider, a rotation nudge slider, a shape picker, and Add Child/Add Parent/
Remove Control/Edit Pivot/Reset Pivot actions. The sidebar stays disabled
until a control is selected -- picking a rig alone isn't enough.

Selecting a control row also selects that Temporal Control in Maya, so the
viewport/Channel Box follow the panel's focused control.

Window behavior matches attribute_switcher's own ``FloatingWidget``: opens
as a borderless auto-close popup that closes itself once the cursor strays
far enough away and stays there past a short grace period, exactly like
every other transient TKM popup -- *unless* the user drags (or resizes) it,
which pins it: auto-close turns off for good and a persistent Close button
appears in the window's bottom bar. Export and Remove and Bake live in the
sidebar itself instead (stacked, full width, right under the shape/action
controls) since they only make sense once a control is selected -- exactly
when the sidebar is enabled. Remove and Bake is scoped to whichever single
control is currently selected in this panel (see ``api.bake_control``).

Both lists stay live while the panel is open (see "live sync" below):
Undo/Redo, or a Temporal Control freshly created from anywhere else (the
right-click menu, a script, another instance of this same panel -- see
api.controls_bus), re-runs ``refresh()`` (debounced, same coalescing
pattern animation_layers' own live sync uses) without closing and
reopening the window. Deletion/reparenting done through this panel's own
actions already calls refresh() directly; nothing else currently notifies
it of those, so a delete/reparent from elsewhere (a script, another
instance of this panel) doesn't show up here until something else -- an
Undo/Redo, or the next control creation -- happens to trigger a refresh.
"""

from maya import cmds

from TheKeyMachine.core import i18n, runtime
from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore

from TheKeyMachine.data import icons


def _t(text):
    return i18n.tr_text(text)


def _localized_options(options):
    return tuple(dict(option, label=_t(option.get("label", ""))) for option in options)


from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.temporal_controls import api, shapes
from TheKeyMachine.tools.temporal_controls.widgets import _OptionList
from TheKeyMachine.ui.widgets import customDialogs, customWidgets as cw, util as wutil

_STALE_WIDGET_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
)


def _short_name(node):
    return (node or "").split("|")[-1].split(":")[-1]


class _NudgeSlider(QtWidgets.QSlider):
    """A rounded, icon-only slider backing the panel's Size and Rotation
    controls -- same pill-track/round-handle language as
    attribute_switcher's own sliders, but grey (not accent-colored) and a
    real ``QSlider`` subclass (dragging is native, not hand-rolled). No
    "Size"/"Rotation" text sits next to it -- the handle carries a small
    icon glyph instead, and hovering surfaces the same information as a
    native tooltip plus a Maya statustip (see ``cw.HelpSystem.push``).

    ``liveValue`` fires continuously (with the slider's raw position, in
    whatever units *value_range* is) while the handle is being dragged, so
    a caller can apply a live effect as the user drags rather than only
    once on release.

    If *spring_back* (Size's own default), the handle always starts
    centered and snaps back to center right after release -- it's a
    one-shot relative nudge, not a value of its own; Size keeps the
    default symmetric ``value_range`` of -100..100 for this reason, since
    "centered" only means something on a symmetric range. If not
    (Rotation), the handle stays wherever it's dropped instead of
    resetting: it's reflecting an absolute state (which of api.ORIENTATIONS'
    6 poses is active), not nudging away from a neutral middle -- see
    ``set_value``, which lets a caller resync the handle to whatever state
    a newly selected control is already in. Rotation passes its own
    ``value_range=(0, len(api.ORIENTATIONS) - 1)`` so its raw slider value
    *is* an index straight into api.ORIENTATIONS, and the handle starts at
    the range's own left edge (index 0, "Up") rather than sitting in the
    middle of a symmetric range the way it would with the -100..100
    default. QSlider only ever holds integers, so this alone already gives
    exactly one stop per pose -- no snapping needed for Rotation.

    If *snap_size* is given, the handle itself visually snaps to the
    nearest multiple of it (in the same units as *value_range*) as it's
    dragged -- real detents, rather than moving freely under the mouse
    while some caller separately, invisibly, rounds the value it acts on.
    Unused by either Size or Rotation today; kept for a future slider that
    needs sub-range detents an integer value_range alone can't express."""

    liveValue = QtCore.Signal(int)
    released = QtCore.Signal()

    # Track thickness and handle diameter -- the pill background is the
    # thick, dominant shape (like attribute_switcher's own PillSlider,
    # whose track fills nearly the full widget height) and the round
    # handle is a visibly smaller circle riding inside it, not the other
    # way around. HANDLE_MARGIN (half the leftover TRACK_HEIGHT-HANDLE_SIZE)
    # is the gap the handle keeps from the track's edges on every side --
    # top/bottom simply from being centered in a taller widget,
    # left/right from _handle_center_bounds() applying that same gap. A
    # bigger handle relative to the track (was 20/28, a 4px margin) keeps
    # that gap small and uniform instead of reading as a wide top/bottom
    # band -- the track's rounded end caps already add their own visual
    # buffer on the left/right that the flat top/bottom edges don't get,
    # so a smaller shared margin is what actually looks even on both axes.
    TRACK_HEIGHT = wutil.DPI(28)
    HANDLE_SIZE = wutil.DPI(24)
    HANDLE_MARGIN = (TRACK_HEIGHT - HANDLE_SIZE) // 2
    ICON_SIZE = wutil.DPI(14)

    # Grey palette (COLORS.ui) -- deliberately not the accent color
    # attribute_switcher's own PillSlider uses, since these two sliders
    # sit in a neutral sidebar next to plain grey list/space widgets.
    _TRACK_COLOR = QtGui.QColor(COLORS.ui.darker_gray.hex)
    _HANDLE_COLOR = QtGui.QColor(COLORS.ui.gray.hex)
    _HANDLE_HOVER_COLOR = QtGui.QColor(COLORS.ui.light_gray.hex)

    def __init__(
        self,
        label,
        icon,
        description="",
        spring_back=True,
        snap_size=None,
        value_range=(-100, 100),
        parent=None,
    ):
        super().__init__(QtCore.Qt.Horizontal, parent)
        self._spring_back = spring_back
        self._snap_size = snap_size
        self._hover = False
        self._dragging = False

        # Widget height follows the track now, not the handle -- the track
        # is the larger of the two shapes (see TRACK_HEIGHT/HANDLE_SIZE
        # above), so it's what defines the control's own footprint.
        self.setFixedHeight(self.TRACK_HEIGHT)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setMouseTracking(True)
        self.setRange(*value_range)
        self.setValue(value_range[0] if not spring_back else 0)

        # Hand-painted (see paintEvent/mouse* below), not QSS ::handle
        # sizing -- three rounds of QSS tweaks all came out lopsided, since
        # this style engine kept the handle's painted height pinned to the
        # groove's height regardless of what the stylesheet's own "height"
        # said. Painting the circle directly with QPainter.drawEllipse (the
        # same technique attribute_switcher's PillSlider uses) is immune to
        # that -- it's just pixels at a radius, not a subcontrol Qt gets to
        # reinterpret. Mouse handling is reimplemented to match (click/drag
        # anywhere jumps the handle there), since QSlider's own hit-testing
        # otherwise still trusts the style's -- wrong -- handle geometry.
        self.setStyleSheet("QSlider{background:transparent;border:none;}")

        self._icon_pixmap = QtGui.QIcon(icon).pixmap(self.ICON_SIZE, self.ICON_SIZE)

        # Native Maya tooltip (Qt's own tooltip bubble) and statustip
        # (Maya's help line, via HelpSystem.push -- the same channel every
        # other TKM control's help text goes through) instead of the
        # in-panel label this slider used to carry.
        self.setToolTip("{}\n{}".format(label, description) if description else label)
        cw.HelpSystem.push(self, label, description)

        self.valueChanged.connect(self._on_value_changed)
        self.sliderReleased.connect(self._on_released)

    def _nearest_snap(self, value):
        snapped = round(value / self._snap_size) * self._snap_size
        return int(round(max(self.minimum(), min(self.maximum(), snapped))))

    def _on_value_changed(self, value):
        if self._snap_size:
            snapped = self._nearest_snap(value)
            if snapped != value:
                block = self.blockSignals(True)
                self.setValue(snapped)
                self.blockSignals(block)
                value = snapped
        self.update()
        self.liveValue.emit(value)

    def _on_released(self):
        if self._spring_back:
            block = self.blockSignals(True)
            self.setValue(0)
            self.blockSignals(block)
            self.update()
        self.released.emit()

    def set_value(self, value):
        """Reposition the handle to *value* without emitting liveValue --
        for a caller resyncing this slider to a newly selected control's
        state (only meaningful when spring_back is False)."""
        block = self.blockSignals(True)
        self.setValue(int(round(value)))
        self.blockSignals(block)
        self.update()

    # ------------------------------------------------------------------
    # Painting and hit-testing -- both driven off the same _track_rect()/
    # _handle_center_x() geometry, so what's drawn and what's clickable
    # never disagree with each other.
    # ------------------------------------------------------------------

    def _track_rect(self):
        y = (self.height() - self.TRACK_HEIGHT) // 2
        return QtCore.QRect(0, y, self.width(), self.TRACK_HEIGHT)

    def _handle_center_bounds(self):
        """(left, right) the handle's *center* can reach -- HANDLE_MARGIN
        inset from each edge, so its travel stops short of the track's
        rounded ends instead of touching them, the same gap it already
        keeps from the top/bottom."""
        left = self.HANDLE_MARGIN + self.HANDLE_SIZE / 2.0
        right = max(left, self.width() - self.HANDLE_MARGIN - self.HANDLE_SIZE / 2.0)
        return left, right

    def _handle_center_x(self):
        span = self.maximum() - self.minimum()
        ratio = 0.0 if span == 0 else (self.value() - self.minimum()) / float(span)
        left, right = self._handle_center_bounds()
        return left + ratio * (right - left)

    def _handle_rect(self):
        cx = self._handle_center_x()
        cy = self.height() / 2.0
        r = self.HANDLE_SIZE / 2.0
        return QtCore.QRectF(cx - r, cy - r, self.HANDLE_SIZE, self.HANDLE_SIZE)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)

        track = self._track_rect()
        painter.setBrush(self._TRACK_COLOR)
        painter.drawRoundedRect(track, self.TRACK_HEIGHT / 2.0, self.TRACK_HEIGHT / 2.0)

        handle = self._handle_rect()
        painter.setBrush(
            self._HANDLE_HOVER_COLOR
            if (self._hover or self._dragging)
            else self._HANDLE_COLOR
        )
        painter.drawEllipse(handle)

        icon_pos = handle.center() - QtCore.QPointF(
            self.ICON_SIZE / 2.0, self.ICON_SIZE / 2.0
        )
        painter.drawPixmap(icon_pos, self._icon_pixmap)
        painter.end()

    def _value_from_x(self, x):
        left, right = self._handle_center_bounds()
        usable = right - left
        if usable <= 0:
            return self.minimum()
        ratio = (x - left) / usable
        ratio = max(0.0, min(1.0, ratio))
        return self.minimum() + ratio * (self.maximum() - self.minimum())

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        self._dragging = True
        self.setSliderDown(True)
        self.setValue(int(round(self._value_from_x(event.x()))))
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.setValue(int(round(self._value_from_x(event.x()))))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or not self._dragging:
            return super().mouseReleaseEvent(event)
        self._dragging = False
        self.setSliderDown(False)
        self.update()
        event.accept()

    def enterEvent(self, event):
        # isEnabled() guard -- Qt still delivers hover enter/leave events to
        # a disabled widget (mouse *press* is what it blocks), so without
        # this the handle kept brightening on hover even while the sidebar
        # (and so this slider) was disabled -- a highlight implying it was
        # interactive when it wasn't.
        if self.isEnabled():
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()


class TempControlsPanelWindow(customDialogs.QFlatToolBarDialog):
    """See module docstring for the overall behavior contract."""

    title = "Temporal Controls Panel"
    icon = icons.temporal_controls

    # Cursor-distance auto-close -- see attribute_switcher.widgets.FloatingWidget,
    # which this mirrors (reimplemented here rather than imported cross-tool).
    # FloatingWidget can get away with a tight DPI(10) tolerance because it
    # opens flush against the toolbar button that launched it -- the cursor
    # already sits right on its edge. This panel instead opens via
    # place_near_cursor() (see customDialogs.QFlatToolBarDialog), which
    # deliberately leaves a DPI(30) gap between the window and the cursor so
    # the popup doesn't appear directly under the pointer. A DPI(10)
    # tolerance is narrower than that gap, so the very first auto-close
    # check (after AUTO_CLOSE_GRACE_MS) already saw the cursor "too far
    # away" and closed the panel before the user could do anything with it.
    # Comfortably clearing that placement gap fixes it.
    AUTO_CLOSE_DIST = wutil.DPI(45)
    AUTO_CLOSE_POLL_MS = 200
    AUTO_CLOSE_GRACE_MS = 400
    DRAG_PIN_DISTANCE = wutil.DPI(10)

    ACTIONS = (
        {"id": "add_child", "icon": "add", "tooltip": "Add Child Control"},
        {"id": "add_parent", "icon": "new", "tooltip": "Add Parent Control"},
        {
            "id": "remove",
            "icon": "remove",
            "tooltip": "Remove Control (extra controls only)",
        },
        {"id": "edit_pivot", "icon": "temp_pivot_edit", "tooltip": "Edit Pivot"},
        {"id": "reset_pivot", "icon": "temp_pivot_reset", "tooltip": "Reset Pivot"},
    )

    # The size this panel actually opens at. place_near_cursor() (see
    # api.open_temp_controls_panel) calls adjustSize(), which resizes to
    # sizeHint() -- so it's sizeHint() below, not just the minimums, that
    # decides the panel's initial on-screen size; the minimums only keep it
    # from being dragged/resized smaller than that afterward.
    DEFAULT_WIDTH = wutil.DPI(700)
    DEFAULT_HEIGHT = wutil.DPI(450)

    # Live sync (see "Both lists stay live..." in the module docstring) --
    # one key for every RuntimeManager-tracked callback this window owns
    # (currently just the Undo/Redo scriptjobs), so closeEvent() can tear
    # them all down in one disconnect_callbacks() call. The
    # api.controls_bus connection isn't RuntimeManager-tracked -- it's a
    # plain Qt signal connection, disconnected by hand in closeEvent
    # instead (see _connect_live_refresh/closeEvent below).
    REFRESH_KEY = "temp_controls_panel_refresh"
    # Any single one of these could in principle fire in a burst (Undo/Redo
    # of a multi-object creation, several controls_bus emits back to back
    # from a scripted loop). Restarting a short singleShot timer on each
    # event instead (same coalescing pattern as background_runners'
    # AnimLayerWeightsRunner) collapses a whole burst into one refresh()
    # once things settle, rather than rebuilding both lists on every event.
    LIVE_REFRESH_DELAY_MS = 150

    def __init__(self, parent=None):
        super().__init__(parent=parent, popup=True, closeButton=False)
        self.setObjectName("temp_controls_panel")
        self.setMinimumWidth(wutil.DPI(560))
        self.setMinimumHeight(wutil.DPI(340))
        self.title_label.setText(self.title)

        self._pinned = False
        self._rigs_cache = {}
        self._current_rig = None
        self._current_control = None

        self._shown_elapsed = QtCore.QElapsedTimer()
        self._auto_close_timer = QtCore.QTimer(self)
        self._auto_close_timer.setInterval(self.AUTO_CLOSE_POLL_MS)
        self._auto_close_timer.timeout.connect(self._process_auto_close_request)

        # Live sync -- see REFRESH_KEY/LIVE_REFRESH_DELAY_MS above and the
        # "live sync" section near showEvent()/closeEvent() below.
        self._runtime_connected = False
        self._live_refresh_timer = QtCore.QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.setInterval(self.LIVE_REFRESH_DELAY_MS)
        self._live_refresh_timer.timeout.connect(self._apply_live_refresh)

        self._build_ui()
        self.grip.installEventFilter(self)
        self.refresh()

    def sizeHint(self):
        return QtCore.QSize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(wutil.DPI(6))

        # Expanding, same as they've always been -- these stretch to fill
        # the window's height (and scroll normally if a scene ever has more
        # rigs/controls than fit). Only Position/Orientation's own lists
        # (see _build_space_column, cap_to_content=True) size to content.
        self.rig_list = _OptionList([])
        self.rig_list.setMinimumWidth(wutil.DPI(150))
        self.rig_list.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
        )
        self.rig_list.selectionChanged.connect(self._on_rig_selected)
        self.rig_list.colorRequested.connect(self._show_rig_color_menu)
        body_layout.addWidget(self.rig_list, 1)

        self.control_list = _OptionList([])
        self.control_list.setMinimumWidth(wutil.DPI(150))
        self.control_list.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
        )
        self.control_list.selectionChanged.connect(self._on_control_selected)
        body_layout.addWidget(self.control_list, 1)

        self.sidebar = self._build_sidebar()
        body_layout.addWidget(self.sidebar, 1)

        self.mainLayout.addWidget(body, 1)
        self.sidebar.setEnabled(False)

    def _build_sidebar(self):
        sidebar = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(wutil.DPI(4))

        # Preferred/Maximum, not Expanding -- Position/Orientation's own
        # lists cap themselves to their content height (_OptionList's
        # setMaximumHeight, see _content_height), and this row just
        # follows them rather than stretching past that to fill the window.
        self.spaces_row = QtWidgets.QWidget()
        self.spaces_row.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
        spaces_layout = QtWidgets.QHBoxLayout(self.spaces_row)
        spaces_layout.setContentsMargins(0, 0, 0, 0)
        spaces_layout.setSpacing(wutil.DPI(4))

        position_col, self.position_list = self._build_space_column(_t("Position"))
        self.position_list.selectionChanged.connect(self._on_position_selected)
        spaces_layout.addWidget(position_col, 1)

        lock_col = QtWidgets.QWidget()
        lock_col_layout = QtWidgets.QVBoxLayout(lock_col)
        lock_col_layout.setContentsMargins(0, 0, 0, 0)
        lock_col_layout.addStretch(1)
        self.lock_button = QtWidgets.QToolButton()
        self.lock_button.setCheckable(True)
        self.lock_button.setAutoRaise(True)
        self.lock_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.lock_button.setIcon(QtGui.QIcon(icons.lock_open))
        self.lock_button.setIconSize(QtCore.QSize(wutil.DPI(15), wutil.DPI(15)))
        # Fixed chip size -- lock.svg and lock_open.svg's shackles aren't
        # identical shapes, and without an explicit size the button's own
        # sizeHint (and the open shackle in particular, which reaches
        # further than the closed one) could grow past this fixed-width
        # column and read as overflowing it. A size clearly larger than
        # the icon keeps the button constant across the toggle either way.
        self.lock_button.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        self.lock_button.setToolTip(_t("Lock Orientation Space to Position Space"))
        # Simple native grey checked state -- no custom color, just enough
        # to read as "toggled" against the panel's own dark background.
        self.lock_button.setStyleSheet(
            "QToolButton:checked { background-color: #5a5a5a; border-radius: %dpx; }"
            % wutil.DPI(3)
        )
        self.lock_button.toggled.connect(self._on_lock_toggled)
        lock_col_layout.addWidget(self.lock_button)
        lock_col_layout.addStretch(1)
        spaces_layout.addWidget(lock_col, 0)

        orientation_col, self.orientation_list = self._build_space_column(
            _t("Orientation")
        )
        self.orientation_list.selectionChanged.connect(self._on_orientation_selected)
        spaces_layout.addWidget(orientation_col, 1)

        layout.addWidget(self.spaces_row)

        anim_title = QtWidgets.QLabel(_t("Anim Controls"))
        anim_title.setAlignment(QtCore.Qt.AlignCenter)
        anim_title.setStyleSheet(self._column_title_style())
        layout.addWidget(anim_title)

        self._size_last_value = 0
        self.size_slider = _NudgeSlider(
            _t("Size"),
            icons.size,
            description=_t(
                "Drag to nudge the selected control's size. Releases back to center."
            ),
            spring_back=True,
        )
        self.size_slider.liveValue.connect(self._on_size_live)
        self.size_slider.released.connect(self._on_size_released)
        layout.addWidget(self.size_slider)

        # Rotation doesn't nudge freely or spring back -- it has exactly 6
        # stops, one per api.ORIENTATIONS pose (Up/Down/Forward/Backward/
        # Right/Left), and the handle stays put wherever it's set,
        # reflecting whichever pose is currently active (see
        # _sync_sidebar, which repositions it for the selected control).
        # value_range=(0, len(api.ORIENTATIONS) - 1) makes the slider's own
        # raw integer value an index straight into api.ORIENTATIONS --
        # QSlider only ever holds integers, so this already gives exactly
        # one stop per pose with no separate snapping needed -- and starts
        # at the range's left edge (index 0, "Up") rather than centered
        # the way Size's symmetric range is.
        self.rotation_slider = _NudgeSlider(
            _t("Rotation"),
            icons.refresh,
            description=_t(
                "Drag to snap the control to one of six fixed orientation poses."
            ),
            spring_back=False,
            value_range=(0, len(api.ORIENTATIONS) - 1),
        )
        self.rotation_slider.liveValue.connect(self._on_rotation_live)
        layout.addWidget(self.rotation_slider)

        self.shape_combo = QtWidgets.QComboBox()
        for shape in shapes.SHAPE_LIST:
            self.shape_combo.addItem(shape["label"], shape["id"])
        self.shape_combo.activated.connect(self._on_shape_activated)
        layout.addWidget(self.shape_combo)

        actions_row = QtWidgets.QWidget()
        actions_layout = QtWidgets.QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(
            wutil.DPI(8), wutil.DPI(6), wutil.DPI(8), wutil.DPI(6)
        )
        actions_layout.setSpacing(wutil.DPI(14))
        actions_layout.addStretch(1)
        self.action_buttons = {}
        for action in self.ACTIONS:
            button = QtWidgets.QToolButton()
            button.setAutoRaise(True)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setIcon(QtGui.QIcon(icons.get(action["icon"])))
            button.setIconSize(QtCore.QSize(wutil.DPI(18), wutil.DPI(18)))
            button.setToolTip(action["tooltip"])
            button.clicked.connect(
                lambda *_args, action_id=action["id"], btn=button: self._on_action(
                    action_id, btn
                )
            )
            self.action_buttons[action["id"]] = button
            actions_layout.addWidget(button)
        actions_layout.addStretch(1)
        layout.addWidget(actions_row)

        # Everything above (spaces_row, sliders, shape combo, action icons)
        # is now content-sized, not Expanding -- this one gap absorbs all
        # of any extra vertical space instead, so the window can still grow
        # taller without anything above stretching past its own content.
        layout.addStretch(1)

        # Export/Remove and Bake live in the sidebar itself (stacked, full
        # width) rather than the window's bottom bar -- they only make
        # sense once a control is selected, which is exactly when the
        # sidebar (and so these buttons) are enabled.
        self.export_button = self._create_sidebar_button("Export", icons.export)
        self.export_button.clicked.connect(self._on_export)
        layout.addWidget(self.export_button)

        self.bake_button = self._create_sidebar_button(
            "Remove and Bake", icons.temporal_controls_bake
        )
        self.bake_button.clicked.connect(self._on_remove_and_bake)
        layout.addWidget(self.bake_button)

        return sidebar

    @staticmethod
    def _create_sidebar_button(text, icon):
        # cw.QFlatButton, not a hand-rolled stylesheet -- the same class
        # (and, left un-highlighted, the same normal/hover/pressed colors)
        # every toolbar Close button already uses, just shorter than its
        # own fixed DPI(34) height.
        button = cw.QFlatButton(text=text, icon=icon, border=wutil.DPI(5))
        button.setFixedHeight(wutil.DPI(24))
        # QFlatButton.DEFAULT_DISABLED_BACKGROUND ("#444444") is exactly
        # this dialog's own background (QFlatDialog.COLOR_BG_TRACK) -- while
        # disabled (no control selected), Export/Remove and Bake vanish into
        # the window instead of just reading as unavailable. #4d4d4d sits
        # about a third of the way from that background toward the button's
        # own enabled fill (QFlatButton.DEFAULT_BACKGROUND, "#5D5D5D") --
        # enough to separate it from the window without reading as enabled.
        # Appended after QFlatButton's own stylesheet, so this :disabled
        # rule -- and only this one -- wins the cascade over its default.
        button.setStyleSheet(
            button.styleSheet() + "QPushButton:disabled{background-color:#4d4d4d;}"
        )
        return button

    def _build_space_column(self, title):
        # Preferred/Maximum -- the list caps its own height to its rows
        # (see _OptionList._content_height), and this column just follows
        # it instead of stretching the list past that.
        column = QtWidgets.QWidget()
        column.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
        column_layout = QtWidgets.QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(wutil.DPI(3))

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(self._column_title_style())
        column_layout.addWidget(title_label)

        # SWITCHABLE_SPACES, not the full SPACES list -- these columns
        # re-drive an already-built control into a different space (see
        # _on_position_selected/_on_orientation_selected), the same
        # operation the right-click menu's own Space submenu offers
        # (the command-id list in temporal_controls.__init__), which already
        # excludes Grab Release
        # for exactly this reason: it's documented as a one-shot
        # creation-time concept, not something to switch back into later.
        option_list = _OptionList(
            list(_localized_options(api.SWITCHABLE_SPACES)), cap_to_content=True
        )
        option_list.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
        column_layout.addWidget(option_list)
        return column, option_list

    @staticmethod
    def _column_title_style():
        return "color: #9a9a9a; font-size: %spx;" % wutil.DPI(11)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self, preselect_control=None):
        """Rebuild both lists from the scene's current rigs.

        With *preselect_control* (Add Child/Add Parent's follow-up call),
        lands directly on that control's own rig -- one selection pass, not
        the first rig's list rebuild followed immediately by a second full
        rig->control->sidebar-sync cycle to correct it. Without one (opening
        the panel, or after Remove/Bake), lands on the first rig (which in
        turn lands on its first control, enabling the sidebar) rather than
        opening -- or resetting after an action -- to a blank panel."""
        self._rigs_cache = api.list_panel_rigs()
        rig_options = []
        for root_target, controls in sorted(
            self._rigs_cache.items(), key=lambda kv: _short_name(kv[0]).lower()
        ):
            color = self._selection_color_for_hex(
                api.get_control_color(controls[0]) if controls else None
            )
            rig_options.append(
                {
                    "id": root_target,
                    "label": _short_name(root_target),
                    "icon": "temporal_controls",
                    "color_suffix": color.suffix,
                    "color_label": _t("Change Color"),
                }
            )
        self.rig_list.refresh(rig_options)
        if preselect_control and self._select_control(preselect_control):
            return
        # Land on the first rig (which in turn lands _on_rig_selected on
        # its first control below) rather than opening to a blank panel.
        self.rig_list.select_id(
            rig_options[0]["id"] if rig_options else None, required=False
        )

    @staticmethod
    def _selection_color_for_hex(color_hex):
        normalized = (color_hex or "").lower()
        for color in COLORS.selection.all:
            if color.hex.lower() == normalized:
                return color
        return COLORS.selection.default

    def _show_rig_color_menu(self, rig_id, button):
        if not rig_id:
            return
        menu = cw.MenuWidget(_t("Change Color"), self, tearoff=False)
        menu.setIcon(QtGui.QIcon(icons.color))
        for color in COLORS.selection.all:
            menu.addAction(
                QtGui.QIcon(icons.selection_set_color_icons.get(color.suffix, "")),
                _t(color.label),
                callback=lambda root=rig_id, value=color.hex: self._set_rig_color(
                    root, value
                ),
            )
        menu.exec_(QtGui.QCursor.pos())

    def _set_rig_color(self, rig_id, color_hex):
        selected_control = self._current_control
        if api.set_rig_color(rig_id, color_hex):
            self.refresh(preselect_control=selected_control)

    def _select_control(self, control):
        """Select *control* (and the rig it belongs to). Returns whether it
        was actually found in the current _rigs_cache -- refresh() uses
        this to fall back to landing on the first rig when it isn't."""
        root_target = api.root_target_for(control) if control else None
        if not root_target:
            root_target = next(
                (
                    rig_id
                    for rig_id, controls in self._rigs_cache.items()
                    if control in controls
                ),
                None,
            )
        if not root_target or root_target not in self._rigs_cache:
            return False
        self.rig_list.select_id(root_target, required=False)
        self.control_list.select_id(control, required=False)
        return True

    def _control_label(self, control):
        label = _short_name(control)
        if api.TkmSceneNode(control).get_attr(api.EXTRA_ATTR):
            label += "  (extra)"
        return label

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_rig_selected(self, rig_id):
        self._current_rig = rig_id
        controls = self._rigs_cache.get(rig_id, []) if rig_id else []
        control_options = [
            {
                "id": control,
                "label": self._control_label(control),
                "icon": "temporal_controls",
            }
            for control in controls
        ]
        self.control_list.refresh(control_options)
        # Land on the rig's first control rather than requiring a second click.
        self.control_list.select_id(
            control_options[0]["id"] if control_options else None, required=False
        )

    def _on_control_selected(self, control_id):
        self._current_control = control_id
        is_tagged_control = bool(
            control_id and api.TkmSceneNode(control_id).get_attr(api.TAG_ATTR)
        )
        self.sidebar.setEnabled(bool(control_id))
        self._set_control_capabilities(is_tagged_control)
        if not control_id:
            return
        try:
            if cmds.objExists(control_id):
                cmds.select(control_id)
        except _STALE_WIDGET_ERRORS:
            pass
        self._sync_sidebar(control_id, sync_spaces=is_tagged_control)

    def _set_control_capabilities(self, has_temporal_metadata):
        """Keep appearance controls available for every listed curve.

        Position/orientation spaces, stacking, and direct removal depend on
        TAG_ATTR's target/driver ownership and remain exclusive to tagged
        Temporal Controls. Shape, size, visual rotation, and pivots operate
        directly on curve CVs/transforms and are valid for secondary controls.
        Bake resolves a secondary selection to its owning tagged control.
        """
        self.spaces_row.setEnabled(has_temporal_metadata)
        for action_id in ("add_child", "add_parent", "remove"):
            self.action_buttons[action_id].setEnabled(has_temporal_metadata)
        self.bake_button.setEnabled(bool(self._current_control))

    def _sync_sidebar(self, control, sync_spaces=True):
        """Reflect *control*'s current state into the sidebar widgets --
        signals are blocked throughout so this pure sync doesn't loop back
        into the space/lock click handlers below."""
        if sync_spaces:
            locked = api.is_control_space_locked(control)

            block = self.position_list.blockSignals(True)
            self.position_list.select_id(
                api.get_control_position_space(control), required=False
            )
            self.position_list.blockSignals(block)

            block = self.orientation_list.blockSignals(True)
            self.orientation_list.select_id(
                api.get_control_orientation_space(control), required=False
            )
            self.orientation_list.blockSignals(block)
            self.orientation_list.setEnabled(not locked)

            block = self.lock_button.blockSignals(True)
            self.lock_button.setChecked(locked)
            self.lock_button.blockSignals(block)
            self.lock_button.setIcon(
                QtGui.QIcon(icons.lock if locked else icons.lock_open)
            )

        shape_id = api.get_control_shape_id(control)
        index = self.shape_combo.findData(shape_id)
        block = self.shape_combo.blockSignals(True)
        self.shape_combo.setCurrentIndex(index if index >= 0 else 0)
        self.shape_combo.blockSignals(block)

        # Rotation's handle reflects an absolute state (see _NudgeSlider),
        # so it needs resyncing to whichever of api.ORIENTATIONS' 6 poses
        # *control* is actually at -- Size's handle always starts back at
        # center, so it needs no equivalent sync.
        self.rotation_slider.set_value(
            self._slider_value_for_orientation(api.get_control_orientation(control))
        )

    # ------------------------------------------------------------------
    # Sidebar actions -- every one of these edits the scene, so each goes
    # through toolCommon.run_tool_callback for proper undo-chunk/progress
    # handling, same as the right-click menu's real actions.
    # ------------------------------------------------------------------

    def _on_position_selected(self, space_id):
        if not self._current_control or not space_id:
            return
        toolCommon.run_tool_callback(
            self.position_list,
            api.set_control_space,
            self._current_control,
            "translate",
            space_id,
        )
        if api.is_control_space_locked(self._current_control):
            block = self.orientation_list.blockSignals(True)
            self.orientation_list.select_id(
                api.get_control_orientation_space(self._current_control), required=False
            )
            self.orientation_list.blockSignals(block)

    def _on_orientation_selected(self, space_id):
        if (
            not self._current_control
            or not space_id
            or api.is_control_space_locked(self._current_control)
        ):
            return
        toolCommon.run_tool_callback(
            self.orientation_list,
            api.set_control_space,
            self._current_control,
            "rotate",
            space_id,
        )

    def _on_lock_toggled(self, checked):
        if not self._current_control:
            return
        toolCommon.run_tool_callback(
            self.lock_button,
            api.set_control_space_locked,
            self._current_control,
            checked,
        )
        self.orientation_list.setEnabled(not checked)
        self.lock_button.setIcon(
            QtGui.QIcon(icons.lock if checked else icons.lock_open)
        )
        if checked:
            block = self.orientation_list.blockSignals(True)
            self.orientation_list.select_id(
                api.get_control_orientation_space(self._current_control), required=False
            )
            self.orientation_list.blockSignals(block)

    # Size applies continuously while dragging: each liveValue tick maps
    # the slider's raw -100..100 position onto a target cumulative scale
    # factor (exponential, not linear -- see _size_factor_for, so growing
    # and shrinking feel symmetric and shrinking can never reach/cross
    # zero), and only the *incremental* factor since the last tick is
    # actually sent to Maya -- so a full drag from center to the edge ends
    # up applying exactly one SIZE_NUDGE_STEP worth of effect in total,
    # just spread continuously across the drag instead of dumped on
    # release. released() resets the tracked "last value" back to 0 to
    # match the handle snapping back to center.

    @staticmethod
    def _size_factor_for(value):
        return 2.0 ** (api.SIZE_NUDGE_STEP * value / 100.0)

    def _on_size_live(self, value):
        if not self._current_control:
            self._size_last_value = value
            return
        factor = self._size_factor_for(value) / self._size_factor_for(
            self._size_last_value
        )
        self._size_last_value = value
        if abs(factor - 1.0) > 1e-9:
            toolCommon.run_tool_callback(
                self.size_slider, api.scale_control, self._current_control, factor
            )

    def _on_size_released(self):
        self._size_last_value = 0

    # Rotation doesn't nudge -- its handle is an absolute position across
    # api.ORIENTATIONS' 6 fixed poses and doesn't spring back (see
    # _NudgeSlider(spring_back=False)). The slider's own raw integer value
    # (value_range=(0, len(api.ORIENTATIONS)-1), see its own construction
    # above) is an index straight into api.ORIENTATIONS -- no separate
    # snapping/conversion needed. Each liveValue tick just asks Maya to
    # snap directly to whichever pose that index names.

    @staticmethod
    def _orientation_id_for(value):
        index = max(0, min(len(api.ORIENTATIONS) - 1, int(value)))
        return api.ORIENTATIONS[index]["id"]

    @staticmethod
    def _slider_value_for_orientation(orientation_id):
        for index, pose in enumerate(api.ORIENTATIONS):
            if pose["id"] == orientation_id:
                return index
        return 0

    def _on_rotation_live(self, value):
        if not self._current_control:
            return
        orientation_id = self._orientation_id_for(value)
        toolCommon.run_tool_callback(
            self.rotation_slider,
            api.set_control_orientation,
            self._current_control,
            orientation_id,
        )

    def _on_shape_activated(self, index):
        if not self._current_control:
            return
        shape_id = self.shape_combo.itemData(index)
        toolCommon.run_tool_callback(
            self.shape_combo, api.set_control_shape, self._current_control, shape_id
        )

    def _on_action(self, action_id, button):
        control = self._current_control
        if not control:
            return
        if action_id == "add_child":
            new_control = toolCommon.run_tool_callback(
                button, api.add_child_control, control
            )
            self.refresh(preselect_control=new_control)
        elif action_id == "add_parent":
            new_control = toolCommon.run_tool_callback(
                button, api.add_parent_control, control
            )
            self.refresh(preselect_control=new_control)
        elif action_id == "remove":
            toolCommon.run_tool_callback(button, api.remove_extra_control, control)
            self.refresh()
        elif action_id == "edit_pivot":
            toolCommon.run_tool_callback(button, api.edit_pivot, control)
        elif action_id == "reset_pivot":
            toolCommon.run_tool_callback(button, api.reset_pivot, control)

    # ------------------------------------------------------------------
    # Sidebar bottom actions (see _build_sidebar) -- always visible whenever
    # the sidebar itself is (i.e. a control is selected), unlike the
    # window's own bottom bar (see _pin), which only appears once pinned
    # and only ever holds Close. Remove and Bake uses the same selection-
    # aware batch path as the right-click menu (see api.bake_controls).
    # ------------------------------------------------------------------

    def _on_export(self):
        wutil.make_inViewMessage("Export is coming soon")

    def _on_remove_and_bake(self):
        if not self._current_control:
            wutil.make_inViewMessage("Select a control first")
            return
        toolCommon.run_tool_callback(self, api.bake_controls)
        self.refresh()

    # ------------------------------------------------------------------
    # Live sync -- see the module docstring's "Both lists stay live..."
    # paragraph and REFRESH_KEY/LIVE_REFRESH_DELAY_MS above. Reconnected on
    # every showEvent() (not just __init__) since api.open_temp_controls_panel
    # reuses this same instance across close/reopen, and closeEvent() tears
    # the callbacks down each time -- same pattern animation_layers' own
    # live sync uses for the same reason.
    # ------------------------------------------------------------------

    def _connect_live_refresh(self):
        manager = runtime.get_runtime_manager()
        for event_name in ("Undo", "Redo"):
            manager.add_scriptjob(
                event=event_name, key=self.REFRESH_KEY, callback=self._on_scene_changed
            )
        # Not RuntimeManager-tracked (see REFRESH_KEY above) -- a direct Qt
        # connection to api.controls_bus, which create_controls_with_options
        # emits right after it actually builds new controls. Narrower than
        # the DAG-change watching this replaced (that fired for every node
        # create/parent/delete in the scene, Temporal Control or not).
        api.controls_bus.controlsCreated.connect(self._on_scene_changed)

    def _on_scene_changed(self, *_args):
        # Restart, not fire directly -- see LIVE_REFRESH_DELAY_MS above.
        self._live_refresh_timer.start()

    def _apply_live_refresh(self):
        if not (wutil.is_valid_widget(self) and self.isVisible()):
            return
        # Keep whichever control is currently open in the sidebar selected
        # across the rebuild instead of snapping back to the first rig --
        # refresh() already falls back to that on its own if the control
        # no longer exists (e.g. it was the thing just deleted).
        self.refresh(preselect_control=self._current_control)

    # ------------------------------------------------------------------
    # Window chrome: cursor-distance auto-close, drag/resize-to-pin
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._pinned:
            self._shown_elapsed.start()
            self._auto_close_timer.start()
        if not self._runtime_connected:
            try:
                self._connect_live_refresh()
                self._runtime_connected = True
            except _STALE_WIDGET_ERRORS:
                pass

    def closeEvent(self, event):
        try:
            runtime.get_runtime_manager().disconnect_callbacks(self.REFRESH_KEY)
        except _STALE_WIDGET_ERRORS:
            pass
        if self._runtime_connected:
            # Plain Qt connection, not RuntimeManager-tracked -- see
            # _connect_live_refresh -- so it needs its own disconnect here
            # rather than going through disconnect_callbacks() above.
            try:
                api.controls_bus.controlsCreated.disconnect(self._on_scene_changed)
            except (RuntimeError, TypeError):
                pass
        self._runtime_connected = False
        self._live_refresh_timer.stop()
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.grip and event.type() == QtCore.QEvent.MouseButtonRelease:
            self._pin()
        return super().eventFilter(watched, event)

    def _process_auto_close_request(self):
        if self._pinned or not self.isVisible():
            self._auto_close_timer.stop()
            return
        if not self._shown_elapsed.isValid():
            return
        if self.AUTO_CLOSE_GRACE_MS - self._shown_elapsed.elapsed() > 0:
            return
        cursor_pos = QtGui.QCursor.pos()
        bounds = self.frameGeometry()
        if bounds.contains(cursor_pos):
            return
        dx = max(bounds.left() - cursor_pos.x(), 0, cursor_pos.x() - bounds.right())
        dy = max(bounds.top() - cursor_pos.y(), 0, cursor_pos.y() - bounds.bottom())
        if (dx * dx + dy * dy) ** 0.5 > self.AUTO_CLOSE_DIST:
            self.close()

    def mouseReleaseEvent(self, event):
        # QFlatFloatingWidget's own version pins (via _ensure_close_button)
        # on *any* click release, not just a real drag -- bypass it, the
        # same fix attribute_switcher's FloatingWidget applies, and only
        # pin past DRAG_PIN_DISTANCE.
        was_dragging = self._is_dragging
        drag_start = QtCore.QPoint(self._drag_start_pos)
        if event.button() == QtCore.Qt.LeftButton and was_dragging:
            self._is_dragging = False
            global_position = wutil.event_global_pos(event)
            if (
                global_position - drag_start
            ).manhattanLength() > self.DRAG_PIN_DISTANCE:
                self._pin()
        customDialogs.QFlatDialog.mouseReleaseEvent(self, event)

    def _pin(self):
        # Export/Remove and Bake live in the sidebar itself (see
        # _build_sidebar) -- the window's own bottom bar, which only
        # appears once pinned, just gets a Close button here.
        if self._pinned:
            return
        self._pinned = True
        self._auto_close_timer.stop()
        # margins=0 -- same as attribute_switcher's FloatingWidget.setBottomBar
        # override -- so the bar spans edge-to-edge with no gap to the window
        # instead of QFlatDialog's own default 8px inset.
        self.setBottomBar(closeButton=True, margins=0)
