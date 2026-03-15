import maya.OpenMayaUI as omui

try:
    from PySide6.QtCore import QSignalBlocker
    from PySide6.QtWidgets import QSlider
except ImportError:
    from PySide2.QtCore import QSignalBlocker
    from PySide2.QtWidgets import QSlider


def DPI(val):
    return omui.MQtUtil.dpiScale(val)


# --- utility: reset slider value without emitting signals -----------------------
class ResetWithoutEmit:
    def __init__(self, slider: QSlider):
        self._slider = slider

    def __call__(self):
        QSignalBlocker(self._slider)
        self._slider.setValue(getattr(self._slider, "defaultValue", 0))
        if hasattr(self._slider, "_apply_stylesheet"):
            self._slider._apply_stylesheet(thick=False)  # type: ignore[attr-defined]
        if hasattr(self._slider, "_pressOffset"):
            self._slider._pressOffset = None  # type: ignore[attr-defined]
