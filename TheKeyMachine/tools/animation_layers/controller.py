"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

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
EXPORT_TYPE = "animation_layers"
EXPORT_SCHEMA_VERSION = 1


def _plug(layer_name, attribute):
    """Shorthand for the ``layer.attribute`` plug strings used throughout
    this module (weight/mute/lock/override)."""
    return "{}.{}".format(layer_name, attribute)


def _tool_debug_flag():
    # Same .env parser as tools.common._debug_timing_enabled(); read once at
    # import (reorder_layer() runs on every drag) -- reload after changing the flag.
    try:
        from TheKeyMachine.core import debug as _debug

        return _debug.is_enabled()
    except Exception:
        return False


_TOOL_DEBUG = _tool_debug_flag()

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


def _is_root(layer_name):
    return bool(layer_name) and layer_name == root_layer_name()


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


def mark_as_group(layer_name):
    """Public entry point for other tools (e.g. ``copy_paste``, when a
    copied layer being pasted turns out to be a group) that need to mark an
    existing/freshly created layer as a group without reaching into the
    private ``_mark_as_group`` helper below."""
    _mark_as_group(layer_name)


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
        return float(cmds.getAttr(_plug(layer_name, "weight")))
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
    """Layer names in real stacking order, root first. ``scene_layer_names()``
    is node-creation order and ignores moveLayerBefore/After (so drag-reorders
    wouldn't show); ``scene_layer_objects()`` walks ``childrenLayers``
    connections instead, which is already depth-first sibling order."""
    try:
        objects = anim_graph.scene_layer_objects()
    except _COMMAND_ERRORS:
        objects = []

    names = []
    seen = set()
    for obj in objects:
        try:
            # absolute=False avoids a leading ":" namespace prefix
            # (.absoluteName() adds one), which otherwise broke the
            # name == root_name check below.
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
    """Create a new animation layer, adding whichever objects are selected
    (or passed via *objects*) as members. An empty selection just creates an
    empty layer, same as create_empty_layer()."""
    objs = objects if objects is not None else (cmds.ls(selection=True, long=True) or [])

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

    if objs:
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
    except _COMMAND_ERRORS as exc:
        cmds.warning("Animation Layers: couldn't reparent '{}' to '{}': {}".format(layer_name, target_parent, exc))
        return False


def delete_layer(layer_name, recursive=False):
    """Delete one layer. Children are reparented to the deleted layer's own
    parent unless *recursive* is set, in which case the whole subtree goes.

    BaseAnimation can only be deleted once it's the last layer left in the
    scene -- Maya refuses while any real layer still exists. Deleting a
    batch that mixes BaseAnimation with real layers should go through
    ``delete_layers()`` instead, which deletes the real layers first.
    """
    if not layer_name or not cmds.objExists(layer_name):
        return False
    if _is_root(layer_name):
        if animation.has_anim_layers():
            return False
        try:
            cmds.delete(layer_name)
            return True
        except _COMMAND_ERRORS:
            return False
    try:
        children = list(cmds.animLayer(layer_name, query=True, children=True) or [])
    except _COMMAND_ERRORS:
        children = []
    if recursive:
        for child in children:
            delete_layer(child, recursive=True)
    else:
        parent = animation.AnimationLayer(layer_name).parent or root_layer_name()
        for child in children:
            move_layer_to_parent(child, parent)
    try:
        cmds.delete(layer_name)
        return True
    except _COMMAND_ERRORS:
        return False


def delete_layers(layer_names, recursive=False):
    """Delete every layer in *layer_names*, deferring BaseAnimation (if
    included) to the very end -- it only actually deletes once every other
    real layer is gone (see ``delete_layer()``), so attempting it first
    would always silently no-op even when the whole scene is being cleared.
    """
    names = [name for name in dict.fromkeys(layer_names or []) if name]
    root_name = root_layer_name()
    ordered = sorted(names, key=lambda name: name == root_name)
    return [name for name in ordered if delete_layer(name, recursive=recursive)]


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


def reorder_layer(layer_name, reference_name, before=False):
    """Move *layer_name* to sit directly before/after *reference_name* among
    its siblings, using animLayer's own evaluation-order flags."""
    if not layer_name or not reference_name or layer_name == reference_name:
        return False
    # animLayer's -moveLayerBefore/-moveLayerAfter flags are named for
    # evaluation order, not UI list position -- "before" in the evaluation
    # stack means *lower* priority (evaluated earlier), which is the
    # opposite of "before" in the row's visual before/after among siblings
    # that this function's own *before* argument means. Swapped here so the
    # two stay in sync with reorder_layer()'s own before/after contract.
    if _TOOL_DEBUG:
        flag = "moveLayerAfter" if before else "moveLayerBefore"
        print('animLayer -edit -{} "{}" "{}";'.format(flag, reference_name, layer_name))
    try:
        if before:
            cmds.animLayer(layer_name, edit=True, moveLayerAfter=reference_name)
        else:
            cmds.animLayer(layer_name, edit=True, moveLayerBefore=reference_name)
        return True
    except _COMMAND_ERRORS as exc:
        cmds.warning("Animation Layers: couldn't reorder '{}' relative to '{}': {}".format(layer_name, reference_name, exc))
        return False


# ---------------------------------------------------------------------------
# Per-layer state
# ---------------------------------------------------------------------------


def set_mute(layer_name, muted):
    muted = bool(muted)
    # BaseAnimation can't be excluded from evaluation -- there's no "layer
    # beneath it" to fall back to -- so muting it isn't allowed, the same
    # way delete_layer() refuses to delete the root layer outright.
    if _is_root(layer_name):
        return False
    # Mirrors Maya's own Mute/Lock pairing: muting a layer also locks it
    # (nothing should be keyable on a layer that isn't even contributing
    # right now), and unmuting it releases that lock again. Routed through
    # set_lock() -- not a second, separate setAttr -- since that's the one
    # place the group lock-cascade/snapshot behavior lives: muting a
    # *group* layer this way correctly cascades the lock onto its children
    # too, and unmuting it restores their own prior individual lock states
    # via the same snapshot set_lock() already keeps for a direct
    # lock/unlock through the Lock toggle.
    set_lock(layer_name, muted)
    try:
        cmds.setAttr(_plug(layer_name, "mute"), muted)
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
                if cmds.getAttr(_plug(current, "lock")):
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
                    if cmds.getAttr(_plug(name, "lock")):
                        previously_locked.append(name)
                except _COMMAND_ERRORS:
                    continue
            _set_lock_snapshot(layer_name, previously_locked)
            for name in descendants:
                try:
                    cmds.setAttr(_plug(name, "lock"), True)
                except _COMMAND_ERRORS:
                    continue
        else:
            previously_locked = set(_get_lock_snapshot(layer_name))
            for name in descendants:
                try:
                    cmds.setAttr(_plug(name, "lock"), name in previously_locked)
                except _COMMAND_ERRORS:
                    continue
            _set_lock_snapshot(layer_name, [])
    try:
        cmds.setAttr(_plug(layer_name, "lock"), locked)
        return True
    except _COMMAND_ERRORS:
        return False


def set_override(layer_name, override):
    try:
        cmds.setAttr(_plug(layer_name, "override"), bool(override))
        return True
    except _COMMAND_ERRORS:
        return False


def set_weight(layer_name, weight):
    try:
        cmds.setAttr(_plug(layer_name, "weight"), max(0.0, min(1.0, float(weight))))
        return True
    except _COMMAND_ERRORS:
        return False


def selected_layer_names():
    """Layers currently selected in Maya's own animLayer selection state --
    the same state ``select_layer()``/``set_selected_layers()`` write to --
    for toolbar quick actions (Smart Merge/Export shortcuts, right-click
    menu) that act without the Animation Layers window open, so they read
    from the live scene selection the same way ``maya.animation.layer_cache``
    already backs every other layer-scope-aware tool (see
    ``copy_paste``/``animation_tools``)."""
    try:
        context = animation.layer_cache.tool_context()
    except _COMMAND_ERRORS:
        return []
    return list(context.get("selected") or [])


def get_parent(layer_name):
    if not layer_name or not cmds.objExists(layer_name):
        return None
    return animation.AnimationLayer(layer_name).parent or root_layer_name()


# Tracks our own last auto-selected layer node, so we can tell "user selected
# something else since" from "selection is just our own prior auto-select" --
# without this, the first auto-select would permanently look like a user one.
_last_auto_selected = {"name": None}


def set_selected_layers(layer_names):
    """Write a *multi*-layer selection into Maya's native animLayer selection
    state, the same state ``select_layer()`` writes to for a single layer.

    The window's own multi-select (ctrl/shift-click) used to always collapse
    down to whichever layer was clicked last, because every click routed
    through ``select_layer()`` -- which only ever leaves one layer selected,
    matching Maya's single "preferred" edit-target semantics for keying. That
    silently broke toolbar quick actions (Smart Merge/Export/Import) invoked
    while several rows were selected in the window, since those read the
    live scene selection via ``selected_layer_names()`` above. The last
    layer in *layer_names* (if any) is also made preferred, matching plain
    single-selection's own "last click wins" keying-target behavior.
    """
    names = [name for name in dict.fromkeys(layer_names or []) if name and cmds.objExists(name)]
    try:
        root_name = root_layer_name()
        selected_set = set(names)
        for name in animation.scene_layer_names(include_root=False):
            cmds.animLayer(name, edit=True, selected=(name in selected_set))
        if root_name:
            cmds.animLayer(root_name, edit=True, selected=(root_name in selected_set))
        if names:
            cmds.animLayer(names[-1], edit=True, preferred=True)
    except _COMMAND_ERRORS:
        pass


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
    try:
        members = cmds.animLayer(layer_name, query=True, attribute=True) or []
    except _COMMAND_ERRORS:
        members = []
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
        if cmds.getAttr(_plug(layer_name, "mute")):
            return 0.0
        return float(cmds.getAttr(_plug(layer_name, "weight"), time=frame))
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

    Uses the scene's full animation range (``animationStartTime``/
    ``animationEndTime``), not the zoomed/visible playback range
    (``playbackOptions -min/-max``) -- the two are independent in Maya, and
    using the visible range meant a layer with keys outside whatever the
    timeline happened to be zoomed to at merge time had that outside data
    silently discarded: baked nowhere (out of range), then deleted along
    with the source layer.
    """
    scene_start = cmds.playbackOptions(query=True, animationStartTime=True)
    scene_end = cmds.playbackOptions(query=True, animationEndTime=True)

    breakpoints = {scene_start, scene_end}
    static_active = []
    any_curve = False
    for layer_name in layer_names:
        try:
            muted = bool(cmds.getAttr(_plug(layer_name, "mute")))
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

    padded = [
        [max(scene_start, start - pad), min(scene_end, end + pad)]
        for start, end in merged
    ]

    # Two ranges that were left separate above (gap > pad, so not merged)
    # can still end up overlapping once each is independently padded by
    # `pad` on both sides (possible whenever pad < gap <= 2*pad) --
    # collapse those now, or bakeResults below gets handed two overlapping
    # time chunks to sample instead of one.
    final = [padded[0]]
    for start, end in padded[1:]:
        if start <= final[-1][1]:
            final[-1][1] = max(final[-1][1], end)
        else:
            final.append([start, end])

    return [tuple(r) for r in final]


def _key_group_weight_envelope(layer_name, ranges, transition=1.0):
    """Animate the merged layer's own weight so it only overrides its
    active window(s), instead of holding its last baked value forever via
    the default constant extrapolation outside its keyed range."""
    scene_start = cmds.playbackOptions(query=True, animationStartTime=True)
    scene_end = cmds.playbackOptions(query=True, animationEndTime=True)
    weight_plug = _plug(layer_name, "weight")

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
    layer and delete the sources. Only the frame ranges where the merging
    layers can actually change the result get sampled (see
    ``_active_ranges``); layers stacked above the merge set are muted during
    the capture pass and restored after, so they keep applying on top of the
    new layer exactly as before. Merging into BaseAnimation itself (rather
    than a new layer) happens either by selecting every real layer -- same
    as Maya's own Merge Layers -- or by including BaseAnimation itself in
    the selection alongside one or more real layers, to bake just those
    layers down into the base without touching the rest of the stack.
    Locking only ever protects the one layer whose position anchors the
    result -- every other selected layer can be locked and still gets
    merged away.
    """
    root_name = root_layer_name()
    raw_names = list(dict.fromkeys(layer_names or []))
    # Explicitly selecting BaseAnimation is itself the signal to merge into
    # it -- it's dropped from layer_names below (it's the destination, not
    # a source to merge), so that intent has to be captured before filtering.
    merge_into_base = bool(root_name) and root_name in raw_names
    layer_names = [name for name in raw_names if name and name != root_name and cmds.objExists(name)]

    ordered = [name for name in _ordered_layer_names() if name != root_name]
    if not merge_into_base:
        # Selecting every real layer implies the same thing, without
        # requiring BaseAnimation to also be explicitly clicked.
        merge_into_base = bool(root_name) and set(layer_names) == set(ordered)

    if len(layer_names) < (1 if merge_into_base else 2):
        if merge_into_base:
            raise RuntimeError("Select one or more animation layers to merge into BaseAnimation.")
        raise RuntimeError("Select two or more animation layers to merge.")

    positions = {name: index for index, name in enumerate(ordered)}

    # ordered[0] is topmost/highest-priority; "above the merge set" (muted
    # during the capture bake below) = smaller position than its topmost member.
    bottom_name = max(layer_names, key=lambda name: positions.get(name, -1))

    if merge_into_base:
        try:
            base_locked = bool(cmds.getAttr(_plug(root_name, "lock")))
        except _COMMAND_ERRORS:
            base_locked = False
        if base_locked:
            raise RuntimeError("{} is locked -- unlock it before merging into it.".format(root_name))
    else:
        try:
            bottom_locked = bool(cmds.getAttr(_plug(bottom_name, "lock")))
        except _COMMAND_ERRORS:
            bottom_locked = False
        if bottom_locked:
            raise RuntimeError("{} is locked -- unlock it before merging.".format(bottom_name))

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

    merge_positions = [positions[name] for name in layer_names if name in positions]
    topmost_index = min(merge_positions) if merge_positions else -1
    others_above = [
        name for name in ordered
        if name not in layer_names and positions[name] < topmost_index
    ]

    muted_state = {}
    for name in others_above:
        try:
            muted_state[name] = bool(cmds.getAttr(_plug(name, "mute")))
        except _COMMAND_ERRORS:
            continue
        if not muted_state[name]:
            try:
                cmds.setAttr(_plug(name, "mute"), True)
            except _COMMAND_ERRORS:
                pass

    destination = None
    try:
        if merge_into_base:
            destination = root_name
        else:
            # Anchored on the corrected bottom-most (closest to
            # BaseAnimation) layer in the selection, not just whichever
            # layer happened to be first in the caller's (arbitrary) order --
            # that's the layer whose position in the stack the merged result
            # should inherit.
            lowest_parent = animation.AnimationLayer(bottom_name).parent or root_layer_name()
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
                    cmds.setAttr(_plug(name, "mute"), False)
                except _COMMAND_ERRORS:
                    pass

    for name in layer_names:
        delete_layer(name, recursive=False)

    return destination


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------


def _curve_keyframe_data(layer_name, plug):
    """Return this *layer's own* keyframe data for *plug* via ``animLayer
    -findCurveForPlug`` -- a plain ``listConnections`` stops at the blend
    node feeding a multi-layer plug and finds nothing."""
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
        "color": node.get("color") if node["is_group"] else None,
        "override": node["override"],
        "passthrough": node["passthrough"],
        "mute": node["mute"],
        "lock": node["lock"],
        "weight": node["weight"],
        "members": {},
    }
    if not node["is_group"]:
        try:
            member_plugs = cmds.animLayer(node["name"], query=True, attribute=True) or []
        except _COMMAND_ERRORS:
            member_plugs = []
        for plug in member_plugs:
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
    """Serialize the given layers (and any nested children) for the clipboard.

    ``_serialize_layer`` already recurses into a node's own children, so a
    name whose ancestor is *also* in *layer_names* is skipped here -- that
    ancestor's own export already carries it as a nested child; exporting it
    again at the top level would duplicate the whole subtree in the file.
    """
    tree = layer_tree()
    if tree is None:
        return None
    names = list(dict.fromkeys(layer_names or ()))
    name_set = set(names)
    exported = []
    for name in names:
        node = find_node(tree, name)
        if node is None:
            continue
        ancestor = node.get("parent")
        covered_by_ancestor = False
        while ancestor:
            if ancestor in name_set:
                covered_by_ancestor = True
                break
            ancestor_node = find_node(tree, ancestor)
            ancestor = ancestor_node.get("parent") if ancestor_node else None
        if covered_by_ancestor:
            continue
        exported.append(_serialize_layer(node))
    if not exported:
        return None
    return {
        "meta": {"type": EXPORT_TYPE, "version": EXPORT_SCHEMA_VERSION},
        "layers": exported,
    }


def _current_preferred_layer_name():
    try:
        for name in animation.scene_layer_names(include_root=False):
            if cmds.animLayer(name, query=True, preferred=True):
                return name
    except _COMMAND_ERRORS:
        pass
    return None


def _write_member_onto_layer(layer_name, plug, member):
    """Add *plug* to *layer_name* as a member and write its keyframe/static
    data onto it -- shared by ``_import_layer`` and ``extract_to_new_layer``.
    *member* is the ``{"keys": [...]}`` / ``{"value": ...}`` shape
    ``_curve_keyframe_data`` and export produce."""
    if not isinstance(member, dict):
        return False
    node_name = plug.split(".")[0]
    if not cmds.objExists(node_name):
        return False
    # Adds exactly this attribute, not every keyable attribute of the node
    # -- ``cmds.animLayer(edit=True, addSelectedObjects=True)`` adds *all*
    # of a selected node's keyable attributes to the layer, silently
    # over-adding members the source data never actually included.
    if not anim_layers.add_plug_to_layer(layer_name, plug):
        return False
    keys = member.get("keys")
    if keys:
        for key in keys:
            try:
                cmds.setKeyframe(plug, time=(key["time"],), value=key["value"], animLayer=layer_name)
            except _COMMAND_ERRORS:
                continue
            # Target the tangent edit at *this layer's* curve, resolved the
            # same layer-aware way `_curve_keyframe_data` reads it back --
            # keying `plug` directly can leave more than one layer's curve
            # feeding it via a blend node, and a plain `keyTangent(plug,
            # ...)` isn't guaranteed to hit the curve just keyed above.
            try:
                found = cmds.animLayer(layer_name, query=True, findCurveForPlug=plug) or []
                curve = found[0] if found else None
            except _COMMAND_ERRORS:
                curve = None
            if curve:
                try:
                    cmds.keyTangent(curve, time=(key["time"], key["time"]), inTangentType=key.get("itt", "auto"), outTangentType=key.get("ott", "auto"))
                except _COMMAND_ERRORS:
                    pass
    elif "value" in member:
        # A static override with no keys -- write it directly by making
        # this the preferred (edit-target) layer first, same targeting
        # ``select_layer()`` uses for keying.
        try:
            cmds.animLayer(layer_name, edit=True, preferred=True)
            cmds.setAttr(plug, member["value"])
        except _COMMAND_ERRORS:
            return False
    return True


def extract_to_new_layer(layer_name, name=None):
    """Move the currently selected objects' membership (and animation) out
    of *layer_name* into a new sibling layer of the same type.

    Snapshots each selected object's own keyframe/static data on
    *layer_name* first (the same layer-aware read export uses), so the new
    layer keeps the exact animation instead of starting from a flat,
    unkeyed override once ``removeSelectedObjects`` clears it off the source.
    """
    if not layer_name or not cmds.objExists(layer_name):
        raise RuntimeError("Layer no longer exists.")
    if _is_root(layer_name):
        raise RuntimeError("BaseAnimation can't be extracted from.")

    selected_objs = set(cmds.ls(selection=True, long=True) or [])
    if not selected_objs:
        raise RuntimeError("Select one or more objects to extract.")

    try:
        member_plugs = cmds.animLayer(layer_name, query=True, attribute=True) or []
    except _COMMAND_ERRORS:
        member_plugs = []
    plugs = [plug for plug in member_plugs if plug.split(".")[0] in selected_objs]
    if not plugs:
        raise RuntimeError("None of the selected objects are members of this layer.")

    snapshots = {}
    for plug in plugs:
        keys = _curve_keyframe_data(layer_name, plug)
        if keys:
            snapshots[plug] = {"keys": keys}
            continue
        try:
            snapshots[plug] = {"value": cmds.getAttr(plug)}
        except _COMMAND_ERRORS:
            continue
    if not snapshots:
        raise RuntimeError("Could not read any animation from the selected objects on this layer.")

    metadata = {
        "name": _unique_layer_name(name or "Extracted"),
        "override": bool(cmds.getAttr(_plug(layer_name, "override"))),
        "passthrough": True,
    }
    parent = animation.AnimationLayer(layer_name).parent
    if parent and cmds.objExists(parent):
        metadata["parent"] = parent

    created = anim_layers.create_layer(metadata)
    if not created:
        raise RuntimeError("Could not create the extracted layer.")

    cmds.animLayer(layer_name, edit=True, removeSelectedObjects=True)
    for plug, member in snapshots.items():
        _write_member_onto_layer(created, plug, member)
    return created


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
        set_group_color(created, entry.get("color"))
    # Writing a static-override value above has to make this layer
    # "preferred" to route the setAttr correctly; import_layers_data()
    # restores whichever layer was preferred before the import started
    # once the whole tree is done.
    for plug, member in (entry.get("members") or {}).items():
        _write_member_onto_layer(created, plug, member)
    # Children must be created first -- locking a still-childless group here
    # would cascade onto nothing (see set_lock's snapshot logic) and leave
    # every imported child unlocked regardless of the source group's state.
    for child in entry.get("children") or ():
        _import_layer(child, parent=created)
    set_mute(created, bool(entry.get("mute")))
    set_lock(created, bool(entry.get("lock")))
    try:
        set_weight(created, float(entry.get("weight", 1.0)))
    except (TypeError, ValueError):
        pass
    return created


def import_layers_data(data):
    if not isinstance(data, dict):
        return []
    metadata = data.get("meta")
    if not (
        isinstance(metadata, dict)
        and metadata.get("type") == EXPORT_TYPE
        and metadata.get("version") == EXPORT_SCHEMA_VERSION
        and isinstance(data.get("layers"), list)
    ):
        return []
    # Writing a static-override value (above) has to make its layer
    # "preferred" to route the setAttr correctly, which otherwise silently
    # leaves whatever layer was being actively edited before the import
    # switched to some deeply-nested imported layer instead.
    previous_preferred = _current_preferred_layer_name()
    created = []
    try:
        for entry in data.get("layers") or ():
            result = _import_layer(entry, parent=None)
            if result:
                created.append(result)
    finally:
        if previous_preferred and cmds.objExists(previous_preferred):
            try:
                cmds.animLayer(previous_preferred, edit=True, preferred=True)
            except _COMMAND_ERRORS:
                pass
    return created


def export_selected(layer_names, file_path=None, operation=None):
    data = export_layers_data(layer_names)
    if not data:
        raise RuntimeError("Select one or more animation layers to export.")
    if operation is not None:
        operation.set_status("Exporting Animation Layers")
    # Always populate the clipboard slot first -- clipboard.export_dialog()
    # only ever copies whatever's *already* saved to that slot's file on
    # disk; without this, calling it directly (the no-file_path/dialog path)
    # exported nothing but stale or nonexistent data from a previous run.
    clipboard.save(CLIPBOARD_SLOT, data)
    if file_path:
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
