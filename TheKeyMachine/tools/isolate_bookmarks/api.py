import re

from maya import cmds

import TheKeyMachine.mods.selectionMod as selectionMod
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
from TheKeyMachine.Qt import QtCore, QtWidgets  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import util as wutil


WINDOW_NAME = "isolate_bookmarksWindow"
ROOT_NODE = "isolate_bookmarks"
POPUP_MENU = "isolate_button_popupMenu"


def create_isolate_bookmark_node():
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()
    if not cmds.objExists(ROOT_NODE):
        general.create_isolate_bookmarks_node()


def list_bookmarks():
    return cmds.listRelatives(ROOT_NODE, children=True) or []


def _bookmark_label(bookmark):
    return bookmark.replace("_isolate_bookmark", "")


def _selected_bookmark(list_widget):
    if isinstance(list_widget, QtWidgets.QListWidget):
        item = list_widget.currentItem()
        return item.text() if item else None

    item = cmds.textScrollList(list_widget, query=True, selectItem=True)
    return item[0] if item else None


def update_bookmark_list(list_widget, *_args):
    bookmarks = list_bookmarks()
    if isinstance(list_widget, QtWidgets.QListWidget):
        current_name = _selected_bookmark(list_widget)
        list_widget.clear()
        for bookmark in bookmarks:
            list_widget.addItem(_bookmark_label(bookmark))

        if current_name:
            matches = list_widget.findItems(current_name, QtCore.Qt.MatchExactly)
            if matches:
                list_widget.setCurrentItem(matches[0])
        elif list_widget.count():
            list_widget.setCurrentRow(0)
        return

    cmds.textScrollList(list_widget, edit=True, removeAll=True)
    for bookmark in bookmarks:
        cmds.textScrollList(list_widget, edit=True, append=_bookmark_label(bookmark))


def create_bookmark(list_widget, *_args):
    current_selection = selectionMod.get_selected_objects()
    if not current_selection:
        return

    text = cmds.promptDialog(
        title="Create Bookmark",
        message="Enter bookmark name:",
        button=["Create", "Cancel"],
        defaultButton="Create",
        cancelButton="Cancel",
        dismissString="Cancel",
    )

    if text != "Create":
        return

    bookmark_name = cmds.promptDialog(query=True, text=True)
    if not bookmark_name:
        cmds.warning("Bookmark name cannot be empty")
        return

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", bookmark_name):
        cmds.warning("Invalid bookmark name. It should start with a letter or underscore and contain only letters, numbers, and underscores")
        return

    create_isolate_bookmark_node()
    bookmark_node = cmds.group(em=True, name="{}_isolate_bookmark".format(bookmark_name))
    cmds.parent(bookmark_node, ROOT_NODE)

    new_groups = []
    for obj in current_selection:
        obj_name = obj.split("|")[-1]
        if "->" in obj_name:
            obj_name = obj_name.split("->")[-1]
        obj_name = obj_name.replace(".", "_")
        new_group = cmds.group(em=True, name="{}_{}_isolate_bookmark_item".format(obj_name, bookmark_name))
        cmds.parent(new_group, bookmark_node)
        new_groups.append(new_group)

    for new_group in new_groups:
        cmds.select(new_group, add=True)

    cmds.select(clear=True)
    update_bookmark_list(list_widget)
    update_isolate_popup_menu()


def remove_bookmark(list_widget, *_args):
    bookmark_name = _selected_bookmark(list_widget)
    if not bookmark_name:
        return

    cmds.delete("{}_isolate_bookmark".format(bookmark_name))
    update_bookmark_list(list_widget)
    update_isolate_popup_menu()


def isolate_bookmark(list_widget=None, bookmark_name=None, *_args):
    current_selection = selectionMod.get_selected_objects(long=True)

    if not bookmark_name and list_widget:
        bookmark_name = _selected_bookmark(list_widget)

    if not bookmark_name:
        cmds.warning("No bookmark selected")
        return

    bookmark_name = bookmark_name.replace("_isolate_bookmark", "")
    bookmark_node = "{}_isolate_bookmark".format(bookmark_name)
    if not cmds.objExists(bookmark_node):
        cmds.warning("Bookmark '{}' not found".format(bookmark_name))
        return

    objects = cmds.listRelatives(bookmark_node, allDescendents=True, fullPath=True) or []
    if not objects:
        cmds.warning("No objects in bookmark '{}'".format(bookmark_name))
        return

    selected_objects = []
    for obj in objects:
        obj_name = obj.rsplit("|", 1)[-1].replace("_isolate_bookmark_item", "")
        obj_name = obj_name.replace("_{}".format(bookmark_name), "")
        if cmds.objExists(obj_name):
            selected_objects.append(obj_name)

    current_panel = cmds.getPanel(wf=True)
    if cmds.getPanel(typeOf=current_panel) != "modelPanel":
        current_panel = cmds.playblast(activeEditor=True)
    if cmds.getPanel(typeOf=current_panel) != "modelPanel":
        return wutil.make_inViewMessage("Focus on a camera or viewport")

    current_state = cmds.isolateSelect(current_panel, query=True, state=True)
    cmds.select(selected_objects)
    if current_state == 0:
        cmds.isolateSelect(current_panel, state=1)
        cmds.isolateSelect(current_panel, addSelected=True)
    else:
        cmds.isolateSelect(current_panel, state=0)
        cmds.isolateSelect(current_panel, state=1)
        cmds.isolateSelect(current_panel, addSelected=True)

    cmds.select(clear=True)
    if current_selection:
        cmds.select(current_selection, replace=True)


def update_isolate_popup_menu(popup_menu=POPUP_MENU, *_args):
    if not cmds.popupMenu(popup_menu, exists=True):
        return

    cmds.popupMenu(popup_menu, e=True, deleteAllItems=True)

    if cmds.objExists(ROOT_NODE):
        for bookmark in list_bookmarks():
            text = bookmark.replace("_isolate_bookmark", "")
            cmds.menuItem(
                l=text,
                parent=popup_menu,
                image=icons.dot_gray,
                c=lambda x, text=text: isolate_bookmark(bookmark_name=text),
            )
        cmds.menuItem(divider=True, parent=popup_menu)

    cmds.menuItem(
        l="Bookmarks",
        c=lambda x: create_isolate_bookmarks_window(),
        annotation="Open isolate bookmarks window",
        image=icons.isolate_bookmarks_menu,
        parent=popup_menu,
    )
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(
        "down_level_checkbox",
        l="Down one level",
        annotation="",
        checkBox=False,
        c=lambda x: bar.toggle_down_one_level(x),
        parent=popup_menu,
    )


class IsolateBookmarksWindow(customDialogs.QFlatToolBarPopupDialog):
    def __init__(self, parent=None):
        self.title = "Isolate Bookmarks"
        self.icon = icons.isolate_bookmarks_menu
        self.COLOR_BG_TRACK = self.DARK_BG_COLOR

        super().__init__(parent=parent, popup=False, closeButton=True)
        self.setObjectName(WINDOW_NAME)
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

        create_isolate_bookmark_node()
        self.refresh()

    def refresh(self):
        update_bookmark_list(self.bookmark_list)

    def create_selected(self, *_args):
        create_bookmark(self.bookmark_list)
        self.refresh()

    def remove_selected(self, *_args):
        remove_bookmark(self.bookmark_list)
        self.refresh()

    def isolate_selected(self, *_args):
        isolate_bookmark(self.bookmark_list)


def _existing_isolate_bookmarks_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME and isinstance(widget, IsolateBookmarksWindow) and wutil.is_valid_widget(widget):
            return widget
    return None


def create_isolate_bookmarks_window(*_args):
    original_selection = selectionMod.get_selected_objects()

    existing = _existing_isolate_bookmarks_window()
    if existing:
        existing.refresh()
        existing.show()
        existing.raise_()
        existing.activateWindow()
        return existing

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = IsolateBookmarksWindow(parent=wutil.get_maya_qt(qt=QtWidgets.QWidget))
    window.show()
    window.raise_()
    window.activateWindow()

    if original_selection:
        cmds.select(original_selection, replace=True)
    else:
        cmds.select(clear=True)

    return window
