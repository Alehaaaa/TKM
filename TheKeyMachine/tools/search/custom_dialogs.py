"""Floating Search dialog and its UI interaction workflow."""

from __future__ import annotations

from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets  # type: ignore

import TheKeyMachine.core.trigger as trigger
from TheKeyMachine.data import icons
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools.search import logic
from TheKeyMachine.tools.search.constants import (
    SEARCH_SETTINGS_NAMESPACE,
    SEARCH_TEXT_KEY,
)
from TheKeyMachine.tools.search import session_state
from TheKeyMachine.tools.search.custom_widgets import SearchLineEdit, SearchResultItemWidget
from TheKeyMachine.tools.search.workers import SearchCatalogThread
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

        matches = logic.ranked_command_rows(self._rows, text)

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
        completion = logic.completion_suffix(self.search_input.text(), title)
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
        saved = session_state.get_position()
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
        session_state.set_position(self.pos().x(), self.pos().y())

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
