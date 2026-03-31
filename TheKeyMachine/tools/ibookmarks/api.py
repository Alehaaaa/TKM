import re

from maya import cmds

import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.mediaMod as media
from TheKeyMachine.widgets import util as wutil


WINDOW_NAME = "iBookmarksWindow"
ROOT_NODE = "iBookmarks"
POPUP_MENU = "isolate_button_popupMenu"


def create_ibookmark_node():
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()
    if not cmds.objExists(ROOT_NODE):
        general.create_ibookmarks_node()


def list_bookmarks():
    return cmds.listRelatives(ROOT_NODE, children=True) or []


def update_bookmark_list(list_widget, *_args):
    bookmarks = list_bookmarks()
    cmds.textScrollList(list_widget, edit=True, removeAll=True)
    for bookmark in bookmarks:
        cmds.textScrollList(list_widget, edit=True, append=bookmark.replace("_ibookmark", ""))


def create_bookmark(list_widget, *_args):
    current_selection = wutil.get_selected_objects()
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

    create_ibookmark_node()
    bookmark_node = cmds.group(em=True, name="{}_ibookmark".format(bookmark_name))
    cmds.parent(bookmark_node, ROOT_NODE)

    new_groups = []
    for obj in current_selection:
        obj_name = obj.split("|")[-1]
        if "->" in obj_name:
            obj_name = obj_name.split("->")[-1]
        obj_name = obj_name.replace(".", "_")
        new_group = cmds.group(em=True, name="{}_{}_ibook".format(obj_name, bookmark_name))
        cmds.parent(new_group, bookmark_node)
        new_groups.append(new_group)

    for new_group in new_groups:
        cmds.select(new_group, add=True)

    cmds.select(clear=True)
    update_bookmark_list(list_widget)
    update_isolate_popup_menu()


def remove_bookmark(list_widget, *_args):
    item = cmds.textScrollList(list_widget, query=True, selectItem=True)
    if not item:
        return

    cmds.delete("{}_ibookmark".format(item[0]))
    update_bookmark_list(list_widget)
    update_isolate_popup_menu()


def isolate_bookmark(list_widget=None, bookmark_name=None, *_args):
    current_selection = wutil.get_selected_objects(long=True)

    if not bookmark_name and list_widget:
        item = cmds.textScrollList(list_widget, query=True, selectItem=True)
        if item:
            bookmark_name = item[0]

    if not bookmark_name:
        cmds.warning("No bookmark selected")
        return

    bookmark_name = bookmark_name.replace("_ibookmark", "")
    bookmark_node = "{}_ibookmark".format(bookmark_name)
    if not cmds.objExists(bookmark_node):
        cmds.warning("Bookmark '{}' not found".format(bookmark_name))
        return

    objects = cmds.listRelatives(bookmark_node, allDescendents=True, fullPath=True) or []
    if not objects:
        cmds.warning("No objects in bookmark '{}'".format(bookmark_name))
        return

    selected_objects = []
    for obj in objects:
        obj_name = obj.rsplit("|", 1)[-1].replace("_ibook", "")
        obj_name = obj_name.replace("_{}".format(bookmark_name), "")
        if cmds.objExists(obj_name):
            selected_objects.append(obj_name)

    current_panel = cmds.getPanel(wf=True)
    if cmds.getPanel(typeOf=current_panel) != "modelPanel":
        current_panel = cmds.playblast(activeEditor=True)
    if cmds.getPanel(typeOf=current_panel) != "modelPanel":
        return wutil.inViewMessage("Focus on a camera or viewport")

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
            text = bookmark.replace("_ibookmark", "")
            cmds.menuItem(
                l=text,
                parent=popup_menu,
                image=media.asset_path("grey_dot_image"),
                c=lambda x, text=text: isolate_bookmark(bookmark_name=text),
            )
        cmds.menuItem(divider=True, parent=popup_menu)

    cmds.menuItem(
        l="Bookmarks",
        c=lambda x: create_ibookmarks_window(),
        annotation="Open isolate bookmarks window",
        image=media.asset_path("ibookmarks_menu_image"),
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


def create_ibookmarks_window(*_args):
    original_selection = wutil.get_selected_objects()

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = cmds.window(WINDOW_NAME, title="Isolate Bookmarks", widthHeight=(265, 140), sizeable=False)
    main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")
    form_layout = cmds.formLayout()
    list_widget = cmds.textScrollList(allowMultiSelection=False, h=130)

    button_layout = cmds.columnLayout(adjustableColumn=True, columnAlign="center")
    cmds.button(label="Create", command=lambda x: create_bookmark(list_widget), width=90)
    cmds.button(label="Remove", command=lambda x: remove_bookmark(list_widget), width=90)
    cmds.button(label="Isolate", command=lambda x: isolate_bookmark(list_widget), width=90)

    cmds.formLayout(
        form_layout,
        edit=True,
        attachForm=[(list_widget, "left", 5), (list_widget, "top", 5), (button_layout, "top", 5), (button_layout, "right", 5)],
        attachControl=[(list_widget, "right", 5, button_layout)],
    )

    cmds.setParent(main_layout)
    cmds.showWindow(window)
    create_ibookmark_node()
    update_bookmark_list(list_widget)

    if original_selection:
        cmds.select(original_selection, replace=True)
    else:
        cmds.select(clear=True)
