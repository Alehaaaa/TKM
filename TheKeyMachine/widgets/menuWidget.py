from __future__ import annotations
"""
SliderWidget — CORE-faithful, single-file recreation (no picks)
===============================================================

Self-contained slider that mimics the original AnimBot/CORE style but
behaves like a tweenmachine: a centered horizontal scrub from -100..+100.
No A/B picks. Context menu on right-click (hook point kept).

What's new (same behavior, nicer structure):
- Wheel works from anywhere inside SliderWidget (buttons/overlays/empty).
- Centralized wheel logic via apply_wheel_delta().
- Clearer separation of responsibilities & comments.

PySide6 or PySide2 (Maya 2017+). No external CORE import.
"""

# --- Qt compat (PySide6 / PySide2) ---------------------------------------------
try:  # Maya 2025+
    from PySide6 import QtWidgets
    from PySide6 import QtGui
    PYSIDE = 6
except ImportError:  # Maya 2017–2024
    from PySide2 import QtWidgets
    from PySide2 import QtGui
    PYSIDE = 2



class MenuWidget(QtWidgets.QMenu):
    def __init__(self, title=None, parent=None):
        if isinstance(title, QtWidgets.QWidget) and parent is None:
            parent = title
            title = None

        super(MenuWidget, self).__init__(title or "", parent)

        if parent and hasattr(parent, "destroyed"):
            parent.destroyed.connect(self.close)

        self.setMouseTracking(True)

    def mouseReleaseEvent(self, e):
        act = self.actionAt(e.pos()) or self.activeAction()
        try:
            if act and act.isEnabled() and act.isCheckable() \
                    and not isinstance(act, QtWidgets.QWidgetAction) \
                    and getattr(act, "menu", lambda: None)() is None:
                prev = act.isChecked()
                act.setChecked(not prev)  # emite toggled(bool)
                try:
                    act.trigger()          # emite triggered(bool) si procede
                except TypeError:
                    act.trigger()
                e.accept()
                return
        except Exception:
            pass

        return super(MenuWidget, self).mouseReleaseEvent(e)
