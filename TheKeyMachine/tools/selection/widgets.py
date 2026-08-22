"""Selector UI owned by the selection tool package."""

from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.maya import selection
from TheKeyMachine.ui.widgets.customDialogs import QFlatToolBarPopupDialog


class SelectorDialog(QFlatToolBarPopupDialog):
    def __init__(self, parent=None):
        self.title = "Selector"
        self.icon = icons.selector
        super().__init__(parent=parent, native_popup=True)
        self.title_label.setText("0")
        self._objects = []
        self._refreshing = False
        self._suppress_next_refresh = False

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.reload_objects)

        self._list_model = QtCore.QStringListModel(self)
        self.list_widget = QtWidgets.QListView(self)
        self.list_widget.setModel(self._list_model)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.selectionModel().selectionChanged.connect(self._on_list_selection_changed)
        self.mainLayout.addWidget(self.list_widget, 1)

        try:
            from TheKeyMachine.core import runtime
            runtime.get_runtime_manager().selection_changed.connect(self._schedule_reload)
        except Exception:
            pass
        self.reload_objects()

    def _schedule_reload(self, *_args):
        if self._suppress_next_refresh:
            self._suppress_next_refresh = False
            return
        if not self._refresh_timer.isActive():
            self._refresh_timer.start(0)

    def reload_objects(self):
        self._refreshing = True
        selected = selection.get_valid_selected_objects(long=True)
        self._objects = sorted(selected, key=lambda node: (node.rsplit("|", 1)[-1].lower(), node.lower()))
        self.title_label.setText(str(len(self._objects)))
        self._list_model.setStringList([node.rsplit("|", 1)[-1] for node in self._objects])

        model = self.list_widget.selectionModel()
        if model and self._objects:
            model.select(
                QtCore.QItemSelection(self._list_model.index(0, 0), self._list_model.index(len(self._objects) - 1, 0)),
                QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows,
            )
        self._refreshing = False

    def _on_list_selection_changed(self, *_args):
        if self._refreshing:
            return
        from maya import cmds

        names = [self._objects[index.row()] for index in self.list_widget.selectionModel().selectedIndexes()]
        names = [name for name in names if cmds.objExists(name)]
        self._suppress_next_refresh = True
        if names:
            cmds.select(names, replace=True)
        else:
            cmds.select(clear=True)
