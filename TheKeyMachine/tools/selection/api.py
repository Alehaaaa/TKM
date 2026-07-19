"""Public entry point for selection tools."""

from TheKeyMachine.tools.selection import controller


def open_selector(*args): return controller.open_selector(*args)
def select_hierarchy(*args): return controller.select_hierarchy(*args)
def select_rig_controls(*args): return controller.select_rig_controls(*args)
def select_rig_controls_animated(*args): return controller.select_rig_controls_animated(*args)
