import maya.cmds as cmds
import maya.OpenMayaUI as omui
try:
    from maya.api import OpenMaya as om
except Exception:
    om = None

try:
    from shiboken6 import wrapInstance, isValid  # type: ignore
    from PySide6 import QtWidgets
    from PySide6.QtCore import QSignalBlocker
    from PySide6.QtWidgets import QSlider, QMainWindow
except ImportError:
    from shiboken2 import wrapInstance, isValid  # type: ignore
    from PySide2 import QtWidgets
    from PySide2.QtCore import QSignalBlocker
    from PySide2.QtWidgets import QSlider, QMainWindow

from TheKeyMachine.mods import mediaMod as media

def DPI(val):
    return omui.MQtUtil.dpiScale(val)


def DPR(val):
    screen = QtWidgets.QApplication.primaryScreen()
    return val * screen.devicePixelRatio()


def get_screen_resolution():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    try:
        # PySide6
        screen = app.primaryScreen()
        screen_rect = screen.geometry()
    except Exception:
        # PySide2 fallback
        desktop = QtWidgets.QDesktopWidget()
        screen_rect = desktop.screenGeometry()

    return screen_rect.width(), screen_rect.height()


def _ls_selected(long=False, ordered=False):
    if ordered:
        return cmds.ls(orderedSelection=True, long=long) or cmds.ls(selection=True, long=long) or []
    return cmds.ls(selection=True, long=long) or []


def get_selected_objects(long=False, ordered=False, orderedSelection=None):
    if orderedSelection is not None:
        ordered = bool(orderedSelection)

    if ordered:
        return _ls_selected(long=long, ordered=True)

    if om is None:
        return _ls_selected(long=long)

    try:
        selection_list = om.MGlobal.getActiveSelectionList()
        selection_strings = selection_list.getSelectionStrings()
    except Exception:
        return _ls_selected(long=long)

    if not selection_strings:
        return []

    try:
        return cmds.ls(selection_strings, long=long) or selection_strings
    except Exception:
        return selection_strings


def get_selected_object_count():
    if om is not None:
        try:
            return om.MGlobal.getActiveSelectionList().length()
        except Exception:
            pass
    return len(_ls_selected())


def get_maya_qt(ptr=None, qt=QMainWindow):
    if ptr is None:
        ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), qt)


def get_control_widget(name, qt_type=QtWidgets.QWidget):
    ptr = omui.MQtUtil.findControl(name)
    if ptr:
        return wrapInstance(int(ptr), qt_type)
    return None


def is_valid_widget(widget, expected_type=None):
    if widget is None:
        return False
    if expected_type is not None and not isinstance(widget, expected_type):
        return False
    try:
        if isValid(widget):
            return True
    except Exception:
        pass
    return False


def check_visible_layout(layout):
    try:
        try:
            s = cmds.workspaceControl(layout, q=True, visible=True) and not cmds.workspaceControl(layout, q=True, collapse=True)
        except Exception:
            s = cmds.window(layout, q=True, visible=True)
    except Exception:
        s = False
    return s


# --- utility: reset slider value without emitting signals -----------------------
class ResetWithoutEmit:
    def __init__(self, slider: QSlider):
        self._slider = slider

    def __call__(self):
        blocker = QSignalBlocker(self._slider)
        try:
            self._slider.setValue(getattr(self._slider, "defaultValue", 0))
            if hasattr(self._slider, "_apply_stylesheet"):
                self._slider._apply_stylesheet(thick=False)  # type: ignore[attr-defined]
            if hasattr(self._slider, "_pressOffset"):
                self._slider._pressOffset = None  # type: ignore[attr-defined]
        finally:
            del blocker


def make_inViewMessage(message, icon=None):

    if not icon:
        icon = media.asset_path("tool_icon")
    else:
        icon = media.asset_path(icon, media.getImage(icon))
    if not icon:
        icon = ""

    cmds.inViewMessage(
        amg='<div style="text-align:center"><img src="' + icon + '">\n\n' + message + "\n\n\n",
        pos="midCenter",
        a=0.9,
        fade=True,
        fst=1000,
    )
