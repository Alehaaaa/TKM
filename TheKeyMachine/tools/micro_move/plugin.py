"""Native Maya manipulators used by the Micro Move tool.

The manipulator owns the complete drag transaction.  Precision is applied in
Maya's manip-to-plug conversion path, so Maya still performs live evaluation,
undo recording, and Auto Key completion exactly like a native manipulator.
"""

import traceback

from maya.api import OpenMaya as om
from maya.api import OpenMayaUI as omui


def maya_useNewAPI():
    """Tell Maya to pass Python API 2.0 objects to this plug-in."""
    pass


MOVE_MANIP_NAME = "tkmMicroMoveManip"
ROTATE_MANIP_NAME = "tkmMicroRotateManip"
MOVE_CONTEXT_COMMAND = "tkmMicroMoveContextCmd"
ROTATE_CONTEXT_COMMAND = "tkmMicroRotateContextCmd"
BUILD_COMMAND = "tkmMicroMoveBuild"
BUILD_ID = "2026_07_15_native_converter_4"

# Private IDs used only by TheKeyMachine's non-persistent manipulator nodes.
MOVE_MANIP_ID = om.MTypeId(0x0013B2A0)
ROTATE_MANIP_ID = om.MTypeId(0x0013B2A1)

_ROTATION_ORDERS = (
    om.MEulerRotation.kXYZ,
    om.MEulerRotation.kYZX,
    om.MEulerRotation.kZXY,
    om.MEulerRotation.kXZY,
    om.MEulerRotation.kYXZ,
    om.MEulerRotation.kZYX,
)


def _runtime_api():
    from TheKeyMachine.tools.micro_move import api

    return api


def _vector_data(value):
    numeric_data = om.MFnNumericData()
    data_object = numeric_data.create(om.MFnNumericData.k3Double)
    numeric_data.setData(
        om.MVector(float(value[0]), float(value[1]), float(value[2]))
    )
    return omui.MManipData(data_object)


def _plug_vector(plug):
    return om.MVector(
        plug.child(0).asDouble(),
        plug.child(1).asDouble(),
        plug.child(2).asDouble(),
    )


def _report_converter_error(label):
    om.MGlobal.displayError(
        "TKM {} converter failed:\n{}".format(label, traceback.format_exc())
    )


class MicroMoveBuildCommand(om.MPxCommand):
    @staticmethod
    def creator():
        return MicroMoveBuildCommand()

    def doIt(self, _args):
        self.setResult(BUILD_ID)


class _PrecisionManipMixin:
    """Shared native drag state and cursor handling."""

    def _initialize_precision(self):
        self._target_plug = None
        self._target_plug_index = None
        self._dragging = False

    def doPress(self):
        self._dragging = True
        self._begin_precision_drag()
        _runtime_api().begin_manipulator_drag()
        return super().doPress()

    def doDrag(self):
        # The base implementation evaluates converter values and writes the
        # target plug inside Maya's native manipulator transaction.
        result = super().doDrag()
        try:
            omui.M3dView.active3dView().refresh(all=False, force=True)
        except RuntimeError:
            pass
        return result

    def doRelease(self):
        try:
            return super().doRelease()
        finally:
            self._dragging = False
            _runtime_api().end_manipulator_drag()

    def _begin_precision_drag(self):
        raise NotImplementedError


class MicroMoveManip(_PrecisionManipMixin, omui.MPxManipContainer):
    def __init__(self):
        super().__init__()
        self._initialize_precision()
        self._move_manip_path = om.MDagPath()
        self._point_index = None
        self._node_path = om.MDagPath()
        self._parent_inverse = om.MMatrix()
        self._world_orientation = om.MQuaternion()
        self._initial_translate = om.MVector()
        self._previous_manip_point = om.MVector()
        self._output_translate = om.MVector()

    @staticmethod
    def creator():
        return MicroMoveManip()

    @staticmethod
    def initialize():
        omui.MPxManipContainer.initialize()

    def createChildren(self):
        self._move_manip_path = self.addFreePointTriadManip(
            "tkmMicroMoveHandle",
            "Micro Move",
        )
        move_fn = omui.MFnFreePointTriadManip(self._move_manip_path)
        self._point_index = move_fn.pointIndex()

    def connectToDependNode(self, node):
        node_fn = om.MFnDependencyNode(node)
        self._target_plug = node_fn.findPlug("translate", False)
        self._target_plug_index = self.addManipToPlugConversion(
            self._target_plug
        )
        self._node_path = om.MFnDagNode(node).getPath()

        world_matrix = self._node_path.inclusiveMatrix()
        self._world_orientation = om.MTransformationMatrix(
            world_matrix
        ).rotation(asQuaternion=True)
        if self._node_path.length() > 1:
            parent_path = om.MDagPath(self._node_path)
            parent_path.pop()
            self._parent_inverse = parent_path.inclusiveMatrixInverse()
        else:
            self._parent_inverse = om.MMatrix()

        transform_fn = om.MFnTransform(self._node_path)
        pivot = transform_fn.rotatePivot(om.MSpace.kWorld)
        self._initial_translate = _plug_vector(self._target_plug)
        self._output_translate = om.MVector(self._initial_translate)

        move_fn = omui.MFnFreePointTriadManip(self._move_manip_path)
        move_fn.setPoint(om.MPoint(0.0, 0.0, 0.0))
        move_fn.setTranslation(om.MVector(pivot), om.MSpace.kWorld)
        move_fn.setRotation(self._world_orientation, om.MSpace.kWorld)
        move_fn.setDrawArrowHead(True)

        self.finishAddingManips()
        return super().connectToDependNode(node)

    def _manip_point(self):
        return om.MVector(
            self.getConverterManipMPointValue(self._point_index)
        )

    def _begin_precision_drag(self):
        self._initial_translate = _plug_vector(self._target_plug)
        self._output_translate = om.MVector(self._initial_translate)
        try:
            self._previous_manip_point = self._manip_point()
        except RuntimeError:
            self._previous_manip_point = om.MVector()

    def plugToManipConversion(self, plug_index):
        """Return the translated plug value from the child manip value.

        Maya's Python binding invokes plugToManipConversion for a plug
        registered by addManipToPlugConversion.  This is opposite the naming
        used by the C++ callback API but matches Autodesk's Python examples.
        """
        try:
            if plug_index != self._target_plug_index:
                return _vector_data(self._output_translate)

            current_point = self._manip_point()
            local_delta = current_point - self._previous_manip_point
            self._previous_manip_point = om.MVector(current_point)

            # The point value is in the oriented manipulator's local frame.
            # Convert it to world, then into the target's parent space because
            # translate channels are always stored in parent coordinates.
            world_delta = local_delta.rotateBy(self._world_orientation)
            parent_delta = world_delta * self._parent_inverse
            self._output_translate += (
                parent_delta * _runtime_api().manipulator_drag_gain()
            )
        except Exception:
            _report_converter_error("translate")
        return _vector_data(self._output_translate)


class MicroRotateManip(_PrecisionManipMixin, omui.MPxManipContainer):
    def __init__(self):
        super().__init__()
        self._initialize_precision()
        self._rotate_manip_path = om.MDagPath()
        self._rotation_index = None
        self._rotation_order = om.MEulerRotation.kXYZ
        self._previous_raw_rotation = om.MQuaternion()
        self._output_rotation = om.MQuaternion()

    @staticmethod
    def creator():
        return MicroRotateManip()

    @staticmethod
    def initialize():
        omui.MPxManipContainer.initialize()

    def createChildren(self):
        self._rotate_manip_path = self.addRotateManip(
            "tkmMicroRotateHandle",
            "Micro Rotate",
        )
        rotate_fn = omui.MFnRotateManip(self._rotate_manip_path)
        self._rotation_index = rotate_fn.rotationIndex()

    def connectToDependNode(self, node):
        node_fn = om.MFnDependencyNode(node)
        self._target_plug = node_fn.findPlug("rotate", False)
        self._target_plug_index = self.addManipToPlugConversion(
            self._target_plug
        )
        rotate_pivot_plug = node_fn.findPlug("rotatePivot", False)
        order_value = node_fn.findPlug("rotateOrder", False).asInt()
        self._rotation_order = _ROTATION_ORDERS[order_value]

        initial_euler = om.MEulerRotation(
            _plug_vector(self._target_plug),
            self._rotation_order,
        )
        self._previous_raw_rotation = initial_euler.asQuaternion()
        self._output_rotation = initial_euler.asQuaternion()

        rotate_fn = omui.MFnRotateManip(self._rotate_manip_path)
        rotate_fn.setInitialRotation(initial_euler)
        rotate_fn.rotateMode = omui.MFnRotateManip.kObjectSpace
        rotate_fn.displayWithNode(node)
        rotate_fn.connectToRotationCenterPlug(rotate_pivot_plug)

        self.finishAddingManips()
        return super().connectToDependNode(node)

    def _raw_rotation(self):
        return self.getConverterManipMEulerRotationValue(
            self._rotation_index
        ).asQuaternion()

    def _begin_precision_drag(self):
        initial_euler = om.MEulerRotation(
            _plug_vector(self._target_plug),
            self._rotation_order,
        )
        self._output_rotation = initial_euler.asQuaternion()
        try:
            self._previous_raw_rotation = self._raw_rotation()
        except RuntimeError:
            self._previous_raw_rotation = initial_euler.asQuaternion()

    def plugToManipConversion(self, plug_index):
        """Return the rotated plug value from the child manip value."""
        try:
            if plug_index == self._target_plug_index:
                current_raw = self._raw_rotation()
                # Converter evaluation is Maya's authoritative drag signal.
                # Preserve object-space composition while scaling the latest
                # native manipulator increment.
                raw_delta = self._previous_raw_rotation.inverse() * current_raw
                scaled_delta = om.MQuaternion.slerp(
                    om.MQuaternion(),
                    raw_delta,
                    _runtime_api().manipulator_drag_gain(),
                )
                self._output_rotation = self._output_rotation * scaled_delta
                self._previous_raw_rotation = current_raw
        except Exception:
            _report_converter_error("rotate")

        euler = self._output_rotation.asEulerRotation()
        euler.reorderIt(self._rotation_order)
        return _vector_data(euler)


class _MicroSelectionContext(omui.MPxSelectionContext):
    manipulator_name = ""
    title = "Micro Move"

    def __init__(self):
        super().__init__()
        self._selection_callback = None
        self.setTitleString(self.title)
        self.setHelpString("Select controls or drag the Micro Move manipulator.")

    def toolOnSetup(self, event):
        self.setAllowPreSelectHilight()
        self._rebuild_manipulators()
        self._selection_callback = om.MModelMessage.addCallback(
            om.MModelMessage.kActiveListModified,
            self._selection_changed,
        )
        return super().toolOnSetup(event)

    def toolOffCleanup(self):
        self.deleteManipulators()
        if self._selection_callback is not None:
            try:
                om.MMessage.removeCallback(self._selection_callback)
            except RuntimeError:
                pass
            self._selection_callback = None
        _runtime_api().end_manipulator_drag(restore_open_cursor=False)
        return super().toolOffCleanup()

    def _selection_changed(self, *_args):
        self._rebuild_manipulators()

    def _rebuild_manipulators(self):
        self.deleteManipulators()
        selection = om.MGlobal.getActiveSelectionList()
        iterator = om.MItSelectionList(selection, om.MFn.kTransform)
        while not iterator.isDone():
            node = iterator.getDependNode()
            if not node.isNull():
                try:
                    manipulator, manip_object = omui.MPxManipContainer.newManipulator(
                        self.manipulator_name
                    )
                    self.addManipulator(manip_object)
                    manipulator.connectToDependNode(node)
                except RuntimeError:
                    pass
            iterator.next()


class MicroMoveContext(_MicroSelectionContext):
    manipulator_name = MOVE_MANIP_NAME
    title = "Micro Move"


class MicroRotateContext(_MicroSelectionContext):
    manipulator_name = ROTATE_MANIP_NAME
    title = "Micro Rotate"


class MicroMoveContextCommand(omui.MPxContextCommand):
    @staticmethod
    def creator():
        return MicroMoveContextCommand()

    def makeObj(self):
        return MicroMoveContext()


class MicroRotateContextCommand(omui.MPxContextCommand):
    @staticmethod
    def creator():
        return MicroRotateContextCommand()

    def makeObj(self):
        return MicroRotateContext()


def initializePlugin(plugin_object):
    plugin = om.MFnPlugin(plugin_object, "TheKeyMachine", "1.0", "Any")
    plugin.registerCommand(BUILD_COMMAND, MicroMoveBuildCommand.creator)
    plugin.registerNode(
        MOVE_MANIP_NAME,
        MOVE_MANIP_ID,
        MicroMoveManip.creator,
        MicroMoveManip.initialize,
        om.MPxNode.kManipContainer,
    )
    plugin.registerNode(
        ROTATE_MANIP_NAME,
        ROTATE_MANIP_ID,
        MicroRotateManip.creator,
        MicroRotateManip.initialize,
        om.MPxNode.kManipContainer,
    )
    plugin.registerContextCommand(
        MOVE_CONTEXT_COMMAND,
        MicroMoveContextCommand.creator,
    )
    plugin.registerContextCommand(
        ROTATE_CONTEXT_COMMAND,
        MicroRotateContextCommand.creator,
    )


def uninitializePlugin(plugin_object):
    plugin = om.MFnPlugin(plugin_object)
    plugin.deregisterContextCommand(ROTATE_CONTEXT_COMMAND)
    plugin.deregisterContextCommand(MOVE_CONTEXT_COMMAND)
    plugin.deregisterNode(ROTATE_MANIP_ID)
    plugin.deregisterNode(MOVE_MANIP_ID)
    plugin.deregisterCommand(BUILD_COMMAND)
