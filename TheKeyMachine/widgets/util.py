import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from shiboken6 import wrapInstance, isValid  # type: ignore
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import QMainWindow
except ImportError:
    from shiboken2 import wrapInstance, isValid  # type: ignore
    from PySide2 import QtWidgets
    from PySide2.QtWidgets import QMainWindow

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


def get_maya_qt(ptr=None, qt=QMainWindow):
    if ptr is None:
        ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), qt)


def get_maya_window_size():
    maya_main_window = get_maya_qt()
    return maya_main_window.width(), maya_main_window.height()


def get_maya_window_geometry():
    maya_main_window = get_maya_qt()
    return maya_main_window.geometry()


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
