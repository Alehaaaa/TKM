"""Animation Recovery history window."""

from datetime import datetime, timedelta
import os

from maya import cmds

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets
from TheKeyMachine.data import icons
from TheKeyMachine.tools.animation_recovery import controller
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import util as wutil


_dialog = None


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
    }.get(value, "Animation Change")


class AnimationRecoveryDialog(customDialogs.QFlatDialog):
    def __init__(self, parent=None):
        customDialogs.QFlatDialog.__init__(self, parent=parent)
        self.setObjectName("tkmAnimationRecoveryDialog")
        self.setWindowTitle("Animation Recovery")
        self.setMinimumSize(wutil.DPI(720), wutil.DPI(360))
        self.resize(wutil.DPI(820), wutil.DPI(470))
        self.addWindowHeader(
            self.root_layout,
            text="Animation Recovery",
            icon=icons.animation_recovery,
        )

        content = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(
            wutil.DPI(12),
            wutil.DPI(4),
            wutil.DPI(12),
            wutil.DPI(10),
        )
        layout.setSpacing(wutil.DPI(7))

        self.scene_label = QtWidgets.QLabel(content)
        self.scene_label.setStyleSheet(
            "color:#dedede; font-size:%spx; font-weight:bold;" % wutil.DPI(12)
        )
        self.scene_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.scene_label)

        self.status_label = QtWidgets.QLabel(content)
        self.status_label.setStyleSheet("color:#a8a8a8; font-size:%spx;" % wutil.DPI(11))
        layout.addWidget(self.status_label)

        self.tree = QtWidgets.QTreeWidget(content)
        self.tree.setObjectName("animationRecoveryTree")
        self.tree.setHeaderLabels(["Change", "Date"])
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self.tree.setColumnWidth(0, wutil.DPI(34))
        tree_palette = self.tree.palette()
        tree_palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#333333"))
        tree_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#383838"))
        self.tree.setPalette(tree_palette)
        self.tree.setStyleSheet(
            """
            QTreeWidget#animationRecoveryTree {
                border:1px solid #484848;
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
            "QFrame#animationRecoveryDetails { background:#383838; border:1px solid #484848; }"
            "QFrame#animationRecoveryDetails QLabel { background:transparent; border:0; color:#bdbdbd; }"
        )
        details_layout = QtWidgets.QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(
            wutil.DPI(14), wutil.DPI(12), wutil.DPI(14), wutil.DPI(12)
        )
        details_layout.setSpacing(wutil.DPI(8))
        details_title = QtWidgets.QLabel("Details:", self.details_frame)
        details_title.setStyleSheet("font-weight:bold; color:#e0e0e0; font-size:%spx;" % wutil.DPI(12))
        details_layout.addWidget(details_title)

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

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, content)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.details_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([wutil.DPI(430), wutil.DPI(330)])
        layout.addWidget(splitter, 1)
        self.root_layout.addWidget(content, 1)

        self.setBottomBar(
            buttons=[
                customDialogs.QFlatDialogButton(
                    "Recover",
                    callback=self.recover_selected,
                    icon=icons.apply,
                    highlight=True,
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
        service = controller.get_service()
        if service is not None:
            service.snapshotSaved.connect(self._snapshot_saved)
            manager = getattr(service, "manager", None)
            if manager is not None:
                manager.scene_opened.connect(self._scene_changed)
                manager.scene_new.connect(self._scene_changed)
        self.reload()

    def _button(self, text):
        if not self.bottomBar:
            return None
        for button in self.bottomBar.findChildren(QtWidgets.QPushButton):
            if button.text() == text:
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
        if path:
            try:
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
        scene_name = os.path.basename(scene_path) if scene_path else "Unknown Scene Name"
        self.scene_label.setText(scene_name)
        self.scene_label.setToolTip(scene_path or scene_name)

        selected_path = self.selected_path()
        self.tree.clear()
        entries = controller.list_recoveries()
        selected_item = None
        for entry in entries:
            item = QtWidgets.QTreeWidgetItem([
                str(entry["change"]),
                _display_date(entry["created"]),
            ])
            item.setData(0, QtCore.Qt.UserRole, entry["path"])
            item.setTextAlignment(0, QtCore.Qt.AlignCenter)
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
        count = len(entries)
        self.status_label.setText(
            "{} saved change{} for this scene".format(count, "" if count == 1 else "s")
        )
        self._sync_actions()

    def recover_selected(self, *_args):
        path = self.selected_path()
        if not path:
            return
        try:
            if controller.restore_recovery(path):
                self.reload()
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


def show_dialog():
    global _dialog
    if _dialog is not None and wutil.is_valid_widget(_dialog):
        _dialog.reload()
        _dialog.show()
        _dialog.raise_()
        _dialog.activateWindow()
        return _dialog
    _dialog = AnimationRecoveryDialog()
    _dialog.destroyed.connect(_clear_dialog)
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
