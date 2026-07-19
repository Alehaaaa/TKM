from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.tools.isolate import api
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import util as wutil


class IsolateBookmarksWindow(customDialogs.QFlatToolBarPopupDialog):
    def __init__(self, parent=None):
        self.title = "Isolate Bookmarks"
        self.icon = icons.isolate_bookmarks_menu
        self.COLOR_BG_TRACK = self.DARK_BG_COLOR
        super().__init__(parent=parent, popup=False, closeButton=True)

        self.setObjectName(api.WINDOW_NAME)
        self.setMinimumWidth(wutil.DPI(260))
        self.title_label.setText(self.title)

        self.bookmark_list = QtWidgets.QListWidget(self)
        self.bookmark_list.setMinimumHeight(wutil.DPI(140))
        self.bookmark_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.bookmark_list.itemDoubleClicked.connect(lambda *_: self.isolate_selected())
        self.mainLayout.addWidget(self.bookmark_list, 1)
        self.setBottomBar(
            buttons=[
                customDialogs.QFlatDialogButton("Create", callback=self.create_selected, icon=icons.add),
                customDialogs.QFlatDialogButton("Remove", callback=self.remove_selected, icon=icons.trash),
                customDialogs.QFlatDialogButton("Isolate", callback=self.isolate_selected, icon=icons.isolate, highlight=True),
            ],
            closeButton=True,
            margins=0,
            spacing=2,
            highlight="Isolate",
        )
        api.create_isolate_bookmark_node()
        self.refresh()

    def refresh(self):
        api.update_bookmark_list(self.bookmark_list)

    def create_selected(self, *_args):
        api.create_bookmark(self.bookmark_list)
        self.refresh()

    def remove_selected(self, *_args):
        api.remove_bookmark(self.bookmark_list)
        self.refresh()

    def isolate_selected(self, *_args):
        api.isolate_bookmark(self.bookmark_list)
