"""Shared animation target, key-range, and selection-context helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import math

from maya import cmds

from TheKeyMachine.maya import selection
from TheKeyMachine.ui.widgets import timeline
from .layers import (
    LayerContext,
    layer_cache,
    layer_graph,
    weight_curves,
)


_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)
_EXPLICIT_CHANNEL_SOURCES = {"channel_box", "graph_editor", "graph_editor_outliner"}


@dataclass(frozen=True)
class SelectionSnapshot:
    """Immutable Maya UI selection state captured before a command mutates it."""

    objects: tuple
    channels: tuple
    graph_keyframes: tuple
    graph_curves: tuple
    graph_outliner_items: tuple
    time_slider_range: object
    current_time: float
    playback_range: tuple


def capture_selection_snapshot():
    """Capture every animation targeting input through one main-thread path."""
    objects = tuple(dict.fromkeys(
        selection.get_selected_objects(long=True, ordered=True) or []
    ))
    channels = tuple(dict.fromkeys(selection.get_selected_channels() or []))
    graph_keyframes = tuple(
        selection.get_graph_editor_selected_keyframes(include_tangents=True)
        or []
    )
    graph_curves = tuple(dict.fromkeys(
        selection.get_graph_editor_selected_curves() or []
    ))
    graph_outliner_items = tuple(dict.fromkeys(
        selection.get_graph_editor_outliner_items() or []
    ))
    time_slider_range = selection.get_selected_time_range()
    try:
        current_time = float(cmds.currentTime(query=True))
    except _COMMAND_ERRORS:
        current_time = 0.0
    try:
        playback_range = tuple(timeline.get_playback_range())
    except _COMMAND_ERRORS:
        playback_range = (current_time, current_time)
    return SelectionSnapshot(
        objects=objects,
        channels=channels,
        graph_keyframes=graph_keyframes,
        graph_curves=graph_curves,
        graph_outliner_items=graph_outliner_items,
        time_slider_range=(
            tuple(time_slider_range) if time_slider_range else None
        ),
        current_time=current_time,
        playback_range=playback_range,
    )


def current_selection_snapshot():
    """Return the invocation snapshot, capturing one when no operation owns it."""
    snapshot = None
    operation = None
    try:
        from TheKeyMachine.tools import common as tool_common

        operation = tool_common.current_tool_operation()
        snapshot = operation.selection_snapshot if operation is not None else None
    except Exception:
        pass
    if snapshot is None:
        snapshot = capture_selection_snapshot()
        if operation is not None:
            operation.selection_snapshot = snapshot
    return snapshot


def _snapshot_time_context(snapshot, default_mode, graph_frames):
    if snapshot.time_slider_range:
        start_frame, end_frame = snapshot.time_slider_range
        first_whole = int(math.ceil(start_frame))
        last_whole = int(math.floor(end_frame))
        return timeline.TimeContext(
            mode="time_slider_range",
            start_frame=start_frame,
            end_frame=end_frame,
            frames=(
                tuple(range(first_whole, last_whole + 1))
                if last_whole >= first_whole
                else (start_frame, end_frame)
            ),
        )
    graph_frames = tuple(sorted(set(float(frame) for frame in graph_frames or [])))
    if graph_frames:
        return timeline.TimeContext(
            mode="graph_editor_keys",
            start_frame=graph_frames[0],
            end_frame=graph_frames[-1],
            frames=graph_frames,
        )
    if default_mode == "current_frame":
        return timeline.TimeContext(
            mode="current_frame",
            start_frame=snapshot.current_time,
            end_frame=snapshot.current_time,
            frames=(snapshot.current_time,),
        )
    start_frame, end_frame = snapshot.playback_range
    return timeline.TimeContext(
        mode="all_animation",
        start_frame=start_frame,
        end_frame=end_frame,
        frames=tuple(range(int(start_frame), int(end_frame) + 1)),
    )


class ToolContext(dict):
    """Public contract for one resolved animation selection and time scope.

    Tools consume named properties rather than the resolver's storage keys.
    Derived contexts are created with ``replace`` so they remain ToolContext
    instances and keep the complete interface.
    """

    _REPLACE_FIELDS = {
        "selection_snapshot": "selection_snapshot",
        "time": "time_context",
        "layer_scope": "layer_context",
        "objects": "target_objects",
        "plugs": "target_plugs",
        "curves": "selected_curves",
        "channels": "selected_channels",
        "selected_keys": "selected_keyframes",
        "source": "source",
        "has_graph_keys": "has_graph_keys",
    }

    def replace(self, **changes):
        """Return a context copy with public fields replaced."""
        unknown = sorted(set(changes) - set(self._REPLACE_FIELDS))
        if unknown:
            raise TypeError(
                "Unknown ToolContext field(s): {}".format(", ".join(unknown))
            )
        values = dict(self)
        for public_name, value in changes.items():
            values[self._REPLACE_FIELDS[public_name]] = value
        return type(self)(values)

    @property
    def selection_snapshot(self):
        """Immutable invocation state used to resolve this context."""
        return self.get("selection_snapshot")

    @property
    def time(self):
        return self.get("time_context")

    @property
    def layer_scope(self):
        return self.get("layer_context") or {}

    @property
    def layers(self):
        return self.layer_scope.get("context") or LayerContext()

    @property
    def objects(self):
        return self.get("target_objects") or []

    @property
    def plugs(self):
        return self.get("target_plugs") or []

    @property
    def curves(self):
        return self.get("selected_curves") or []

    @property
    def channels(self):
        return self.get("selected_channels") or []

    @property
    def selected_keys(self):
        return self.get("selected_keyframes") or []

    @property
    def source(self):
        return self.get("source") or "none"

    @property
    def has_graph_keys(self):
        return bool(self.get("has_graph_keys"))

    def key_times(self, curve):
        if self.time and self.time.mode == "graph_editor_keys":
            selected = [
                float(key_time)
                for selected_curve, key_time in self.selected_keys
                if selected_curve == curve
            ]
            return selected or selected_key_times(curve)

        query = {"query": True, "timeChange": True}
        if self.time and self.time.mode in ("current_frame", "time_slider_range"):
            query["time"] = self.time.timerange
        try:
            return cmds.keyframe(curve, **query) or []
        except _COMMAND_ERRORS:
            return []

    def key_data(self, curve):
        if self.time and self.time.mode == "graph_editor_keys":
            data = []
            for key_time in self.key_times(curve):
                try:
                    values = cmds.keyframe(
                        curve,
                        query=True,
                        time=(key_time, key_time),
                        valueChange=True,
                    ) or []
                except _COMMAND_ERRORS:
                    values = []
                if values:
                    data.append((float(key_time), float(values[0])))
            return data

        query = {"query": True}
        if self.time and self.time.mode in ("current_frame", "time_slider_range"):
            query["time"] = self.time.timerange
        try:
            times = cmds.keyframe(curve, timeChange=True, **query) or []
            values = cmds.keyframe(curve, valueChange=True, **query) or []
        except _COMMAND_ERRORS:
            return []
        if len(times) != len(values):
            return []
        return [
            (float(key_time), float(value))
            for key_time, value in zip(times, values)
        ]

    def curves_for_plugs(self, plugs):
        plugs = list(dict.fromkeys(plug for plug in plugs or [] if plug))
        if not plugs:
            return []
        if self.layer_scope.get("has_layers"):
            curve_layers = layer_graph.ownership(
                plugs,
                self.layer_scope.get("scope_layer_names") or [],
                scene_layers=self.layer_scope["scene_layers"],
            )
            self.layer_scope.setdefault("curve_layers", {}).update(curve_layers)
            return list(curve_layers)
        return layer_graph.curves_for_plugs(plugs)

    def key_range(self, plugs=None, objects=None, channels=None):
        if self.time and self.time.mode == "graph_editor_keys" and self.time.frames:
            return self.time.start_frame, self.time.end_frame

        query = {"query": True, "timeChange": True}
        if self.time and self.time.mode == "time_slider_range":
            query["time"] = self.time.timerange
        plugs = self.plugs if plugs is None else plugs
        objects = self.objects if objects is None else objects
        channels = self.channels if channels is None else channels
        frames = []
        try:
            if plugs:
                for plug in plugs:
                    frames.extend(cmds.keyframe(plug, **query) or [])
            else:
                if channels:
                    query["attribute"] = channels
                for obj in objects:
                    frames.extend(cmds.keyframe(obj, **query) or [])
        except _COMMAND_ERRORS:
            return None
        return (min(frames), max(frames)) if frames else None


def notify_empty(target="animation", action=None):
    """Show the shared concise empty-result message for animation tools."""
    from TheKeyMachine.ui.widgets import util as wutil

    message = "No {}".format(target)
    if action:
        message += " to {}".format(action)
    return wutil.make_inViewMessage(message)


def selection_time_kwargs(time_context):
    if time_context and time_context.mode in ("graph_editor_keys", "time_slider_range"):
        return {"time": (time_context.start_frame, time_context.end_frame)}
    return {}


def capture_time_slider_selection():
    """Capture Maya's native highlighted playback range without touching selection.

    Maya 2024 added editable playback-selection flags. Keeping their raw start
    and end values avoids the inclusive/exclusive conversion used by key tools.
    """
    try:
        visible = cmds.playbackOptions(query=True, selectionVisible=True)
        if visible:
            start_frame = cmds.playbackOptions(query=True, selectionStartTime=True)
            end_frame = cmds.playbackOptions(query=True, selectionEndTime=True)
            return "native", start_frame, end_frame
    except _COMMAND_ERRORS:
        pass
    selected_range = selection.get_selected_time_range()
    return ("time_control",) + tuple(selected_range) if selected_range else None


def restore_time_slider_selection(selected_range):
    """Restore a captured playback range without reselecting objects."""
    if not selected_range:
        return False
    backend, start_frame, end_frame = selected_range
    if backend == "time_control":
        current = selection.get_selected_time_range()
        if current == (start_frame, end_frame):
            return True
        frames = (
            (start_frame,)
            if start_frame == end_frame
            else (start_frame, end_frame)
        )
        return timeline.select_time_slider_range(frames)
    try:
        current = capture_time_slider_selection()
        if current == selected_range:
            return True
        undo_enabled = False
        try:
            undo_enabled = bool(cmds.undoInfo(query=True, state=True))
            if undo_enabled:
                cmds.undoInfo(stateWithoutFlush=False)
            cmds.playbackOptions(
                edit=True,
                selectionStartTime=start_frame,
                selectionEndTime=end_frame,
                selectionVisible=True,
            )
        finally:
            if undo_enabled:
                cmds.undoInfo(stateWithoutFlush=True)
        return True
    except _COMMAND_ERRORS:
        return False


@contextmanager
def preserve_time_slider_selection():
    """Keep a highlighted range across a command's side effects."""
    selected_range = capture_time_slider_selection()
    try:
        yield selected_range
    finally:
        restore_time_slider_selection(selected_range)


def selected_key_times(curve):
    try:
        return cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
    except _COMMAND_ERRORS:
        return []


def resolve_context(
    default_mode="all_animation",
    include_channels=True,
    include_graph=True,
    include_shapes=False,
    resolve_curves=False,
    snapshot=None,
):
    """Resolve the shared animation-tool selection and time precedence.

    Target and time scopes are resolved independently. Channel Box attributes
    restrict targets first, followed by explicit Graph Editor keys or tangent
    handles, then selected objects. A highlighted Time Slider range restricts
    time without discarding the selected Graph Editor curves.
    """

    # Capture the UI attribute selection before any scene or graph queries.
    # Every animation tool consumes this one snapshot for the whole command.
    snapshot = snapshot or current_selection_snapshot()
    channel_selection = list(snapshot.channels) if include_channels else []
    selected_objects = list(snapshot.objects)
    attribute_nodes = list(selected_objects)
    if include_shapes:
        for node in selected_objects:
            try:
                attribute_nodes.extend(
                    cmds.listRelatives(node, shapes=True, fullPath=True) or []
                )
            except _COMMAND_ERRORS:
                continue
        attribute_nodes = list(dict.fromkeys(attribute_nodes))
    channel_plugs = []
    channel_source = "none"
    if include_channels:
        channel_plugs, channel_source = selection.get_attribute_plugs_from_nodes(
            attribute_nodes,
            selected_only=True,
            selected_channels=channel_selection,
        )
    has_channel_selection = bool(
        channel_source == "channel_box" and channel_plugs
    )
    selected_keyframes = list(snapshot.graph_keyframes) if include_graph else []
    graph_curves = list(snapshot.graph_curves) if include_graph else []
    time_context = _snapshot_time_context(
        snapshot,
        default_mode,
        [] if has_channel_selection else [
            key_time for _curve, key_time in selected_keyframes
        ],
    )
    target_plugs = []
    selected_curves = []
    selected_channels = []
    source = "objects" if selected_objects else "none"

    if has_channel_selection:
        target_plugs = list(dict.fromkeys(channel_plugs))
        selected_channels = selection.attribute_names_from_plugs(target_plugs)
        selected_keyframes = []
        source = "channel_box"
    elif selected_keyframes or graph_curves:
        selected_curves = list(dict.fromkeys(
            curve for curve, _key_time in selected_keyframes
        )) or graph_curves
        target_plugs = selection.get_anim_curve_output_plugs(selected_curves)
        selected_channels = selection.attribute_names_from_plugs(target_plugs)
        graph_objects = selection.object_names_from_plugs(target_plugs)
        if graph_objects:
            selected_objects = graph_objects
        source = (
            "graph_editor" if selected_keyframes else "graph_editor_outliner"
        )
        if time_context.mode != "graph_editor_keys":
            # The curves remain the explicit target, while the highlighted
            # Time Slider range becomes the operation's time scope.
            selected_keyframes = []
    else:
        selected_keyframes = []
    if (
        source not in _EXPLICIT_CHANNEL_SOURCES
        and include_channels
    ):
        channel_plugs, channel_source = selection.get_attribute_plugs_from_nodes(
            attribute_nodes,
            selected_only=False,
            selected_channels=channel_selection,
        )
        if channel_plugs:
            target_plugs = list(dict.fromkeys(channel_plugs))
            selected_channels = selection.attribute_names_from_plugs(target_plugs)
            source = channel_source

    layer_context = layer_cache.tool_context()
    target_info = ToolContext({
        "target_plugs": target_plugs,
        "target_objects": selected_objects,
        "selected_channels": selected_channels,
        "selected_curves": selected_curves,
        "selected_keyframes": selected_keyframes,
        "time_context": time_context,
        "source": source,
        "has_graph_keys": bool(selected_keyframes),
        "layer_context": layer_context,
        "selection_snapshot": snapshot,
    })
    if resolve_curves:
        target_info = target_info.replace(
            curves=_resolve_curves(
                target_info,
                include_shapes=include_shapes,
            )
        )
    return target_info


def _resolve_curves(target_info, include_shapes=True):
    resolved = list(dict.fromkeys(target_info.curves))
    if target_info.source == "graph_editor" and resolved:
        return resolved
    lookup_plugs = list(dict.fromkeys(target_info.plugs))
    selected_objects = list(dict.fromkeys(target_info.objects))
    if target_info.source not in _EXPLICIT_CHANNEL_SOURCES:
        lookup_nodes = list(selected_objects)
        if include_shapes:
            for node in selected_objects:
                try:
                    lookup_nodes.extend(
                        cmds.listRelatives(node, shapes=True, fullPath=True) or []
                    )
                except _COMMAND_ERRORS:
                    continue
        lookup_nodes = list(dict.fromkeys(lookup_nodes))
        lookup_plugs.extend(
            "{}.{}".format(node, attribute)
            for node in lookup_nodes
            for attribute in selection.get_keyable_scalar_attributes(node)
        )
    lookup_plugs = list(dict.fromkeys(lookup_plugs))

    resolved.extend(target_info.curves_for_plugs(lookup_plugs))

    layer_context = target_info.layer_scope
    if layer_context.get("has_layers") and target_info.source != "channel_box":

        curve_layers = layer_context.setdefault("curve_layers", {})
        for layer_name in layer_context.get("scope_layer_names") or []:
            for curve in weight_curves(layer_name):
                curve_layers[curve] = layer_name
                resolved.append(curve)
    return list(dict.fromkeys(resolved))


@contextmanager
def preserve_key_selection():
    scene_selection = cmds.ls(selection=True, long=True) or []
    try:
        selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
    except _COMMAND_ERRORS:
        selected_curves = []
    selected_keys = [
        (curve, frame)
        for curve in dict.fromkeys(selected_curves)
        for frame in selected_key_times(curve)
    ]
    try:
        yield
    finally:
        try:
            cmds.selectKey(clear=True)
        except _COMMAND_ERRORS:
            pass
        for curve, frame in selected_keys:
            try:
                if cmds.keyframe(curve, query=True, time=(frame, frame)):
                    cmds.selectKey(
                        curve,
                        add=True,
                        keyframe=True,
                        time=(frame, frame),
                    )
            except _COMMAND_ERRORS:
                continue
        try:
            existing = [item for item in scene_selection if cmds.objExists(item)]
            cmds.select(existing, replace=True) if existing else cmds.select(clear=True)
        except _COMMAND_ERRORS:
            pass
