from maya import cmds

import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.core.scene_nodes import TkmSceneNode
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon


def create_locator(*_args):
    selection = selectionMod.get_selected_objects()
    if not selection:
        return
    TkmSceneNode.root().child("Temp_Locators", icon=icons.cube)

    operation = toolCommon.current_tool_operation()
    if operation is not None:
        operation.set_total(len(selection)).set_status("Creating Locators")
    for index, obj in enumerate(selection):
        if operation is not None and operation.cancelled:
            break
        locator = cmds.spaceLocator()[0]
        cmds.matchTransform(locator, obj)
        cmds.setAttr(locator + ".overrideEnabled", 1)
        cmds.setAttr(locator + ".overrideColor", 13)
        for axis in "XYZ":
            cmds.setAttr(locator + ".localScale" + axis, 5)
        locator = cmds.rename(locator, "Temp_Locator_{}".format(index))
        cmds.parent(locator, "Temp_Locators")
        if operation is not None:
            operation.step()
    cmds.select(selection)


def select_temp_locators(*_args):
    locators = [name for name in cmds.ls("Temp_Locator_*") or [] if name.rsplit("_", 1)[-1].isdigit()]
    if locators:
        cmds.select(locators)


def delete_temp_locators(*_args):
    if not cmds.objExists("Temp_Locators"):
        return
    locators = [name for name in cmds.ls("Temp_Locator_*") or [] if name.rsplit("_", 1)[-1].isdigit()]
    if locators:
        cmds.delete(locators)
