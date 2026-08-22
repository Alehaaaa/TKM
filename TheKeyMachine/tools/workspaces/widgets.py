"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Modified by: Alehaaaa / alehaaaa.github.io



"""

"""The Workspaces editor window.

Six columns, left to right: Workspace, Toolbar, Position, Alignment, Color
Group, Tools. Selecting a Toolbar drives what the Position/Alignment/Color
Group/Tools columns show; selecting a Color Group drives what the Tools
column shows. Everything applies immediately to the live toolbar(s) -- there
is no separate "Apply" step, matching the toolbar's own right-click pinning
menu.

The Color Group column reorders whole color runs (see
``registry.group_sections_by_color`` / ``controller.get_color_groups``) as one
atomic unit rather than individual sections, matching how the toolbar itself
now visually clusters sections by color. A group spanning more than one
section shows every member's tools in the Tools column, one small header per
section.

Workspace/Toolbar/Position/Alignment/Color Group rows are styled like the
Hotkeys window's section list (tools/hotkeys/controller.py): alternating row shading
with a flat highlight fill on selection, rather than the list's native
selection palette. Tools is the one exception: rows there are checkable
buttons that fill with the section's color when pinned.
"""

import json

from maya import cmds

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets
from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets import customWidgets as cw
from TheKeyMachine.ui.widgets.util import DPI, is_valid_widget

from TheKeyMachine.tools.workspaces import controller

# Workspace/Toolbar/Position/Alignment/Color Group are simple, single-purpose
# picker columns -- taller rows read more like Maya's own list pickers.
# Tools is a dense list of many small toggles, so it stays compact.
ROW_HEIGHT_TALL = DPI(32)
ROW_HEIGHT_TOOLS = DPI(20)
ROW_HEIGHT_TOOLS_HEADER = DPI(26)

LIST_CONTAINER_STYLE = (
    "QListWidget{background:#2d2d2d;border:1px solid #3a3a3a;color:#d0d0d0;outline:none;}"
    "QListWidget::item{margin:0px;padding:0px;border:none;}"
)


def _swatch_icon(hex_color, size=13):
    """A small filled circle icon used as a section's color legend."""
    dim = max(1, int(DPI(size)))
    pixmap = QtGui.QPixmap(dim, dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(hex_color or "#787878"))
    painter.drawEllipse(QtCore.QRectF(1, 1, dim - 2, dim - 2))
    painter.end()
    return QtGui.QIcon(pixmap)


def _text_badge_qicon(text, size=16):
    """Short-text icon for tools with no real icon, exactly like Hotkeys'
    ``_text_badge_qicon`` (tools/hotkeys/controller.py) -- the same ``text`` field
    tool/slider-mode definitions already carry for this purpose.
    """
    dim = max(1, int(DPI(size)))
    pixmap = QtGui.QPixmap(int(DPI(size + 8)), dim)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtGui.QColor("#d0d0d0"))
    font = QtGui.QFont()
    font.setBold(True)
    font.setPixelSize(int(DPI(9)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, text or "")
    painter.end()
    return QtGui.QIcon(pixmap)


def _group_row_label(group):
    """Display title for one Color Group row: the first section's label, plus
    a "(+N)" count when the group clusters more than one section."""
    sections = group.get("sections") or []
    if not sections:
        return group.get("id") or ""
    if len(sections) == 1:
        return sections[0]["label"]
    return "{} (+{})".format(sections[0]["label"], len(sections) - 1)


def _group_row_tooltip(group):
    """Full member list for a Color Group row's tooltip."""
    sections = group.get("sections") or []
    return ", ".join(section["label"] for section in sections)


def _section_header_label(text):
    """A non-interactive divider naming which section's tools follow, used
    in the Tools column when a Color Group clusters multiple sections."""
    label = QtWidgets.QLabel(" " + text)
    label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
    label.setStyleSheet(
        "color:#8a8a8a;background:transparent;font-weight:bold;font-size:%spx;" % int(DPI(10))
    )
    return label


class _DropIndicator(QtWidgets.QFrame):
    """Line marking where a dragged row will land.

    Drawn over the viewport ourselves: rows in this window are opaque item
    widgets (not delegate-painted text), and item widgets sit on top of --
    and hide -- the view's own native drop-indicator painting.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(DPI(2))
        self.setStyleSheet("background-color: #5f88a8;")
        self.hide()


class ReorderableListWidget(QtWidgets.QListWidget):
    """A ``QListWidget`` of item widgets that can be drag-reordered.

    Drag-start (via selection) and the actual reorder-on-drop both stay on
    Qt's native ``InternalMove`` machinery -- that part already works
    correctly. What it gets wrong with item widgets instead of delegate-
    painted rows is purely visual: the default drag pixmap is blank (there's
    nothing for a delegate to render) and the native drop-indicator paints
    behind the item widgets, invisibly. Both are fixed here on top of the
    unchanged native path: the dragged row's own rendering follows the
    cursor at the point it was grabbed, and a line drawn ourselves marks
    the drop position.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._indicator = _DropIndicator(self.viewport())
        self._press_pos = None

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        super().mousePressEvent(event)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        widget = self.itemWidget(item) if item is not None else None
        if widget is None:
            super().startDrag(supportedActions)
            return

        rect = self.visualItemRect(item)
        hotspot = (self._press_pos - rect.topLeft()) if self._press_pos is not None else widget.rect().center()

        drag = QtGui.QDrag(self)
        drag.setMimeData(self.model().mimeData(self.selectedIndexes()))
        drag.setPixmap(widget.grab())
        drag.setHotSpot(hotspot)
        drag.exec_(supportedActions, QtCore.Qt.MoveAction)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        self._update_indicator(event.pos())

    def dragLeaveEvent(self, event):
        self._indicator.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._indicator.hide()
        super().dropEvent(event)

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


class _Column(QtWidgets.QWidget):
    """A titled, native-styled list used as one of the editor's selection columns."""

    def __init__(self, title, parent=None, list_widget_cls=QtWidgets.QListWidget):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DPI(4))

        title_label = QtWidgets.QLabel(title, self)
        title_label.setStyleSheet("color: #9a9a9a; font-size: %spx; font-weight: bold;" % int(DPI(10)))
        layout.addWidget(title_label)

        self.list_widget = list_widget_cls(self)
        self.list_widget.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.list_widget.setFocusPolicy(QtCore.Qt.NoFocus)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.list_widget.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list_widget.setStyleSheet(LIST_CONTAINER_STYLE)
        layout.addWidget(self.list_widget, 1)


class HotkeySelectableItemWidget(QtWidgets.QWidget):
    """Mirrors ``tools.hotkeys.controller.HotkeySelectableItemWidget``: alternating
    row shading with a flat highlight fill (plus a focus rect) on selection,
    painted by the widget itself instead of the list's native selection.
    """

    clicked = QtCore.Signal()

    def __init__(self, parent=None, base_color=None, selected_color=None):
        super().__init__(parent)
        self._selected = False
        self.setObjectName("WorkspacesSelectableItemWidget")
        self.setProperty("rowSelected", False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#WorkspacesSelectableItemWidget{background:%s;}"
            "#WorkspacesSelectableItemWidget[rowSelected='true']{background:%s;}"
            % ((base_color or "#2b2b2b"), (selected_color or base_color or "#2b2b2b"))
        )

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("rowSelected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

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


class SelectableRow(HotkeySelectableItemWidget):
    """A left-aligned icon(optional)+label row, styled like Hotkeys' section rows."""

    SELECTED_COLOR = "#5f88a8"

    def __init__(self, label, icon=None, description=None, row_index=0, parent=None):
        base_color = "#2b2b2b" if row_index % 2 == 0 else "#2e2e2e"
        super().__init__(parent, base_color=base_color, selected_color=self.SELECTED_COLOR)
        if description:
            self.setToolTip(description)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(DPI(8), 0, DPI(8), 0)
        layout.setSpacing(DPI(6))

        if icon is not None:
            icon_label = QtWidgets.QLabel(self)
            dim = int(DPI(15))
            icon_label.setFixedSize(dim, dim)
            icon_label.setAlignment(QtCore.Qt.AlignCenter)
            qicon = icon if isinstance(icon, QtGui.QIcon) else QtGui.QIcon(icon)
            icon_label.setPixmap(qicon.pixmap(dim, dim))
            icon_label.setStyleSheet("background:transparent;")
            layout.addWidget(icon_label)

        self.title_label = QtWidgets.QLabel(label, self)
        self.title_label.setStyleSheet("background:transparent;color:#d0d0d0;")
        layout.addWidget(self.title_label, 1)

        for watched in self.findChildren(QtWidgets.QLabel):
            watched.installEventFilter(self)

    def set_selected(self, selected):
        super().set_selected(selected)
        self.title_label.setStyleSheet(
            "background:transparent;color:%s;" % ("#ffffff" if selected else "#d0d0d0")
        )

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.clicked.emit()
        return super().eventFilter(watched, event)


class WorkspaceRow(HotkeySelectableItemWidget):
    """One row in the Workspace column: click to apply, double-click to rename."""

    SELECTED_COLOR = "#5f88a8"

    def __init__(self, ws_id, name, on_select, on_rename, row_index=0, parent=None):
        base_color = "#2b2b2b" if row_index % 2 == 0 else "#2e2e2e"
        super().__init__(parent, base_color=base_color, selected_color=self.SELECTED_COLOR)
        self.ws_id = ws_id
        self._on_select = on_select

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(DPI(4), 0, DPI(4), 0)
        layout.setSpacing(0)

        self.name_button = cw.InlineRenameButton(
            name, self,
            # Match the button's own "text-align:left;padding-left:6px"
            # style exactly: left inset 0 lets the editor's own 6px internal
            # padding (see _sync_inline_rename_style) land the text where the
            # button's real label sits, instead of the centered default. A
            # small top/bottom inset (vs. the default DPI(5)) gives the field
            # more height to work with.
            rename_alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            rename_margins=(0, DPI(2), DPI(6), DPI(2)),
        )
        self.name_button.setFlat(True)
        self.name_button.setCursor(QtCore.Qt.PointingHandCursor)
        # QPushButton's default vertical size policy is Fixed to its own
        # native size hint, so the layout below was only ever centering it
        # within the row instead of stretching it to the row's real height --
        # the rename editor, positioned relative to the button's own rect,
        # inherited that smaller height even though ROW_HEIGHT_TALL is taller.
        self.name_button.setFixedHeight(ROW_HEIGHT_TALL)
        # InlineRenameButton's editor defaults to near-black text
        # ("tkm_text_color", see customWidgets._sync_inline_rename_style),
        # meant for light buttons. Rows here are dark (#2b2b2b/#2e2e2e), so
        # that default is almost invisible against them -- not literally
        # clipped, but unreadable enough to look cut off. Use the same light
        # color the row's own label text uses instead.
        self.name_button.setProperty("tkm_text_color", "#ffffff")
        self.name_button.set_rename_target(ws_id, name, on_rename)
        self.name_button.clicked.connect(self._emit_select)
        layout.addWidget(self.name_button, 1)

        self._apply_button_style(False)

    def _emit_select(self, *_args):
        if callable(self._on_select):
            self._on_select(self.ws_id)

    def _apply_button_style(self, selected):
        # While a rename is active, the button's own stylesheet is holding
        # the text-hiding "color: transparent" override (see
        # InlineRenameButton._apply_hidden_text_style) -- overwriting it here
        # in response to a selection change elsewhere would undo that and
        # let the real, non-transparent label show through behind the editor.
        if self.name_button.is_renaming():
            return
        self.name_button.setStyleSheet(
            "QPushButton{background:transparent;color:%s;border:none;text-align:left;padding-left:6px;}"
            % ("#ffffff" if selected else "#d0d0d0")
        )

    def set_selected(self, selected):
        super().set_selected(selected)
        self._apply_button_style(selected)

    def start_inline_rename(self):
        self.name_button.start_inline_rename()

    def commit_rename(self):
        """Finish an in-progress rename (if any), applying its current text.
        Safe to call unconditionally."""
        self.name_button.commit_inline_rename()

    def set_rename_target(self, ws_id, name, on_rename):
        self.name_button.set_rename_target(ws_id, name, on_rename)


class ToolPinButton(QtWidgets.QToolButton):
    """A checkable row for one pinnable tool: checked -> filled with the section color.

    No checkbox indicator -- the whole row is the toggle, matching the
    toolbar's own tool buttons (see ``customWidgets.QFlatToolButton``).
    """

    def __init__(self, section_id, tool_id, label, icon_path, badge_text, color_hex, checked, on_toggle, parent=None):
        super().__init__(parent)
        self.section_id = section_id
        self.tool_id = tool_id
        self._color_hex = color_hex or "#5D5D5D"
        self._on_toggle = on_toggle

        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setText(" " + (label or tool_id))
        if icon_path:
            self.setIcon(QtGui.QIcon(icon_path))
        elif badge_text:
            self.setIcon(_text_badge_qicon(badge_text))
        self.setIconSize(QtCore.QSize(int(DPI(16)), int(DPI(16))))
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setFixedHeight(ROW_HEIGHT_TOOLS)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        self.set_checked_silently(checked)
        self.toggled.connect(self._handle_toggle)

    def _refresh_style(self):
        if self.isChecked():
            self.setStyleSheet(
                "QToolButton { text-align: left; padding-left: 8px; background-color: %s;"
                " color: #1a1a1a; border: none; font-weight: bold; }" % self._color_hex
            )
        else:
            self.setStyleSheet(
                "QToolButton { text-align: left; padding-left: 8px; background-color: transparent;"
                " color: #d0d0d0; border: none; }"
                " QToolButton:hover { background-color: #3a3a3a; }"
            )

    def _handle_toggle(self, checked):
        self._refresh_style()
        if callable(self._on_toggle):
            self._on_toggle(self.section_id, self.tool_id, checked)

    def set_checked_silently(self, checked):
        blocked = self.blockSignals(True)
        try:
            self.setChecked(bool(checked))
        finally:
            self.blockSignals(blocked)
        self._refresh_style()


class WorkspacesWindow(customDialogs.QFlatDialog):
    def __init__(self, parent=None):
        from TheKeyMachine.core import i18n
        from TheKeyMachine.tools import registry

        super().__init__(parent=parent)
        # Reuses the workspaces_window tool's own lang.json label -- same
        # word already translated for its menu entry.
        workspaces_label = registry.get_tool("workspaces_window").get("label") or "Workspaces"
        self.setWindowTitle(workspaces_label)
        self.resize(DPI(1080), DPI(620))
        self.setMinimumSize(DPI(1000), DPI(540))

        self._current_toolbar_id = "main"
        self._current_workspace_id = None
        self._current_group_id = None
        self._current_group_key = None
        self._current_groups_by_id = {}
        self._watched_group_sections = []
        self._workspace_rows = {}
        self._toolbar_rows = {}
        self._position_rows = {}
        self._alignment_rows = {}
        self._group_rows = {}

        main = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setSpacing(DPI(8))
        self.addWindowHeader(
            parentLayout=main_layout,
            icon=icons.align,
            text=workspaces_label,
            textColor="#d8d8d8",
        )

        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setContentsMargins(DPI(2), 0, DPI(2), 0)
        columns_layout.setSpacing(DPI(10))
        main_layout.addLayout(columns_layout, 1)

        self.workspace_column = _Column(i18n.tr("workspaces_column_workspace", "Workspace"), self)
        self.toolbar_column = _Column(i18n.tr("workspaces_column_toolbar", "Toolbar"), self)
        # "Position" reuses the dock menu's own "Position" section id.
        self.position_column = _Column(i18n.tr("position_section", "Position"), self)
        self.alignment_column = _Column(i18n.tr("workspaces_column_alignment", "Alignment"), self)
        self.group_column = _Column(
            i18n.tr("workspaces_column_color_group", "Color Group"),
            self,
            list_widget_cls=ReorderableListWidget,
        )
        # "Tools" reuses the Hotkeys editor's own panel-header word.
        self.tools_column = _Column(i18n.tr("hotkeys_panel_tools", "Tools"), self)

        for column in (
            self.workspace_column,
            self.toolbar_column,
            self.position_column,
            self.alignment_column,
            self.group_column,
            self.tools_column,
        ):
            columns_layout.addWidget(column, 1)

        # Qt's internal-move drag needs a real selection to know what's being
        # dragged; NoSelection (used everywhere else, since these rows paint
        # their own highlight) would silently swallow the drag. The native
        # selection rectangle this re-enables is invisible anyway -- each
        # SelectableRow paints an opaque background over its whole item rect.
        self.group_column.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.group_column.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.group_column.list_widget.setDefaultDropAction(QtCore.Qt.MoveAction)
        # The placement line is drawn by ReorderableListWidget itself, on top
        # of the item widgets that would otherwise hide the native one.
        self.group_column.list_widget.setDropIndicatorShown(False)
        self.group_column.list_widget.model().rowsMoved.connect(self._on_groups_reordered)

        self.root_layout.insertWidget(0, main, 1)
        self._build_bottom_bar()

        self._build_toolbar_list()
        self._refresh_workspace_list()
        self._select_toolbar(self._current_toolbar_id)

    # ---------------------------------------------------------------- bottom bar

    def _build_bottom_bar(self):
        # The second button is context-sensitive: a custom (user-created)
        # workspace can be deleted outright, while a built-in one only ever
        # gets its defaults restored. Rebuilding the whole bar (rather than
        # mutating one button in place) keeps this to one code path that
        # always reflects whichever workspace is currently selected.
        if controller.is_custom_workspace(self._current_workspace_id):
            second_button = customDialogs.QFlatDialogButton(
                "Delete Workspace",
                callback=self._delete_workspace,
                icon=icons.get("trash"),
                i18n_key="workspaces_delete_button",
            )
        else:
            # Reuses the toolbar pinning menu's own "Restore Defaults" word.
            second_button = customDialogs.QFlatDialogButton(
                "Restore Defaults", callback=self._restore_defaults, icon=icons.reload,
                i18n_key="restore_defaults",
            )

        self.setBottomBar(
            buttons=[
                customDialogs.QFlatDialogButton(
                    "New Workspace",
                    callback=self._create_new_workspace,
                    icon=icons.add,
                    i18n_key="workspaces_new_button",
                ),
                second_button,
                customDialogs.QFlatDialogButton(
                    "Import", callback=self._import_workspaces, icon=icons.get("import"),
                    i18n_key="workspaces_import_button",
                ),
                customDialogs.QFlatDialogButton(
                    "Export", callback=self._export_workspaces, icon=icons.get("export"),
                    i18n_key="workspaces_export_button",
                ),
            ],
            closeButton=True,
        )

    def _import_workspaces(self, *_args):
        from TheKeyMachine.core import i18n

        result = cmds.fileDialog2(
            fileMode=1,
            caption=i18n.tr("workspaces_import_caption", "Import Workspaces"),
            fileFilter="JSON Files (*.json)",
        )
        if not result:
            return
        try:
            with open(result[0], "r") as handle:
                data = json.load(handle)
        except Exception as exc:
            cmds.warning("Could not import workspaces: {}".format(exc))
            return

        if not controller.import_workspaces_data(data):
            cmds.warning("Invalid workspaces file.")
            return
        self._refresh_workspace_list()

    def _export_workspaces(self, *_args):
        from TheKeyMachine.core import i18n

        result = cmds.fileDialog2(
            fileMode=0,
            caption=i18n.tr("workspaces_export_caption", "Export Workspaces"),
            fileFilter="JSON Files (*.json)",
        )
        if not result:
            return
        path = result[0]
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w") as handle:
                json.dump(controller.export_workspaces_data(), handle, indent=2, sort_keys=True)
        except Exception as exc:
            cmds.warning("Could not export workspaces: {}".format(exc))

    def _restore_defaults(self, *_args):
        from TheKeyMachine.core import i18n
        from TheKeyMachine.core import workspaces

        ws_id = controller.get_active_workspace()
        ws_name = workspaces.get_active_workspace_name()
        clicked = customDialogs.QFlatConfirmDialog.question(
            self,
            i18n.tr("restore_defaults", "Restore Defaults"),
            i18n.tr("workspaces_restore_message", "Restore the '{}' workspace defaults?").format(ws_name),
            buttons=[customDialogs.QFlatConfirmDialog.Yes, customDialogs.QFlatConfirmDialog.Cancel],
            highlight=customDialogs.QFlatConfirmDialog.Yes,
            title=i18n.tr("workspaces_restore_heading", "Restore toolbar defaults?"),
            icon=icons.warning,
        )
        if clicked != customDialogs.QFlatConfirmDialog.Yes:
            return

        controller.apply_workspace(ws_id)
        self._refresh_position_list()
        self._refresh_alignment_list()
        self._refresh_group_list()

    def _delete_workspace(self, *_args):
        from TheKeyMachine.core import i18n

        ws_id = self._current_workspace_id
        if not ws_id or not controller.is_custom_workspace(ws_id):
            return

        ws_name = next(
            (entry["name"] for entry in controller.list_workspaces() if entry["id"] == ws_id), ws_id
        )
        clicked = customDialogs.QFlatConfirmDialog.question(
            self,
            i18n.tr("workspaces_delete_button", "Delete Workspace"),
            i18n.tr(
                "workspaces_delete_message", "Delete the '{}' workspace? This cannot be undone."
            ).format(ws_name),
            buttons=[customDialogs.QFlatConfirmDialog.Yes, customDialogs.QFlatConfirmDialog.Cancel],
            highlight=customDialogs.QFlatConfirmDialog.Yes,
            title=i18n.tr("workspaces_delete_heading", "Delete workspace?"),
            icon=icons.warning,
        )
        if clicked != customDialogs.QFlatConfirmDialog.Yes:
            return

        controller.delete_workspace(ws_id)
        # Deleting a workspace only changes which id is active if it was the
        # one selected -- always re-apply whatever is active now so the live
        # toolbars never keep showing a workspace that no longer exists.
        controller.apply_workspace(controller.get_active_workspace())
        self._refresh_workspace_list()
        self._select_toolbar(self._current_toolbar_id)

    # ---------------------------------------------------------------- workspace column

    def _refresh_workspace_list(self, select_id=None):
        list_widget = self.workspace_column.list_widget
        list_widget.clear()
        self._workspace_rows = {}

        select_id = select_id or controller.get_active_workspace()
        self._current_workspace_id = select_id

        for row_index, entry in enumerate(controller.list_workspaces()):
            item = QtWidgets.QListWidgetItem(list_widget)
            row = WorkspaceRow(
                entry["id"], entry["name"], self._select_workspace, self._commit_workspace_rename, row_index=row_index
            )
            item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TALL))
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)
            self._workspace_rows[entry["id"]] = row
            row.set_selected(entry["id"] == select_id)

        self._build_bottom_bar()

    def _commit_active_workspace_rename(self):
        """Finish whichever workspace row is mid-rename (if any), applying
        its current text. Most other selection changes in this window (a
        different toolbar, position, alignment, or color group) happen by
        clicking a plain, non-focusable row rather than a real button, so
        they never trigger the editor's own focus-out -- without this, a
        rename left in progress would just be silently abandoned rather than
        applied the moment the user moves on to something else."""
        for row in self._workspace_rows.values():
            if is_valid_widget(row):
                row.commit_rename()

    def _select_workspace(self, ws_id):
        self._commit_active_workspace_rename()
        controller.apply_workspace(ws_id)
        self._current_workspace_id = ws_id
        for row_id, row in self._workspace_rows.items():
            row.set_selected(row_id == ws_id)
        self._build_bottom_bar()
        self._refresh_position_list()
        self._refresh_alignment_list()
        self._refresh_group_list()

    def _commit_workspace_rename(self, ws_id, new_name):
        controller.rename_workspace(ws_id, new_name)
        row = self._workspace_rows.get(ws_id)
        if row is not None and is_valid_widget(row):
            row.set_rename_target(ws_id, new_name, self._commit_workspace_rename)

    def _create_new_workspace(self, *_args):
        existing_names = {entry["name"] for entry in controller.list_workspaces()}
        base_name = "Workspace"
        name = base_name
        counter = 2
        while name in existing_names:
            name = "{} {}".format(base_name, counter)
            counter += 1

        ws_id = controller.create_workspace_from_current(name)
        self._refresh_workspace_list(select_id=ws_id)
        row = self._workspace_rows.get(ws_id)
        if row is not None:
            row.start_inline_rename()

    # ---------------------------------------------------------------- toolbar column

    def _build_toolbar_list(self):
        list_widget = self.toolbar_column.list_widget
        list_widget.clear()
        self._toolbar_rows = {}
        for row_index, entry in enumerate(controller.get_toolbars()):
            item = QtWidgets.QListWidgetItem(list_widget)
            row = SelectableRow(entry["label"], row_index=row_index)
            row.clicked.connect(lambda toolbar_id=entry["id"]: self._select_toolbar(toolbar_id))
            item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TALL))
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)
            self._toolbar_rows[entry["id"]] = row

    def _select_toolbar(self, toolbar_id):
        self._commit_active_workspace_rename()
        self._current_toolbar_id = toolbar_id
        for tb_id, row in self._toolbar_rows.items():
            row.set_selected(tb_id == toolbar_id)

        self._refresh_position_list()
        self._refresh_alignment_list()
        self._refresh_group_list()

    # ---------------------------------------------------------------- position column

    def _refresh_position_list(self):
        list_widget = self.position_column.list_widget
        list_widget.clear()
        self._position_rows = {}
        current = controller.get_current_position(self._current_toolbar_id)
        for row_index, (position_id, label, description) in enumerate(
            controller.get_position_options(self._current_toolbar_id)
        ):
            item = QtWidgets.QListWidgetItem(list_widget)
            row = SelectableRow(label, description=description, row_index=row_index)
            row.clicked.connect(lambda position_id=position_id: self._select_position(position_id))
            item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TALL))
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)
            self._position_rows[position_id] = row
            row.set_selected(position_id == current)

    def _select_position(self, position_id):
        self._commit_active_workspace_rename()
        controller.set_position(self._current_toolbar_id, position_id)
        for pid, row in self._position_rows.items():
            row.set_selected(pid == position_id)

    # ---------------------------------------------------------------- alignment column

    def _refresh_alignment_list(self):
        list_widget = self.alignment_column.list_widget
        list_widget.clear()
        self._alignment_rows = {}
        current = controller.get_current_alignment(self._current_toolbar_id)
        for row_index, (alignment_name, label, description) in enumerate(controller.get_alignment_options()):
            item = QtWidgets.QListWidgetItem(list_widget)
            row = SelectableRow(label, description=description, row_index=row_index)
            row.clicked.connect(lambda alignment_name=alignment_name: self._select_alignment(alignment_name))
            item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TALL))
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)
            self._alignment_rows[alignment_name] = row
            row.set_selected(alignment_name == current)

    def _select_alignment(self, alignment_name):
        self._commit_active_workspace_rename()
        controller.set_alignment(self._current_toolbar_id, alignment_name)
        for name, row in self._alignment_rows.items():
            row.set_selected(name == alignment_name)

    # ---------------------------------------------------------------- color group column

    def _refresh_group_list(self, select_section_id=None):
        list_widget = self.group_column.list_widget
        list_widget.clear()
        self._group_rows = {}
        groups = controller.get_color_groups(self._current_toolbar_id)
        # Cached for the rest of this window's lifetime until the next
        # refresh: _select_group/_refresh_tools_list/_on_groups_reordered all
        # need to look a group up by id right after this same list was just
        # computed, and re-querying the controller (which rescans every
        # toolbar section) each time would just repeat this exact work.
        self._current_groups_by_id = {group["id"]: group for group in groups}
        select_id = None
        for row_index, group in enumerate(groups):
            item = QtWidgets.QListWidgetItem(list_widget)
            item.setData(QtCore.Qt.UserRole, group["id"])
            row = SelectableRow(
                _group_row_label(group),
                icon=_swatch_icon(group["color"]),
                description=_group_row_tooltip(group),
                row_index=row_index,
            )
            row.clicked.connect(lambda group_id=group["id"]: self._select_group(group_id))
            item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TALL))
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)
            self._group_rows[group["id"]] = row
            if select_section_id and select_section_id in group.get("section_ids", ()):
                select_id = group["id"]

        self._detach_group_watch()
        self._current_group_id = None
        self._current_group_key = None

        if select_id:
            self._select_group(select_id)
        elif groups:
            self._select_group(groups[0]["id"])
        else:
            self._refresh_tools_list()

    def _on_groups_reordered(self, *_args):
        list_widget = self.group_column.list_widget
        # Identify the dragged group by one of its member section ids, not
        # its own id string: that string is a concatenation of member
        # section ids (see controller.get_color_groups), which this very
        # reorder can change if it merges or splits color runs. The section
        # identity survives that even when the group id doesn't.
        dragged_item = list_widget.currentItem()
        dragged_group_id = dragged_item.data(QtCore.Qt.UserRole) if dragged_item is not None else None
        dragged_group = self._current_groups_by_id.get(dragged_group_id) or {}
        dragged_section_ids = dragged_group.get("section_ids") or ()
        dragged_section_id = dragged_section_ids[0] if dragged_section_ids else None

        new_order = [list_widget.item(row).data(QtCore.Qt.UserRole) for row in range(list_widget.count())]
        controller.reorder_color_groups(self._current_toolbar_id, new_order)
        # Reordering groups can change which sections end up color-adjacent,
        # so two groups may merge (or a group may split) -- rebuild so the
        # column reflects whatever the new run boundaries actually are, and
        # keep whatever group the dragged section landed in selected (a
        # rebuild would otherwise always default back to the first group).
        # Deferred: rebuilding synchronously here would delete list items
        # while Qt's own internal-move drag handling is still unwinding.
        QtCore.QTimer.singleShot(0, lambda: self._refresh_group_list(select_section_id=dragged_section_id))

    def _select_group(self, group_id):
        self._commit_active_workspace_rename()
        group_key = (self._current_toolbar_id, group_id)
        if group_key != getattr(self, "_current_group_key", None):
            self._detach_group_watch()
            self._current_group_id = group_id
            self._current_group_key = group_key
            self._refresh_tools_list()
            if group_id is not None:
                self._watched_group_sections = controller.watch_group_pins(
                    self._current_toolbar_id, group_id, self._on_live_pins_changed
                )

        for gid, row in self._group_rows.items():
            row.set_selected(gid == group_id)

    def _detach_group_watch(self):
        if self._watched_group_sections:
            controller.unwatch_group_pins(self._watched_group_sections, self._on_live_pins_changed)
        self._watched_group_sections = []

    def _on_live_pins_changed(self, *_args):
        # Deferred: this can fire synchronously from inside a ToolPinButton's
        # own toggled signal (clicking a row in this same list), and
        # rebuilding the list synchronously would delete that button mid-click.
        QtCore.QTimer.singleShot(0, lambda: self._refresh_tools_list(preserve_scroll=True))

    # ---------------------------------------------------------------- tools column

    def _refresh_tools_list(self, preserve_scroll=False):
        list_widget = self.tools_column.list_widget
        if not is_valid_widget(list_widget):
            return
        scroll_value = list_widget.verticalScrollBar().value() if preserve_scroll else 0
        list_widget.clear()

        if self._current_group_id:
            group = self._current_groups_by_id.get(self._current_group_id) or {}
            color = group.get("color") or "#5D5D5D"
            member_sections = group.get("sections") or []
            show_headers = len(member_sections) > 1

            for section in member_sections:
                if show_headers:
                    header_item = QtWidgets.QListWidgetItem(list_widget)
                    header_item.setFlags(QtCore.Qt.NoItemFlags)
                    header_item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TOOLS_HEADER))
                    list_widget.addItem(header_item)
                    list_widget.setItemWidget(header_item, _section_header_label(section["label"]))

                for tool in controller.get_section_tools(self._current_toolbar_id, section["id"]):
                    item = QtWidgets.QListWidgetItem(list_widget)
                    row = ToolPinButton(
                        section["id"], tool["id"], tool["label"], tool.get("icon"), tool.get("badge_text"), color,
                        tool["checked"], self._on_tool_toggled,
                    )
                    row.setToolTip(tool.get("description") or "")
                    item.setSizeHint(QtCore.QSize(0, ROW_HEIGHT_TOOLS))
                    list_widget.addItem(item)
                    list_widget.setItemWidget(item, row)

        if preserve_scroll:
            list_widget.verticalScrollBar().setValue(scroll_value)

    def _on_tool_toggled(self, section_id, tool_id, checked):
        controller.set_tool_pinned(self._current_toolbar_id, section_id, tool_id, checked)

    # ---------------------------------------------------------------- lifecycle

    def showEvent(self, event):
        # The window is a singleton that is shown/hidden rather than rebuilt
        # (see tools.workspaces.api), and its pin-change watch is torn down on
        # close. Resync everything from the live toolbars each time it comes
        # back, so nothing pinned/renamed/reordered while it was hidden is
        # shown stale, and the watch is always attached to the right section.
        super().showEvent(event)
        self._refresh_workspace_list()
        self._select_toolbar(self._current_toolbar_id)

    def closeEvent(self, event):
        self._detach_group_watch()
        super().closeEvent(event)
