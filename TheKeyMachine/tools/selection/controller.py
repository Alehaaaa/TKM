"""Selection traversal and Selector-window behavior."""

from maya import cmds

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.mods import selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


SELECTOR_TOOL_ID = "selector"
SELECTOR_SECTION_ID = "selection_tools"
SELECTOR_TOOLBAR_ID = "main"


def is_selector_pinned():
    """Whether the Selector toolbutton is currently pinned/visible on the main toolbar.

    Reads through the same ``get_section_tools`` the Workspaces editor uses,
    so this always agrees with what a user sees there and on the toolbar's
    own right-click pinning menu. Only the main toolbar is tracked here --
    checking the graph toolbar too (and OR-ing the two) is what used to make
    this getter stick at True forever: the graph toolbar is usually closed,
    so it always fell back to its "pinned by default" workspace setting no
    matter what the main toolbar's actual state was.
    """
    from TheKeyMachine.tools.workspaces import controller as workspacesController

    for entry in workspacesController.get_section_tools(SELECTOR_TOOLBAR_ID, SELECTOR_SECTION_ID):
        if entry["id"] == SELECTOR_TOOL_ID:
            return bool(entry["checked"])
    return False


def set_selector_pinned(enabled):
    """Pin or unpin the Selector toolbutton on the main toolbar."""
    from TheKeyMachine.tools.workspaces import controller as workspacesController

    return workspacesController.set_tool_pinned(
        SELECTOR_TOOLBAR_ID, SELECTOR_SECTION_ID, SELECTOR_TOOL_ID, bool(enabled)
    )


def _selected_roots():
    roots = []
    for node in selectionMod.get_selected_objects(long=True):
        if node.startswith("|"):
            current = "|" + node.lstrip("|").split("|", 1)[0]
        else:
            current = node
            while True:
                parents = cmds.listRelatives(current, parent=True, fullPath=True) or []
                if not parents:
                    break
                current = parents[0]
        if current not in roots:
            roots.append(current)
    return roots


def _descendant_transforms(root):
    nodes = [root]
    nodes.extend(cmds.listRelatives(root, allDescendents=True, type="transform", fullPath=True) or [])
    return list(dict.fromkeys(nodes))


def _is_curve_control(node):
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []
    return any(cmds.nodeType(shape) == "nurbsCurve" for shape in shapes)


def _control_nodes(nodes):
    nodes = list(dict.fromkeys(nodes or ()))
    if not nodes:
        return []
    shapes = cmds.listRelatives(
        nodes,
        shapes=True,
        noIntermediate=True,
        fullPath=True,
    ) or []
    curve_shapes = cmds.ls(shapes, type="nurbsCurve", long=True) or []
    curve_parents = set(
        cmds.listRelatives(curve_shapes, parent=True, fullPath=True) or []
    )
    return [node for node in nodes if node in curve_parents]


def _rig_controls(animated_only=False):
    descendants = []
    for root in _selected_roots():
        descendants.extend(_descendant_transforms(root))
    controls = _control_nodes(descendants)
    if not animated_only:
        return controls
    operation = toolCommon.current_tool_operation()
    if operation:
        operation.set_total(len(controls))
    animated = []
    for node in controls:
        if operation and operation.cancelled:
            break
        if selectionMod.is_node_animated(node):
            animated.append(node)
        if operation:
            operation.step()
    return animated


def open_selector(*args, **kwargs):
    if not selectionMod.get_selected_objects():
        return

    from TheKeyMachine.tools.selection.widgets import SelectorDialog

    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, SelectorDialog):
            widget.close()
            widget.deleteLater()
    dialog = SelectorDialog()
    dialog.place_near_cursor()
    dialog.activateWindow()
    dialog.list_widget.setFocus()
    return dialog


def select_hierarchy(*args):
    selected = selectionMod.get_selected_objects(long=True)
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    controls = []
    for node in selected:
        for descendant in _descendant_transforms(node):
            if _is_curve_control(descendant) and descendant not in controls:
                controls.append(descendant)
    if controls:
        cmds.select(controls, add=True)
    return controls


def select_rig_controls(*args):
    controls = _rig_controls(animated_only=False)
    if not controls:
        return wutil.make_inViewMessage("No rig controls found")
    cmds.select(controls, replace=True)
    return controls


def select_rig_controls_animated(*args):
    controls = _rig_controls(animated_only=True)
    if not controls:
        return wutil.make_inViewMessage("No animated rig controls found")
    cmds.select(controls, replace=True)
    return controls
