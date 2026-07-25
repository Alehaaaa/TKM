"""
Animation-layer support shared by sliders, selection, and copy/paste tools.

The core owns layer state, exact per-layer curve traversal, clipboard metadata,
and shared key destinations. Interactive slider preference policy lives in the
slider feature shim.
"""

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from TheKeyMachine.core import openMayaUtils as omutils


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
    """One animation layer and the state shared by all layer-aware tools."""

    def __init__(self, layer=None, root=False):
        self.layer = layer
        self.name = layer if isinstance(layer, str) else None
        self.root = bool(root)
        self.selected = False
        self.preferred = False
        self.locked = False
        self.muted = False
        self.override = False
        self.passthrough = True
        self.parent = None
        self.rotation_accumulation_mode = None
        self.scale_accumulation_mode = None
        self.refresh()

    @property
    def layer_id(self):
        return BASE_LAYER_ID if self.root else self.name

    def refresh(self):
        node = omutils.dependency_node_fn(self.layer)
        if node is None:
            if self.name:
                self.selected = _query_layer_flag(self.name, "selected")
                self.preferred = _query_layer_flag(self.name, "preferred")
                self.locked = _query_layer_flag(self.name, "lock")
                self.muted = _query_layer_flag(self.name, "mute")
                self.override = _query_layer_flag(self.name, "override")
                self.passthrough = _query_layer_flag(
                    self.name, "passthrough", default=True
                )
                self.parent = _layer_parent(self.name)
                self.rotation_accumulation_mode = _accumulation_mode(
                    self.name, "rotationAccumulationMode"
                )
                self.scale_accumulation_mode = _accumulation_mode(
                    self.name, "scaleAccumulationMode"
                )
            return
        try:
            self.name = node.name()
        except Exception:
            self.name = omutils.mobject_name(self.layer)
        for attribute, field, default in (
            ("selected", "selected", False),
            ("preferred", "preferred", False),
            ("lock", "locked", False),
            ("mute", "muted", False),
            ("override", "override", False),
            ("passthrough", "passthrough", True),
        ):
            try:
                value = node.findPlug(attribute, True).asBool()
            except Exception:
                value = default
            setattr(self, field, bool(value))

        self.rotation_accumulation_mode = _accumulation_mode(
            self.name, "rotationAccumulationMode", node=node
        )
        self.scale_accumulation_mode = _accumulation_mode(
            self.name, "scaleAccumulationMode", node=node
        )
        if self.name:
            self.parent = _layer_parent(self.name)

    def as_dict(self):
        return {
            "name": self.name,
            "root": self.root,
            "selected": self.selected,
            "preferred": self.preferred,
            "locked": self.locked,
            "muted": self.muted,
            "override": self.override,
            "passthrough": self.passthrough,
            "parent": self.parent or None,
            "rotation_accumulation_mode": self.rotation_accumulation_mode,
            "scale_accumulation_mode": self.scale_accumulation_mode,
        }


class LayerCache(object):
    """Current scene layer graph, refreshed at the start of each operation."""

    def __init__(self):
        self.scene_layers = []
        self.selected_layers = []
        self.selected_unlocked_layers = []
        self.unlocked_layers = []
        self.preferred = None
        self.root = AnimationLayer(root=True)
        # Do NOT call reset() here – module-level instantiation happens at
        # import/reload time, when Maya may refuse cmds.animLayer queries with
        # "Unable to parse the argument list". Data is populated lazily on the
        # first real call to capture_context().

    def reset(self):
        root_name = root_layer_name()
        names = scene_layer_names(include_root=True)
        graph_names = [
            _layer_name(layer)
            for layer in _scene_layers()
        ]
        graph_names = [name for name in graph_names if name]
        if graph_names:
            names = list(dict.fromkeys(graph_names + names))
        self.scene_layers = [
            AnimationLayer(
                omutils.mobject_from_node(name) or name,
                root=bool(root_name and name == root_name),
            )
            for name in names
        ]
        self.root = next(
            (layer for layer in self.scene_layers if layer.root),
            AnimationLayer(root=True),
        )
        self.selected_layers = [layer for layer in self.scene_layers if layer.selected]
        self.selected_unlocked_layers = [
            layer for layer in self.selected_layers if not layer.locked
        ]
        self.unlocked_layers = [layer for layer in self.scene_layers if not layer.locked]
        self.preferred = next(
            (
                layer
                for layer in self.selected_unlocked_layers
                if layer.preferred
            ),
            self.selected_unlocked_layers[-1]
            if self.selected_unlocked_layers
            else None,
        )
        return self

    def by_id(self, layer_id):
        return next(
            (layer for layer in self.scene_layers if layer.layer_id == layer_id),
            None,
        )

    def capture(self):
        selected = [layer.layer_id for layer in self.selected_layers]
        selected_unlocked = [
            layer.layer_id for layer in self.selected_unlocked_layers
        ]
        explicitly_selected = bool(selected)
        layers = {
            layer.layer_id: layer.as_dict()
            for layer in self.scene_layers
            if layer.layer_id
        }
        return {
            "has_layers": any(not layer.root for layer in self.scene_layers),
            "root_name": self.root.name,
            "layers": layers,
            "selected": selected,
            "selected_unlocked": selected_unlocked,
            "active": self.preferred.layer_id if self.preferred else None,
            "selection_explicit": explicitly_selected,
            "copy_scope": "selected" if explicitly_selected else "all",
            "copy_layer_ids": (
                list(selected_unlocked) if explicitly_selected else list(layers)
            ),
        }


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
        return omutils.mobject_from_node(root_name)
    except Exception:
        return None


def _scene_layers():
    if om is None:
        return []
    root = _root_layer()
    if root is None:
        return []

    layers = []

    def _append_layer(layer):
        if layer is None:
            return
        layers.append(layer)
        try:
            node = omutils.dependency_node_fn(layer)
            children = node.findPlug("childrenLayers", True)
        except Exception:
            return
        for index in range(children.numElements() - 1, -1, -1):
            try:
                connections = children.elementByPhysicalIndex(index).connectedTo(True, False)
            except Exception:
                connections = []
            if connections:
                _append_layer(connections[0].node())

    _append_layer(root)

    return layers


def has_anim_layers():
    return bool(scene_layer_names(include_root=False))


def anim_curve_for_layer(plug, layer):
    if om is None or plug is None or layer is None:
        return None

    root_layer = _root_layer()
    is_root = bool(root_layer and layer == root_layer)
    scene_layers = _scene_layers()

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
            node_fn = omutils.dependency_node_fn(current_node)
            layer_plug = node_fn.findPlug("wa", True)
            if layer_plug and layer == layer_plug.source().node():
                target_blend = current_node
                break
        except Exception:
            pass

    if target_blend is None:
        return None

    try:
        node_fn = omutils.dependency_node_fn(target_blend)
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
            return omutils.mobject_name(curve_node)
    except Exception:
        pass
    return None


def _layer_name(layer):
    if layer is None:
        return None
    try:
        node = omutils.dependency_node_fn(layer)
        return node.name() if node is not None else None
    except Exception:
        return omutils.mobject_name(layer)


def _layer_graph_for_plug(plug_name, scene_layers=None):
    """Resolve one plug plus the scene's layer graph and its root.

    ``scene_layers`` lets a caller that already walked the graph (e.g.
    ``get_anim_curves_from_plugs`` resolving many plugs at once) pass it
    straight through instead of re-walking it -- ``_scene_layers()`` was
    otherwise re-querying the whole animLayer graph from Maya once per plug,
    which dominated resolution time for any sizeable selection.
    """
    if om is None:
        return None, None, []
    plug = omutils.mplug_from_name(plug_name)
    if plug is None:
        return None, None, []
    if scene_layers is None:
        scene_layers = _scene_layers()
    if not scene_layers:
        return plug, None, []
    # _scene_layers() always appends the root before any children, so the
    # first entry is the root layer -- no separate _root_layer() call needed.
    return plug, scene_layers[0], scene_layers


def _direct_anim_curve_for_plug(plug_name):
    if cmds is None:
        return None
    try:
        curves = cmds.listConnections(
            plug_name,
            source=True,
            destination=False,
            type="animCurve",
        ) or []
    except _COMMAND_ERRORS:
        curves = []
    return curves[0] if curves else None


def get_anim_curves_by_layer_for_plug(plug_name, scene_layers=None):
    """Return every available animation-layer curve for a plug.

    Entries use ``layer=None`` for the root/base layer so callers can keep
    layered data distinct without depending on OpenMaya objects. Pass an
    already-resolved ``scene_layers`` (see ``_layer_graph_for_plug``) when
    resolving many plugs in a row.
    """
    plug, root_layer, scene_layers = _layer_graph_for_plug(plug_name, scene_layers=scene_layers)
    if plug is None:
        return []

    entries = []
    for layer in scene_layers:
        curve = anim_curve_for_layer(plug, layer)
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


# ---------------------------------------------------------------------------
# Command-layer context

BASE_LAYER_ID = "__base__"
_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)


def root_layer_name():
    """Return Maya's root animation layer name, if animation layers exist."""
    if cmds is None:
        return None
    try:
        return cmds.animLayer(query=True, root=True) or None
    except _COMMAND_ERRORS:
        return None


def scene_layer_names(include_root=True):
    """Return animation layers in Maya's evaluation order."""
    if cmds is None:
        return []
    root_name = root_layer_name()
    names = []
    try:
        names = list(cmds.ls(type="animLayer") or [])
    except _COMMAND_ERRORS:
        names = []
    if root_name and root_name not in names:
        names.insert(0, root_name)
    if root_name in names:
        names.remove(root_name)
        names.insert(0, root_name)
    if not include_root and root_name:
        names = [name for name in names if name != root_name]
    return list(dict.fromkeys(names))


def _query_layer_flag(layer_name, flag, default=False):
    if not layer_name or cmds is None:
        return default
    try:
        return bool(cmds.animLayer(layer_name, query=True, **{flag: True}))
    except _COMMAND_ERRORS:
        return default


def _accumulation_mode(layer_name, attribute, node=None, default=None):
    """Read an animLayer accumulation-mode value directly from the node
    instead of ``cmds.animLayer(query=True, <flag>=True)``.

    That query flag reliably prints "Unable to parse the argument list" to
    the Script Editor for rotationAccumulationMode/scaleAccumulationMode on
    some layers (BaseAnimation, freshly created layers), even though the
    underlying attribute reads back fine. Wrapping the call in try/except
    only stops the Python exception -- Maya still prints its own error
    banner underneath, which is the noise users see. Reading the attribute
    directly (OpenMaya when we already have the node, cmds.getAttr
    otherwise) never touches that broken flag, so nothing gets printed.
    """
    if node is not None:
        try:
            return node.findPlug(attribute, True).asInt()
        except Exception:
            pass
    if not layer_name or cmds is None:
        return default
    try:
        value = cmds.getAttr("{}.{}".format(layer_name, attribute))
    except Exception:
        return default
    return default if value is None else value


def _layer_parent(layer_name):
    """Resolve an animLayer's parent without ``cmds.animLayer(query=True,
    parent=True)``.

    That flag turned out to have the same "Unable to parse the argument
    list" issue as the accumulation-mode ones -- it's the last remaining
    cmds.animLayer query flag in the normal refresh path. A parent layer
    connects to a child through the child's ``message`` plug into the
    parent's ``childrenLayers`` array (the same link ``_scene_layers()``
    already walks via OpenMaya), so ``listConnections`` -- a different,
    unaffected command -- can read it back directly.
    """
    if not layer_name or cmds is None:
        return None
    try:
        destinations = cmds.listConnections(
            "{}.message".format(layer_name),
            source=False,
            destination=True,
            type="animLayer",
            plugs=True,
        ) or []
    except Exception:
        destinations = []
    for destination in destinations:
        if ".childrenLayers" not in destination:
            continue
        node_name = destination.split(".", 1)[0]
        if node_name != layer_name:
            return node_name
    return None


cache = LayerCache()


def layer_metadata(layer_name):
    """Capture the state needed to faithfully recreate an animation layer."""
    cached = cache.by_id(layer_id_for_name(layer_name))
    if cached is not None:
        return cached.as_dict()
    # Uncached (e.g. a layer just created this operation, before the next
    # cache.reset()): build through the same AnimationLayer.refresh() path
    # the cache itself uses, instead of a second, cmds-heavy implementation.
    # That path already prefers OpenMaya over cmds.animLayer(query=True,
    # ...) wherever possible, which is what keeps this from re-triggering
    # "Unable to parse the argument list" on a freshly created layer.
    root_name = root_layer_name()
    is_root = bool(layer_name and layer_name == root_name)
    return AnimationLayer(layer_name, root=is_root).as_dict()


def capture_context():
    """Snapshot selection and state for all animation layers.

    ``copy_layer_ids`` implements the shared copy rule: selected editable
    layers when the layer editor has an explicit selection, otherwise every
    layer (including BaseAnimation).
    """
    return cache.reset().capture()


def layer_id_for_name(layer_name):
    return BASE_LAYER_ID if not layer_name or layer_name == root_layer_name() else layer_name


def layer_name_for_id(layer_id, context=None):
    if layer_id in (None, BASE_LAYER_ID):
        return None
    metadata = ((context or {}).get("layers") or {}).get(layer_id) or {}
    return metadata.get("name") or layer_id


def layer_contains_plug(layer_name, plug_name):
    """Return whether ``plug_name`` is already a member of ``layer_name``."""
    if not layer_name or not plug_name or cmds is None:
        return False
    root_name = root_layer_name()
    if layer_name == root_name:
        return True
    try:
        attributes = cmds.animLayer(layer_name, query=True, attribute=True) or []
    except _COMMAND_ERRORS:
        attributes = []
    if plug_name in attributes:
        return True
    node_name, _, attr_name = str(plug_name).partition(".")
    short_node = node_name.rsplit("|", 1)[-1]
    for attribute in attributes:
        attribute_node, _, attribute_attr = str(attribute).partition(".")
        # Comparing node names alone matches any attribute on the same node,
        # not the one being checked (e.g. pTorus1.visibility being a member
        # would falsely mark pTorus1.scaleX as one too). Require the same
        # attribute name as well.
        if attribute_attr != attr_name:
            continue
        if attribute_node == node_name:
            return True
        if attribute_node.rsplit("|", 1)[-1] == short_node:
            return True
    try:
        affected = cmds.animLayer(plug_name, query=True, affectedLayers=True) or []
    except _COMMAND_ERRORS:
        affected = []
    return layer_name in affected


def selected_destination_for_plug(plug_name, context=None):
    """Resolve the current paste/key destination for one plug.

    A selected, unlocked non-root layer is the destination for as long as
    it's active -- the same way keying with a layer highlighted in Maya's
    Anim Layer Editor adds new attributes to that layer instead of quietly
    keying BaseAnimation. A locked selected layer blocks the attribute
    instead. ``member`` reports prior membership for callers that care, but
    no longer changes which layer is targeted.
    """
    context = context or capture_context()
    selected = list(context.get("selected") or [])
    if not selected:
        return {"layer": None, "layer_id": BASE_LAYER_ID, "blocked": False, "member": True}

    layer_id = context.get("active") or selected[-1]
    if layer_id == BASE_LAYER_ID:
        metadata = (context.get("layers") or {}).get(BASE_LAYER_ID) or {}
        return {
            "layer": None,
            "layer_id": BASE_LAYER_ID,
            "blocked": bool(metadata.get("locked")),
            "member": True,
        }

    layer_name = layer_name_for_id(layer_id, context)
    member = layer_contains_plug(layer_name, plug_name)
    metadata = (context.get("layers") or {}).get(layer_id) or layer_metadata(layer_name)
    return {
        "layer": layer_name,
        "layer_id": layer_id,
        "blocked": bool(metadata.get("locked")),
        "member": member,
    }


def group_attributes_by_destination(node, attributes, context=None):
    """Group attributes by the layer on which a tool should create keys."""
    context = context or capture_context()
    groups = {}
    blocked = []
    for attribute in attributes or []:
        plug = "{}.{}".format(node, attribute)
        destination = selected_destination_for_plug(plug, context=context)
        if destination.get("blocked"):
            blocked.append(attribute)
            continue
        groups.setdefault(destination.get("layer"), []).append(attribute)
    return groups, blocked


def cut_keys_in_destination(node, attributes, timerange, context=None):
    """Cut keys only from the resolved destination layers."""
    groups, blocked = group_attributes_by_destination(
        node, attributes, context=context
    )
    for layer_name, grouped_attributes in groups.items():
        if has_anim_layers():
            for attribute in grouped_attributes:
                curve = get_anim_curve_for_plug(
                    "{}.{}".format(node, attribute),
                    layer_name=layer_name,
                )
                if not curve:
                    continue
                try:
                    cmds.cutKey(curve, time=timerange, option="keys")
                except _COMMAND_ERRORS:
                    pass
            continue
        try:
            cmds.cutKey(
                node,
                attribute=grouped_attributes,
                time=timerange,
                option="keys",
            )
        except _COMMAND_ERRORS:
            pass
    return blocked


def set_keyframe_in_destination(node, attributes, time=None, context=None):
    """Set keys on the current editable layer.

    Returns ``(keyed_attrs, blocked_attrs)``. A layer group that raises is
    skipped as before, but a group that runs without error and still keys
    nothing (Maya can silently no-op ``setKeyframe`` for some attribute/layer
    combinations) is no longer reported as a false success -- callers used to
    have no way to tell the two apart.
    """
    groups, blocked = group_attributes_by_destination(
        node, attributes, context=context
    )
    keyed = []
    for layer_name, grouped_attributes in groups.items():
        kwargs = {"attribute": grouped_attributes}
        if time is not None:
            kwargs["time"] = (time,)
        if layer_name:
            kwargs["animLayer"] = layer_name
        try:
            result = cmds.setKeyframe(node, **kwargs)
        except _COMMAND_ERRORS:
            continue
        if result:
            keyed.extend(grouped_attributes)
    return keyed, blocked


def get_anim_curve_for_plug(
    plug_name,
    layer_name=None,
    layer_selector=None,
    scene_layers=None,
):
    """Return one layer curve for a plug.

    ``layer_name=None`` addresses BaseAnimation. A feature-specific
    ``layer_selector`` may instead choose an animation-layer object from the
    refreshed shared cache. Pass an already-resolved ``scene_layers`` (see
    ``_layer_graph_for_plug``) when resolving many plugs in a row.
    """
    plug, root_layer, scene_layers = _layer_graph_for_plug(plug_name, scene_layers=scene_layers)
    if plug is None:
        return None
    if not scene_layers:
        return _direct_anim_curve_for_plug(plug_name)
    if layer_selector is not None:
        cache.reset()
        try:
            target_layer = layer_selector(plug)
        except Exception:
            return None
        return (
            anim_curve_for_layer(plug, target_layer)
            or _direct_anim_curve_for_plug(plug_name)
        )

    if layer_name:
        for layer in scene_layers:
            if _layer_name(layer) == layer_name:
                # A specific, named non-root layer was requested. If it has
                # no curve yet for this plug, that's a real answer -- a
                # freshly created layer legitimately has none yet -- not an
                # invitation to substitute _direct_anim_curve_for_plug's
                # unlayered lookup, which finds the first animCurve directly
                # connected to the plug with no regard for which layer it
                # actually belongs to. On a plug already animated on
                # BaseAnimation, that fallback silently returned Base's
                # curve for an AnimLayer1 request, so callers like
                # _cut_destination_keys ended up cutting Base's keys while
                # believing they were touching the new layer.
                return anim_curve_for_layer(plug, layer)
        return None

    return (
        anim_curve_for_layer(plug, root_layer)
        or _direct_anim_curve_for_plug(plug_name)
    )


def get_anim_curves_from_plugs(
    plugs,
    layer_selector=None,
    include_all_layers=False,
):
    """Resolve unique curves for plugs through one shared lookup path.

    Walks the scene's animLayer graph once for the whole batch instead of
    once per plug -- resolving hundreds of plugs one at a time previously
    meant hundreds of redundant re-walks of the same, unchanged graph.
    """
    curves = []
    scene_layers = _scene_layers()
    for plug_name in dict.fromkeys(plugs or []):
        if not plug_name:
            continue
        if include_all_layers:
            resolved = [
                entry["curve"]
                for entry in get_anim_curves_by_layer_for_plug(plug_name, scene_layers=scene_layers)
                if entry.get("curve")
            ]
        else:
            curve = get_anim_curve_for_plug(
                plug_name,
                layer_selector=layer_selector,
                scene_layers=scene_layers,
            )
            resolved = [curve] if curve else []
        if include_all_layers and not resolved:
            curve = get_anim_curve_for_plug(plug_name, scene_layers=scene_layers)
            resolved = [curve] if curve else []
        for curve in resolved:
            if curve and curve not in curves:
                curves.append(curve)
    return curves


def add_plug_to_layer(layer_name, plug_name):
    if not layer_name or not plug_name or cmds is None:
        return False
    try:
        cmds.animLayer(layer_name, edit=True, attribute=plug_name)
        return True
    except _COMMAND_ERRORS:
        return False


def create_layer(metadata):
    """Create a layer from clipboard metadata, initially editable."""
    if cmds is None or not isinstance(metadata, dict) or metadata.get("root"):
        return None
    requested_name = metadata.get("name")
    if not requested_name:
        return None
    if requested_name in scene_layer_names(include_root=True):
        return requested_name

    kwargs = {"override": bool(metadata.get("override"))}
    parent = metadata.get("parent")
    if parent and parent in scene_layer_names(include_root=True):
        kwargs["parent"] = parent
    try:
        layer_name = cmds.animLayer(requested_name, **kwargs)
    except _COMMAND_ERRORS:
        try:
            layer_name = cmds.animLayer(requested_name)
        except _COMMAND_ERRORS:
            return None
    layer_name = layer_name or requested_name
    try:
        cmds.animLayer(
            layer_name, edit=True, override=bool(metadata.get("override"))
        )
    except _COMMAND_ERRORS:
        pass
    passthrough = metadata.get("passthrough")
    if passthrough is not None:
        try:
            cmds.animLayer(layer_name, edit=True, passthrough=passthrough)
        except _COMMAND_ERRORS:
            pass

    # rotationAccumulationMode/scaleAccumulationMode: cmds.animLayer(edit=True,
    # <flag>=value) is the same flag pair that prints "Unable to parse the
    # argument list" on query for a layer just created in this evaluation
    # (see _accumulation_mode). Setting the underlying attribute directly
    # with setAttr has the same effect without going through that flag.
    for attribute, key in (
        ("rotationAccumulationMode", "rotation_accumulation_mode"),
        ("scaleAccumulationMode", "scale_accumulation_mode"),
    ):
        value = metadata.get(key)
        if value is None:
            continue
        try:
            cmds.setAttr("{}.{}".format(layer_name, attribute), value)
        except _COMMAND_ERRORS:
            pass
    return layer_name


def restore_layer_state(layer_name, metadata):
    """Apply non-structural layer state after keys have been created."""
    if not layer_name or not isinstance(metadata, dict) or cmds is None:
        return
    for flag, key in (("mute", "muted"), ("lock", "locked")):
        try:
            cmds.animLayer(layer_name, edit=True, **{flag: bool(metadata.get(key))})
        except _COMMAND_ERRORS:
            pass


def prepare_paste_context(copied_context, plugs):
    """Recreate a copied active layer when a non-layered scene receives keys."""
    current = capture_context()
    if current.get("has_layers") or not isinstance(copied_context, dict):
        return current, {}
    source_id = copied_context.get("active")
    if source_id in (None, BASE_LAYER_ID):
        return current, {}
    metadata = dict(
        ((copied_context.get("layers") or {}).get(source_id)) or {}
    )
    if not metadata or metadata.get("locked"):
        return current, {}
    layer_name = create_layer(metadata)
    if not layer_name:
        return current, {}
    for plug in dict.fromkeys(plugs or []):
        add_plug_to_layer(layer_name, plug)
    try:
        root_name = root_layer_name()
        if root_name:
            cmds.animLayer(root_name, edit=True, selected=False)
        cmds.animLayer(layer_name, edit=True, selected=True, preferred=True)
    except _COMMAND_ERRORS:
        pass
    return capture_context(), {layer_name: metadata}


def restore_created_layer_states(created_layers):
    for layer_name, metadata in (created_layers or {}).items():
        restore_layer_state(layer_name, metadata)
