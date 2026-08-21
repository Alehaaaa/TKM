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

from TheKeyMachine.data import icons
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.temporal_controls import api
from TheKeyMachine.ui.widgets import customDialogs, customWidgets as cw, util as wutil


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

        icon_size = wutil.DPI(16)
        icon_label = QtWidgets.QLabel(self)
        icon_label.setFixedSize(icon_size, icon_size)
        icon_label.setPixmap(QtGui.QIcon(icons.temporal_controls).pixmap(icon_size, icon_size))
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
        if self._enabled_option:
            self.clicked.emit()
        super().mousePressEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.MouseButtonPress and self._enabled_option:
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

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setUniformItemSizes(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
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

        for row_index, option in enumerate(options):
            item = QtWidgets.QListWidgetItem(self)
            item.setFlags(QtCore.Qt.NoItemFlags)
            item.setSizeHint(QtCore.QSize(0, self.ROW_HEIGHT))

            option_id = option["id"]
            row = _OptionRow(option, row_index, parent=self)
            row.clicked.connect(lambda option_id=option_id: self.select_id(option_id))

            self.setItemWidget(item, row)
            self._row_order.append(option_id)
            self._rows_by_id[option_id] = row

    def select_id(self, option_id):
        row = self._rows_by_id.get(option_id)
        if row is None or not row.is_enabled():
            row, option_id = None, None
            for candidate_id in self._row_order:
                candidate = self._rows_by_id[candidate_id]
                if candidate.is_enabled():
                    row, option_id = candidate, candidate_id
                    break

        for row_id, candidate_row in self._rows_by_id.items():
            candidate_row.set_selected(row_id == option_id)
        self._selected_id = option_id

    def selected_id(self):
        return self._selected_id


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

        self.setObjectName("temporal_controls_dialog")
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.grip.hide()

        self._build_columns()
        self._build_reset_row()
        self._build_entry_row()
        self._build_color_row()

        self._apply_last_used_options()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_columns(self):
        columns_row = QtWidgets.QWidget()
        columns_layout = QtWidgets.QHBoxLayout(columns_row)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(wutil.DPI(6))

        self.system_list = self._add_column(columns_layout, "System", api.SYSTEMS)
        self.position_list = self._add_column(columns_layout, "Position", api.SPACES)
        self.orientation_list = self._add_column(columns_layout, "Orientation", api.SPACES)

        self.mainLayout.addWidget(columns_row)

    def _add_column(self, parent_layout, title, options):
        column = QtWidgets.QWidget()
        column_layout = QtWidgets.QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(wutil.DPI(3))

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(self.COLUMN_TITLE_STYLE)
        column_layout.addWidget(title_label)

        option_list = _OptionList(options)
        option_list.setFixedHeight(wutil.DPI(190))
        column_layout.addWidget(option_list, 1)

        parent_layout.addWidget(column, 1)
        return option_list

    def _build_reset_row(self):
        self.reset_checkbox = QtWidgets.QCheckBox("Reset Properties")
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
        self.name_field.setPlaceholderText("Optional Label")
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
        self.color_row = QtWidgets.QWidget()
        color_layout = QtWidgets.QHBoxLayout(self.color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(wutil.DPI(1))

        for color in COLORS.selection.all:
            color_layout.addWidget(self._create_color_button(color))

        self.mainLayout.addSpacing(wutil.DPI(4))
        self.mainLayout.addWidget(self.color_row)
        self.mainLayout.setSpacing(wutil.DPI(4))

    def _create_color_button(self, color):
        tooltip = "Apply with {} Control Color".format(color.label)
        # Smaller than selection_sets' own swatches -- keeps the whole dialog
        # (which is sized to exactly fit this row) from getting too wide.
        button_size = max(1, int(round(wutil.DPI(22) * 0.7)))
        icon_size = max(1, int(round(wutil.DPI(20) * 0.7)))
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
        self._compress_to_contents()
        self.place_near_cursor()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.hide()

    def _compress_to_contents(self):
        # Width matches the color-swatch row exactly -- it's the narrowest
        # "natural" row, so pinning to it (rather than the wider column list)
        # keeps the dialog no bigger than it needs to be.
        margins = self.mainLayout.contentsMargins()
        target_width = self.color_row.sizeHint().width() + margins.left() + margins.right()
        self.setFixedWidth(target_width)
        self.adjustSize()

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
