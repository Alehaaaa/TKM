"""Selection traversal and Selector-window behavior."""

from maya import cmds

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.maya import animation
from TheKeyMachine.maya import selection
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import util as wutil


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
    seen = set()
    for node in selection.get_selected_objects(long=True):
        if node.startswith("|"):
            current = "|" + node.lstrip("|").split("|", 1)[0]
        else:
            current = node
            while True:
                parents = cmds.listRelatives(current, parent=True, fullPath=True) or []
                if not parents:
                    break
                current = parents[0]
        if current not in seen:
            seen.add(current)
            roots.append(current)
    return roots


def _nurbs_curve_controls(roots):
    """Return control transforms below *roots* that own NURBS curve shapes."""
    if isinstance(roots, str):
        roots = (roots,)
    roots = tuple(dict.fromkeys(root for root in (roots or ()) if root))
    if not roots:
        return []

    # Ask Maya for curve shapes directly instead of walking every transform
    # and then inspecting all of their shapes.  Besides being cheaper on large
    # rigs, the typed query prevents joints, meshes, locators, and intermediate
    # construction shapes from entering either rig-control selection path.
    curve_shapes = cmds.ls(
        roots,
        dagObjects=True,
        type="nurbsCurve",
        noIntermediate=True,
        long=True,
    ) or []
    # Every result is a full DAG path, so its parent transform is the path
    # before the final separator. Deriving that locally avoids a second Maya
    # command and still deduplicates controls that own multiple curve shapes.
    return list(
        dict.fromkeys(
            shape.rsplit("|", 1)[0] for shape in curve_shapes if "|" in shape
        )
    )


def _rig_controls(animated_only=False, operation=None):
    controls = _nurbs_curve_controls(_selected_roots())
    if not animated_only:
        return controls

    operation = toolCommon.require_tool_operation(operation)

    def _filter_batch(batch):
        return [node for node in batch if selection.is_node_animated(node)]

    return [
        node
        for batch in operation.process(
            controls,
            _filter_batch,
            batch_size=32,
            status="Finding Animated Rig Controls",
            strategy="worker",
        )
        for node in batch
    ]


def open_selector(*args, **kwargs):
    if not selection.get_selected_objects():
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


def select_hierarchy(*args, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    selected = selection.get_selected_objects(long=True)
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    def _collect_batch(batch):
        return _nurbs_curve_controls(batch)

    controls = list(dict.fromkeys(
        control
        for batch in operation.process(
            selected,
            _collect_batch,
            batch_size=8,
            status="Finding Hierarchy Controls",
            strategy="worker",
        )
        for control in batch
    ))
    if controls:
        cmds.select(controls, add=True)
    return controls


def select_rig_controls(*args, tool_operation=None):
    toolCommon.require_tool_operation(tool_operation)
    controls = _rig_controls(animated_only=False)
    if not controls:
        return wutil.make_inViewMessage("No rig controls found")
    cmds.select(controls, replace=True)
    return controls


def select_rig_controls_animated(*args, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    controls = _rig_controls(animated_only=True, operation=operation)
    if not controls:
        return wutil.make_inViewMessage("No animated rig controls found")
    cmds.select(controls, replace=True)
    return controls


def select_all_animation_curves(*args):
    curves = cmds.ls(
        type=("animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU")
    ) or []
    if curves:
        cmds.select(curves)
        cmds.selectKey(add=True)
    else:
        animation.notify_empty()


def clear_selected_keys(*args):
    cmds.selectKey(clear=True)
