from maya import cmds

from TheKeyMachine.maya import selection
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.data import icons


ROOT_NODE = "Isolate_Bookmarks"


_down_one_level = False


def create_isolate_bookmarks_node():
    """Return the TkmSceneNode that parents all isolate bookmark nodes, creating it if missing."""
    return TkmSceneNode.root().child(ROOT_NODE, lock_transform=True, icon=icons.isolate_bookmarks)


def is_down_one_level():
    return _down_one_level


def set_down_one_level(enabled):
    global _down_one_level
    _down_one_level = bool(enabled)
    return _down_one_level


def root_node(node, down_one_level=False):
    matches = cmds.ls(node, long=True) or []
    if not matches:
        return None
    node = matches[0]
    previous = None
    while True:
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        if not parents:
            return previous if down_one_level and previous else node
        previous = node
        node = parents[0]


def active_model_panel():
    panel = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    for panel in cmds.getPanel(visiblePanels=True) or []:
        if cmds.getPanel(typeOf=panel) == "modelPanel":
            return panel
    return None


def isolate_master(*_args):
    panel = active_model_panel()
    if not panel:
        return False

    selected = selection.get_selected_objects()
    isolated = bool(cmds.isolateSelect(panel, query=True, state=True))
    if not selected:
        if isolated:
            cmds.isolateSelect(panel, state=False)
        return False

    original_selection = list(selected)
    roots = [root_node(node, down_one_level=_down_one_level) for node in selected]
    roots = [node for node in roots if node]
    if not roots:
        return False

    try:
        if isolated:
            cmds.isolateSelect(panel, state=False)
        cmds.select(roots, replace=True)
        cmds.isolateSelect(panel, state=True)
        cmds.isolateSelect(panel, addSelected=True)
        return True
    finally:
        cmds.select(original_selection, replace=True)
