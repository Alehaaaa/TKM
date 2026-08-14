"""Animation-layer graph traversal and animCurve ownership."""

from __future__ import annotations

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

try:
    from maya import cmds
except ImportError:
    cmds = None

from TheKeyMachine.maya import maya_api


_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)
_ANIM_CURVE_TYPES = set()
_BLEND_NODE_TYPES = set()
_ROTATION_BLEND_TYPES = set()

if om is not None:
    _ANIM_CURVE_TYPES = {
        om.MFn.kAnimCurveTimeToAngular,
        om.MFn.kAnimCurveTimeToDistance,
        om.MFn.kAnimCurveTimeToUnitless,
        om.MFn.kAnimCurveTimeToTime,
    }
    _BLEND_NODE_TYPES = {
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
    _ROTATION_BLEND_TYPES = {om.MFn.kBlendNodeAdditiveRotation}


def root_layer_name():
    if cmds is None:
        return None
    try:
        return cmds.animLayer(query=True, root=True) or None
    except _COMMAND_ERRORS:
        return None


def scene_layer_objects():
    """Return the root and child layers in Maya evaluation order."""
    if om is None:
        return []
    root_name = root_layer_name()
    try:
        root = maya_api.mobject_from_node(root_name) if root_name else None
    except Exception:
        root = None
    if root is None:
        return []

    layers = []

    def append_layer(layer):
        layers.append(layer)
        try:
            children = maya_api.dependency_node_fn(layer).findPlug(
                "childrenLayers",
                True,
            )
        except Exception:
            return
        for index in range(children.numElements() - 1, -1, -1):
            try:
                connections = children.elementByPhysicalIndex(index).connectedTo(
                    True,
                    False,
                )
            except Exception:
                connections = []
            if connections:
                append_layer(connections[0].node())

    append_layer(root)
    return layers


def _layer_name(layer):
    if layer is None:
        return None
    try:
        node = maya_api.dependency_node_fn(layer)
        return node.name() if node is not None else None
    except Exception:
        return maya_api.mobject_name(layer)


def _curve_from_blend_input(plug, blend_node, root):
    try:
        input_plug = maya_api.dependency_node_fn(blend_node).findPlug(
            "ia" if root else "ib",
            True,
        )
    except Exception:
        return None

    if blend_node.apiType() in _ROTATION_BLEND_TYPES:
        child_index = 0
        try:
            if plug.isChild:
                parent = plug.parent()
                child_index = next(
                    index
                    for index in range(parent.numChildren())
                    if parent.child(index) == plug
                )
            if input_plug.isCompound and child_index < input_plug.numChildren():
                input_plug = input_plug.child(child_index)
        except (Exception, StopIteration):
            return None

    try:
        curve = input_plug.source().node()
        if curve and curve.apiType() in _ANIM_CURVE_TYPES:
            return maya_api.mobject_name(curve)
    except Exception:
        pass
    return None


def _layer_curves(plug, scene_layers):
    if om is None or plug is None or not scene_layers:
        return {}
    root_name = _layer_name(scene_layers[0])
    layer_names = {_layer_name(layer) for layer in scene_layers}
    try:
        iterator = om.MItDependencyGraph(
            plug,
            om.MFn.kInvalid,
            direction=om.MItDependencyGraph.kUpstream,
            traversal=om.MItDependencyGraph.kBreadthFirst,
            level=om.MItDependencyGraph.kNodeLevel,
        )
    except Exception:
        return {}

    root_blend = None
    layer_blends = {}
    while not iterator.isDone():
        node = iterator.currentNode()
        node_name = _layer_name(node)
        if node_name in layer_names:
            iterator.prune()
        iterator.next()
        if node.apiType() not in _BLEND_NODE_TYPES:
            continue
        root_blend = node
        try:
            layer = maya_api.dependency_node_fn(node).findPlug("wa", True).source().node()
            layer_name = _layer_name(layer)
        except Exception:
            layer_name = None
        if layer_name and layer_name != root_name and layer_name in layer_names:
            layer_blends.setdefault(layer_name, node)

    curves = {}
    if root_blend is not None and root_name:
        curve = _curve_from_blend_input(plug, root_blend, True)
        if curve:
            curves[root_name] = curve
    for layer_name, blend_node in layer_blends.items():
        curve = _curve_from_blend_input(plug, blend_node, False)
        if curve:
            curves[layer_name] = curve
    return curves


def _unlayered_curve(plug_name):
    if cmds is None:
        return None
    try:
        curves = cmds.listConnections(
            plug_name,
            source=True,
            destination=False,
            type="animCurve",
            skipConversionNodes=True,
        ) or []
    except _COMMAND_ERRORS:
        curves = []
    return curves[0] if curves else None


class LayerGraph(object):
    """Resolve animCurve ownership through Maya's animation-layer graph."""

    def curves_by_layer(self, plug_name, scene_layers=None):
        if om is None:
            return []
        plug = maya_api.mplug_from_name(plug_name)
        if plug is None:
            return []
        if scene_layers is None:
            scene_layers = scene_layer_objects()
        if not scene_layers:
            curve = _unlayered_curve(plug_name)
            return [{"layer": None, "curve": curve, "root": True}] if curve else []

        root_layer = scene_layers[0]
        layer_curves = _layer_curves(plug, scene_layers)
        try:
            source = plug.source().node()
            direct_curve = (
                maya_api.mobject_name(source)
                if source and source.apiType() in _ANIM_CURVE_TYPES
                else None
            )
        except Exception:
            direct_curve = None

        entries = []
        for layer in scene_layers:
            root = layer == root_layer
            layer_name = _layer_name(layer)
            curve = (
                direct_curve or layer_curves.get(layer_name) or _unlayered_curve(plug_name)
                if root
                else layer_curves.get(layer_name)
            )
            if curve:
                entries.append({
                    "layer": None if root else layer_name,
                    "curve": curve,
                    "root": root,
                })
        return entries

    def curve_for_plug(
        self,
        plug_name,
        layer_name=None,
        scene_layers=None,
    ):
        scene_layers = scene_layers or scene_layer_objects()
        entries = self.curves_by_layer(plug_name, scene_layers=scene_layers)
        if not entries:
            return None
        if layer_name:
            return next(
                (entry["curve"] for entry in entries if entry["layer"] == layer_name),
                None,
            )
        return next((entry["curve"] for entry in entries if entry["root"]), None)

    def editable_curve_for_plug(self, plug_name, layer_context):
        """Return the curve on the preferred editable layer for one plug.

        The layer snapshot owns selection, locking, and evaluation order. Curve
        ownership is already resolved here, so consumers do not need a second
        dependency-graph traversal merely to choose among the resulting curves.
        """
        entries = self.curves_by_layer(
            plug_name,
            scene_layers=(layer_context or {}).get("scene_layers"),
        )
        if not entries:
            return None

        layer_context = layer_context or {}
        if not layer_context.get("has_layers"):
            return entries[0]["curve"]
        root_name = layer_context.get("root_name")
        explicit = bool(layer_context.get("selection_explicit"))
        selected = list(layer_context.get("selected_unlocked") or [])
        scope = list(layer_context.get("scope_layer_names") or [])
        active = layer_context.get("active_layer")

        candidates = []
        if active:
            candidates.append(active)
        candidates.extend(reversed(selected if explicit else scope))

        snapshot = layer_context.get("context") or {}
        root_editable = any(
            metadata.get("root") and not metadata.get("locked")
            for metadata in (snapshot.get("layers") or {}).values()
        )
        if root_editable and root_name:
            candidates.append(root_name)

        for layer_name in dict.fromkeys(candidates):
            curve = next(
                (
                    entry["curve"]
                    for entry in entries
                    if (entry["root"] and layer_name == root_name)
                    or entry["layer"] == layer_name
                ),
                None,
            )
            if curve:
                return curve
        return None

    def editable_curves_for_plugs(self, plugs, layer_context):
        curves = []
        for plug_name in dict.fromkeys(plugs or []):
            curve = self.editable_curve_for_plug(plug_name, layer_context)
            if curve and curve not in curves:
                curves.append(curve)
        return curves

    def curves_for_plugs(self, plugs, include_all_layers=False):
        curves = []
        scene_layers = scene_layer_objects()
        for plug_name in dict.fromkeys(plugs or []):
            if not plug_name:
                continue
            if include_all_layers:
                resolved = [
                    entry["curve"]
                    for entry in self.curves_by_layer(
                        plug_name,
                        scene_layers=scene_layers,
                    )
                    if entry.get("curve")
                ]
            else:
                curve = self.curve_for_plug(
                    plug_name,
                    scene_layers=scene_layers,
                )
                resolved = [curve] if curve else []
            curves.extend(curve for curve in resolved if curve not in curves)
        return curves

    def ownership(self, plug_names, layer_names, scene_layers=None):
        requested = set(layer_names or [])
        if not requested:
            return {}
        scene_layers = scene_layers or scene_layer_objects()
        root_name = root_layer_name()
        ownership = {}
        for plug_name in dict.fromkeys(plug_names or []):
            for entry in self.curves_by_layer(
                plug_name,
                scene_layers=scene_layers,
            ):
                layer_name = root_name if entry["root"] else entry["layer"]
                if layer_name in requested and entry["curve"]:
                    ownership[entry["curve"]] = layer_name
        return ownership


layer_graph = LayerGraph()
