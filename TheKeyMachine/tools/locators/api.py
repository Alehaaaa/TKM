from maya import cmds

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon


def create_locator(*_args):
    selection = selectionMod.get_selected_objects()
    if not selection:
        return
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()
    if not cmds.objExists("temp_locators"):
        cmds.group(empty=True, name="temp_locators")
        cmds.parent("temp_locators", "TheKeyMachine")

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
        locator = cmds.rename(locator, "tkm_temp_locator_{}".format(index))
        cmds.parent(locator, "temp_locators")
        if operation is not None:
            operation.step()
    cmds.select(selection)


def select_temp_locators(*_args):
    locators = [name for name in cmds.ls("tkm_temp_locator_*") or [] if name.rsplit("_", 1)[-1].isdigit()]
    if locators:
        cmds.select(locators)


def delete_temp_locators(*_args):
    if not cmds.objExists("temp_locators"):
        return
    locators = [name for name in cmds.ls("tkm_temp_locator_*") or [] if name.rsplit("_", 1)[-1].isdigit()]
    if locators:
        cmds.delete(locators)
