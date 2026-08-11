"""Custom Qt widgets used by Search."""

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore
from TheKeyMachine.core import trigger
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


class SearchLineEdit(QtWidgets.QLineEdit):
    """Line edit that paints the selected tool's remaining text as a suffix."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._completion = ""
        self._completion_secondary = False
        self._result_icon_visible = False
        self._result_icon = QtWidgets.QLabel(self)
        self._result_icon.setAlignment(QtCore.Qt.AlignCenter)
        self._result_icon.setFixedSize(wutil.DPI(42), wutil.DPI(42))
        self._result_icon.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._result_icon.hide()

    def set_completion(self, completion, secondary=False):
        completion = completion or ""
        secondary = bool(secondary)
        if completion == self._completion and secondary == self._completion_secondary:
            return
        self._completion = completion
        self._completion_secondary = secondary
        self.update()

    def set_result_icon(self, icon_path=None, fallback_text=""):
        self._result_icon_visible = bool(icon_path or fallback_text)
        self._result_icon.clear()
        if icon_path:
            self._result_icon.setPixmap(
                QtGui.QIcon(icon_path).pixmap(wutil.DPI(36), wutil.DPI(36))
            )
            self._result_icon.setStyleSheet("background:transparent;")
        elif fallback_text:
            self._result_icon.setText(str(fallback_text)[:2].upper())
            self._result_icon.setStyleSheet(
                "background:transparent;color:#aeb8c0;font-size:%spx;" % wutil.DPI(11)
            )
        self._result_icon.setVisible(self._result_icon_visible)
        self.setTextMargins(0, 0, wutil.DPI(46) if self._result_icon_visible else 0, 0)
        self._position_result_icon()
        self.update()

    def _position_result_icon(self):
        margin = wutil.DPI(5)
        self._result_icon.move(
            self.width() - self._result_icon.width() - margin,
            max(0, int((self.height() - self._result_icon.height()) / 2)),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_result_icon()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._completion or self.cursorPosition() != len(self.text()):
            return

        cursor_rect = self.cursorRect()
        # Start immediately after the caret. Using its left edge can paint the
        # completion over the last entered characters on some Qt/Maya versions.
        # cursorRect is the most reliable reference across Maya/Qt versions.
        # Its right edge includes extra cursor advance, so apply the measured
        # optical correction instead of deriving placement from outer padding.
        completion_x = cursor_rect.right() - max(1, int(wutil.DPI(1))) - 3
        completion_right = (
            self._result_icon.x() - wutil.DPI(4)
            if self._result_icon_visible
            else self.contentsRect().right() - wutil.DPI(8)
        )
        available = completion_right - completion_x
        if available <= 0:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        # Text antialiasing visually darkens #444444 over the input background;
        # this compensated value matches the floating shell perceptually.
        painter.setPen(QtGui.QColor("#606060"))
        if self._completion_secondary:
            completion_font = QtGui.QFont(self.font())
            completion_font.setPointSizeF(max(7.0, completion_font.pointSizeF() * 0.72))
            painter.setFont(completion_font)
        suffix = painter.fontMetrics().elidedText(self._completion, QtCore.Qt.ElideRight, available)
        rect = QtCore.QRect(
            completion_x,
            cursor_rect.top() - 1,
            available,
            cursor_rect.height(),
        )
        painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, suffix)
        painter.end()


class SearchResultItemWidget(QtWidgets.QWidget):
    """Compact, fixed-layout result row with selection that never shifts its icon."""

    clicked = QtCore.Signal()
    invoked = QtCore.Signal()

    def __init__(self, row, row_index=0, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setObjectName("SearchResultItemWidget")
        self.setProperty("rowSelected", False)
        self.setProperty("rowBase", "#2b2b2b" if row_index % 2 == 0 else "#2e2e2e")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#SearchResultItemWidget{background:%s;}"
            "#SearchResultItemWidget[rowSelected='true']{background:#5f88a8;}"
            % ("#2b2b2b" if row_index % 2 == 0 else "#2e2e2e")
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(2), 0, wutil.DPI(6), 0)
        layout.setSpacing(wutil.DPI(3))

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_path = row.get("icon")
        if icon_path:
            self.icon_label.setPixmap(QtGui.QIcon(icon_path).pixmap(wutil.DPI(19), wutil.DPI(19)))
        else:
            title = str(row.get("title") or row.get("command") or "")
            fallback = str(row.get("badge_text") or title[:2]).upper()
            self.icon_label.setText(fallback)
            self.icon_label.setStyleSheet("background:transparent;color:#aeb8c0;font-size:%spx;" % wutil.DPI(8))
        layout.addWidget(self.icon_label)

        self.check_box = None
        if row.get("checkable"):
            is_choice_row = bool(row.get("choice_group"))
            self.check_box = wutil.make_row_check_control(
                self, "SearchResultCheckBox", radio=is_choice_row
            )
            self.check_box.setProperty("tkm_window_anchor", False)
            # A radio row's size is already fixed to its indicator by
            # make_row_check_control -- see its docstring for why a looser
            # box here would throw the checked-state gradient off-center.
            if not is_choice_row:
                self.check_box.setFixedSize(wutil.DPI(15), wutil.DPI(18))
            self.check_box.setFocusPolicy(QtCore.Qt.NoFocus)
            # Dispatch by name instead of caching a direct callable -- see the
            # same fix in mods/hotkeysMod.py's HotkeyCommandItemWidget for why.
            command_name = row.get("command")
            can_run = bool(command_name) and trigger.has_command(command_name)
            toolCommon.connect_tool_control(
                self.check_box,
                (lambda *_args, name=command_name: trigger.execute_command(name)) if can_run else None,
                checkable=True,
                getter=row.get("get_checked"),
                setter=row.get("set_checked"),
                changed_signal=row.get("changed_signal"),
                bind_fn=row.get("bind_checked_fn"),
                state_key=row.get("state_key"),
            )
            wutil.bind_choice_row_state(self.check_box, row.get("choice_group"), row.get("choice_value"))
            layout.addWidget(self.check_box)

        self.title_label = QtWidgets.QLabel(str(row.get("title") or row.get("command") or ""), self)
        self.title_label.setStyleSheet("background:transparent;color:#d0d0d0;")
        layout.addWidget(self.title_label, 1)

        for watched in (self.icon_label, self.title_label):
            watched.installEventFilter(self)

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("rowSelected", self._selected)
        self.title_label.setStyleSheet(
            "background:transparent;color:%s;"
            % ("#ffffff" if selected else "#d0d0d0")
        )
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.invoked.emit()
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self.invoked.emit()
            return True
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.clicked.emit()
        return super().eventFilter(watched, event)

"""Floating Search dialog and its UI interaction workflow."""

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore

import TheKeyMachine.core.trigger as trigger
from TheKeyMachine.data import icons
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools.search import controller
from TheKeyMachine.tools.search.controller import (
    SEARCH_SETTINGS_NAMESPACE,
    SEARCH_TEXT_KEY,
    SearchCatalogThread,
)
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import util as wutil


class SearchDialog(customDialogs.QFlatFloatingWidget):
    def __init__(self, parent=None):
        super().__init__(popup=True, closeButton=False, parent=parent or wutil.get_maya_qt())
        # A real Qt popup owns focus while open and consumes the first click
        # outside it. That click dismisses Search instead of also operating Maya.
        self.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        # The shared floating shell sizes itself to content by default. Search
        # owns two explicit size states and must remain user-resizable while
        # expanded, so disable that automatic min/max constraint here.
        self.root_layout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.setProperty("tkm_floating_widget", True)
        self.setObjectName("search_window")
        self.setWindowTitle("Search")
        self._default_width = wutil.DPI(620)
        self._collapsed_height = wutil.DPI(68)
        self._expanded_height = int(round(self._default_width / 1.5))
        self._results_expanded = False
        self.resize(self._default_width, self._collapsed_height)
        self.setMinimumWidth(wutil.DPI(440))
        self.setMinimumHeight(self._collapsed_height)
        self.setMaximumHeight(self._collapsed_height)
        # Search uses the same frameless draggable shell as Attribute Switcher.
        # Its grip is enabled only while search results are expanded.
        self.grip.hide()
        self.grip.setEnabled(False)

        self._rows = []
        self._catalog_ready = False
        self._pending_result_rows = []
        self._pending_result_index = 0
        self._choice_groups = {}
        self._restoring_position = False
        self._position_save_timer = QtCore.QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.timeout.connect(self._save_position)
        self._result_build_timer = QtCore.QTimer(self)
        self._result_build_timer.setSingleShot(True)
        self._result_build_timer.timeout.connect(self._populate_next_result_batch)

        layout = self.mainLayout
        layout.setContentsMargins(wutil.DPI(8), wutil.DPI(8), wutil.DPI(8), wutil.DPI(8))
        layout.setSpacing(wutil.DPI(8))

        search_row = QtWidgets.QWidget(self)
        search_row_layout = QtWidgets.QHBoxLayout(search_row)
        search_row_layout.setContentsMargins(0, 0, 0, 0)
        search_row_layout.setSpacing(wutil.DPI(8))

        search_icon = QtWidgets.QLabel(search_row)
        search_icon.setFixedSize(wutil.DPI(52), wutil.DPI(52))
        search_icon.setAlignment(QtCore.Qt.AlignCenter)
        search_icon.setPixmap(QtGui.QIcon(icons.search).pixmap(wutil.DPI(44), wutil.DPI(44)))
        search_row_layout.addWidget(search_icon)

        self.search_input = SearchLineEdit(search_row)
        self.search_input.setPlaceholderText("TKM Search")
        placeholder_role = getattr(QtGui.QPalette, "PlaceholderText", None)
        if placeholder_role is not None:
            input_palette = self.search_input.palette()
            input_palette.setColor(placeholder_role, QtGui.QColor("#606060"))
            self.search_input.setPalette(input_palette)
        self.search_input.setClearButtonEnabled(False)
        self.search_input.setMinimumHeight(wutil.DPI(52))
        font = self.search_input.font()
        font.setPointSize(24)
        self.search_input.setFont(font)
        self.search_input.setStyleSheet(
            "QLineEdit{background:#252525;border:1px solid #4b4b4b;border-radius:%spx;"
            "padding:0 %spx;color:#eeeeee;selection-background-color:#5f88a8;}"
            % (wutil.DPI(7), wutil.DPI(8))
        )
        search_row_layout.addWidget(self.search_input, 1)
        layout.addWidget(search_row)

        self.results_panel = QtWidgets.QWidget(self)
        results_panel_layout = QtWidgets.QVBoxLayout(self.results_panel)
        results_panel_layout.setContentsMargins(0, 0, 0, 0)
        results_panel_layout.setSpacing(wutil.DPI(6))

        self.results = QtWidgets.QListWidget(self.results_panel)
        self.results.setObjectName("SearchToolResults")
        self.results.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.results.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.results.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.results.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.results.setStyleSheet(
            "#SearchToolResults{background:#2b2b2b;color:#d8d8d8;border:1px solid #3d3d3d;}"
            "#SearchToolResults::item{margin:0px;padding:0px;border:none;}"
            "#SearchToolResults::item:selected{margin:0px;padding:0px;border:none;background:transparent;}"
        )
        results_panel_layout.addWidget(self.results, 1)

        self.hint_widget = QtWidgets.QWidget(self.results_panel)
        hint_layout = QtWidgets.QHBoxLayout(self.hint_widget)
        hint_layout.setContentsMargins(
            0, 0, wutil.DPI(6), wutil.DPI(18)
        )
        hint_layout.setSpacing(wutil.DPI(6))
        hint_icon = QtWidgets.QLabel(self.hint_widget)
        hint_icon.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        hint_icon.setAlignment(QtCore.Qt.AlignCenter)
        hint_icon.setPixmap(QtGui.QIcon(icons.about).pixmap(wutil.DPI(22), wutil.DPI(22)))
        hint_layout.addWidget(hint_icon)
        hint_label = QtWidgets.QLabel("Press Enter to run the command", self.hint_widget)
        hint_layout.addWidget(hint_label)
        hint_layout.addStretch(1)
        results_panel_layout.addWidget(self.hint_widget)
        layout.addWidget(self.results_panel, 1)
        self.results_panel.hide()

        self.search_input.installEventFilter(self)
        self.results.installEventFilter(self)
        self.search_input.textChanged.connect(self._filter_results)
        self.results.currentItemChanged.connect(self._update_completion)

        saved_text = settings.get_setting(
            SEARCH_TEXT_KEY, "", namespace=SEARCH_SETTINGS_NAMESPACE
        ) or ""
        self.search_input.setText(str(saved_text))
        self._filter_results(self.search_input.text())
        self._restore_or_center()
        self._start_catalog_load()

    def _start_catalog_load(self):
        self._catalog_thread = SearchCatalogThread(self)
        self._catalog_thread.loaded.connect(self._on_catalog_loaded)
        self._catalog_thread.failed.connect(self._on_catalog_failed)
        self._catalog_thread.start()

    def _on_catalog_loaded(self, rows):
        self._rows = list(rows or [])
        self._catalog_ready = True
        self._filter_results(self.search_input.text())

    def _on_catalog_failed(self, error):
        self._rows = []
        self._catalog_ready = True
        if error:
            print("[TheKeyMachine] Search catalog failed to load: {}".format(error))
        self._filter_results(self.search_input.text())

    def _filter_results(self, text):
        self._result_build_timer.stop()
        self._pending_result_rows = []
        self._pending_result_index = 0
        self._choice_groups = {}
        settings.set_setting(
            SEARCH_TEXT_KEY, str(text), namespace=SEARCH_SETTINGS_NAMESPACE
        )
        if not str(text).strip():
            self.results.clear()
            self.search_input.set_completion("")
            self.search_input.set_result_icon()
            self._set_results_visible(False)
            return

        if not self._catalog_ready:
            self.results.clear()
            self.search_input.set_completion("")
            self.search_input.set_result_icon()
            self._set_results_visible(False)
            return

        matches = controller.ranked_command_rows(self._rows, text)

        self.results.clear()
        self._pending_result_rows = matches
        self._set_results_visible(True)
        self._populate_next_result_batch()

    def _populate_next_result_batch(self):
        batch_end = min(self._pending_result_index + 20, len(self._pending_result_rows))
        for row_index in range(self._pending_result_index, batch_end):
            row = self._pending_result_rows[row_index]
            title = str(row.get("title") or row.get("command") or "")
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, row.get("command"))
            item.setData(QtCore.Qt.UserRole + 1, title)
            item.setData(QtCore.Qt.UserRole + 2, row.get("icon"))
            item.setData(QtCore.Qt.UserRole + 3, row.get("badge_text") or title[:2])
            item.setSizeHint(QtCore.QSize(0, wutil.DPI(20)))
            self.results.addItem(item)
            widget = SearchResultItemWidget(row, row_index=row_index, parent=self.results)
            widget.clicked.connect(lambda target=item: self._select_result_item(target))
            widget.invoked.connect(lambda target=item: self._invoke_result_item(target))
            self.results.setItemWidget(item, widget)
            wutil.sync_choice_group_button(
                self._choice_groups, row.get("choice_group"), widget.check_box, parent=self.results
            )

        first_batch = self._pending_result_index == 0
        self._pending_result_index = batch_end
        if first_batch and self.results.count():
            self.results.setCurrentRow(0)
        elif not self._pending_result_rows:
            self.search_input.set_completion("")

        if self._pending_result_index < len(self._pending_result_rows):
            self._result_build_timer.start(0)

    def _set_results_visible(self, visible):
        visible = bool(visible)
        if visible == self._results_expanded:
            return

        self._results_expanded = visible
        if visible:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(wutil.DPI(220))
            self.results_panel.show()
            self.resize(self.width(), self._expanded_height)
            self.grip.setEnabled(True)
            self.grip.show()
            self.grip.raise_()
        else:
            self.results_panel.hide()
            self.grip.hide()
            self.grip.setEnabled(False)
            self.setMinimumHeight(self._collapsed_height)
            self.setMaximumHeight(self._collapsed_height)
            self.resize(self.width(), self._collapsed_height)

    def _update_completion(self, current, _previous=None):
        previous = _previous
        if previous is not None:
            previous_widget = self.results.itemWidget(previous)
            if previous_widget:
                previous_widget.set_selected(False)
        if current is None:
            self.search_input.set_completion("")
            self.search_input.set_result_icon()
            return
        current_widget = self.results.itemWidget(current)
        if current_widget:
            current_widget.set_selected(True)
        title = current.data(QtCore.Qt.UserRole + 1) or ""
        completion = controller.completion_suffix(self.search_input.text(), title)
        if completion:
            self.search_input.set_completion(completion)
        elif self.search_input.text().strip():
            self.search_input.set_completion(" - {}".format(title), secondary=True)
        else:
            self.search_input.set_completion("")
        self.search_input.set_result_icon(
            current.data(QtCore.Qt.UserRole + 2),
            current.data(QtCore.Qt.UserRole + 3) or title,
        )

    def _select_result_item(self, item):
        self.results.setCurrentItem(item)
        self.search_input.setFocus()

    def _invoke_result_item(self, item):
        self.results.setCurrentItem(item)
        self.run_current_tool()

    def _move_selection(self, step):
        count = self.results.count()
        if not count:
            return
        row = self.results.currentRow()
        row = 0 if row < 0 else (row + step) % count
        self.results.setCurrentRow(row)
        self.results.scrollToItem(self.results.currentItem())

    def eventFilter(self, watched, event):
        if watched in (self.search_input, self.results) and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key_Down:
                self._move_selection(1)
                return True
            if key == QtCore.Qt.Key_Up:
                self._move_selection(-1)
                return True
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self.run_current_tool()
                return True
            if key == QtCore.Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def run_current_tool(self):
        item = self.results.currentItem()
        if item is None:
            return
        command = item.data(QtCore.Qt.UserRole)
        if not command:
            return
        settings.set_setting(
            SEARCH_TEXT_KEY, self.search_input.text(), namespace=SEARCH_SETTINGS_NAMESPACE
        )
        self.close()
        QtCore.QTimer.singleShot(0, lambda name=str(command): trigger.execute_command(name))

    def _restore_or_center(self):
        saved = controller.get_position()
        self._restoring_position = True
        try:
            if isinstance(saved, (list, tuple)) and len(saved) >= 2:
                self.move(int(saved[0]), int(saved[1]))
                self._clamp_to_screen()
                return
            self._move_to_default_position()
        finally:
            self._restoring_position = False

    def _move_to_default_position(self):
        parent = self.parentWidget() or wutil.get_maya_qt()
        geometry = parent.frameGeometry() if parent else QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            int(geometry.x() + (geometry.width() - self.width()) / 2),
            int(geometry.y() + (geometry.height() / 3.0)),
        )
        self._clamp_to_screen()

    def restore_default_position(self):
        self._restoring_position = True
        try:
            self._move_to_default_position()
        finally:
            self._restoring_position = False

    def _clamp_to_screen(self):
        center = self.frameGeometry().center()
        screen = QtGui.QGuiApplication.screenAt(center) or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = max(geometry.left(), min(self.x(), geometry.right() - self.width() + 1))
        y = max(geometry.top(), min(self.y(), geometry.bottom() - self.height() + 1))
        self.move(x, y)

    def focus_search(self):
        self.show()
        if self._results_expanded:
            self.resize(self.width(), self._expanded_height)
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self._restoring_position:
            self._position_save_timer.start(150)

    def _save_position(self):
        controller.set_position(self.pos().x(), self.pos().y())

    def closeEvent(self, event):
        settings.set_setting(
            SEARCH_TEXT_KEY, self.search_input.text(), namespace=SEARCH_SETTINGS_NAMESPACE
        )
        self._position_save_timer.stop()
        self._save_position()
        super().closeEvent(event)

    def hideEvent(self, event):
        from TheKeyMachine.tools.search import api as searchApi

        searchApi._emit_search_window_state(False)
        super().hideEvent(event)

    def resizeEvent(self, event):
        customDialogs.QFlatDialog.resizeEvent(self, event)
        grip = getattr(self, "grip", None)
        if grip is not None:
            size = grip.sizeHint()
            grip.setFixedSize(size)
            grip.move(self.width() - size.width(), self.height() - size.height())
            grip.raise_()
