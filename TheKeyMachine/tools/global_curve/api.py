"""Public API for the Graph Editor Global Curve."""

from TheKeyMachine.tools.global_curve import controller


def set_enabled(*args): return controller.set_enabled(*args)
def has_global_curves(): return controller.has_global_curves()
def create_additional(*args): return controller.create_additional(*args)
def remove_all(*args): return controller.remove_all(*args)
def recapture_active(*args): return controller.recapture_active(*args)
def tangent_mode_choices(): return controller.tangent_mode_choices()
def get_tangent_mode(): return controller.get_tangent_mode()
def set_tangent_mode(*args): return controller.set_tangent_mode(*args)
def get_affect_time(): return controller.get_affect_time()
def set_affect_time(*args): return controller.set_affect_time(*args)
def get_snap_keys(): return controller.get_snap_keys()
def set_snap_keys(*args): return controller.set_snap_keys(*args)
def cleanup(): return controller.cleanup()
