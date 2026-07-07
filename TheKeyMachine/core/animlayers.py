"""
Animation-layer support shared by sliders, selection, and copy/paste tools.

When animation layers are present, callers can resolve either the best editable
layer curve for a plug or every available layer curve for layered copy/paste.
"""

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


ANIM_CURVE_TYPES = set()
BLEND_NODE_TYPES = set()
BLEND_NODE_ROTATION_TYPES = set()

if om is not None:
    ANIM_CURVE_TYPES = {
        om.MFn.kAnimCurveTimeToAngular,
        om.MFn.kAnimCurveTimeToDistance,
        om.MFn.kAnimCurveTimeToUnitless,
        om.MFn.kAnimCurveTimeToTime,
    }
    BLEND_NODE_TYPES = {
        om.MFn.kBlendNodeDoubleLinear,
        om.MFn.kBlendNodeAdditiveRotation,
        om.MFn.kBlendNodeAdditiveScale,
        om.MFn.kBlendNodeBoolean,
        om.MFn.kBlendNodeEnum,
        om.MFn.kBlendNodeDouble,
        om.MFn.kBlendNodeDoubleAngle,
        om.MFn.kBlendNodeFloat,
        om.MFn.kBlendNodeFloatAngle,
        om.MFn.kBlendNodeFloatLinear,
        om.MFn.kBlendNodeInt16,
        om.MFn.kBlendNodeInt32,
        om.MFn.kBlendNodeBase,
    }
    BLEND_NODE_ROTATION_TYPES = {om.MFn.kBlendNodeAdditiveRotation}


class AnimationLayer(object):
    def __init__(self, layer=None):
        self.layer = layer
        self.selected = False
        self.locked = False
        self.refresh()

    def refresh(self):
        if self.layer is None or om is None:
            return
        node = om.MFnDependencyNode(self.layer)
        try:
            self.selected = bool(node.findPlug("selected", True).asBool())
        except Exception:
            self.selected = False
        try:
            self.locked = bool(node.findPlug("lock", True).asBool())
        except Exception:
            self.locked = False


class LayerCache(object):
    def __init__(self):
        self.scene_layers = []
        self.selected_layers = []
        self.unlocked_layers = []
        self.root = AnimationLayer()
        self.reset()

    def reset(self):
        self.scene_layers = _scene_layers(include_locked=True) or []
        self.selected_layers = _selected_layers(_scene_layers(include_locked=False) or [])
        self.unlocked_layers = _scene_layers(include_locked=False) or []
        self.root = AnimationLayer(_root_layer())


cache = LayerCache()


def _mobject_name(mobject):
    try:
        return om.MFnDependencyNode(mobject).absoluteName()
    except Exception:
        try:
            return om.MFnDependencyNode(mobject).name()
        except Exception:
            return None


def _mplug_from_name(plug_name):
    if om is None or not plug_name:
        return None
    try:
        selection = om.MSelectionList()
        selection.add(str(plug_name))
        return selection.getPlug(0)
    except Exception:
        return None


def _root_layer():
    if om is None or cmds is None:
        return None
    try:
        root_name = cmds.animLayer(q=True, root=True)
    except Exception:
        root_name = None
    if not root_name:
        return None
    try:
        selection = om.MSelectionList()
        selection.add(root_name)
        return selection.getDependNode(0)
    except Exception:
        return None


def _scene_layers(include_locked=False):
    if om is None:
        return []
    root = _root_layer()
    if root is None:
        return []

    layers = [root]
    try:
        root_node = om.MFnDependencyNode(root)
        children = root_node.findPlug("childrenLayers", True)
        for index in range(children.numElements() - 1, -1, -1):
            connections = children.elementByPhysicalIndex(index).connectedTo(True, False)
            if connections:
                layers.append(connections[0].node())
    except Exception:
        pass

    if include_locked:
        return layers

    unlocked = []
    for layer in layers:
        try:
            node = om.MFnDependencyNode(layer)
            if node.findPlug("lock", True).asBool():
                continue
        except Exception:
            pass
        unlocked.append(layer)
    return unlocked


def _selected_layers(layers):
    selected = []
    for layer in layers or []:
        try:
            node = om.MFnDependencyNode(layer)
            if node.findPlug("selected", True).asBool():
                selected.append(layer)
        except Exception:
            pass
    return selected


def has_anim_layers():
    if om is None:
        return False
    count = 0
    try:
        iterator = om.MItDependencyNodes(om.MFn.kAnimLayer)
        while not iterator.isDone():
            if count > 0:
                return True
            count += 1
            iterator.next()
    except Exception:
        return False
    return False


def _best_layer(plug):
    root = cache.root
    selected_layers = cache.selected_layers
    scene_layers = cache.scene_layers

    if root.locked:
        root_layer = None
    elif root.selected and not len(selected_layers) > 1:
        return root.layer
    else:
        root_layer = root.layer

    best_layer = None
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

    if selected_layers:
        while not iterator.isDone():
            layer = iterator.currentNode()
            if layer in scene_layers:
                iterator.prune()
                if layer in selected_layers:
                    best_layer = layer
            iterator.next()

    if best_layer:
        return best_layer

    iterator.reset()
    while not iterator.isDone():
        layer = iterator.currentNode()
        if layer in scene_layers:
            iterator.prune()
            if layer in cache.unlocked_layers:
                best_layer = layer
        iterator.next()

    return best_layer or root_layer


def _anim_curve_for_layer(plug, layer):
    if om is None or plug is None or layer is None:
        return None

    is_root = bool(cache.root.layer and layer == cache.root.layer)
    scene_layers = cache.scene_layers

    try:
        iterator = om.MItDependencyGraph(
            plug,
            om.MFn.kInvalid,
            direction=om.MItDependencyGraph.kUpstream,
            traversal=om.MItDependencyGraph.kBreadthFirst,
            level=om.MItDependencyGraph.kNodeLevel,
        )
    except Exception:
        return None

    target_blend = None
    while not iterator.isDone():
        current_node = iterator.currentNode()
        if current_node in scene_layers:
            iterator.prune()
        iterator.next()

        if current_node.apiType() not in BLEND_NODE_TYPES:
            continue

        if is_root:
            target_blend = current_node
            continue

        try:
            node_fn = om.MFnDependencyNode(current_node)
            layer_plug = node_fn.findPlug("wa", True)
            if layer_plug and layer == layer_plug.source().node():
                target_blend = current_node
                break
        except Exception:
            pass

    if target_blend is None:
        return None

    try:
        node_fn = om.MFnDependencyNode(target_blend)
        input_plug = node_fn.findPlug("ia" if is_root else "ib", True)
    except Exception:
        return None

    if target_blend.apiType() in BLEND_NODE_ROTATION_TYPES:
        child_index = 0
        try:
            if plug.isChild:
                parent = plug.parent()
                for index in range(parent.numChildren()):
                    if parent.child(index) == plug:
                        child_index = index
                        break
            if input_plug.isCompound and child_index < input_plug.numChildren():
                input_plug = input_plug.child(child_index)
        except Exception:
            return None

    try:
        source = input_plug.source()
        curve_node = source.node()
        if curve_node and curve_node.apiType() in ANIM_CURVE_TYPES:
            return _mobject_name(curve_node)
    except Exception:
        pass
    return None


def get_anim_curve_for_plug(plug_name):
    """Return the best animCurve for a plug, respecting selected/unlocked layers."""
    if om is None:
        return None
    plug = _mplug_from_name(plug_name)
    if plug is None:
        return None

    cache.reset()
    if not has_anim_layers():
        return None

    layer = _best_layer(plug)
    return _anim_curve_for_layer(plug, layer)


def _layer_name(layer):
    if layer is None:
        return None
    try:
        return om.MFnDependencyNode(layer).name()
    except Exception:
        return _mobject_name(layer)


def get_anim_curves_by_layer_for_plug(plug_name):
    """Return every available animation-layer curve for a plug.

    Entries use ``layer=None`` for the root/base layer so callers can keep
    layered data distinct without depending on OpenMaya objects.
    """
    if om is None:
        return []
    plug = _mplug_from_name(plug_name)
    if plug is None:
        return []

    cache.reset()
    if not has_anim_layers():
        return []

    entries = []
    root_layer = cache.root.layer
    for layer in cache.scene_layers:
        curve = _anim_curve_for_layer(plug, layer)
        if not curve:
            continue
        is_root = bool(root_layer and layer == root_layer)
        entries.append(
            {
                "layer": None if is_root else _layer_name(layer),
                "curve": curve,
                "root": is_root,
            }
        )
    return entries
