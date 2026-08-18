"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Modified by: Alehaaaa / alehaaaa.github.io



"""

"""Animation Layers Manager -- scene layer tree, mutation, grouping, and smart merge.

Owns every Maya-side operation the Animation Layers window needs: reading the
live layer tree, creating/deleting/renaming/reordering/grouping layers, and
the "smart merge" bake. Presentation lives in ``widgets.py``; this module
never touches Qt.

Layer state itself (``AnimationLayer``, ``LayerCache``, curve ownership) is
owned by ``maya.animation.layers`` / ``maya.animation.graph`` -- this module
is the feature-specific orchestration on top of that shared domain layer, not
a second implementation of it.

Groups are plain animation layers used purely as parent containers -- Maya's
own nested-layer evaluation already blends a child layer's weight with its
parent's, so "a group with its own weight" falls directly out of that native
behavior. A group is distinguished from an ordinary layer only by a private
boolean attribute (``GROUP_ATTRIBUTE``) added to the layer node, used solely
to pick a folder icon in the UI -- it carries no evaluation meaning.
"""
import re

from maya import cmds  # type: ignore

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import maya_api
from TheKeyMachine.maya.animation import layers as anim_layers
from TheKeyMachine.maya.animation import graph as anim_graph
from TheKeyMachine.tools import clipboard
from TheKeyMachine.data.colors import COLORS


_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)

GROUP_ATTRIBUTE = "tkmAnimLayerGroup"
GROUP_COLOR_ATTRIBUTE = "tkmAnimLayerColor"
GROUP_LOCK_SNAPSHOT_ATTRIBUTE = "tkmAnimLayerLockSnapshot"
DEFAULT_GROUP_COLOR_SUFFIX = COLORS.selection.gray.light.suffix
CLIPBOARD_SLOT = "animation_layers"


# ---------------------------------------------------------------------------
# Layer tree
# ---------------------------------------------------------------------------


def root_layer_name():
    return anim_graph.root_layer_name()


def has_layers():
    return bool(animation.has_anim_layers())


def is_group(layer_name):
    if not layer_name or not cmds.objExists(layer_name):
        return False
    try:
        return bool(
            cmds.attributeQuery(GROUP_ATTRIBUTE, node=layer_name, exists=True)
            and cmds.getAttr("{}.{}".format(layer_name, GROUP_ATTRIBUTE))
        )
    except _COMMAND_ERRORS:
        return False


def _mark_as_group(layer_name):
    if not cmds.attributeQuery(GROUP_ATTRIBUTE, node=layer_name, exists=True):
        try:
            cmds.addAttr(layer_name, longName=GROUP_ATTRIBUTE, attributeType="bool", keyable=False, hidden=True)
        except _COMMAND_ERRORS:
            return
    try:
        cmds.setAttr("{}.{}".format(layer_name, GROUP_ATTRIBUTE), True)
    except _COMMAND_ERRORS:
        pass


def get_weight(layer_name):
    try:
        return float(cmds.getAttr("{}.weight".format(layer_name)))
    except _COMMAND_ERRORS:
        return 1.0


def get_group_color(layer_name):
    """Return the group's display color suffix (see ``data.colors.COLORS.selection``).

    Every group always has one -- an unset attribute (never colored, or
    freshly created) resolves to ``DEFAULT_GROUP_COLOR_SUFFIX`` (light gray)
    rather than ``None``, so a group's border/icon is always visible and
    "set a color" is really "change the color".
    """
    if not layer_name or not cmds.objExists(layer_name):
        return DEFAULT_GROUP_COLOR_SUFFIX
    try:
        if not cmds.attributeQuery(GROUP_COLOR_ATTRIBUTE, node=layer_name, exists=True):
            return DEFAULT_GROUP_COLOR_SUFFIX
        value = cmds.getAttr("{}.{}".format(layer_name, GROUP_COLOR_ATTRIBUTE))
    except _COMMAND_ERRORS:
        return DEFAULT_GROUP_COLOR_SUFFIX
    return value or DEFAULT_GROUP_COLOR_SUFFIX


def set_group_color(layer_name, suffix):
    """Assign (``suffix`` truthy) or clear (``suffix`` falsy) a group's display color.

    Storage-only, same pattern as ``GROUP_ATTRIBUTE``: a private string
    attribute on the layer node, read back by the UI to tint the group's
    icon/border. Carries no evaluation meaning to Maya.
    """
    if not layer_name or not cmds.objExists(layer_name):
        return
    if not cmds.attributeQuery(GROUP_COLOR_ATTRIBUTE, node=layer_name, exists=True):
        try:
            cmds.addAttr(layer_name, longName=GROUP_COLOR_ATTRIBUTE, dataType="string", keyable=False, hidden=True)
        except _COMMAND_ERRORS:
            return
    try:
        cmds.setAttr("{}.{}".format(layer_name, GROUP_COLOR_ATTRIBUTE), suffix or "", type="string")
    except _COMMAND_ERRORS:
        pass


def _layer_node(name, is_root):
    layer = animation.AnimationLayer(name, root=is_root)
    node_is_group = (not is_root) and is_group(name)
    return {
        "name": name,
        "is_root": is_root,
        "is_group": node_is_group,
        "color": get_group_color(name) if node_is_group else None,
        "mute": layer.muted,
        "lock": layer.locked,
        "override": layer.override,
        "passthrough": layer.passthrough,
        "selected": layer.selected,
        "preferred": layer.preferred,
        "weight": 1.0 if is_root else get_weight(name),
        # AnimationLayer.parent already avoids the buggy
        # cmds.animLayer(query=True, parent=True) flag (see
        # maya.animation.layers._layer_parent) -- reuse it rather than
        # re-querying parent a second, riskier way.
        "parent": None if is_root else layer.parent,
        "children": [],
    }


def _ordered_layer_names():
    """Layer names in Maya's real stacking/evaluation order, root first.

    ``animation.scene_layer_names()`` comes from ``cmds.ls(type="animLayer")``,
    which is node-creation order and never changes when a layer is moved
    with ``moveLayerAfter``/``moveLayerBefore`` -- using it here made the
    window's list silently ignore every drag-reorder even though the scene
    itself reordered correctly. ``scene_layer_objects()`` instead walks each
    layer's ``childrenLayers`` connections (the same array those commands
    edit), so it's already a depth-first walk in true sibling order; filtered
    down to one parent's direct children -- which is exactly what
    ``layer_tree()`` below does -- that relative order survives intact.
    """
    try:
        objects = anim_graph.scene_layer_objects()
    except _COMMAND_ERRORS:
        objects = []

    names = []
    seen = set()
    for obj in objects:
        try:
            # absolute=False -> MFnDependencyNode.name(), not .absoluteName():
            # the latter always root-namespace-qualifies with a leading ":"
            # (":BaseAnimation", ":Layer1", ...), which both leaked into the
            # UI as a stray ":" prefix and broke the `name == root_name`
            # check below (root_layer_name() returns the plain cmds name),
            # making BaseAnimation register as a non-root layer and show up
            # inline with everything else instead of being excluded/placed
            # at the bottom.
            name = maya_api.mobject_name(obj, absolute=False)
        except _COMMAND_ERRORS:
            name = None
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    if names:
        return names
    # Fallback so a transient graph-walk failure still shows something.
    return animation.scene_layer_names(include_root=True)


def layer_tree():
    """Return the full scene layer hierarchy as a nested dict, or ``None``."""
    root_name = root_layer_name()
    if not root_name:
        return None

    ordered = _ordered_layer_names()
    if root_name not in ordered:
        ordered.insert(0, root_name)

    nodes = {name: _layer_node(name, name == root_name) for name in ordered}
    root_node = nodes[root_name]
    for name in ordered:
        node = nodes[name]
        if node["is_root"]:
            continue
        parent_name = node["parent"] or root_name
        parent_node = nodes.get(parent_name, root_node)
        parent_node["children"].append(node)
    return root_node


def flatten_tree(node, depth=0, out=None, inherited_color=None):
    """Depth-first (name, depth) pairs for every layer, in stack order --
    with the root/BaseAnimation layer appended dead last.

    Maya's own Animation Layer Editor always shows BaseAnimation as the
    bottom-most row (the foundation every other layer stacks on top of), not
    interleaved by however the graph walk happened to visit it, so it's
    appended here only once every real descendant has already been added.

    Also annotates each node with the color it should display: ``_border_color``
    is the nearest color-owning ancestor's suffix (or the node's own, if it set
    one), and ``_is_color_owner`` marks the node that actually owns that color
    (thick border) versus one merely inheriting it (thin border). The root
    itself never carries a color.
    """
    if out is None:
        out = []
    if node is None:
        return out
    is_root = bool(node.get("is_root"))
    own_color = node.get("color")
    effective_color = own_color or inherited_color
    next_depth = depth if is_root else depth + 1
    if not is_root:
        out.append(node)
        node["_depth"] = depth
        node["_border_color"] = effective_color
        node["_is_color_owner"] = bool(own_color)
    for child in node.get("children") or ():
        flatten_tree(child, next_depth, out, effective_color)
    if is_root:
        node["_depth"] = 0
        node["_border_color"] = None
        node["_is_color_owner"] = False
        out.append(node)
    return out


def find_node(tree, layer_name):
    if tree is None:
        return None
    if tree.get("name") == layer_name:
        return tree
    for child in tree.get("children") or ():
        found = find_node(child, layer_name)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def _sanitize_layer_name(name):
    name = re.sub(r"[^0-9A-Za-z_]+", "_", str(name or "").strip())
    name = name.strip("_")
    if name and name[0].isdigit():
        name = "_" + name
    return name


def _unique_layer_name(base):
    base = _sanitize_layer_name(base) or "AnimLayer"
    if not cmds.objExists(base):
        return base
    index = 1
    while cmds.objExists("{}{}".format(base, index)):
        index += 1
    return "{}{}".format(base, index)


def rename_layer(layer_name, new_name):
    clean = _sanitize_layer_name(new_name)
    if not clean or clean == layer_name:
        return layer_name
    if cmds.objExists(clean):
        clean = _unique_layer_name(clean)
    try:
        return cmds.rename(layer_name, clean)
    except _COMMAND_ERRORS:
        return layer_name


# ---------------------------------------------------------------------------
# Create / delete / group
# ---------------------------------------------------------------------------


def create_layer_from_selection(name=None, additive=True, objects=None, parent=None):
    objs = objects if objects is not None else (cmds.ls(selection=True, long=True) or [])
    if not objs:
        raise RuntimeError("Select one or more objects to create an animation layer from.")

    metadata = {
        "name": _unique_layer_name(name or "AnimLayer"),
        "override": not additive,
        "passthrough": True,
    }
    if parent and cmds.objExists(parent):
        metadata["parent"] = parent

    created = anim_layers.create_layer(metadata)
    if not created:
        raise RuntimeError("Could not create the animation layer.")

    previous_selection = cmds.ls(selection=True, long=True) or []
    try:
        cmds.select(objs, replace=True)
        cmds.animLayer(created, edit=True, addSelectedObjects=True)
    finally:
        if previous_selection:
            cmds.select(previous_selection, replace=True)
    return created


def create_empty_layer(name=None, additive=True, parent=None):
    metadata = {
        "name": _unique_layer_name(name or "AnimLayer"),
        "override": not additive,
        "passthrough": True,
    }
    if parent and cmds.objExists(parent):
        metadata["parent"] = parent
    created = anim_layers.create_layer(metadata)
    if not created:
        raise RuntimeError("Could not create the animation layer.")
    return created


def create_group(name=None, member_names=None, parent=None):
    metadata = {
        "name": _unique_layer_name(name or "Group"),
        "override": False,
        "passthrough": True,
    }
    if parent and cmds.objExists(parent):
        metadata["parent"] = parent
    created = anim_layers.create_layer(metadata)
    if not created:
        raise RuntimeError("Could not create the animation layer group.")
    _mark_as_group(created)
    for member in member_names or ():
        move_layer_to_parent(member, created)
    return created


def move_layer_to_parent(layer_name, parent_name=None):
    target_parent = parent_name or root_layer_name()
    if not target_parent or layer_name == target_parent:
        return False
    try:
        cmds.animLayer(layer_name, edit=True, parent=target_parent)
        return True
    except _COMMAND_ERRORS:
        return False


def delete_layer(layer_name, recursive=False):
    """Delete one layer. Children are reparented to the deleted layer's own
    parent unless *recursive* is set, in which case the whole subtree goes.

    The root/BaseAnimation layer is never deleted directly here -- Maya
    doesn't allow it while any real layer still exists, and once the last
    real layer is gone BaseAnimation disappears on its own (it only exists
    as a side effect of having at least one animLayer), so "delete
    BaseAnimation along with everything else" already falls out of deleting
    every real layer without needing a special case for it.
    """
    if not layer_name or layer_name == root_layer_name():
        return False
    if not cmds.objExists(layer_name):
        return False
    if recursive:
        for child in list(cmds.animLayer(layer_name, query=True, children=True) or []):
            delete_layer(child, recursive=True)
    else:
        parent = animation.AnimationLayer(layer_name).parent or root_layer_name()
        for child in list(cmds.animLayer(layer_name, query=True, children=True) or []):
            move_layer_to_parent(child, parent)
    try:
        cmds.delete(layer_name)
        return True
    except _COMMAND_ERRORS:
        return False


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


def reorder_layer(layer_name, reference_name, before=False):
    """Move *layer_name* to sit directly before/after *reference_name* among
    its siblings, using animLayer's own evaluation-order flags."""
    if not layer_name or not reference_name or layer_name == reference_name:
        return False
    try:
        if before:
            cmds.animLayer(layer_name, edit=True, moveLayerBefore=reference_name)
        else:
            cmds.animLayer(layer_name, edit=True, moveLayerAfter=reference_name)
        return True
    except _COMMAND_ERRORS:
        return False


# ---------------------------------------------------------------------------
# Per-layer state
# ---------------------------------------------------------------------------


def set_mute(layer_name, muted):
    # Direct attribute set, same as set_weight() below -- animLayer's own
    # -mute edit flag is a thin wrapper around this same .mute attribute,
    # so going straight to setAttr is just as correct and one command
    # cheaper, with no edit-flag indirection to go wrong.
    try:
        cmds.setAttr("{}.mute".format(layer_name), bool(muted))
        return True
    except _COMMAND_ERRORS:
        return False


def _descendant_layer_names(layer_name):
    """Every layer nested under *layer_name* at any depth, via the reliable
    ``animLayer -query -children`` flag (unlike ``-query -parent``, this one
    isn't affected by the "Unable to parse the argument list" bug -- see
    ``_layer_parent`` in ``maya.animation.layers`` for that one)."""
    result = []
    try:
        direct = cmds.animLayer(layer_name, query=True, children=True) or []
    except _COMMAND_ERRORS:
        direct = []
    for child in direct:
        result.append(child)
        result.extend(_descendant_layer_names(child))
    return result


def _get_lock_snapshot(layer_name):
    try:
        if not cmds.attributeQuery(GROUP_LOCK_SNAPSHOT_ATTRIBUTE, node=layer_name, exists=True):
            return []
        value = cmds.getAttr("{}.{}".format(layer_name, GROUP_LOCK_SNAPSHOT_ATTRIBUTE)) or ""
    except _COMMAND_ERRORS:
        return []
    return [name for name in value.split(",") if name]


def _set_lock_snapshot(layer_name, names):
    if not cmds.attributeQuery(GROUP_LOCK_SNAPSHOT_ATTRIBUTE, node=layer_name, exists=True):
        try:
            cmds.addAttr(layer_name, longName=GROUP_LOCK_SNAPSHOT_ATTRIBUTE, dataType="string", keyable=False, hidden=True)
        except _COMMAND_ERRORS:
            return
    try:
        cmds.setAttr("{}.{}".format(layer_name, GROUP_LOCK_SNAPSHOT_ATTRIBUTE), ",".join(names or []), type="string")
    except _COMMAND_ERRORS:
        pass


def _has_locked_ancestor_group(layer_name):
    """True if any group *layer_name* is nested under (at any depth) is
    itself locked -- a locked group is the thing that has to be unlocked to
    release its children, so an individual child (or a nested group) can't
    unlock itself out from under it."""
    root_name = root_layer_name()
    current = get_parent(layer_name)
    seen = set()
    while current and current != root_name and current not in seen:
        seen.add(current)
        if is_group(current):
            try:
                if cmds.getAttr("{}.lock".format(current)):
                    return True
            except _COMMAND_ERRORS:
                pass
        current = get_parent(current)
    return False


def set_lock(layer_name, locked):
    """Lock/unlock one layer -- cascading to every layer nested under it
    when *layer_name* is a group.

    Locking a group locks all its children along with it. Unlocking it
    restores each child to whatever it was individually locked to *before*
    the group lock was applied (recorded on the group node itself), instead
    of blindly unlocking everything -- a child that was deliberately locked
    on its own stays locked after its group is unlocked.

    Unlocking a single layer (or a nested group) is refused outright while
    any ancestor group is still locked -- that ancestor is what has to be
    unlocked first to release it.
    """
    locked = bool(locked)
    if not locked and _has_locked_ancestor_group(layer_name):
        return False
    if is_group(layer_name):
        descendants = _descendant_layer_names(layer_name)
        if locked:
            previously_locked = []
            for name in descendants:
                try:
                    if cmds.getAttr("{}.lock".format(name)):
                        previously_locked.append(name)
                except _COMMAND_ERRORS:
                    continue
            _set_lock_snapshot(layer_name, previously_locked)
            for name in descendants:
                try:
                    cmds.setAttr("{}.lock".format(name), True)
                except _COMMAND_ERRORS:
                    continue
        else:
            previously_locked = set(_get_lock_snapshot(layer_name))
            for name in descendants:
                try:
                    cmds.setAttr("{}.lock".format(name), name in previously_locked)
                except _COMMAND_ERRORS:
                    continue
            _set_lock_snapshot(layer_name, [])
    try:
        cmds.setAttr("{}.lock".format(layer_name), locked)
        return True
    except _COMMAND_ERRORS:
        return False


def set_override(layer_name, override):
    try:
        cmds.setAttr("{}.override".format(layer_name), bool(override))
        return True
    except _COMMAND_ERRORS:
        return False


def set_weight(layer_name, weight):
    try:
        cmds.setAttr("{}.weight".format(layer_name), max(0.0, min(1.0, float(weight))))
        return True
    except _COMMAND_ERRORS:
        return False


def selected_layer_names():
    """Layers currently selected in Maya's own animLayer selection state --
    the same state ``select_layer()`` writes to -- for toolbar quick actions
    (Smart Merge/Export shortcuts, right-click menu) that act without the
    Animation Layers window open, so they read from the live scene selection
    the same way ``maya.animation.layer_cache`` already backs every other
    layer-scope-aware tool (see ``copy_paste``/``animation_tools``)."""
    try:
        context = animation.layer_cache.tool_context()
    except _COMMAND_ERRORS:
        return []
    return list(context.get("selected") or [])


def get_parent(layer_name):
    if not layer_name or not cmds.objExists(layer_name):
        return None
    return animation.AnimationLayer(layer_name).parent or root_layer_name()


# Remembers the layer node this module last auto-selected for the Channel
# Box, so a later click on a *different* row can tell "the user has since
# selected something of their own" apart from "the only thing selected is
# the layer node our own previous click put there" -- otherwise the very
# first auto-select would leave a selection behind that permanently looks
# like a "prior object selection" and silently disables the behavior for
# every click after the first.
_last_auto_selected = {"name": None}


def select_layer(layer_name, weight_attribute=True):
    """Mark *layer_name* selected/preferred (native keying-target semantics)
    and, only when nothing *else* is already selected, also select the layer
    node itself so its Weight attribute shows in the Channel Box."""
    try:
        root_name = root_layer_name()
        for name in animation.scene_layer_names(include_root=False):
            cmds.animLayer(name, edit=True, selected=(name == layer_name))
        if root_name:
            cmds.animLayer(root_name, edit=True, selected=(root_name == layer_name))
        cmds.animLayer(layer_name, edit=True, preferred=True)
    except _COMMAND_ERRORS:
        pass

    if not weight_attribute:
        return

    current = cmds.ls(selection=True) or []
    eligible = not current or (len(current) == 1 and current[0] == _last_auto_selected.get("name"))
    if not eligible:
        _last_auto_selected["name"] = None
        return
    try:
        cmds.select(layer_name, replace=True)
        _last_auto_selected["name"] = layer_name
    except _COMMAND_ERRORS:
        pass


def add_selected_to_layer(layer_name):
    objs = cmds.ls(selection=True, long=True) or []
    if not objs:
        raise RuntimeError("Select one or more objects first.")
    cmds.animLayer(layer_name, edit=True, addSelectedObjects=True)


def remove_selected_from_layer(layer_name):
    objs = cmds.ls(selection=True, long=True) or []
    if not objs:
        raise RuntimeError("Select one or more objects first.")
    cmds.animLayer(layer_name, edit=True, removeSelectedObjects=True)


def select_layer_objects(layer_name):
    members = cmds.animLayer(layer_name, query=True, attribute=True) or []
    objects = sorted({plug.split(".")[0] for plug in members})
    if not objects:
        raise RuntimeError("This layer has no members.")
    cmds.select(objects, replace=True)
    return objects


# ---------------------------------------------------------------------------
# Smart Merge
# ---------------------------------------------------------------------------


def _weight_curve_for(layer_name):
    curves = animation.weight_curves(layer_name)
    return curves[0] if curves else None


def _layer_weight_at(layer_name, frame):
    try:
        if cmds.getAttr("{}.mute".format(layer_name)):
            return 0.0
        return float(cmds.getAttr("{}.weight".format(layer_name), time=frame))
    except _COMMAND_ERRORS:
        return 0.0


def _any_layer_active_at(layer_names, frame):
    return any(_layer_weight_at(name, frame) for name in layer_names)


def _active_ranges(layer_names, pad=1.0):
    """Frame ranges (inclusive) where at least one of *layer_names* has a
    non-zero, unmuted weight -- the only place merging them can change
    anything. This is the core of "smart" merge: a layer that only does
    something for a handful of frames in a long shot gets baked over a
    handful of frames, not the whole timeline.
    """
    scene_start = cmds.playbackOptions(query=True, min=True)
    scene_end = cmds.playbackOptions(query=True, max=True)

    breakpoints = {scene_start, scene_end}
    static_active = []
    any_curve = False
    for layer_name in layer_names:
        try:
            muted = bool(cmds.getAttr("{}.mute".format(layer_name)))
        except _COMMAND_ERRORS:
            muted = False
        if muted:
            continue
        curve = _weight_curve_for(layer_name)
        if curve:
            any_curve = True
            try:
                times = cmds.keyframe(curve, query=True, timeChange=True) or []
            except _COMMAND_ERRORS:
                times = []
            breakpoints.update(times)
        else:
            if get_weight(layer_name):
                static_active.append(layer_name)

    if not any_curve:
        # Every merging layer has a flat (unanimated) weight -- either all of
        # them are muted/zero (nothing to bake) or at least one is a constant
        # nonzero weight for the whole range (bake the whole range once).
        if not static_active:
            return []
        return [(scene_start, scene_end)]

    ordered = sorted(breakpoints)
    active_segments = []
    for start, end in zip(ordered[:-1], ordered[1:]):
        if end <= start:
            continue
        midpoint = (start + end) / 2.0
        if _any_layer_active_at(layer_names, midpoint) or _any_layer_active_at(layer_names, start):
            active_segments.append([start, end])

    if not active_segments:
        return []

    merged = [list(active_segments[0])]
    for start, end in active_segments[1:]:
        if start <= merged[-1][1] + pad:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return [
        (max(scene_start, start - pad), min(scene_end, end + pad))
        for start, end in merged
    ]


def _key_group_weight_envelope(layer_name, ranges, transition=1.0):
    """Animate the merged layer's own weight so it only overrides its
    active window(s), instead of holding its last baked value forever via
    the default constant extrapolation outside its keyed range."""
    scene_start = cmds.playbackOptions(query=True, min=True)
    scene_end = cmds.playbackOptions(query=True, max=True)
    weight_plug = "{}.weight".format(layer_name)

    if len(ranges) == 1 and ranges[0][0] <= scene_start and ranges[0][1] >= scene_end:
        cmds.setAttr(weight_plug, 1.0)
        return

    for start, end in ranges:
        cmds.setKeyframe(weight_plug, time=(start,), value=1.0, itt="linear", ott="linear")
        cmds.setKeyframe(weight_plug, time=(end,), value=1.0, itt="linear", ott="linear")
        before = start - transition
        after = end + transition
        if before < start:
            cmds.setKeyframe(weight_plug, time=(before,), value=0.0, itt="linear", ott="linear")
        if after > end:
            cmds.setKeyframe(weight_plug, time=(after,), value=0.0, itt="linear", ott="linear")
    try:
        cmds.setInfinity(weight_plug, preInfinite="constant", postInfinite="constant")
    except _COMMAND_ERRORS:
        pass


def smart_merge_layers(layer_names, operation=None):
    """Bake the combined contribution of *layer_names* into one new override
    layer and delete the sources.

    Efficiency first: only the frame ranges where the merging layers can
    actually change the result get sampled (see ``_active_ranges``) instead
    of the full playback range, and only layers stacked *above* the merge
    set are muted during the capture pass -- layers below keep contributing
    normally, since their contribution belongs in the captured value, and
    layers above are restored afterwards to keep applying on top of the new
    layer exactly as they did on top of the old ones. See
    ``_key_group_weight_envelope`` for how the destination avoids affecting
    anything outside its own active window(s).

    Selecting literally every real layer merges down into BaseAnimation
    itself instead of creating a new "Merged" layer -- matching Maya's own
    native Merge Layers behavior when the whole stack is selected -- unless
    BaseAnimation is locked, in which case there's nothing to bake into and
    this refuses outright rather than silently falling back to a new layer.
    """
    layer_names = [name for name in dict.fromkeys(layer_names or []) if name and cmds.objExists(name)]
    if len(layer_names) < 2:
        raise RuntimeError("Select two or more animation layers to merge.")
    locked_names = [name for name in layer_names if cmds.getAttr("{}.lock".format(name))]
    if locked_names:
        raise RuntimeError("{} is locked -- unlock it before merging.".format(locked_names[0]))

    root_name = root_layer_name()
    all_real_layers = [name for name in _ordered_layer_names() if name != root_name]
    merge_into_base = bool(root_name) and set(layer_names) == set(all_real_layers)
    if merge_into_base:
        try:
            base_locked = bool(cmds.getAttr("{}.lock".format(root_name)))
        except _COMMAND_ERRORS:
            base_locked = False
        if base_locked:
            raise RuntimeError("{} is locked -- unlock it before merging every layer into it.".format(root_name))

    members = set()
    for name in layer_names:
        try:
            members.update(cmds.animLayer(name, query=True, attribute=True) or [])
        except _COMMAND_ERRORS:
            pass

    if not members:
        for name in layer_names:
            delete_layer(name, recursive=False)
        return None

    ranges = _active_ranges(layer_names)
    if not ranges:
        for name in layer_names:
            delete_layer(name, recursive=False)
        return None

    ordered = [name for name in _ordered_layer_names() if name != root_layer_name()]
    merge_indices = [ordered.index(name) for name in layer_names if name in ordered]
    top_index = max(merge_indices) if merge_indices else -1
    others_above = [
        name for name in ordered
        if name not in layer_names and ordered.index(name) > top_index
    ]

    muted_state = {}
    for name in others_above:
        try:
            muted_state[name] = bool(cmds.getAttr("{}.mute".format(name)))
        except _COMMAND_ERRORS:
            continue
        if not muted_state[name]:
            try:
                cmds.setAttr("{}.mute".format(name), True)
            except _COMMAND_ERRORS:
                pass

    destination = None
    try:
        if merge_into_base:
            destination = root_name
        else:
            lowest_parent = animation.AnimationLayer(layer_names[0]).parent or root_layer_name()
            destination = anim_layers.create_layer({
                "name": _unique_layer_name("Merged"),
                "override": True,
                "passthrough": True,
                "parent": lowest_parent,
            })
            if not destination:
                raise RuntimeError("Could not create the merged layer.")

        member_objects = sorted({plug.split(".")[0] for plug in members})
        previous_selection = cmds.ls(selection=True, long=True) or []
        try:
            cmds.select(member_objects, replace=True)
            cmds.animLayer(destination, edit=True, addSelectedObjects=True)
        finally:
            if previous_selection:
                cmds.select(previous_selection, replace=True)

        if operation is not None:
            operation.set_total(len(ranges), reset=True)

        cmds.bakeResults(
            list(members),
            time=[tuple(r) for r in ranges],
            simulation=True,
            sampleBy=1,
            disableImplicitControl=True,
            preserveOutsideKeys=True,
            # True = Maya's actual "Smart Bake": keys are only inserted where
            # the value genuinely changes, instead of stamping one on every
            # single sampled frame across the active range(s).
            sparseAnimCurveBake=True,
            minimizeRotation=True,
            destinationLayer=destination,
        )

        if operation is not None:
            operation.step(len(ranges))

        if not merge_into_base:
            # BaseAnimation isn't a blended override -- it has no weight
            # envelope to key, it's just always fully active.
            _key_group_weight_envelope(destination, ranges)
    finally:
        for name, was_muted in muted_state.items():
            if not was_muted:
                try:
                    cmds.setAttr("{}.mute".format(name), False)
                except _COMMAND_ERRORS:
                    pass

    for name in layer_names:
        delete_layer(name, recursive=False)

    return destination


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------


def _curve_keyframe_data(layer_name, plug):
    """Return this *layer's own* keyframe data for *plug* -- not whatever
    curve happens to be nearest.

    With more than one animation layer touching an attribute, the object's
    plug is fed by a blend node (``animBlendNodeAdditive``/...), not by any
    single layer's curve directly -- a plain ``listConnections(plug,
    type="animCurve")`` from the object's own attribute stops at that blend
    node and finds nothing, silently dropping every layer's animation except
    in the degenerate single-curve case. ``animLayer -findCurveForPlug`` is
    the documented, layer-aware way to resolve *this* layer's curve for the
    plug regardless of how many other layers also touch it.
    """
    curve = None
    try:
        found = cmds.animLayer(layer_name, query=True, findCurveForPlug=plug) or []
        curve = found[0] if found else None
    except _COMMAND_ERRORS:
        curve = None
    if not curve:
        # Fallback for the rare case the plug is fed directly with no blend
        # node in between at all (e.g. only one layer ever touched it).
        connections = cmds.listConnections(plug, source=True, destination=False, type="animCurve", skipConversionNodes=True) or []
        curve = connections[0] if connections else None
    if not curve:
        return None
    times = cmds.keyframe(curve, query=True, timeChange=True) or []
    values = cmds.keyframe(curve, query=True, valueChange=True) or []
    in_types = cmds.keyTangent(curve, query=True, inTangentType=True) or []
    out_types = cmds.keyTangent(curve, query=True, outTangentType=True) or []
    keys = []
    for index, time in enumerate(times):
        keys.append({
            "time": time,
            "value": values[index] if index < len(values) else 0.0,
            "itt": in_types[index] if index < len(in_types) else "auto",
            "ott": out_types[index] if index < len(out_types) else "auto",
        })
    return keys


def _serialize_layer(node):
    data = {
        "name": node["name"],
        "is_group": node["is_group"],
        "override": node["override"],
        "passthrough": node["passthrough"],
        "mute": node["mute"],
        "lock": node["lock"],
        "weight": node["weight"],
        "members": {},
    }
    if not node["is_group"]:
        for plug in cmds.animLayer(node["name"], query=True, attribute=True) or []:
            keys = _curve_keyframe_data(node["name"], plug)
            if keys:
                data["members"][plug] = {"keys": keys}
                continue
            # A member can be a plain static override (added to the layer,
            # value changed, never keyed) -- no curve exists at all, but the
            # value itself is still real per-layer data that would otherwise
            # be silently dropped on export.
            try:
                data["members"][plug] = {"value": cmds.getAttr(plug)}
            except _COMMAND_ERRORS:
                continue
    data["children"] = [_serialize_layer(child) for child in node.get("children") or ()]
    return data


def export_layers_data(layer_names):
    """Serialize the given layers (and any nested children) for the clipboard."""
    tree = layer_tree()
    if tree is None:
        return None
    exported = []
    for name in layer_names or ():
        node = find_node(tree, name)
        if node is not None:
            exported.append(_serialize_layer(node))
    if not exported:
        return None
    return {"layers": exported}


def _import_layer(entry, parent=None):
    metadata = {
        "name": _unique_layer_name(entry.get("name") or "AnimLayer"),
        "override": bool(entry.get("override")),
        "passthrough": bool(entry.get("passthrough", True)),
    }
    if parent:
        metadata["parent"] = parent
    created = anim_layers.create_layer(metadata)
    if not created:
        return None
    if entry.get("is_group"):
        _mark_as_group(created)
    for plug, member in (entry.get("members") or {}).items():
        node_name = plug.split(".")[0]
        if not cmds.objExists(node_name):
            continue
        try:
            cmds.select(node_name, replace=True)
            cmds.animLayer(created, edit=True, addSelectedObjects=True)
        except _COMMAND_ERRORS:
            continue
        # Back-compat: earlier-exported files store a bare list of keys
        # instead of the current {"keys": [...]} / {"value": ...} shape.
        keys = member.get("keys") if isinstance(member, dict) else member
        if keys:
            for key in keys:
                try:
                    cmds.setKeyframe(plug, time=(key["time"],), value=key["value"], animLayer=created)
                    cmds.keyTangent(plug, time=(key["time"], key["time"]), inTangentType=key.get("itt", "auto"), outTangentType=key.get("ott", "auto"))
                except _COMMAND_ERRORS:
                    continue
        elif isinstance(member, dict) and "value" in member:
            # A static override with no keys -- write it directly into this
            # layer by making it the preferred (edit-target) layer first,
            # same targeting ``select_layer()`` uses for keying.
            try:
                cmds.animLayer(created, edit=True, preferred=True)
                cmds.setAttr(plug, member["value"])
            except _COMMAND_ERRORS:
                continue
    set_mute(created, bool(entry.get("mute")))
    set_lock(created, bool(entry.get("lock")))
    try:
        set_weight(created, float(entry.get("weight", 1.0)))
    except (TypeError, ValueError):
        pass
    for child in entry.get("children") or ():
        _import_layer(child, parent=created)
    return created


def import_layers_data(data):
    if not isinstance(data, dict):
        return []
    created = []
    for entry in data.get("layers") or ():
        result = _import_layer(entry, parent=None)
        if result:
            created.append(result)
    return created


def export_selected(layer_names, file_path=None, operation=None):
    data = export_layers_data(layer_names)
    if not data:
        raise RuntimeError("Select one or more animation layers to export.")
    if operation is not None:
        operation.set_status("Exporting Animation Layers")
    if file_path:
        clipboard.save(CLIPBOARD_SLOT, data)
        return clipboard.export_to(CLIPBOARD_SLOT, file_path, operation=operation)
    return clipboard.export_dialog(CLIPBOARD_SLOT, "Export Animation Layers", operation=operation)


def import_from_file(file_path=None, operation=None):
    if operation is not None:
        operation.set_status("Importing Animation Layers")
    if file_path:
        data = clipboard.import_from(CLIPBOARD_SLOT, file_path, operation=operation)
    else:
        data = clipboard.import_dialog(CLIPBOARD_SLOT, "Import Animation Layers", operation=operation)
    if not data:
        return []
    return import_layers_data(data)
