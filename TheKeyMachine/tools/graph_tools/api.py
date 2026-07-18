from TheKeyMachine.tools.graph_tools import controller


def select_objects_from_selected_curves(*args): return controller.select_objects_from_selected_curves(*args)
def isolate_curves(*args): return controller.isolate_curves(*args)
def flip_curves(*args): return controller.flip_curves(*args)
def overlap_forward(*args): return controller.overlap_curves(1, *args)
def overlap_backward(*args): return controller.overlap_curves(-1, *args)
def toggle_mute(*args): return controller.toggle_mute(*args)
def toggle_lock(*args): return controller.toggle_lock(*args)
def match_keys(*args): return controller.match_keys(*args)
def enable_filter(*args): return controller.set_filter_enabled(True)
def disable_filter(*args): return controller.set_filter_enabled(False)
