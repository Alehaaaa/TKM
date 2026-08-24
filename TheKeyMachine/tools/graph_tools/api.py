from TheKeyMachine.tools.graph_tools import controller


def select_objects_from_selected_curves(*args, **kwargs): return controller.select_objects_from_selected_curves(*args, **kwargs)
def isolate_curves(*args, **kwargs): return controller.isolate_curves(*args, **kwargs)
def flip_curves(*args, **kwargs): return controller.flip_curves(*args, **kwargs)
def overlap_forward(*args, **kwargs): return controller.overlap_curves(1, *args, **kwargs)
def overlap_backward(*args, **kwargs): return controller.overlap_curves(-1, *args, **kwargs)
def toggle_mute(*args, **kwargs): return controller.toggle_mute(*args, **kwargs)
def toggle_lock(*args, **kwargs): return controller.toggle_lock(*args, **kwargs)
def match_keys(*args, **kwargs): return controller.match_keys(*args, **kwargs)
def enable_filter(*args, **kwargs): return controller.set_filter_enabled(True, *args, **kwargs)
def disable_filter(*args, **kwargs): return controller.set_filter_enabled(False, *args, **kwargs)
