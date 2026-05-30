from maya import OpenMaya as om
from maya import cmds, utils

from TheKeyMachine.Qt import QtCompat, QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.helperMod as helper
from TheKeyMachine.data import icons
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon


MICRO_MOVE_HELPERS_GROUP = "tkm_microMove_helpers"

micro_move_selected_objects = []
micro_move_callback_ids = []
micro_move_drivers = []
micro_move_animation_data = {}

micro_rotate_callback_ids = []
micro_rotate_selected_objects = []
micro_rotate_drivers = []
micro_rotate_animation_data = {}


def _build_micro_cursor(image_name):
    image_path = icons.path(image_name)
    pixmap = QtGui.QPixmap(image_path) if image_path else QtGui.QPixmap()
    if pixmap.isNull():
        return None
    return QtGui.QCursor(
        pixmap.scaled(33, 33, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation),
        3,
        3,
    )


_MICRO_CURSOR_OPEN = _build_micro_cursor("micro_manipulator_open.png")
_MICRO_CURSOR_PINCHED = _build_micro_cursor("micro_manipulator.png")


def _clear_micro_cursor():
    app = QtWidgets.QApplication.instance()
    if not app:
        return
    try:
        while app.overrideCursor() is not None:
            app.restoreOverrideCursor()
    except Exception:
        try:
            app.restoreOverrideCursor()
        except Exception:
            pass


def _set_micro_cursor(pinched=False):
    cursor = _MICRO_CURSOR_PINCHED if pinched else _MICRO_CURSOR_OPEN
    if cursor is None:
        return
    _clear_micro_cursor()
    try:
        QtWidgets.QApplication.setOverrideCursor(cursor)
    except Exception:
        pass


def _ensure_micro_move_helpers_group():
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()

    if not cmds.objExists(MICRO_MOVE_HELPERS_GROUP):
        group = cmds.createNode("transform", name=MICRO_MOVE_HELPERS_GROUP)
    else:
        group = MICRO_MOVE_HELPERS_GROUP

    try:
        current_parent = cmds.listRelatives(group, parent=True, fullPath=False) or []
        if not current_parent or current_parent[0] != "TheKeyMachine":
            cmds.parent(group, "TheKeyMachine")
    except Exception:
        pass

    return group


def micro_move_copy_animation(object_name, attributes):
    global micro_move_animation_data

    if object_name not in micro_move_animation_data:
        micro_move_animation_data[object_name] = {}

    for attribute in attributes:
        keyframes = cmds.keyframe(object_name, attribute=attribute, query=True, timeChange=True)
        if keyframes:
            micro_move_animation_data[object_name][attribute] = {}
            for frame in keyframes:
                value = cmds.getAttr("{}.{}".format(object_name, attribute), time=frame)
                micro_move_animation_data[object_name][attribute][frame] = value


def micro_move_paste_animation(object_name):
    global micro_move_animation_data

    if object_name in micro_move_animation_data:
        for attribute, frames in micro_move_animation_data[object_name].items():
            for frame, value in frames.items():
                cmds.setKeyframe(object_name, attribute=attribute, time=(frame,), value=value)


def micro_move_attribute_callback_function(msg, plug, other_plug, client_data):
    if msg & om.MNodeMessage.kAttributeSet:
        driver_name = client_data
        attr_name = plug.partialName()
        duplicated_name = f"{driver_name.replace('_driver', '_connect')}.{attr_name}"
        driver_value = cmds.getAttr(plug.name())

        if isinstance(driver_value, list) or isinstance(driver_value, tuple):
            modified_values = [value / 6 for value in driver_value[0]]
            cmds.setAttr(duplicated_name, *modified_values, type="double3")
        else:
            cmds.setAttr(duplicated_name, driver_value / 6)


def add_micro_move_callback(object_name):
    selection_list = om.MSelectionList()
    selection_list.add(object_name)
    mobject = om.MObject()
    selection_list.getDependNode(0, mobject)

    callback_id = om.MNodeMessage.addAttributeChangedCallback(mobject, micro_move_attribute_callback_function, object_name)
    micro_move_callback_ids.append(callback_id)


def micro_move_pre_drag(*args):
    global micro_move_selected_objects, micro_move_drivers

    toolCommon.open_undo_chunk()
    _set_micro_cursor(pinched=True)

    micro_move_selected_objects = selectionMod.get_selected_objects()
    if not micro_move_selected_objects:
        raise Exception("Please select an object")
    original_selection = list(micro_move_selected_objects)

    transform_attrs = ["translateX", "translateY", "translateZ"]
    helpers_group = _ensure_micro_move_helpers_group()

    for selected in micro_move_selected_objects:
        for attr in transform_attrs:
            micro_move_copy_animation(selected, transform_attrs)

    for selected in micro_move_selected_objects:
        duplicated = cmds.duplicate(selected, name=f"{selected}_connect", parentOnly=True)[0]
        driver = cmds.duplicate(selected, name=f"{selected}_driver", parentOnly=True)[0]
        try:
            cmds.parent(duplicated, helpers_group)
        except Exception:
            pass
        try:
            cmds.parent(driver, helpers_group)
        except Exception:
            pass
        micro_move_drivers.append(driver)

        for attr in transform_attrs:
            cmds.transformLimits(driver, e=True, tx=(0, 0), etx=(False, False))
            cmds.transformLimits(driver, e=True, ty=(0, 0), ety=(False, False))
            cmds.transformLimits(driver, e=True, tz=(0, 0), etz=(False, False))

        for attr in transform_attrs:
            if not cmds.getAttr(f"{selected}.{attr}", lock=True):
                original_value = cmds.getAttr(f"{selected}.{attr}")
                new_value = original_value * 6
                cmds.setAttr(f"{driver}.{attr}", new_value)

        for attr in transform_attrs:
            if cmds.getAttr(f"{selected}.{attr}", se=True):
                cmds.connectAttr(f"{duplicated}.{attr}", f"{selected}.{attr}", force=True)

        add_micro_move_callback(driver)

    if original_selection:
        cmds.select(original_selection, replace=True)
    micro_move_drivers.clear()


def micro_move_post_drag():
    global micro_move_selected_objects, micro_move_animation_data
    _set_micro_cursor(pinched=False)

    for selected in micro_move_selected_objects:
        duplicate_name = f"{selected}_connect"
        if cmds.objExists(duplicate_name):
            translate_values = {}
            for attr in ["translateX", "translateY", "translateZ"]:
                if cmds.getAttr(f"{duplicate_name}.{attr}", se=True):
                    translate_values[attr] = cmds.getAttr(f"{duplicate_name}.{attr}")
            cmds.delete(duplicate_name)
        else:
            translate_values = {"translateX": 0, "translateY": 0, "translateZ": 0}
            cmds.delete(duplicate_name)

        driver_name = f"{selected}_driver"
        if cmds.objExists(driver_name):
            cmds.delete(driver_name)

        micro_move_paste_animation(selected)

        for attr, value in translate_values.items():
            if cmds.getAttr(f"{selected}.{attr}", se=True):
                cmds.setAttr(f"{selected}.{attr}", value)

    remove_micro_move_callbacks()
    micro_move_animation_data.clear()
    if micro_move_selected_objects:
        cmds.select(micro_move_selected_objects)

    toolCommon.close_undo_chunk()


def remove_micro_move_callbacks():
    global micro_move_callback_ids
    for callback_id in micro_move_callback_ids:
        om.MMessage.removeCallback(callback_id)
    micro_move_callback_ids = []


def micro_move_post_drag_deferred(*args):
    cmds.evalDeferred(micro_move_post_drag)


def micro_rotate_copy_animation(object_name, attributes):
    global micro_rotate_animation_data

    if object_name not in micro_rotate_animation_data:
        micro_rotate_animation_data[object_name] = {}

    for attribute in attributes:
        keyframes = cmds.keyframe(object_name, attribute=attribute, query=True, timeChange=True)
        if keyframes:
            micro_rotate_animation_data[object_name][attribute] = {}
            for frame in keyframes:
                value = cmds.getAttr("{}.{}".format(object_name, attribute), time=frame)
                micro_rotate_animation_data[object_name][attribute][frame] = value


def micro_rotate_paste_animation(object_name):
    global micro_rotate_animation_data

    if object_name in micro_rotate_animation_data:
        for attribute, frames in micro_rotate_animation_data[object_name].items():
            for frame, value in frames.items():
                cmds.setKeyframe(object_name, attribute=attribute, time=(frame,), value=value)


def micro_rotate_pack_funtion():
    global micro_rotate_selected_objects, micro_rotate_drivers

    def add_micro_rotate_callback(source_object, target_object):
        selection_list = om.MSelectionList()
        selection_list.add(source_object)
        mobject = om.MObject()
        selection_list.getDependNode(0, mobject)

        def add_micro_rotate_dirty_callback(mobject, plug, client_data):
            if plug.partialName() in ("r", "rx", "ry", "rz"):
                rotation = cmds.getAttr(f"{source_object}.rotate")[0]
                half_rotation = [value / 6 for value in rotation]
                cmds.rotate(half_rotation[0], half_rotation[1], half_rotation[2], target_object, absolute=True)

        callback_id = om.MNodeMessage.addNodeDirtyPlugCallback(mobject, add_micro_rotate_dirty_callback, None)
        micro_rotate_callback_ids.append(callback_id)

    micro_rotate_selected_objects = selectionMod.get_selected_objects()
    original_selection = list(micro_rotate_selected_objects)
    helpers_group = _ensure_micro_move_helpers_group()

    transform_attrs = ["rotateX", "rotateY", "rotateZ"]
    for selected in micro_rotate_selected_objects:
        for attr in transform_attrs:
            micro_rotate_copy_animation(selected, transform_attrs)

    for selected in micro_rotate_selected_objects:
        connect = cmds.duplicate(selected, name=f"{selected}_connect", parentOnly=True)[0]
        driver = cmds.duplicate(selected, name=f"{selected}_driver", parentOnly=True)[0]
        try:
            cmds.parent(connect, helpers_group)
        except Exception:
            pass
        try:
            cmds.parent(driver, helpers_group)
        except Exception:
            pass
        micro_rotate_drivers.append(driver)

        for attr in transform_attrs:
            cmds.transformLimits(driver, e=True, rx=(0, 0), erx=(False, False))
            cmds.transformLimits(driver, e=True, ry=(0, 0), ery=(False, False))
            cmds.transformLimits(driver, e=True, rz=(0, 0), erz=(False, False))

        for attr in transform_attrs:
            if not cmds.getAttr(f"{selected}.{attr}", lock=True):
                original_value = cmds.getAttr(f"{selected}.{attr}")
                new_value = original_value * 6
                cmds.setAttr(f"{driver}.{attr}", new_value)

        for attr in transform_attrs:
            if cmds.getAttr(f"{selected}.{attr}", se=True):
                try:
                    cmds.connectAttr(f"{connect}.{attr}", f"{selected}.{attr}", force=True)
                except RuntimeError as e:
                    print(f"Unable to connect {attr} from {connect} to {selected}: {e}")

        add_micro_rotate_callback(driver, connect)

    if original_selection:
        cmds.select(original_selection, replace=True)
    micro_rotate_drivers.clear()


def micro_rotate_pre_drag(*args):
    toolCommon.open_undo_chunk()
    _set_micro_cursor(pinched=True)
    micro_rotate_pack_funtion()


def micro_rotate_post_deferred():
    try:
        global micro_rotate_selected_objects, micro_rotate_animation_data
        _set_micro_cursor(pinched=False)

        for selected in micro_rotate_selected_objects:
            duplicate_name = f"{selected}_connect"
            driver_name = f"{selected}_driver"

            if cmds.objExists(duplicate_name):
                rotate_values = {}
                for attr in ["rotateX", "rotateY", "rotateZ"]:
                    if cmds.getAttr(f"{duplicate_name}.{attr}", se=True):
                        rotate_values[attr] = cmds.getAttr(f"{duplicate_name}.{attr}")
                cmds.delete(duplicate_name)
            else:
                rotate_values = {"rotateX": 0, "rotateY": 0, "rotateZ": 0}
                cmds.delete(duplicate_name)

            if cmds.objExists(duplicate_name):
                cmds.delete(duplicate_name)
            if cmds.objExists(driver_name):
                cmds.delete(driver_name)

            micro_rotate_paste_animation(selected)

            for attr, value in rotate_values.items():
                if cmds.getAttr(f"{selected}.{attr}", se=True):
                    cmds.setAttr(f"{selected}.{attr}", value)

        remove_micro_rotate_callbacks()
        micro_rotate_animation_data.clear()
        if micro_rotate_selected_objects:
            cmds.select(micro_rotate_selected_objects)

    finally:
        toolCommon.close_undo_chunk()


def remove_micro_rotate_callbacks():
    global micro_rotate_callback_ids
    for callback_id in micro_rotate_callback_ids:
        om.MMessage.removeCallback(callback_id)
    micro_rotate_callback_ids = []


def micro_rotate_post_drag(*args):
    cmds.evalDeferred(micro_rotate_post_deferred)


def activate_micro_move(*args):
    current_context = cmds.currentCtx()
    micro_move_context = "microMoveCtx"
    micro_rotate_context = "microRotateCtx"
    _ensure_micro_move_helpers_group()

    if cmds.contextInfo("dummyCtx", exists=True):
        if cmds.contextInfo(micro_rotate_context, exists=True):
            cmds.deleteUI(micro_rotate_context, toolContext=True)

        if cmds.contextInfo(micro_move_context, exists=True):
            cmds.deleteUI(micro_move_context, toolContext=True)

        if cmds.contextInfo("dummyCtx", exists=True):
            cmds.deleteUI("dummyCtx", toolContext=True)

        cmds.setToolTo("moveSuperContext")
        _clear_micro_cursor()

    else:
        if current_context == "RotateSuperContext":
            if cmds.contextInfo(micro_rotate_context, exists=True):
                cmds.setToolTo(micro_rotate_context)
                _set_micro_cursor(pinched=False)
            else:
                cmds.manipRotateContext(micro_rotate_context)
                cmds.manipRotateContext(
                    micro_rotate_context,
                    e=True,
                    preDragCommand=(micro_rotate_pre_drag, "transform"),
                    postDragCommand=(micro_rotate_post_drag, "transform"),
                    mode=2,
                )
                cmds.setToolTo(micro_rotate_context)
                _set_micro_cursor(pinched=False)

        elif current_context == "moveSuperContext":
            if cmds.contextInfo(micro_move_context, exists=True):
                cmds.setToolTo(micro_move_context)
                _set_micro_cursor(pinched=False)
            else:
                cmds.manipMoveContext(micro_move_context)
                cmds.manipMoveContext(
                    micro_move_context,
                    e=True,
                    preDragCommand=(micro_move_pre_drag, "transform"),
                    postDragCommand=(micro_move_post_drag_deferred, "transform"),
                    mode=0,
                )
                cmds.setToolTo(micro_move_context)
                _set_micro_cursor(pinched=False)


class MicroMoveController(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)

    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner
        self._enabled = False
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh_context)

    def is_enabled(self):
        return self._enabled

    def _refresh_context(self):
        if not self._enabled or not QtCompat.isValid(self._owner):
            return
        utils.executeDeferred(activate_micro_move)

    def activate(self):
        self._enabled = toolCommon.open_undo_chunk()
        activate_micro_move()
        self._timer.start()
        self.stateChanged.emit(self.is_enabled())

    def deactivate(self):
        self._enabled = False
        self._timer.stop()
        try:
            _clear_micro_cursor()
        except Exception:
            pass
        try:
            cmds.manipMoveContext("dummyCtx")
            cmds.setToolTo("dummyCtx")
        except Exception:
            pass
        try:
            toolCommon.close_undo_chunk()
        except Exception:
            pass
        self.stateChanged.emit(False)

    def toggle(self, checked=None, button_widget=None):
        if checked is None:
            checked = not self._enabled

        checked = bool(checked)

        if checked:
            self.activate()
        else:
            self.deactivate()
