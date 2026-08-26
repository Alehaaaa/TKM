"""The Temporal Controls creation dialog.

Opens when ``temporal_controls`` is clicked with a selection. Three single-select
lists (System / Position / Orientation) choose how the controls this tool is
about to build will be shaped and driven; a name field and a color swatch row
(borrowed straight from ``selection_sets``) round it out. Clicking a color
swatch applies immediately with that color (same one-click "create with this
color" pattern as ``selection_sets``' own creation dialog); the OK button does
the same using whichever color is currently picked. Confirming calls back
into ``api.create_controls_with_options()`` with the chosen values, covering
every object that was selected when the dialog was opened -- not just one.
"""

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore
from TheKeyMachine.core import i18n

from TheKeyMachine.data import icons
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.temporal_controls import api
from TheKeyMachine.ui.widgets import customDialogs, customWidgets as cw, util as wutil


def _t(text):
    return i18n.tr_text(text)


def _localized_options(options):
    """Return display copies so language changes never mutate API constants."""
    return tuple(dict(option, label=_t(option.get("label", ""))) for option in options)


class _OptionRow(QtWidgets.QWidget):
    """One icon+label row. Selection is drawn by the row itself -- the same
    ``HotkeySelectableItemWidget`` pattern ``tools/hotkeys`` uses for its
    section/command lists: a ``rowSelected`` dynamic property flips a QSS
    background, and the native ``PE_FrameFocusRect`` style primitive draws
    the highlight border, so it matches whatever the current Qt style
    actually renders for a focused/selected row instead of a hand-picked
    color -- that's what makes it read as "native" rather than a flat
    stylesheet rectangle.
    """

    clicked = QtCore.Signal()
    colorClicked = QtCore.Signal(object)

    BASE_COLORS = ("#2b2b2b", "#2e2e2e")
    SELECTED_COLOR = "#5f88a8"

    def __init__(self, option, row_index, parent=None):
        super().__init__(parent)
        self._enabled_option = not option.get("disabled")
        self._selected = False

        base_color = self.BASE_COLORS[row_index % 2]
        self.setObjectName("TemporalControlsOptionRow")
        self.setProperty("rowSelected", False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#TemporalControlsOptionRow{background:%s;}"
            "#TemporalControlsOptionRow[rowSelected='true']{background:%s;}"
            % (base_color, self.SELECTED_COLOR)
        )
        if self._enabled_option:
            self.setCursor(QtCore.Qt.PointingHandCursor)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(6), 0)
        layout.setSpacing(wutil.DPI(6))

        # Optional color button before the icon -- used by the Temp Controls
        # Panel's rig list. It is deliberately the exact rounded-square
        # swatch used by both creation dialogs, rather than the old passive
        # painted dot. The button owns its click, so choosing a color does
        # not also select the row underneath it.
        color_suffix = option.get("color_suffix")
        if color_suffix:
            color_label = option.get("color_label") or _t("Change Color")
            button_size = max(1, int(round(wutil.DPI(30) * 0.7)))
            icon_size = max(1, int(round(wutil.DPI(28) * 0.7)))
            color_button = cw.create_tool_button_from_data(
                {
                    "key": "temporal_controls_rig_color{}".format(color_suffix),
                    "label": color_label,
                    "icon": icons.selection_set_color_icons.get(color_suffix),
                    "tooltip": color_label,
                },
                callback=None,
            )
            color_button.setFixedSize(button_size, button_size)
            color_button.setIconSize(QtCore.QSize(icon_size, icon_size))
            color_button.clicked.connect(lambda *_args, button=color_button: self.colorClicked.emit(button))
            layout.addWidget(color_button)

        icon_size = wutil.DPI(16)
        icon_label = QtWidgets.QLabel(self)
        icon_label.setFixedSize(icon_size, icon_size)
        row_icon = icons.get(option.get("icon"), icons.temporal_controls)
        icon_label.setPixmap(QtGui.QIcon(row_icon).pixmap(icon_size, icon_size))
        layout.addWidget(icon_label)

        self.title_label = QtWidgets.QLabel(option["label"], self)
        self._text_color = "#cfcfcf" if self._enabled_option else "#6a6a6a"
        self.title_label.setStyleSheet("background:transparent;color:%s;" % self._text_color)
        layout.addWidget(self.title_label, 1)

        for watched in (icon_label, self.title_label):
            watched.installEventFilter(self)

    def is_enabled(self):
        return self._enabled_option

    def set_selected(self, selected):
        self._selected = bool(selected) and self._enabled_option
        self.setProperty("rowSelected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        if self._enabled_option:
            self.title_label.setStyleSheet(
                "background:transparent;color:%s;" % ("#ffffff" if self._selected else self._text_color)
            )
        self.update()

    def mousePressEvent(self, event):
        # self.isEnabled() is the *effective* state (own + every ancestor,
        # including the containing _OptionList) -- checked in addition to
        # the per-option "disabled" flag so a whole disabled/locked list
        # (see TempControlsPanelWindow's Orientation column) can't still be
        # clicked into just because this row itself was never individually
        # disabled.
        if self._enabled_option and self.isEnabled():
            self.clicked.emit()
        super().mousePressEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.MouseButtonPress and self._enabled_option and self.isEnabled():
            self.clicked.emit()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._selected:
            return
        option = QtWidgets.QStyleOptionFocusRect()
        option.initFrom(self)
        option.rect = self.rect()
        option.state |= QtWidgets.QStyle.State_HasFocus
        keyboard_focus = getattr(QtWidgets.QStyle, "State_KeyboardFocusChange", None)
        if keyboard_focus is not None:
            option.state |= keyboard_focus
        option.backgroundColor = self.palette().color(QtGui.QPalette.Window)
        painter = QtGui.QPainter(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_FrameFocusRect, option, painter, self)


class _OptionList(QtWidgets.QListWidget):
    """A compact single-select list of icon+label rows for one option column."""

    ROW_HEIGHT = wutil.DPI(28)
    # Emits the newly selected option id (or None once a not-required list
    # is explicitly cleared) -- the Temp Controls Panel's rig/control lists
    # listen to this to react to selection; System/Position/Orientation's
    # columns don't need to (their creation dialog just reads
    # selected_id() at confirm time), so this is unused there.
    selectionChanged = QtCore.Signal(object)
    colorRequested = QtCore.Signal(object, object)

    def __init__(self, options, parent=None, cap_to_content=False):
        super().__init__(parent)
        # cap_to_content (Position/Orientation's columns only, see
        # TempControlsPanelWindow._build_space_column) means this list caps
        # its own height to exactly fit however many rows it has instead of
        # stretching into any extra space a taller window gives it (see
        # _content_height/refresh below). The rig/control lists -- and
        # System/Position/Orientation in the original creation dialog --
        # leave this off and just stretch/scroll normally, same as always.
        self._cap_to_content = cap_to_content
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setUniformItemSizes(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        if cap_to_content:
            # Off, not just AsNeeded -- _content_height's own height cap is
            # meant to fit every row exactly, so a vertical scrollbar should
            # never be needed; forcing it off avoids one popping into a
            # couple-px-short gap and clipping a row's own icon/swatch/
            # selected-highlight color. Lists that don't cap (rig/control)
            # keep the normal AsNeeded default -- they can genuinely have
            # more rows than fit and need to scroll.
            self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(
            """
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                outline: none;
            }
            QListWidget::item {
                border: none;
                padding: 0px;
                margin: 0px;
            }
            """
        )

        self._row_order = []
        self._rows_by_id = {}
        self._selected_id = None
        self.refresh(options)

    def refresh(self, options):
        """Rebuild every row from *options* -- used both at construction and
        by the Temp Controls Panel's rig/control lists, which repopulate
        dynamically as the scene changes rather than staying fixed like
        System/Position/Orientation's option sets do.

        If this list was built with cap_to_content=True, also caps its own
        height to exactly fit however many rows it has (see
        _content_height) -- a caller that wants a fixed height regardless
        of content (the original creation dialog's columns, via
        setFixedHeight after construction) still wins, since that call
        happens after this one and setFixedHeight pins both min and max."""
        self.clear()
        self._row_order = []
        self._rows_by_id = {}
        self._selected_id = None

        for row_index, option in enumerate(options):
            item = QtWidgets.QListWidgetItem(self)
            item.setFlags(QtCore.Qt.NoItemFlags)
            item.setSizeHint(QtCore.QSize(0, self.ROW_HEIGHT))

            option_id = option["id"]
            row = _OptionRow(option, row_index, parent=self)
            row.clicked.connect(lambda option_id=option_id: self.select_id(option_id))
            row.colorClicked.connect(
                lambda button, option_id=option_id: self.colorRequested.emit(option_id, button)
            )

            self.setItemWidget(item, row)
            self._row_order.append(option_id)
            self._rows_by_id[option_id] = row

        if self._cap_to_content:
            self.setMaximumHeight(self._content_height())

    def _content_height(self):
        # At least one row's worth even when empty, so the box doesn't
        # collapse to a sliver -- +4 covers the stylesheet's 1px top/bottom
        # border plus a little slack for QAbstractItemView's own internal
        # frame/spacing this doesn't otherwise account for (scrollbar is
        # forced off above regardless, so this only affects a possible
        # couple px of empty space at the bottom, never a scrollbar/clip).
        rows = max(1, len(self._row_order))
        return rows * self.ROW_HEIGHT + 4

    def select_id(self, option_id, required=True):
        """Select *option_id*. When *required* (System/Position/Orientation's
        default), an invalid/disabled id falls back to the first enabled
        row -- these columns always want something selected. When not
        required (the panel's rig/control lists), an invalid id -- including
        an explicit ``None`` -- just clears the selection instead."""
        row = self._rows_by_id.get(option_id) if option_id is not None else None
        if row is None or not row.is_enabled():
            row, option_id = None, None
            if required:
                for candidate_id in self._row_order:
                    candidate = self._rows_by_id[candidate_id]
                    if candidate.is_enabled():
                        row, option_id = candidate, candidate_id
                        break

        for row_id, candidate_row in self._rows_by_id.items():
            candidate_row.set_selected(row_id == option_id)
        self._selected_id = option_id
        self.selectionChanged.emit(option_id)

    def selected_id(self):
        return self._selected_id

    def clear_selection(self):
        self.select_id(None, required=False)


class TemporalControlsDialog(customDialogs.QFlatToolBarPopupDialog):
    """Floating creation dialog, built the same way every other TKM popup
    (Bake Custom Interval, Animation Layers, Selector, ...) builds its
    icon+title header: ``self.title``/``self.icon`` set before
    ``super().__init__()``, then ``self.title_label.setText(self.title)``."""

    COLUMN_TITLE_STYLE = "color: #9a9a9a; font-weight: bold; font-size: %spx;" % wutil.DPI(11)

    def __init__(self, objects, parent=None, on_confirmed=None, on_rejected=None):
        self.title = "Temporal Controls"
        self.icon = icons.temporal_controls
        super().__init__(parent=parent, popup=False)
        self.title_label.setText(self.title)

        self.objects = list(objects or [])
        self.on_confirmed = on_confirmed
        self.on_rejected = on_rejected
        self._completed = False
        self._selected_color = None
        self._color_buttons = {}
        # Tracks Position's own last value (independent of Orientation) so
        # _on_position_space_changed can tell whether Orientation was
        # "following" Position (selected_id() still equal to the value
        # Position just moved away from) -- see that method.
        self._last_position_space = None

        self.setObjectName("temporal_controls_dialog")

        self._build_columns()
        self.position_list.selectionChanged.connect(self._on_position_space_changed)
        self._build_reset_row()
        self._build_entry_row()
        self._build_color_row()

        self._apply_last_used_options()
        self.resize(self.OPEN_WIDTH, self.OPEN_HEIGHT)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_columns(self):
        columns_row = QtWidgets.QWidget()
        columns_row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        columns_layout = QtWidgets.QHBoxLayout(columns_row)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(wutil.DPI(6))

        self.system_list = self._add_column(columns_layout, _t("System"), _localized_options(api.SYSTEMS))
        self.position_list = self._add_column(columns_layout, _t("Position"), _localized_options(api.SPACES))
        self.orientation_list = self._add_column(columns_layout, _t("Orientation"), _localized_options(api.SPACES))

        self.mainLayout.addWidget(columns_row, 1)

    def _add_column(self, parent_layout, title, options):
        column = QtWidgets.QWidget()
        column.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        column_layout = QtWidgets.QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(wutil.DPI(3))

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(self.COLUMN_TITLE_STYLE)
        column_layout.addWidget(title_label)

        option_list = _OptionList(options)
        option_list.setMinimumHeight(wutil.DPI(120))
        option_list.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        column_layout.addWidget(option_list, 1)

        parent_layout.addWidget(column, 1)
        return option_list

    def _build_reset_row(self):
        self.reset_checkbox = QtWidgets.QCheckBox(_t("Reset Properties"))
        self.reset_checkbox.setStyleSheet("color: #a8a8a8; font-size: %spx;" % wutil.DPI(11))
        self.reset_checkbox.toggled.connect(self._on_reset_toggled)
        self.mainLayout.addSpacing(wutil.DPI(4))
        self.mainLayout.addWidget(self.reset_checkbox)

    def _build_entry_row(self):
        top_row = QtWidgets.QWidget()
        top_row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        top_row_layout = QtWidgets.QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(wutil.DPI(6))

        self.entry_frame = QtWidgets.QFrame()
        self.entry_frame.setObjectName("temporal_controls_entry")
        self.entry_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.entry_frame.setFixedHeight(wutil.DPI(34))
        self.entry_frame.setStyleSheet(
            """
            QFrame#temporal_controls_entry {
                background-color: %s;
                border-radius: 7px;
            }
            """
            % COLORS.toolbar.turquoise.hex
        )
        entry_layout = QtWidgets.QHBoxLayout(self.entry_frame)
        entry_layout.setContentsMargins(wutil.DPI(10), 0, wutil.DPI(10), 0)
        entry_layout.setSpacing(0)

        self.name_field = cw.PersistentPlaceholderLineEdit()
        self.name_field.setPlaceholderText(_t("Optional Label"))
        self.name_field.setAlignment(QtCore.Qt.AlignCenter)
        self.name_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.name_field.setStyleSheet(
            """
            QLineEdit {
                background-color: transparent;
                border: none;
                color: #101010;
                padding: 0px 6px;
            }
            QLineEdit::placeholder {
                color: transparent;
            }
            """
        )
        self.name_field.returnPressed.connect(self._confirm)
        entry_layout.addWidget(self.name_field, 1)
        top_row_layout.addWidget(self.entry_frame, 1)

        self.confirm_button = cw.QFlatButton(text="", icon=icons.apply, highlight=True)
        self.confirm_button.setFixedWidth(wutil.DPI(36))
        self.confirm_button.clicked.connect(self._confirm)
        top_row_layout.addWidget(self.confirm_button, 0, QtCore.Qt.AlignVCenter)

        self.cancel_button = QtWidgets.QToolButton()
        self.cancel_button.setAutoRaise(True)
        self.cancel_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.cancel_button.setIcon(QtGui.QIcon(icons.close))
        self.cancel_button.setIconSize(QtCore.QSize(wutil.DPI(18), wutil.DPI(18)))
        self.cancel_button.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        self.cancel_button.setStyleSheet(
            """
            QToolButton { background-color: transparent; border: none; }
            QToolButton:hover { background-color: rgba(255, 255, 255, 0.08); }
            QToolButton:pressed { background-color: rgba(0, 0, 0, 0.45); }
            """
        )
        self.cancel_button.clicked.connect(self.close)
        top_row_layout.addWidget(self.cancel_button, 0, QtCore.Qt.AlignVCenter)

        self.mainLayout.addSpacing(wutil.DPI(4))
        self.mainLayout.addWidget(top_row)

    def _build_color_row(self):
        # Matches selection_sets' own color row exactly (size policy, spacing,
        # trailing stretch) -- see selection_sets/widgets.py's equivalent
        # _build_color_row/_create_color_button, which this was modeled on.
        self.color_row = QtWidgets.QWidget()
        self.color_row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        color_layout = QtWidgets.QHBoxLayout(self.color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(wutil.DPI(1))

        for color in COLORS.selection.all:
            color_layout.addWidget(self._create_color_button(color))

        color_layout.addStretch(1)
        self.mainLayout.addSpacing(wutil.DPI(4))
        self.mainLayout.addWidget(self.color_row)
        self.mainLayout.setSpacing(wutil.DPI(4))

    def _create_color_button(self, color):
        tooltip = "Apply with {} Control Color".format(color.label)
        # Same size as selection_sets' own swatches.
        button_size = max(1, int(round(wutil.DPI(30) * 0.7)))
        icon_size = max(1, int(round(wutil.DPI(28) * 0.7)))
        button = cw.create_tool_button_from_data(
            {
                "key": "temporal_controls_color_{}".format(color.suffix),
                "label": tooltip,
                "icon": icons.selection_set_color_icons.get(color.suffix),
                "tooltip": tooltip,
            },
            callback=None,
        )
        button.setFixedSize(button_size, button_size)
        button.setIconSize(QtCore.QSize(icon_size, icon_size))
        # One click both picks the color and confirms -- "Apply with this
        # color" -- the same behavior selection_sets' own color row uses for
        # its creation dialog (_create_set_from_color_click).
        button.connect_tool(lambda *_args, c=color: self._apply_with_color(c), checkable=True)
        button.setStyleSheet(button.styleSheet() + " QToolButton:checked { background-color: #4a4a4a; color: #ffffff; }")
        self._color_buttons[color.suffix] = button
        return button

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _apply_last_used_options(self):
        last = api.get_last_used_options()
        self.system_list.select_id(last.get("system") or api.DEFAULT_SYSTEM)
        self.position_list.select_id(last.get("position_space") or api.DEFAULT_SPACE)
        self.orientation_list.select_id(last.get("orientation_space") or api.DEFAULT_SPACE)
        self._set_selected_color(COLORS.selection.get(last.get("color"), COLORS.selection.default))

    def _on_position_space_changed(self, space_id):
        """Move Orientation along with Position when Orientation was still
        matching Position's previous space -- i.e. it read as "following"
        Position rather than a deliberate separate choice. If the user had
        already picked a different Orientation space, that choice is left
        alone. There's no explicit lock toggle here (unlike the Temp
        Controls Panel's own lock_button on an existing control) since this
        dialog is a one-shot creation form -- "still equal to Position"
        is the only signal available for "was following"."""
        previous_position_space = self._last_position_space
        if previous_position_space is not None and self.orientation_list.selected_id() == previous_position_space:
            self.orientation_list.select_id(space_id)
        self._last_position_space = space_id

    def _on_reset_toggled(self, checked):
        if not checked:
            return
        self.system_list.select_id(api.DEFAULT_SYSTEM)
        self.position_list.select_id(api.DEFAULT_SPACE)
        self.orientation_list.select_id(api.DEFAULT_SPACE)
        self._set_selected_color(COLORS.selection.default)
        self.name_field.clear()

    def _set_selected_color(self, color):
        self._selected_color = color
        for suffix, button in self._color_buttons.items():
            block = button.blockSignals(True)
            button.setChecked(suffix == color.suffix)
            button.blockSignals(block)

    def _apply_with_color(self, color):
        self._set_selected_color(color)
        self._confirm()

    # ------------------------------------------------------------------
    # Chrome
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._place_current_size_near_cursor()

    OPEN_WIDTH = wutil.DPI(320)
    OPEN_HEIGHT = wutil.DPI(396)

    def _place_current_size_near_cursor(self):
        w, h = self.width(), self.height()
        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()

        v_offset = wutil.DPI(30)
        y = cursor_pos.y() - h - v_offset
        if y < geo.top():
            y = cursor_pos.y() + v_offset

        x = cursor_pos.x() - w // 2
        x = max(geo.left(), min(x, geo.right() - w))
        y = max(geo.top(), min(y, geo.bottom() - h))
        self.move(x, y)

    def closeEvent(self, event):
        if not self._completed and callable(self.on_rejected):
            self.on_rejected()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------

    def _confirm(self):
        system = self.system_list.selected_id() or api.DEFAULT_SYSTEM
        position_space = self.position_list.selected_id() or api.DEFAULT_SPACE
        orientation_space = self.orientation_list.selected_id() or api.DEFAULT_SPACE
        label = self.name_field.text().strip()
        color = self._selected_color or COLORS.selection.default

        # Persisted per-session (TheKeyMachine's settings store lives on disk
        # under the current Maya user prefs, so it also survives a restart --
        # a superset of "remember for this Maya instance").
        if self.reset_checkbox.isChecked():
            api.clear_last_used_options()
        else:
            api.save_last_used_options(system, position_space, orientation_space, color.suffix)

        self._completed = True
        self.close()
        if callable(self.on_confirmed):
            # self.objects is the full selection captured when the dialog was
            # opened -- every object gets a control, not just one.
            self.on_confirmed(system, position_space, orientation_space, label, color.hex)
