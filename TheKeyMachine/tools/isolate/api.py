import re

from maya import cmds

from TheKeyMachine.maya import selection
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.tools.isolate import controller
from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import util as wutil


WINDOW_NAME = "isolate_bookmarksWindow"
POPUP_MENU = "isolate_button_popupMenu"
# Stamped on each bookmark item node so the original selected object can be
# read back directly instead of reverse-parsed out of the node's name.
ITEM_OBJECT_ATTR = "tkmIsolateBookmarkObject"
_BOOKMARK_NODE_SUFFIX = "_isolate_bookmark"
_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _bookmark_node_name(bookmark_name):
    return "{}{}".format(bookmark_name, _BOOKMARK_NODE_SUFFIX)


def _bookmark_label(bookmark_node_name):
    if bookmark_node_name.endswith(_BOOKMARK_NODE_SUFFIX):
        return bookmark_node_name[: -len(_BOOKMARK_NODE_SUFFIX)]
    return bookmark_node_name


def isolate_master(*args):
    return controller.isolate_master(*args)


def is_down_one_level():
    return controller.is_down_one_level()


def set_down_one_level(enabled):
    return controller.set_down_one_level(enabled)


def toggle_down_one_level(checked=None, *_args):
    if isinstance(checked, bool):
        return controller.set_down_one_level(checked)
    return controller.set_down_one_level(not controller.is_down_one_level())


def create_isolate_bookmark_node():
    """Return the TkmSceneNode that parents all isolate bookmarks, creating it if missing."""
    return controller.create_isolate_bookmarks_node()


def list_bookmarks():
    """Return the bare bookmark names (display labels), in scene order."""
    nodes = cmds.listRelatives(controller.ROOT_NODE, children=True) or []
    return [_bookmark_label(node) for node in nodes]


def _validate_new_bookmark_name(bookmark_name):
    if not bookmark_name:
        cmds.warning("Bookmark name cannot be empty")
        return False
    if not _NAME_PATTERN.match(bookmark_name):
        cmds.warning(
            "Invalid bookmark name. It should start with a letter or underscore "
            "and contain only letters, numbers, and underscores"
        )
        return False
    if cmds.objExists(_bookmark_node_name(bookmark_name)):
        # TkmSceneNode.child() adopts an existing node by name rather than
        # uniquifying it, so a repeat name must be rejected here -- otherwise
        # the new selection would silently merge into the old bookmark.
        cmds.warning("A bookmark named '{}' already exists".format(bookmark_name))
        return False
    return True


def create_bookmark(bookmark_name=None):
    """Create a bookmark from the current selection.

    Prompts for a name when ``bookmark_name`` isn't supplied. Returns the new
    bookmark's name, or None if the selection was empty, the prompt was
    cancelled, or the name was invalid.
    """
    current_selection = selection.get_selected_objects()
    if not current_selection:
        wutil.make_inViewMessage("Select something to bookmark")
        return None

    if bookmark_name is None:
        from TheKeyMachine.tools import common as toolCommon

        toolCommon.finish_active_progress()
        text = cmds.promptDialog(
            title="Create Bookmark",
            message="Enter bookmark name:",
            button=["Create", "Cancel"],
            defaultButton="Create",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if text != "Create":
            return None
        bookmark_name = cmds.promptDialog(query=True, text=True)

    if not _validate_new_bookmark_name(bookmark_name):
        return None

    bookmarks_root = create_isolate_bookmark_node()
    bookmark_node = bookmarks_root.child(_bookmark_node_name(bookmark_name))

    new_groups = []
    for index, obj in enumerate(current_selection):
        obj_name = obj.split("|")[-1]
        if "->" in obj_name:
            obj_name = obj_name.split("->")[-1]
        obj_name = obj_name.replace(".", "_").replace(":", "_")
        item_node = bookmark_node.child("{}_{}_isolate_bookmark_item_{}".format(obj_name, bookmark_name, index))
        # Store the actual selected object so it can be restored directly by
        # isolate_bookmark() instead of reverse-parsed out of the node name.
        item_node.set_attr(ITEM_OBJECT_ATTR, obj)
        new_groups.append(item_node.name)

    for new_group in new_groups:
        cmds.select(new_group, add=True)
    cmds.select(clear=True)

    update_isolate_popup_menu()
    return bookmark_name


def rename_bookmark(old_name, new_name):
    """Rename an existing bookmark in place. Returns the new name, or None on failure."""
    if not new_name or old_name == new_name:
        return None
    if not _NAME_PATTERN.match(new_name):
        cmds.warning(
            "Invalid bookmark name. It should start with a letter or underscore "
            "and contain only letters, numbers, and underscores"
        )
        return None

    old_node = _bookmark_node_name(old_name)
    if not cmds.objExists(old_node):
        cmds.warning("Bookmark '{}' not found".format(old_name))
        return None

    new_node = _bookmark_node_name(new_name)
    if cmds.objExists(new_node):
        cmds.warning("A bookmark named '{}' already exists".format(new_name))
        return None

    cmds.rename(old_node, new_node)
    update_isolate_popup_menu()
    return new_name


def remove_bookmark(bookmark_name):
    bookmark_node_name = _bookmark_node_name(bookmark_name)
    if cmds.objExists(bookmark_node_name):
        cmds.delete(bookmark_node_name)
    update_isolate_popup_menu()


def isolate_bookmark(bookmark_name=None, *_args):
    current_selection = selection.get_selected_objects(long=True)

    if not bookmark_name:
        cmds.warning("No bookmark selected")
        return

    bookmark_node = _bookmark_node_name(bookmark_name)
    if not cmds.objExists(bookmark_node):
        cmds.warning("Bookmark '{}' not found".format(bookmark_name))
        return

    item_nodes = cmds.listRelatives(bookmark_node, allDescendents=True, fullPath=True) or []
    if not item_nodes:
        cmds.warning("No objects in bookmark '{}'".format(bookmark_name))
        return

    selected_objects = []
    for item_node in item_nodes:
        obj_name = TkmSceneNode(item_node).get_attr(ITEM_OBJECT_ATTR)
        if obj_name and cmds.objExists(obj_name):
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

    if cmds.objExists(controller.ROOT_NODE):
        for text in list_bookmarks():
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
        c=lambda value: controller.set_down_one_level(value),
        parent=popup_menu,
    )


def _existing_isolate_bookmarks_window():
    from TheKeyMachine.tools.isolate.widgets import IsolateBookmarksWindow

    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME and isinstance(widget, IsolateBookmarksWindow) and wutil.is_valid_widget(widget):
            return widget
    return None


def create_isolate_bookmarks_window(*_args, anchor_widget=None):
    from TheKeyMachine.tools.isolate.widgets import IsolateBookmarksWindow

    original_selection = selection.get_selected_objects()

    def _present(win):
        if anchor_widget is not None:
            win.present_above_toolbar_button(anchor_widget)
        else:
            win.present_beside_cursor()

    existing = _existing_isolate_bookmarks_window()
    if existing:
        existing.set_popup_mode(True)
        existing.refresh()
        _present(existing)
        return existing

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = IsolateBookmarksWindow(parent=wutil.get_maya_qt(qt=QtWidgets.QWidget))
    _present(window)

    if original_selection:
        cmds.select(original_selection, replace=True)
    else:
        cmds.select(clear=True)

    return window
