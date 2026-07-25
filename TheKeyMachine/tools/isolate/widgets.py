from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.isolate import api
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import customWidgets as cw
from TheKeyMachine.widgets import util as wutil


class IsolateBookmarkRow(QtWidgets.QWidget):
    """One row per bookmark: click the name to isolate, use the pencil icon
    (or double-click the name) to rename, and the trash icon to delete.
    """

    def __init__(self, bookmark_name, window, parent=None):
        super().__init__(parent)
        self.bookmark_name = bookmark_name
        self._window = window

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(2), wutil.DPI(2), wutil.DPI(2), wutil.DPI(2))
        layout.setSpacing(wutil.DPI(4))

        self.name_button = cw.InlineRenameButton(bookmark_name, self)
        self.name_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.name_button.setFixedHeight(wutil.DPI(28))
        self.name_button.setToolTip("Click to isolate, double-click to rename")
        self.name_button.set_rename_target(bookmark_name, bookmark_name, self._commit_rename)
        self.name_button.clicked.connect(self._isolate)
        layout.addWidget(self.name_button, 1)

        self.rename_button = cw.QFlatToolButton(icon=icons.rename, tooltip="Rename bookmark")
        self.rename_button.clicked.connect(self.name_button.start_inline_rename)
        layout.addWidget(self.rename_button)

        self.delete_button = cw.QFlatToolButton(icon=icons.trash, tooltip="Delete bookmark")
        self.delete_button.clicked.connect(self._delete)
        layout.addWidget(self.delete_button)

    def _isolate(self, *_args):
        api.isolate_bookmark(bookmark_name=self.bookmark_name)

    def _commit_rename(self, old_name, new_name):
        renamed = api.rename_bookmark(old_name, new_name)
        if not renamed:
            self.name_button.setText(self.bookmark_name)
            return
        self.bookmark_name = renamed
        self.name_button.set_rename_target(renamed, renamed, self._commit_rename)

    def _delete(self, *_args):
        api.remove_bookmark(self.bookmark_name)
        self._window.refresh()


class IsolateBookmarksWindow(
    toolCommon.FloatingToolWindowMixin,
    customDialogs.QFlatPinnableToolBarPopupDialog,
):
    def __init__(self, parent=None, popup=True):
        self.title = "Isolate Bookmarks"
        self.icon = icons.isolate_bookmarks_menu
        self.COLOR_BG_TRACK = self.DARK_BG_COLOR
        super().__init__(
            parent=parent,
            popup=popup,
            bottom_bar_kwargs={"margins": 0, "spacing": 2},
        )

        self.setObjectName(api.WINDOW_NAME)
        self.setMinimumWidth(wutil.DPI(260))
        self.title_label.setText(self.title)

        self.create_button = cw.QFlatToolButton(icon=icons.add, tooltip="Create bookmark from selection")
        self.create_button.clicked.connect(self.create_selected)
        self.title_layout.addWidget(self.create_button)

        self.bookmark_list = QtWidgets.QListWidget(self)
        self.bookmark_list.setMinimumHeight(wutil.DPI(140))
        self.bookmark_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.bookmark_list.setFocusPolicy(QtCore.Qt.NoFocus)
        self.mainLayout.addWidget(self.bookmark_list, 1)

        api.create_isolate_bookmark_node()
        self.refresh()

    def refresh(self):
        self.bookmark_list.clear()
        for bookmark_name in api.list_bookmarks():
            item = QtWidgets.QListWidgetItem(self.bookmark_list)
            row = IsolateBookmarkRow(bookmark_name, self)
            item.setSizeHint(row.sizeHint())
            self.bookmark_list.addItem(item)
            self.bookmark_list.setItemWidget(item, row)

    def create_selected(self, *_args):
        if api.create_bookmark() is not None:
            self.refresh()
