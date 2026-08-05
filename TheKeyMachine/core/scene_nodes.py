"""Centralized ownership of TheKeyMachine's root scene node and its children.

Several unrelated features (isolate bookmarks, tracer, follow cam, temp pivot,
locators, animation recovery, ...) each need a persistent node parented under
the single ``"TheKeyMachine"`` root, and until now every one of them hand-rolled
its own ``objExists`` / ``createNode`` / ``parent`` / attribute-locking
boilerplate. ``TkmSceneNode`` is the single place that owns that boilerplate:
tools create and look up their scene nodes through it instead of duplicating
the pattern, and can ask it for TKM's version/build info the same way.

Usage::

    from TheKeyMachine.core.scene_nodes import TkmSceneNode

    root = TkmSceneNode.root()                       # ensures "TheKeyMachine" exists
    bookmarks = root.child("Isolate_Bookmarks", lock_transform=True, icon=icons.isolate_bookmarks)
    bookmark = bookmarks.child("run_isolate_bookmark")

    tracer = root.child("Tracer", icon=icons.tracer)
    offset = tracer.child("Tracer_Offset")

    scene_id = root.get_attr("tkmAnimationRecoverySceneId")
    if scene_id is None:
        root.set_attr("tkmAnimationRecoverySceneId", new_id, dataType="string")
"""

from maya import cmds

import TheKeyMachine.mods.generalMod as general


ROOT_NAME = "TheKeyMachine"

_LOCKED_TRANSFORM_ATTRS = (
    "translateX", "translateY", "translateZ",
    "rotateX", "rotateY", "rotateZ",
    "scaleX", "scaleY", "scaleZ",
    "visibility",
)


class TkmSceneNode:
    """A single node in TheKeyMachine's scene-node hierarchy (the root or a child).

    Every instance simply wraps an existing Maya node name; the class does not
    cache or track renames. Use ``TkmSceneNode.root()`` to get (and lazily
    create) TheKeyMachine's root node, then call ``.child(...)`` on it to get
    or create tool-owned nodes underneath.
    """

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "TkmSceneNode({!r})".format(self.name)

    def __eq__(self, other):
        return isinstance(other, TkmSceneNode) and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def root(cls):
        """Return TheKeyMachine's root scene node, creating it if missing."""
        if not cmds.objExists(ROOT_NAME):
            node = cmds.createNode(
                "dagContainer", name=ROOT_NAME, skipSelect=True
            )
            cmds.setAttr(node + ".iconName", general.get_tkm_node_image(), type="string")
            cls(node).lock_transform()
            cmds.addAttr(
                node,
                longName="version",
                niceName="version",
                attributeType="enum",
                enumName="v{} {}".format(
                    general.get_thekeymachine_version(),
                    general.get_thekeymachine_stage_version(),
                ),
                keyable=True,
            )
            cmds.addAttr(
                node,
                longName="series",
                niceName="series",
                attributeType="enum",
                enumName=general.get_thekeymachine_codename(),
                keyable=True,
            )
        return cls(ROOT_NAME)

    @classmethod
    def root_exists(cls):
        """Return True without creating the root node (use before optional cleanup)."""
        return cmds.objExists(ROOT_NAME)

    def child(self, name, *, node_type="transform", lock_transform=False, icon=None):
        """Return the child node *name* under this node, creating/re-homing it as needed.

        Safe to call repeatedly: an existing node is reused, and if it was ever
        moved elsewhere in the scene it is re-parented back under this node.

        Pass *icon* (a path from ``TheKeyMachine.data.icons``) to give the node
        its owning tool's icon in the outliner, the same way ``root()`` stamps
        the TKM icon on the root node. Only ``dagContainer`` nodes support a
        custom outliner icon, so supplying *icon* creates the node as one
        regardless of *node_type*.
        """
        if not cmds.objExists(name):
            node = cmds.createNode(
                "dagContainer" if icon else node_type,
                name=name,
                skipSelect=True,
            )
            if icon:
                cmds.setAttr(node + ".iconName", icon, type="string")
            if lock_transform:
                TkmSceneNode(node).lock_transform()
        else:
            node = name

        current_parents = cmds.listRelatives(node, parent=True, fullPath=False) or []
        if not current_parents or current_parents[0] != self.name:
            cmds.parent(node, self.name)

        return TkmSceneNode(node)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def exists(self):
        return cmds.objExists(self.name)

    def children(self):
        """Return the direct children of this node as ``TkmSceneNode`` wrappers."""
        if not self.exists:
            return []
        return [TkmSceneNode(child) for child in cmds.listRelatives(self.name, children=True, fullPath=False) or []]

    def is_managed(self):
        """Return True if this node exists and lives under TheKeyMachine root."""
        if not self.exists:
            return False
        if self.name == ROOT_NAME:
            return True
        long_names = cmds.ls(self.name, long=True) or []
        return bool(long_names) and "|{}|".format(ROOT_NAME) in long_names[0]

    @staticmethod
    def info():
        """Return TheKeyMachine's version/build info (does not require the root node)."""
        return {
            "version": general.get_thekeymachine_version(),
            "stage": general.get_thekeymachine_stage_version(),
            "build": general.get_thekeymachine_build_version(),
            "codename": general.get_thekeymachine_codename(),
        }

    # ------------------------------------------------------------------
    # Attributes
    # ------------------------------------------------------------------

    def get_attr(self, attribute, default=None):
        plug = "{}.{}".format(self.name, attribute)
        if not cmds.objExists(plug):
            return default
        return cmds.getAttr(plug)

    def set_attr(self, attribute, value, **add_attr_kwargs):
        """Set a custom attribute on this node, adding it first if it doesn't exist yet.

        Refuses to touch the TKM root: the root only ever parents other tools'
        nodes and must stay free of tool-owned data. Create a child with
        ``TkmSceneNode.root().child(...)`` and stamp the attribute there instead.
        """
        if self.name == ROOT_NAME:
            raise RuntimeError(
                "TkmSceneNode: refusing to set '{}' on the TheKeyMachine root node. "
                "Tools must not store data on the shared root -- create a child node "
                "with root().child(your_node_name) and set the attribute there.".format(attribute)
            )
        plug = "{}.{}".format(self.name, attribute)
        if not cmds.objExists(plug):
            if isinstance(value, str) and "dataType" not in add_attr_kwargs and "attributeType" not in add_attr_kwargs:
                add_attr_kwargs["dataType"] = "string"
            cmds.addAttr(self.name, longName=attribute, **add_attr_kwargs)
        if isinstance(value, str) and cmds.getAttr(plug, type=True) == "string":
            cmds.setAttr(plug, value, type="string")
        else:
            cmds.setAttr(plug, value)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def lock_transform(self):
        """Lock and hide the standard transform attributes (idempotent)."""
        for attr in _LOCKED_TRANSFORM_ATTRS:
            plug = "{}.{}".format(self.name, attr)
            if cmds.objExists(plug):
                cmds.setAttr(plug, lock=True, keyable=False, channelBox=False)

    def delete(self):
        """Delete this node. Refuses to delete the TKM root -- every tool's nodes
        hang off it, so only Maya (deleting the whole scene node) removes it."""
        if self.name == ROOT_NAME:
            raise RuntimeError(
                "TkmSceneNode: refusing to delete the TheKeyMachine root node. "
                "Delete the specific child node your tool owns instead."
            )
        if self.exists:
            cmds.delete(self.name)
