"""Animation-layer state, curve ownership, and key destinations."""

from __future__ import annotations

try:
    from maya import cmds
except ImportError:
    cmds = None

from TheKeyMachine.maya import maya_api
from .graph import layer_graph, root_layer_name, scene_layer_objects


BASE_LAYER_ID = "__base__"
_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)


class LayerContext(dict):
    """One animation-layer snapshot used throughout a tool operation."""

    @property
    def active(self):
        return self.get("active")

    def destination_for_plug(self, plug, resolve_membership=True):
        """Resolve the editable layer for one plug in this snapshot."""
        selected = list(self.get("selected") or [])
        if not selected:
            return {
                "layer": None,
                "layer_id": BASE_LAYER_ID,
                "blocked": False,
                "member": True,
            }

        layer_id = self.active or selected[-1]
        metadata = (self.get("layers") or {}).get(layer_id) or {}
        if layer_id == BASE_LAYER_ID:
            return {
                "layer": None,
                "layer_id": BASE_LAYER_ID,
                "blocked": bool(metadata.get("locked")),
                "member": True,
            }

        layer_name = layer_name_for_id(layer_id, context=self)
        return {
            "layer": layer_name,
            "layer_id": layer_id,
            "blocked": bool(metadata.get("locked")),
            "member": (
                layer_contains_plug(layer_name, plug)
                if resolve_membership
                else None
            ),
        }

    def group_by_destination(self, node, attributes):
        groups = {}
        blocked = []
        for attribute in attributes or []:
            destination = self.destination_for_plug(
                "{}.{}".format(node, attribute),
                resolve_membership=False,
            )
            if destination["blocked"]:
                blocked.append(attribute)
            else:
                groups.setdefault(destination["layer"], []).append(attribute)
        return groups, blocked

    def cut_keys(self, node, attributes, timerange):
        groups, blocked = self.group_by_destination(node, attributes)
        layered = bool(self.get("has_layers"))
        for layer_name, grouped_attributes in groups.items():
            if layered:
                for attribute in grouped_attributes:
                    curve = layer_graph.curve_for_plug(
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

    def set_keyframe(self, node, attributes, time=None):
        groups, blocked = self.group_by_destination(node, attributes)
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

    def ensure_destination(
        self,
        layer_id,
        metadata,
        plug,
        existing_layer_names=None,
    ):
        """Resolve or create a writable destination in this scene snapshot."""
        if layer_id in (None, BASE_LAYER_ID):
            return {
                "layer": None,
                "created": False,
                "blocked": False,
                "member": True,
            }

        metadata = dict(metadata or {})
        layer_name = metadata.get("name") or layer_id
        known_layers = existing_layer_names
        if known_layers is None:
            known_layers = {
                data.get("name") or known_id
                for known_id, data in (self.get("layers") or {}).items()
                if known_id != BASE_LAYER_ID
            }
        exists = layer_name in known_layers
        if exists and layer_metadata(layer_name).get("locked"):
            return {
                "layer": layer_name,
                "created": False,
                "blocked": True,
                "member": False,
            }
        if not exists:
            layer_name = create_layer(metadata)
            if not layer_name:
                return {
                    "layer": None,
                    "created": False,
                    "blocked": False,
                    "member": False,
                }
            known_layers.add(layer_name)

        member = not plug or layer_contains_plug(layer_name, plug)
        if plug and not member:
            member = add_plug_to_layer(layer_name, plug)
        return {
            "layer": layer_name,
            "created": not exists,
            "blocked": False,
            "member": bool(member),
        }

    def prepare_paste(self, plugs):
        """Restore this copied context's active layer into the current scene."""
        current = layer_cache.capture()
        if current.get("has_layers"):
            return current, {}
        source_id = self.active
        if source_id in (None, BASE_LAYER_ID):
            return current, {}
        metadata = dict((self.get("layers") or {}).get(source_id) or {})
        if not metadata or metadata.get("locked"):
            return current, {}

        plugs = list(dict.fromkeys(plugs or []))
        destination = current.ensure_destination(
            source_id,
            metadata,
            plugs[0] if plugs else None,
        )
        layer_name = destination["layer"]
        if not layer_name or destination["blocked"] or not destination["member"]:
            return current, {}
        for plug in plugs[1:]:
            if not layer_contains_plug(layer_name, plug):
                add_plug_to_layer(layer_name, plug)
        try:
            root_name = root_layer_name()
            if root_name:
                cmds.animLayer(root_name, edit=True, selected=False)
            cmds.animLayer(layer_name, edit=True, selected=True, preferred=True)
        except _COMMAND_ERRORS:
            pass
        created = {layer_name: metadata} if destination["created"] else {}
        return layer_cache.capture(), created

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
        node = maya_api.dependency_node_fn(self.layer)
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
            self.name = maya_api.mobject_name(self.layer)
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
        # first real call to layer_cache.capture().

    def reset(self):
        root_name = root_layer_name()
        names = scene_layer_names(include_root=True)
        graph_names = [
            maya_api.mobject_name(layer, absolute=False)
            for layer in scene_layer_objects()
        ]
        graph_names = [name for name in graph_names if name]
        if graph_names:
            names = list(dict.fromkeys(graph_names + names))
        self.scene_layers = [
            AnimationLayer(
                maya_api.mobject_from_node(name) or name,
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
        self.reset()
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
        return LayerContext({
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
        })

    def tool_context(self):
        """Build the editable layer scope from this cache's current snapshot."""
        context = self.capture()
        root_name = context.get("root_name")
        layer_data = context.get("layers") or {}
        selected_ids = list(context.get("selected") or [])
        selected_unlocked_ids = list(context.get("selected_unlocked") or [])
        explicit = bool(selected_ids)
        scope_ids = selected_unlocked_ids if explicit else [
            layer_id
            for layer_id, metadata in layer_data.items()
            if not metadata.get("locked")
        ]

        def layer_name(layer_id):
            if layer_id == BASE_LAYER_ID:
                return root_name
            return layer_name_for_id(layer_id, context=context)

        scope_names = [
            name for name in map(layer_name, scope_ids) if name
        ]
        selected_names = [
            name for name in map(layer_name, selected_ids) if name
        ]
        selected_unlocked_names = [
            name for name in map(layer_name, selected_unlocked_ids) if name
        ]
        active_id = context.get("active")
        active_name = (
            layer_name(active_id)
            if active_id
            else (scope_names[-1] if scope_names else None)
        )
        scene_layers = []
        for layer in self.scene_layers:
            layer_object = layer.layer
            if isinstance(layer_object, str):
                layer_object = maya_api.mobject_from_node(layer_object)
            if layer_object is not None:
                scene_layers.append(layer_object)

        return {
            "has_layers": bool(context.get("has_layers")),
            "root_name": root_name,
            "selected": selected_names,
            "selected_unlocked": selected_unlocked_names,
            "selection_explicit": explicit,
            "scope_layer_names": list(dict.fromkeys(scope_names)),
            "active_layer": active_name,
            "context": context,
            "scene_layers": scene_layers,
        }


def has_anim_layers():
    return bool(scene_layer_names(include_root=False))


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
    connects to a child through *some* plug of the child into the parent's
    ``childrenLayers`` array (the same link ``scene_layer_objects()`` already
    walks via OpenMaya) -- but not specifically the child's ``message`` plug
    (verified empty even for a layer with a real parent), so querying just
    that one attribute always came back with nothing and every layer looked
    like a top-level layer. Querying the whole node's connections (no
    attribute suffix) and filtering the destination side for
    ``childrenLayers`` finds it regardless of which plug actually carries it.
    """
    if not layer_name or cmds is None:
        return None
    try:
        destinations = cmds.listConnections(
            layer_name,
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


layer_cache = LayerCache()


def layer_metadata(layer_name):
    """Capture the state needed to faithfully recreate an animation layer."""
    cached = layer_cache.by_id(layer_id_for_name(layer_name))
    if cached is not None:
        return cached.as_dict()
    # Uncached (e.g. a layer just created this operation, before the next
    # layer_cache.reset()): build through the same AnimationLayer.refresh() path
    # the cache itself uses, instead of a second, cmds-heavy implementation.
    # That path already prefers OpenMaya over cmds.animLayer(query=True,
    # ...) wherever possible, which is what keeps this from re-triggering
    # "Unable to parse the argument list" on a freshly created layer.
    root_name = root_layer_name()
    is_root = bool(layer_name and layer_name == root_name)
    return AnimationLayer(layer_name, root=is_root).as_dict()


def weight_curves(layer_name):
    """Return animCurves driving one animation layer's weight plug."""
    if not layer_name or cmds is None:
        return []
    weight_plug = "{}.weight".format(layer_name)
    try:
        curves = cmds.listConnections(
            weight_plug,
            source=True,
            destination=False,
            type="animCurve",
            skipConversionNodes=True,
        ) or []
    except _COMMAND_ERRORS:
        curves = []
    if isinstance(curves, str):
        curves = [curves]
    return list(dict.fromkeys(curves))


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


def restore_created_layer_states(created_layers):
    for layer_name, metadata in (created_layers or {}).items():
        if not layer_name or not isinstance(metadata, dict) or cmds is None:
            continue
        for flag, key in (("mute", "muted"), ("lock", "locked")):
            try:
                cmds.animLayer(
                    layer_name,
                    edit=True,
                    **{flag: bool(metadata.get(key))}
                )
            except _COMMAND_ERRORS:
                pass
