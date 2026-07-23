"""Animation-layer curve resolution specific to interactive sliders.

The shared layer model and curve traversal live in :mod:`core.animlayers`.
This shim owns the slider policy of preferring a selected editable layer and
otherwise the highest editable affected layer.
"""

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

from TheKeyMachine.core import animlayers as core_animlayers


def _select_slider_layer(plug):
    cache = core_animlayers.cache
    root = cache.root
    selected_layers = [
        layer.layer for layer in cache.selected_unlocked_layers
    ]
    scene_layers = [layer.layer for layer in cache.scene_layers]
    unlocked_layers = [layer.layer for layer in cache.unlocked_layers]

    if root.locked:
        root_layer = None
    elif root.selected and len(selected_layers) <= 1:
        return root.layer
    else:
        root_layer = root.layer

    try:
        iterator = om.MItDependencyGraph(
            plug,
            om.MFn.kAnimLayer,
            direction=om.MItDependencyGraph.kDownstream,
            traversal=om.MItDependencyGraph.kBreadthFirst,
            level=om.MItDependencyGraph.kNodeLevel,
        )
    except Exception:
        return root_layer

    best_layer = None
    for candidates in (selected_layers, unlocked_layers):
        if not candidates:
            continue
        iterator.reset()
        best_layer = None
        while not iterator.isDone():
            layer = iterator.currentNode()
            if layer in scene_layers:
                iterator.prune()
                if layer in candidates:
                    best_layer = layer
            iterator.next()
        if best_layer:
            return best_layer
    return best_layer or root_layer


def get_slider_anim_curve_for_plug(plug_name):
    """Return the curve chosen by the interactive-slider layer policy."""
    curves = core_animlayers.get_anim_curves_from_plugs(
        [plug_name],
        layer_selector=_select_slider_layer,
    )
    return curves[0] if curves else None


def get_slider_anim_curves_from_plugs(plugs):
    return core_animlayers.get_anim_curves_from_plugs(
        plugs,
        layer_selector=_select_slider_layer,
    )
