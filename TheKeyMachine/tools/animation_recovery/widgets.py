"""Animation Recovery history window."""

from datetime import datetime, timedelta
import os

from maya import cmds

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets
from TheKeyMachine.core import trigger
from TheKeyMachine.data import icons
from TheKeyMachine.tools import registry
from TheKeyMachine.tools.animation_recovery import controller
from TheKeyMachine.ui.widgets import customDialogs, customWidgets
from TheKeyMachine.ui.widgets import util as wutil


_dialog = None

# Newest first: top connects down, middle connects both ways, bottom connects
# up. A single checkpoint has no connector. The circle closes each endpoint.
_STATUS_ICONS = {
    "white": (icons.recovery_dot_white, icons.recovery_dot_white_first,
              icons.recovery_dot_white_last, icons.recovery_dot_white_single),
    "green": (icons.recovery_dot_green, icons.recovery_dot_green_first,
              icons.recovery_dot_green_last, icons.recovery_dot_green_single),
    "muted_green": (icons.recovery_dot_green_muted, icons.recovery_dot_green_muted_first,
                    icons.recovery_dot_green_muted_last, icons.recovery_dot_green_muted_single),
}


def _status_icon(status, row_index, row_count):
    through, top, bottom, single = _STATUS_ICONS.get(status, _STATUS_ICONS["white"])
    if row_count == 1:
        return single
    if row_index == 0:
        return top
    if row_index == row_count - 1:
        return bottom
    return through


def _display_date(value):
    today = datetime.now().date()
    if value.date() == today:
        prefix = "Today"
    elif value.date() == today - timedelta(days=1):
        prefix = "Yesterday"
    else:
        prefix = value.strftime("%b %d, %Y")
    return "{}, {}".format(prefix, value.strftime("%H:%M:%S"))


def _details_date(value):
    if not isinstance(value, datetime):
        return "Unknown"
    return value.strftime("%A, %B %d, %Y at %I:%M:%S %p")


def _range_text(value):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return "Unknown"

    def _number(item):
        if item is None:
            return "Unknown"
        number = float(item)
        return str(int(number)) if number.is_integer() else "{:g}".format(number)

    return "[{}, {}]".format(_number(value[0]), _number(value[1]))


def _frame_text(value):
    if value is None:
        return "Unknown"
    return "{:.1f}".format(float(value))


def _reason_text(value):
    return {
        "animation": "Animation Change",
        "dag": "Hierarchy Change",
        "scene_save": "Scene Save",
        "recovery": "Recovered Point",
        "transform": "Attribute Change",
        "layer": "Animation Layer Change",
        "crash": "Crash Scene Save",
    }.get(value, "Animation Change")


def _empty_state(tree, text):
    label = QtWidgets.QLabel(text, tree.viewport())
    label.setAlignment(QtCore.Qt.AlignCenter)
    label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
    label.setStyleSheet("color:#a8a8a8;background:transparent;")
    layout = QtWidgets.QVBoxLayout(tree.viewport())
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(label)
    label.hide()
    return label


def _row_identity(item):
    if item is None:
        return None
    data = item.data(0, QtCore.Qt.UserRole)
    return data.get("scene_id") if isinstance(data, dict) else data


def _scroll_state(tree):
    top = tree.itemAt(1, 1)
    return (_row_identity(top), tree.visualItemRect(top).top() if top else 0,
            tree.verticalScrollBar().value(), tree.horizontalScrollBar().value())


def _restore_scroll(tree, state):
    identity, offset, vertical, horizontal = state
    tree.doItemsLayout()
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        if identity is not None and _row_identity(item) == identity:
            tree.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtTop)
            vertical = tree.verticalScrollBar().value() - offset
            break
    tree.verticalScrollBar().setValue(vertical)
    tree.horizontalScrollBar().setValue(horizontal)


class AnimationRecoveryDialog(customDialogs.QFlatDialog):
    def __init__(self, parent=None):
        self.browse_scenes = False
        self._scene_reader = None
        self.dismissal_tokens = []
        self.history_scene_id = None
        self.startup_mode = False
        self.extra_entries = []
        self.requested_path = None
        super().__init__(parent=parent)
        self.setObjectName("tkmAnimationRecoveryDialog")
        self.setWindowTitle("Animation Recovery")
        self.setMinimumSize(wutil.DPI(720), wutil.DPI(360))
        self.resize(wutil.DPI(820), wutil.DPI(470))
        main = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setSpacing(wutil.DPI(8))
        self.addWindowHeader(
            parentLayout=main_layout,
            icon=icons.animation_recovery,
            text=registry.get_tool("animation_recovery").get("label") or "Animation Recovery",
            textColor="#d8d8d8",
        )
        main_layout.addLayout(self._build_content(main), 1)
        self.root_layout.insertWidget(0, main, 1)
        self._build_bottom_bar()
        service = controller.get_service()
        if service is not None:
            service.snapshotSaved.connect(self._snapshot_saved)
            service.historyMaintained.connect(self._history_maintained)
            manager = getattr(service, "manager", None)
            if manager is not None:
                manager.scene_opened.connect(self._scene_changed)
                manager.scene_new.connect(self._scene_changed)
        self.reload()

    def _build_content(self, content):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(wutil.DPI(8))

        self.scene_browser = self._build_scene_browser(content)
        self.scene_browser.hide()
        scene_heading = QtWidgets.QHBoxLayout()
        scene_heading.setSpacing(wutil.DPI(8))
        self.scenes_toggle = QtWidgets.QToolButton(content)
        self.scenes_toggle.setFixedSize(wutil.DPI(28), wutil.DPI(28))
        self.scenes_toggle.setAutoRaise(False)
        self.scenes_toggle.setCheckable(True)
        self.scenes_toggle.setArrowType(QtCore.Qt.UpArrow)
        self.scenes_toggle.setToolTip("Show scene histories")
        self.scenes_toggle.toggled.connect(self._toggle_scenes)
        scene_heading.addWidget(self.scenes_toggle)
        self.scene_label = QtWidgets.QLabel(content)
        self.scene_label.setStyleSheet(
            "color:#dedede; font-size:%spx; font-weight:bold;" % wutil.DPI(12)
        )
        self.scene_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        scene_heading.addWidget(self.scene_label, 1)
        self.scene_modified_label = QtWidgets.QLabel(content)
        self.scene_modified_label.setStyleSheet("color:#bcbcbc;font-size:%spx;" % wutil.DPI(11))
        scene_heading.addWidget(self.scene_modified_label)
        self.refresh_scenes_button = QtWidgets.QToolButton(content)
        self.refresh_scenes_button.setFixedSize(wutil.DPI(28), wutil.DPI(28))
        self.refresh_scenes_button.setAutoRaise(False)
        self.refresh_scenes_button.setIcon(QtGui.QIcon(icons.refresh))
        self.refresh_scenes_button.setToolTip("Refresh scene histories")
        self.refresh_scenes_button.clicked.connect(self._refresh_scenes)
        scene_heading.addWidget(self.refresh_scenes_button)
        layout.addLayout(scene_heading)
        layout.addWidget(self.scene_browser)

        self.tree = QtWidgets.QTreeWidget(content)
        self.tree.setObjectName("animationRecoveryTree")
        self.tree.setHeaderLabels(["Change", "Date"])
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setUniformRowHeights(True)
        self.tree.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.checkpoints_empty = _empty_state(self.tree, "No checkpoints yet")
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self.tree.setColumnWidth(0, wutil.DPI(28))
        self.tree.setIconSize(QtCore.QSize(wutil.DPI(22), wutil.DPI(22)))
        tree_palette = self.tree.palette()
        tree_palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#333333"))
        tree_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#383838"))
        self.tree.setPalette(tree_palette)
        self.tree.setStyleSheet(
            """
            QTreeWidget#animationRecoveryTree {
                border:1px solid #3a3a3a;
                color:#c8c8c8;
                outline:0;
            }
            QTreeWidget#animationRecoveryTree::item {
                height:%spx;
                border:0;
                padding-left:%spx;
            }
            QTreeWidget#animationRecoveryTree::item:selected {
                background:#505050;
                color:#eeeeee;
            }
            """ % (wutil.DPI(22), wutil.DPI(5))
        )
        self.tree.itemSelectionChanged.connect(self._sync_actions)

        self.details_frame = QtWidgets.QFrame(content)
        self.details_frame.setObjectName("animationRecoveryDetails")
        self.details_frame.setStyleSheet(
            "QFrame#animationRecoveryDetails { background:transparent; border:0; }"
            "QFrame#animationRecoveryDetails QLabel { background:transparent; border:0; color:#bdbdbd; }"
        )
        details_layout = QtWidgets.QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(wutil.DPI(8))
        details_grid = QtWidgets.QGridLayout()
        details_grid.setContentsMargins(0, 0, 0, 0)
        details_grid.setHorizontalSpacing(wutil.DPI(8))
        details_grid.setVerticalSpacing(wutil.DPI(7))
        self._details_labels = {}
        fields = (
            ("source_file", "Source file:"),
            ("location", "Location:"),
            ("date", "Date:"),
            ("reason", "Reason:"),
            ("current_frame", "Current Frame:"),
            ("playback_range", "Playback Range:"),
            ("animation_range", "Animation Range:"),
            ("selected_objects", "Selected Objects:"),
        )
        for row, (key, title) in enumerate(fields):
            title_label = QtWidgets.QLabel(title, self.details_frame)
            title_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            value_label = QtWidgets.QLabel("", self.details_frame)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            details_grid.addWidget(title_label, row, 0)
            details_grid.addWidget(value_label, row, 1)
            self._details_labels[key] = value_label
        details_grid.setColumnStretch(1, 1)
        details_layout.addLayout(details_grid)
        details_layout.addStretch(1)

        sections = QtWidgets.QGridLayout()
        sections.setContentsMargins(0, 0, 0, 0)
        sections.setHorizontalSpacing(wutil.DPI(12))
        sections.setVerticalSpacing(wutil.DPI(8))
        sections.setColumnStretch(0, 3)
        sections.setColumnStretch(1, 2)
        sections.setRowStretch(1, 1)
        for column, title in enumerate(("Checkpoints", "Details")):
            label = QtWidgets.QLabel(title, content)
            label.setStyleSheet("color:#bcbcbc;font-size:%spx;" % wutil.DPI(11))
            sections.addWidget(label, 0, column)
        sections.addWidget(self.tree, 1, 0)
        details_scroll = QtWidgets.QScrollArea(content)
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        details_scroll.setContentsMargins(0, 0, 0, 0)
        details_scroll.setWidget(self.details_frame)
        details_scroll.setStyleSheet("QScrollArea{background:transparent;}")
        details_scroll.viewport().setAutoFillBackground(False)
        self.details_frame.setAutoFillBackground(False)
        sections.addWidget(details_scroll, 1, 1)
        layout.addLayout(sections, 1)
        return layout

    def _build_scene_browser(self, parent):
        panel = QtWidgets.QWidget(parent)
        layout = QtWidgets.QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(wutil.DPI(12))
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        self.scenes_tree = QtWidgets.QTreeWidget(panel)
        self.scenes_tree.setHeaderLabels(["Scene", "Last Modified"])
        self.scenes_tree.setRootIsDecorated(False)
        self.scenes_tree.setUniformRowHeights(True)
        self.scenes_tree.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.scenes_empty = _empty_state(self.scenes_tree, "No scene histories yet")
        self.scenes_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.scenes_tree.setMinimumHeight(wutil.DPI(150))
        self.scenes_tree.setMaximumHeight(wutil.DPI(230))
        self.scenes_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.scenes_tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.scenes_tree.currentItemChanged.connect(self._history_selected)
        layout.addWidget(self.scenes_tree, 0, 0)
        details = QtWidgets.QVBoxLayout()
        details.setContentsMargins(wutil.DPI(12), wutil.DPI(10), wutil.DPI(12), wutil.DPI(10))
        self.scene_summary = QtWidgets.QLabel("Select a scene to browse its checkpoints.", panel)
        self.scene_summary.setWordWrap(True)
        self.scene_summary.setTextFormat(QtCore.Qt.PlainText)
        self.scene_summary.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        details.addWidget(self.scene_summary)
        details.addStretch(1)
        self.merge_scenes_button = customWidgets.QFlatButton(
            text="Smart Merge Checkpoints", highlight=True, parent=panel)
        self.merge_scenes_button.setToolTip(
            "Keep the first checkpoint, scene saves, and the latest checkpoint; merge intermediate changes.")
        self.merge_scenes_button.clicked.connect(lambda: self._maintain_scene_history("merge"))
        details.addWidget(self.merge_scenes_button)
        self.delete_scene_button = customWidgets.QFlatButton(
            text="Delete All Scene Checkpoints", parent=panel)
        self.delete_scene_button.clicked.connect(lambda: self._maintain_scene_history("delete"))
        details.addWidget(self.delete_scene_button)
        layout.addLayout(details, 0, 1)
        return panel

    def _toggle_scenes(self, expanded):
        self.scene_browser.setVisible(expanded)
        self.scenes_toggle.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.UpArrow)
        self.scenes_toggle.setToolTip("Hide scene histories" if expanded else "Show scene histories")
        if expanded:
            self._refresh_scenes()

    def _refresh_scenes(self, *_args):
        if self._scene_reader is not None and self._scene_reader.isRunning():
            return
        self.refresh_scenes_button.setEnabled(False)
        # Reuse the Hotkeys background reader. Parent to the service so closing
        # the window cannot destroy a running thread.
        reader = wutil.BackgroundCallThread(controller.list_recovery_scenes, controller.get_service())
        self._scene_reader = reader
        reader.loaded.connect(self._scenes_loaded)
        reader.failed.connect(self._scenes_failed)
        reader.finished.connect(reader.deleteLater)
        reader.finished.connect(self._scene_read_finished)
        reader.start()

    def _scene_read_finished(self):
        self._scene_reader = None
        self.refresh_scenes_button.setEnabled(True)

    def _scenes_failed(self, error):
        self.scene_summary.setText("Scene histories could not be read: " + error)

    def _scenes_loaded(self, scenes):
        if not self.browse_scenes:
            return
        current_id = controller.current_scene_id()
        selected_id = self.history_scene_id or current_id
        scroll = _scroll_state(self.scenes_tree)
        self.scenes_tree.blockSignals(True)
        self.scenes_tree.clear()
        selected = None
        for scene in scenes:
            item = QtWidgets.QTreeWidgetItem([scene["name"], _display_date(datetime.fromtimestamp(scene["modified"]))])
            item.setSizeHint(0, QtCore.QSize(0, wutil.DPI(24)))
            item.setData(0, QtCore.Qt.UserRole, scene)
            if scene["scene_id"] == current_id:
                for column in (0, 1):
                    font = item.font(column)
                    font.setBold(True)
                    item.setFont(column, font)
            item.setToolTip(0, scene["source"])
            item.setToolTip(1, "Latest recorded animation change")
            self.scenes_tree.addTopLevelItem(item)
            if scene["scene_id"] == selected_id:
                selected = item
        if selected is not None:
            self.scenes_tree.setCurrentItem(selected)
        self.scenes_tree.blockSignals(False)
        self.scenes_empty.setVisible(not scenes)
        _restore_scroll(self.scenes_tree, scroll)
        if selected is not None:
            self._history_selected(selected, None)
        elif not scenes:
            self.scene_summary.setText("No scene histories recorded yet.")

    def _history_selected(self, current, _previous):
        if current is None:
            return
        scene = current.data(0, QtCore.Qt.UserRole)
        changed_scene = scene["scene_id"] != (self.history_scene_id or controller.current_scene_id())
        self.history_scene_id = scene["scene_id"]
        if changed_scene or not self.selected_path():
            self.requested_path = scene["latest"]
        self.extra_entries = []
        self.scene_summary.setText("{}\nLocation: {}\nLast scene save: {}\n{} checkpoints".format(
            scene["name"], os.path.dirname(scene["source"]),
            _details_date(datetime.fromtimestamp(scene["saved"])) if scene["saved"] else "Unavailable",
            scene["checkpoint_count"]))
        self.reload()

    def _maintain_scene_history(self, action):
        scene_id = self.history_scene_id or controller.current_scene_id()
        if action == "delete":
            clicked = customDialogs.QFlatConfirmDialog.question(
                self, "Delete Scene Checkpoints", title="Delete all checkpoints for this scene?",
                message="This permanently removes all recovery data for the selected scene, including checkpoints and metadata. The Maya scene file is kept.",
                buttons=[customDialogs.QFlatDialogButton("Delete", positive=True, icon=icons.trash),
                         customDialogs.QFlatDialogButton("Cancel", positive=False, icon=icons.cancel)],
                highlight="Cancel")
            if not clicked or not clicked.get("positive"):
                return
        service = controller.get_service()
        if service and service.maintain_history(scene_id, action):
            self.merge_scenes_button.setEnabled(False)
            self.delete_scene_button.setEnabled(False)

    def _history_maintained(self, scene_id, error):
        self.merge_scenes_button.setEnabled(True)
        self.delete_scene_button.setEnabled(True)
        if error:
            cmds.warning("Animation Recovery: " + error)
        self.reload()
        if self.browse_scenes:
            self._refresh_scenes()

    def _build_bottom_bar(self):
        self.setBottomBar(
            buttons=[
                customDialogs.QFlatDialogButton(
                    "Recover",
                    callback=self.recover_selected,
                    icon=icons.apply,
                ),
                customDialogs.QFlatDialogButton(
                    "Delete",
                    callback=self.delete_selected,
                    icon=icons.trash,
                ),
            ],
            closeButton=True,
            highlight="Recover",
        )
        self.recover_button = self._button("Recover")
        self.delete_button = self._button("Delete")
        if self.delete_button:
            self.delete_button.hide()

    def done(self, result):
        self._dismiss_startup_offer()
        super().done(result)

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self._dismiss_startup_offer()

    def _dismiss_startup_offer(self):
        if self.dismissal_tokens:
            from TheKeyMachine.tools.animation_recovery import startup
            startup.dismiss_candidates(controller, self.dismissal_tokens)
            self.dismissal_tokens = []

    def _button(self, text):
        if not self.bottomBar:
            return None
        for button in self.bottomBar.findChildren(QtWidgets.QPushButton):
            if button.property("tkm_dialog_button_name") == text:
                return button
        return None

    def selected_path(self):
        selected = self.tree.selectedItems()
        return selected[0].data(0, QtCore.Qt.UserRole) if selected else None

    def _sync_actions(self):
        enabled = bool(self.selected_path())
        if self.recover_button:
            self.recover_button.setEnabled(enabled)
        if self.delete_button:
            self.delete_button.setEnabled(enabled)
        self._update_details()

    def _set_detail(self, key, value):
        label = self._details_labels.get(key)
        if label is not None:
            label.setText(value)

    def _update_details(self):
        path = self.selected_path()
        details = {}
        if not path:
            for key in self._details_labels:
                self._set_detail(key, "—")
            return
        if path:
            try:
                details = next((entry for entry in self.extra_entries if entry["path"] == path), None)
                if details is None:
                    details = controller.recovery_details(path)
            except Exception:
                details = {}
        self._set_detail("source_file", details.get("source_file") or "Unknown")
        self._set_detail("location", details.get("location") or "")
        self._set_detail("date", _details_date(details.get("created")))
        self._set_detail("reason", _reason_text(details.get("reason")))
        self._set_detail("current_frame", _frame_text(details.get("current_frame")))
        self._set_detail("playback_range", _range_text(details.get("playback_range")))
        self._set_detail("animation_range", _range_text(details.get("animation_range")))
        selected_objects = details.get("selected_objects")
        self._set_detail(
            "selected_objects",
            "Unknown" if selected_objects is None else str(selected_objects),
        )

    def _snapshot_saved(self, *_args):
        if self.isVisible():
            self.reload()

    def _scene_changed(self, *_args):
        if self.isVisible():
            QtCore.QTimer.singleShot(0, self.reload)

    def reload(self):
        try:
            scene_path = cmds.file(query=True, sceneName=True) or ""
        except Exception:
            scene_path = ""
        scene_name = os.path.basename(scene_path) if scene_path else "Untitled Scene"
        self.scene_label.setText(scene_name)
        self.scene_label.setToolTip(scene_path or scene_name)

        scroll = _scroll_state(self.tree) if not self.requested_path else None
        selected_path = self.requested_path or self.selected_path()
        self.requested_path = None
        self.tree.blockSignals(True)
        self.tree.clear()
        entries = controller.list_recoveries(scene_id=self.history_scene_id)
        entries += self.extra_entries
        entries.sort(key=lambda entry: entry["created"], reverse=True)
        if (self.startup_mode or self.history_scene_id) and entries:
            detail_path = selected_path if any(entry["path"] == selected_path for entry in entries) else entries[0]["path"]
            details = next((entry for entry in self.extra_entries if entry["path"] == detail_path), None)
            if details is None:
                details = controller.recovery_details(detail_path)
            self.scene_label.setText(details.get("source_file") or "Untitled Scene")
            self.scene_label.setToolTip(details.get("location") or "")
        self.scene_modified_label.setText(
            _display_date(entries[0]["created"]) if self.browse_scenes and entries else "")
        self.scene_modified_label.setToolTip("Latest recorded animation change")
        selected_item = None
        for row_index, entry in enumerate(entries):
            item = QtWidgets.QTreeWidgetItem([
                "",
                _display_date(entry["created"]),
            ])
            item.setData(0, QtCore.Qt.UserRole, entry["path"])
            item.setTextAlignment(0, QtCore.Qt.AlignCenter)
            item.setIcon(0, QtGui.QIcon(_status_icon(entry.get("status"), row_index, len(entries))))
            item.setToolTip(0, "Change {}".format(entry["change"]))
            if entry.get("reason") == "scene_save":
                scene_save_brush = QtGui.QBrush(QtGui.QColor("#3f4a42"))
                item.setBackground(0, scene_save_brush)
                item.setBackground(1, scene_save_brush)
            self.tree.addTopLevelItem(item)
            if entry["path"] == selected_path:
                selected_item = item
        if selected_item is None and self.tree.topLevelItemCount():
            selected_item = self.tree.topLevelItem(0)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
        self.tree.blockSignals(False)
        self.checkpoints_empty.setVisible(not entries)
        if scroll is not None:
            _restore_scroll(self.tree, scroll)
        self._sync_actions()

    def recover_selected(self, *_args):
        path = self.selected_path()
        if not path:
            return
        # Keep browsing the source history even if recovery opens another scene.
        if self.history_scene_id is None:
            self.history_scene_id = controller._recovery_scene_id(path) or controller.current_scene_id()
        is_crash = any(entry["path"] == path for entry in self.extra_entries)
        try:
            if self.startup_mode or is_crash:
                from TheKeyMachine.tools.animation_recovery import startup
                result = startup.load_selected(controller, path, crash=is_crash)
            else:
                result = trigger.execute_command("animation_recovery_restore", path)
            if result:
                self._dismiss_startup_offer()
                self.startup_mode = False
                current_id = controller.current_scene_id()
                for index in range(self.scenes_tree.topLevelItemCount()):
                    item = self.scenes_tree.topLevelItem(index)
                    scene = item.data(0, QtCore.Qt.UserRole)
                    for column in (0, 1):
                        font = item.font(column)
                        font.setBold(scene["scene_id"] == current_id)
                        item.setFont(column, font)
        except Exception as exc:
            from maya import cmds

            cmds.warning("Animation Recovery failed: {}".format(exc))

    def delete_selected(self, *_args):
        path = self.selected_path()
        if not path:
            return
        clicked = customDialogs.QFlatConfirmDialog.question(
            self,
            "Delete Recovery",
            title="Delete this saved change?",
            message="This recovery entry will be permanently removed.",
            buttons=[
                customDialogs.QFlatDialogButton("Delete", positive=True, icon=icons.trash),
                customDialogs.QFlatDialogButton("Cancel", positive=False, icon=icons.cancel),
            ],
            highlight="Delete",
        )
        if clicked and clicked.get("positive") and controller.delete_recovery(path):
            self.reload()


def show_dialog(scene_id=None, selected_path=None, startup=False, extra_entries=None, dismissal_tokens=None, browse_scenes=False):
    global _dialog
    if _dialog is None or not wutil.is_valid_widget(_dialog):
        _dialog = AnimationRecoveryDialog()
        _dialog.destroyed.connect(_clear_dialog)
    # Reopening the visible window must retain any offer it already displayed.
    _dialog.dismissal_tokens = sorted(set(_dialog.dismissal_tokens) | set(dismissal_tokens or []))
    _dialog.browse_scenes = browse_scenes
    _dialog.scenes_toggle.setChecked(False)
    _dialog.scenes_toggle.setVisible(browse_scenes)
    _dialog.refresh_scenes_button.setVisible(browse_scenes)
    _dialog.scene_browser.hide()
    _dialog.scene_modified_label.setVisible(browse_scenes)
    _dialog.history_scene_id = scene_id
    _dialog.startup_mode = startup
    _dialog.extra_entries = list(extra_entries or [])
    _dialog.requested_path = selected_path
    _dialog.reload()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    return _dialog


def _clear_dialog(*_args):
    global _dialog
    _dialog = None


def close_dialog():
    global _dialog
    if _dialog is not None and wutil.is_valid_widget(_dialog):
        _dialog.close()
        _dialog.deleteLater()
    _dialog = None
