"""Background runner registry.

Background runners are persistent helpers and automatic switches that should be
owned by the RuntimeManager rather than individual toolbar widgets.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from maya import cmds

try:
    from maya.api import OpenMaya as om  # type: ignore
except ImportError:  # pragma: no cover
    om = None

try:
    from maya.api import OpenMayaAnim as oma  # type: ignore
except ImportError:  # pragma: no cover
    oma = None

from TheKeyMachine.core.Qt import QtCore, QtGui  # type: ignore

from TheKeyMachine.core import settings
from TheKeyMachine.maya import maya_api
from TheKeyMachine.maya import animation
from TheKeyMachine.maya import selection as maya_selection
from TheKeyMachine.maya import runtime as maya_runtime
from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import timeline as timelineWidgets
from TheKeyMachine.ui.widgets import util as wutil


RUNNER_SETTINGS_NAMESPACE = "background_runners"
CHANNELBOX_HIGHLIGHT_ID = "channelbox_selection_highlight"
CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID = "channelbox_clear_on_selection_change"
CAMERA_ORBIT_SELECTION_ID = "camera_orbit_selection"
HIDE_STATIC_CURVES_ID = "hide_static_animation_curves"
ANIMATION_RECOVERY_ID = "animation_recovery"
ANIM_LAYER_WEIGHTS_ID = "anim_layer_weights"
SELECTOR_TOOLBAR_PIN_ID = "selector_toolbar_pin"
AUTO_PAUSE_VIEWPORT_ID = "auto_pause_viewport"
CHANNELBOX_TINT_KEY = "background_runner:channelbox_selection_highlight"
ANIM_LAYER_WEIGHTS_TINT_KEY = "background_runner:anim_layer_weights"

# The registered trigger command id for each runner -- see
# tools/background_runners/__init__.py's TOOLS dict, which is the actual
# source of truth for these names. Kept here, next to the runner ids
# themselves, so every consumer (the dropdown menu, the Hotkeys editor) reads
# the same mapping instead of each hardcoding its own copy.
RUNNER_COMMAND_IDS = {
    CHANNELBOX_HIGHLIGHT_ID: "background_runner_channelbox_selection_highlight",
    CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID: "background_runner_channelbox_clear_on_selection_change",
    CAMERA_ORBIT_SELECTION_ID: "background_runner_camera_orbit_selection",
    HIDE_STATIC_CURVES_ID: "hide_static_animation_curves",
    ANIMATION_RECOVERY_ID: "background_runner_animation_recovery",
    ANIM_LAYER_WEIGHTS_ID: "background_runner_anim_layer_weights",
    SELECTOR_TOOLBAR_PIN_ID: "background_runner_selector_toolbar_pin",
    AUTO_PAUSE_VIEWPORT_ID: "auto_pause_viewport",
}

_CONTROLLER: Optional["BackgroundRunnerController"] = None


def _runner_setting_key(runner_id):
    return "runner_{}".format(runner_id)


def get_runner_enabled(runner_id, default=False):
    return bool(settings.get_setting(_runner_setting_key(runner_id), default, namespace=RUNNER_SETTINGS_NAMESPACE))


def set_runner_enabled(runner_id, enabled):
    controller = get_controller()
    controller.set_enabled(runner_id, enabled)


def toggle_runner_enabled(runner_id):
    """Toggle one registered runner and return its new state."""
    spec = get_runner_specs().get(runner_id)
    if not spec:
        raise KeyError("Unknown background runner: {}".format(runner_id))
    getter = spec.get("get_enabled")
    enabled = not bool(getter()) if callable(getter) else True
    set_runner_enabled(runner_id, enabled)
    return enabled


def turn_all_runners_off():
    """Disable every registered runner and stop its live service."""
    controller = get_controller()
    for runner_id in controller.runner_ids():
        controller.set_enabled(runner_id, False)


def restore_runner_defaults():
    """Restore every registered runner to its declared default state."""
    controller = get_controller()
    for runner_id, spec in get_runner_specs().items():
        controller.set_enabled(runner_id, spec.get("default", False))


def toggle_channelbox_selection_highlight():
    return toggle_runner_enabled(CHANNELBOX_HIGHLIGHT_ID)


def toggle_channelbox_clear_on_selection_change():
    return toggle_runner_enabled(CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID)


def toggle_camera_orbit_selection():
    return toggle_runner_enabled(CAMERA_ORBIT_SELECTION_ID)


def toggle_hide_static_animation_curves():
    return toggle_runner_enabled(HIDE_STATIC_CURVES_ID)


def toggle_animation_recovery():
    return toggle_runner_enabled(ANIMATION_RECOVERY_ID)


def toggle_anim_layer_weights():
    return toggle_runner_enabled(ANIM_LAYER_WEIGHTS_ID)


def toggle_selector_toolbar_pin():
    return toggle_runner_enabled(SELECTOR_TOOLBAR_PIN_ID)


def toggle_auto_pause_viewport():
    return toggle_runner_enabled(AUTO_PAUSE_VIEWPORT_ID)


def changed_signal_for_runner(runner_id, manager=None):
    if manager is None:
        from TheKeyMachine.core import runtime

        manager = runtime.get_runtime_manager(start=False)
    signal = getattr(manager, "backgroundRunnerChanged", None)
    if signal is None:
        return None

    class _RunnerSignal(QtCore.QObject):
        changed = QtCore.Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._runner_id = runner_id
            signal.connect(self._relay)

        def _relay(self, changed_runner_id, *_args):
            if changed_runner_id == self._runner_id:
                self.changed.emit()

    relay_attr = "_tkm_background_runner_signal_{}".format(runner_id)
    relay = getattr(manager, relay_attr, None)
    if relay is None:
        relay = _RunnerSignal(manager)
        setattr(manager, relay_attr, relay)
    return relay.changed


def _emit_runner_triggered(manager, runner_id):
    try:
        manager.backgroundRunnerTriggered.emit(runner_id)
    except Exception:
        pass


def _is_playing(manager=None):
    if manager is not None and hasattr(manager, "is_playing"):
        return bool(manager.is_playing())
    try:
        return bool(cmds.play(query=True, state=True))
    except Exception:
        return False


def _get_channelbox_name():
    try:
        if cmds.channelBox("mainChannelBox", exists=True):
            return "mainChannelBox"
    except Exception:
        pass
    return "mainChannelBox"


def _has_channelbox_attribute_selection():
    channelbox = _get_channelbox_name()
    query_flags = (
        "selectedMainAttributes",
        "selectedShapeAttributes",
        "selectedHistoryAttributes",
        "selectedOutputAttributes",
    )
    for flag in query_flags:
        try:
            selected = cmds.channelBox(channelbox, query=True, **{flag: True}) or []
        except Exception:
            selected = []
        if selected:
            return True
    return False


def _clear_channelbox_attribute_selection():
    if not _has_channelbox_attribute_selection():
        return False

    channelbox = _get_channelbox_name()
    clear_attempts = (
        lambda: cmds.channelBox(channelbox, edit=True, select=""),
        lambda: cmds.channelBox(channelbox, edit=True, select=[]),
        lambda: cmds.channelBox(channelbox, edit=True, selectedMainAttributes=[]),
        lambda: cmds.channelBox(channelbox, edit=True, selectedShapeAttributes=[]),
        lambda: cmds.channelBox(channelbox, edit=True, selectedHistoryAttributes=[]),
        lambda: cmds.channelBox(channelbox, edit=True, selectedOutputAttributes=[]),
    )
    for clear in clear_attempts:
        try:
            clear()
            return True
        except Exception:
            pass
    return False


def _current_model_panel():
    panel = None
    for query_flag in ("withFocus", "underPointer"):
        try:
            panel = cmds.getPanel(**{query_flag: True})
        except Exception:
            panel = None
        if panel:
            try:
                if cmds.getPanel(typeOf=panel) == "modelPanel":
                    return panel
            except Exception:
                pass

    try:
        visible_panels = cmds.getPanel(visiblePanels=True) or []
    except Exception:
        visible_panels = []
    for panel in visible_panels:
        try:
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                return panel
        except Exception:
            pass
    return None


def _current_camera_nodes():
    panel = _current_model_panel()
    if not panel:
        return None, None
    try:
        camera = cmds.modelEditor(panel, query=True, camera=True)
    except Exception:
        return None, None
    if not camera:
        return None, None

    try:
        if cmds.nodeType(camera) == "camera":
            shape = camera
            parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            transform = parents[0] if parents else None
        else:
            transform = camera
            shapes = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
            shape = shapes[0] if shapes else None
    except Exception:
        return None, None
    return transform, shape


def _as_transform_node(node):
    if not node:
        return None
    node = str(node).split(".", 1)[0]
    try:
        if not cmds.objExists(node):
            return None
        if cmds.nodeType(node) == "transform":
            return node
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        return parents[0] if parents else None
    except Exception:
        return None


def _selection_transform_nodes():
    try:
        selection = cmds.ls(selection=True, long=True, flatten=True) or []
    except Exception:
        selection = []

    transforms = []
    seen = set()
    for node in selection:
        transform = _as_transform_node(node)
        if not transform or transform in seen:
            continue
        transforms.append(transform)
        seen.add(transform)
    return transforms


def _selection_center():
    try:
        selection = cmds.ls(selection=True, long=True, flatten=True) or []
    except Exception:
        selection = []
    if not selection:
        return None

    try:
        bbox = cmds.exactWorldBoundingBox(selection, ignoreInvisible=False)
        if bbox and len(bbox) == 6:
            return (
                (bbox[0] + bbox[3]) * 0.5,
                (bbox[1] + bbox[4]) * 0.5,
                (bbox[2] + bbox[5]) * 0.5,
            )
    except Exception:
        pass

    points = []
    for node in selection:
        try:
            points.append(cmds.xform(node, query=True, worldSpace=True, rotatePivot=True))
        except Exception:
            pass
    if not points:
        return None
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _set_camera_orbit_point_to_selection():
    center = _selection_center()
    if center is None:
        return False

    camera_transform, camera_shape = _current_camera_nodes()
    if not camera_shape:
        return False

    changed = maya_api.set_plug_vector(camera_shape, "tumblePivot", center)

    if camera_transform:
        try:
            camera_position = cmds.xform(camera_transform, query=True, worldSpace=True, translation=True)
            distance = math.sqrt(
                (camera_position[0] - center[0]) ** 2
                + (camera_position[1] - center[1]) ** 2
                + (camera_position[2] - center[2]) ** 2
            )
            changed = maya_api.set_plug_double(camera_shape, "centerOfInterest", distance) or changed
        except Exception:
            pass

    return changed


class ChannelBoxSelectionHighlightRunner(QtCore.QObject):
    def __init__(self, manager, parent=None):
        super().__init__(parent or manager)
        self._manager = manager
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self.sync)
        self._has_selection = False

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.sync(force=True)

    def stop(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        self._set_highlight_visible(False)
        self._has_selection = False

    def sync(self, force=False):
        has_selection = _has_channelbox_attribute_selection()
        if not force and has_selection == self._has_selection:
            return
        self._has_selection = has_selection
        self._set_highlight_visible(has_selection)
        _emit_runner_triggered(self._manager, CHANNELBOX_HIGHLIGHT_ID)

    def _set_highlight_visible(self, visible):
        if visible:
            color = QtGui.QColor(78, 142, 198, 58)
            timelineWidgets.show_timeline_tint(
                timerange=timelineWidgets.get_playback_range(),
                color=color,
                duration_ms=None,
                key=CHANNELBOX_TINT_KEY,
                owner=self._manager,
                z_index=-1,
            )
        else:
            self._manager.clear_managed_widget(CHANNELBOX_TINT_KEY)


class ChannelBoxClearOnSelectionChangeRunner(QtCore.QObject):
    RUNTIME_KEY = "background_runner:channelbox_clear_on_selection_change"

    def __init__(self, manager, parent=None):
        super().__init__(parent or manager)
        self._manager = manager

    def start(self):
        self._manager.connect_signal(
            self._manager.selection_changed,
            self._schedule_clear,
            key=self.RUNTIME_KEY,
            unique=True,
        )

    def stop(self):
        self._manager.disconnect_callbacks(self.RUNTIME_KEY)

    def _schedule_clear(self, *_args):
        _emit_runner_triggered(self._manager, CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID)
        QtCore.QTimer.singleShot(0, _clear_channelbox_attribute_selection)


class CameraOrbitSelectionRunner(QtCore.QObject):
    RUNTIME_KEY = "background_runner:camera_orbit_selection"
    TIME_KEY = "background_runner:camera_orbit_selection_time"
    PLAYBACK_KEY = "background_runner:camera_orbit_selection_playback"
    WATCH_KEY = "background_runner:camera_orbit_selection_watch"
    UPDATE_DELAY_MS = 200

    def __init__(self, manager, parent=None):
        super().__init__(parent or manager)
        self._manager = manager
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._update_orbit_point)
        self._updating = False

    def start(self):
        self._manager.connect_signal(
            self._manager.selection_changed,
            self._on_selection_changed,
            key=self.RUNTIME_KEY,
            unique=True,
        )
        self._connect_time_changed()
        self._manager.connect_signal(
            self._manager.playbackStateChanged,
            self._on_playback_state_changed,
            key=self.PLAYBACK_KEY,
            unique=False,
        )
        self._refresh_watched_nodes()
        self._schedule_update()

    def stop(self):
        self._manager.disconnect_callbacks(self.RUNTIME_KEY)
        self._manager.disconnect_callbacks(self.TIME_KEY)
        self._manager.disconnect_callbacks(self.PLAYBACK_KEY)
        self._manager.disconnect_callbacks(self.WATCH_KEY)
        try:
            self._update_timer.stop()
        except Exception:
            pass

    def _connect_time_changed(self):
        if _is_playing(self._manager):
            self._manager.disconnect_callbacks(self.TIME_KEY)
            return False
        return self._manager.connect_signal(
            self._manager.time_changed,
            self._schedule_update,
            key=self.TIME_KEY,
            unique=True,
        )

    def _schedule_update(self, *_args, delay_ms=UPDATE_DELAY_MS, restart=True):
        if self._updating:
            return
        if _is_playing(self._manager):
            try:
                self._update_timer.stop()
            except Exception:
                pass
            return
        if restart and self._update_timer.isActive():
            self._update_timer.stop()
        if restart or not self._update_timer.isActive():
            self._update_timer.start(int(delay_ms))

    def _on_selection_changed(self, *_args):
        self._refresh_watched_nodes()
        self._schedule_update()

    def _on_watched_node_changed(self, *_args):
        self._schedule_update(delay_ms=self.UPDATE_DELAY_MS, restart=True)

    def _on_playback_state_changed(self, playing):
        if playing:
            self._manager.disconnect_callbacks(self.TIME_KEY)
            try:
                self._update_timer.stop()
            except Exception:
                pass
            return
        self._connect_time_changed()

    def _refresh_watched_nodes(self):
        self._manager.disconnect_callbacks(self.WATCH_KEY)

        watched_nodes = []
        seen = set()
        for node in _selection_transform_nodes():
            if node not in seen:
                watched_nodes.append(node)
                seen.add(node)

        camera_transform, _camera_shape = _current_camera_nodes()
        if camera_transform and camera_transform not in seen:
            watched_nodes.append(camera_transform)
            seen.add(camera_transform)

        for node in watched_nodes:
            self._manager.add_node_attribute_changed_callback(
                node,
                self._on_watched_node_changed,
                key=self.WATCH_KEY,
            )

    def _update_orbit_point(self):
        if self._updating:
            return
        if _is_playing(self._manager):
            return
        self._updating = True
        try:
            if _set_camera_orbit_point_to_selection():
                _emit_runner_triggered(self._manager, CAMERA_ORBIT_SELECTION_ID)
        finally:
            self._updating = False


class HideStaticAnimationCurvesRunner(QtCore.QObject):
    """Select only non-flat channels in an open Graph Editor."""

    RUNTIME_KEY = "background_runner:hide_static_animation_curves"
    EDITOR = "graphEditor1GraphEd"
    OUTLINER_SELECTION = "graphEditor1FromOutliner"
    SYNC_DELAY_MS = 100

    def __init__(self, manager, parent=None):
        super().__init__(parent or manager)
        self._manager = manager
        self._running = False
        self._sync_timer = QtCore.QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(self.SYNC_DELAY_MS)
        self._sync_timer.timeout.connect(self._run_scheduled_sync)

    def start(self):
        if self._running:
            self.sync()
            return
        self._running = True
        for signal in (
            self._manager.selection_changed,
            self._manager.graph_editor_opened,
        ):
            self._manager.connect_signal(signal, self._schedule_sync, key=self.RUNTIME_KEY, unique=False)
        # An already-open Graph Editor is ready to update immediately. Deferred
        # syncing remains useful only for subsequent Maya UI/selection events.
        self.sync()

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._manager.disconnect_callbacks(self.RUNTIME_KEY)
        self._sync_timer.stop()
        self.sync(include_flat=True)

    def _schedule_sync(self, *_args):
        if not self._running:
            return
        self._sync_timer.start()

    def _run_scheduled_sync(self):
        if self._running:
            self.sync()

    @staticmethod
    def _visible_graph_editors():
        """Resolve Maya's canonical Graph Editor like the graph toolbar does."""
        try:
            if "graphEditor1" not in (cmds.getPanel(vis=True) or []):
                return []
        except Exception:
            return []
        graph_widget = wutil.get_control_widget("graphEditor1")
        if not graph_widget or not wutil.is_valid_widget(graph_widget):
            return []
        try:
            return (
                [HideStaticAnimationCurvesRunner.EDITOR]
                if cmds.animCurveEditor(
                    HideStaticAnimationCurvesRunner.EDITOR, exists=True
                )
                else []
            )
        except Exception:
            return []

    @staticmethod
    def _is_flat_curve(curve):
        try:
            values = cmds.keyframe(curve, query=True, valueChange=True) or []
        except Exception:
            values = []
        if len(values) < 2:
            return bool(values)
        first = values[0]
        return all(abs(value - first) <= 1e-10 for value in values[1:])

    @staticmethod
    def _selected_curve_attributes():
        try:
            nodes = cmds.ls(selection=True, long=True) or []
        except Exception:
            nodes = []

        lookup_nodes = list(nodes)
        for node in nodes:
            try:
                lookup_nodes.extend(cmds.listRelatives(node, shapes=True, fullPath=True) or [])
            except Exception:
                pass

        curve_attributes = []
        seen = set()
        for node in lookup_nodes:
            try:
                attributes = cmds.listAttr(node, keyable=True, scalar=True) or []
                attributes.extend(cmds.listAttr(node, channelBox=True, scalar=True) or [])
            except Exception:
                attributes = []
            for attribute in attributes:
                plug = "{}.{}".format(node, attribute)
                try:
                    curves = cmds.keyframe(plug, query=True, name=True) or []
                except Exception:
                    curves = []
                for curve in curves:
                    pair = (curve, plug)
                    if pair not in seen:
                        curve_attributes.append(pair)
                        seen.add(pair)
        return curve_attributes

    def sync(self, include_flat=False):
        editors = self._visible_graph_editors()
        if not editors:
            return

        attributes = []
        seen = set()
        for curve, attribute in self._selected_curve_attributes():
            if not include_flat and self._is_flat_curve(curve):
                continue
            if attribute and attribute not in seen:
                attributes.append(attribute)
                seen.add(attribute)

        try:
            if not cmds.selectionConnection(
                self.OUTLINER_SELECTION, exists=True
            ):
                return
            cmds.selectionConnection(
                self.OUTLINER_SELECTION, edit=True, clear=True
            )
            for attribute in attributes:
                cmds.selectionConnection(
                    self.OUTLINER_SELECTION, edit=True, select=attribute
                )
        except Exception:
            return

        updated = False
        for editor in editors:
            try:
                cmds.animCurveEditor(
                    editor,
                    edit=True,
                    forceMainConnection=self.OUTLINER_SELECTION,
                )
                maya_selection.refresh_graph_editor(editor)
                updated = True
            except Exception:
                continue
        if updated:
            _emit_runner_triggered(self._manager, HIDE_STATIC_CURVES_ID)


MIN_CURVE_SAMPLES = 50
MAX_CURVE_SAMPLES = 500


def _evaluate_weight_curve(curve_name, key_times, start_frame, end_frame):
    """Densely sample a weight curve through its own curve function set.

    ``cmds.keyframe`` only reports key values, then some kind of fitted
    line has to guess at the shape between them -- which drifts from the
    real curve for anything but simple even spline tangents (linear
    segments, stepped keys, weighted/broken tangents all read differently).
    Evaluating the curve itself through ``MFnAnimCurve.evaluate()`` instead
    reproduces the exact value Maya would show at every sampled frame,
    tangents and pre/post-infinity behavior included, because it *is* the
    same evaluation Maya itself runs -- no separate approximation to keep
    in sync with. One sample per frame (capped for very long ranges) is
    dense enough that the result reads as a smooth curve without needing
    any curve-fitting of our own.
    """
    if oma is None or om is None:
        return None
    curve_mobject = maya_api.mobject_from_node(curve_name)
    if curve_mobject is None:
        return None
    try:
        curve_fn = oma.MFnAnimCurve(curve_mobject)
    except Exception:
        return None

    span = max(1.0, float(end_frame - start_frame))
    sample_count = int(max(MIN_CURVE_SAMPLES, min(MAX_CURVE_SAMPLES, round(span) + 1)))
    time_unit = om.MTime.uiUnit()

    frames = set(key_times)
    frames.update(
        start_frame + (span * index) / (sample_count - 1) for index in range(sample_count)
    )

    samples = []
    for frame in sorted(frames):
        try:
            value = curve_fn.evaluate(om.MTime(frame, time_unit))
        except Exception:
            continue
        samples.append((frame, max(0.0, min(1.0, value))))
    return tuple(samples) if len(samples) >= 2 else None


def _weight_curve_domain():
    """A frame domain to sample weight curves across, wider than what's
    currently framed on the timeline.

    Reframing the timeline -- dragging the range bar, zooming, "frame all"
    -- doesn't go through any of the runner's callbacks (it isn't a scene
    edit), so sampling would otherwise go stale the moment a reframe brings
    unsampled frames into view. Sampling the union of the scene's overall
    animation range and the current playback range, padded by half that
    span on each side, comfortably covers ordinary reframing without
    needing a resample; ``AnimLayerWeightsTint`` renormalizes the mapping
    against the live playback range on every paint regardless (see its
    ``paintEvent``), so this only has to provide the data.
    """
    playback_start, playback_end = timelineWidgets.get_playback_range()
    try:
        anim_start = cmds.playbackOptions(query=True, animationStartTime=True)
        anim_end = cmds.playbackOptions(query=True, animationEndTime=True)
    except Exception:
        anim_start, anim_end = playback_start, playback_end

    domain_start = min(playback_start, anim_start)
    domain_end = max(playback_end, anim_end)
    margin = max(10.0, (domain_end - domain_start) * 0.5)
    return domain_start - margin, domain_end + margin


def _layer_weight_points(layer_name, start_frame, end_frame):
    """Return raw ``(frame, value)`` weight-curve points for one layer.

    ``frame`` is an actual scene frame number, left unnormalized -- the
    widget maps frame to x against whatever the playback range is *at paint
    time*, so a range edit (dragging the timeline's min/max) doesn't leave
    already-resolved curves stretched against a stale range until the next
    recompute. ``value`` is the layer weight clamped to 0..1. A layer with
    no weight animation curve (a static weight -- most commonly 1.0, an
    untouched layer) resolves to a flat pair spanning ``start_frame`` to
    ``end_frame``, so it always draws a steady line rather than nothing.
    Returns ``None`` when the layer has no readable weight plug at all.
    """
    weight_plug = "{}.weight".format(layer_name)
    if not cmds.objExists(weight_plug):
        return None

    try:
        curves = cmds.listConnections(
            weight_plug, source=True, destination=False, type="animCurve"
        ) or []
    except Exception:
        curves = []

    if not curves:
        try:
            value = max(0.0, min(1.0, float(cmds.getAttr(weight_plug))))
        except Exception:
            value = 1.0
        return ((start_frame, value), (end_frame, value))

    try:
        times = cmds.keyframe(weight_plug, query=True, timeChange=True) or []
        values = cmds.keyframe(weight_plug, query=True, valueChange=True) or []
    except Exception:
        times, values = [], []
    if not times or len(times) != len(values):
        return None

    keys = sorted(zip(times, values))

    sampled = _evaluate_weight_curve(curves[0], [t for t, _ in keys], start_frame, end_frame)
    if sampled:
        return sampled

    # Fallback for the rare case OpenMayaAnim evaluation isn't available:
    # approximate from keyframe values directly, holding flat outside the
    # first/last key the way Maya's default pre/post-infinity behaves.
    samples = []
    first_time, first_value = keys[0]
    last_time, last_value = keys[-1]
    if first_time > start_frame:
        samples.append((start_frame, first_value))
    samples.extend(keys)
    if last_time < end_frame:
        samples.append((end_frame, last_value))

    return tuple((time, max(0.0, min(1.0, value))) for time, value in samples)


def _value_at_frame(points, frame):
    """Linearly interpolate a resolved weight curve's value at ``frame``.

    ``points`` is the same dense ``(frame, value)`` sequence used to paint
    the curve, sorted by frame and pre-sampled across a domain wider than
    any one visible range (see ``_weight_curve_domain``), so this holds up
    across a reframe without needing new data -- clamping to the nearest
    end for a frame that still falls outside it.
    """
    if not points:
        return 0.0
    if frame <= points[0][0]:
        return points[0][1]
    if frame >= points[-1][0]:
        return points[-1][1]

    previous_frame, previous_value = points[0]
    for next_frame, next_value in points[1:]:
        if next_frame >= frame:
            if next_frame == previous_frame:
                return next_value
            t = (frame - previous_frame) / (next_frame - previous_frame)
            return previous_value + (next_value - previous_value) * t
        previous_frame, previous_value = next_frame, next_value
    return points[-1][1]


class AnimLayerWeightsTint(timelineWidgets.TimelineTint):
    """Full-width timeline overlay plotting anim-layer weight curves.

    No background wash -- ``TimelineTint``'s own fill is skipped entirely
    (see ``paintEvent``) so only the curves, and the selected layer's name
    tag, are visible over the timeline.
    """

    CURVE_COLOR = (255, 255, 255)
    HIGHLIGHTED_ALPHA = 140
    HIGHLIGHTED_WIDTH = 1.4
    NORMAL_ALPHA = 80
    NORMAL_WIDTH = 1.2

    # Black composited over the timeline at one-third opacity lands at the
    # same visual intensity as the previous opaque ~30 RGB muted shade on
    # Maya's usual ~45 RGB timeline, while adapting naturally to its theme.
    MUTED_COLOR = (0, 0, 0)
    MUTED_ALPHA = 90
    UNSELECTED_MUTED_ALPHA = 45
    # Pen-width multiples: long, loosely spaced dashes rather than Qt's
    # tighter default pattern.
    MUTED_DASH_PATTERN = (6.0, 6.0)

    LABEL_TEXT_COLOR = QtGui.QColor(20, 20, 20, 235)
    LABEL_FONT_SIZE = 10
    LABEL_PAD_X = 4
    LABEL_PAD_Y = 1
    LABEL_LEFT_INSET = 4
    LABEL_GAP = 3

    def __init__(self, parent=None, z_index=-2):
        self._layer_curves = ()
        super().__init__(
            timerange=timelineWidgets.get_playback_range(),
            color=(0, 0, 0, 0),
            duration_ms=None,
            parent=parent,
            center_line=False,
            icon=None,
            full_width=True,
            icon_scale=1.0,
            z_index=z_index,
        )

    def set_layer_curves(self, layer_curves):
        self._layer_curves = tuple(layer_curves or ())
        self.update()

    def paintEvent(self, event):
        # Deliberately not calling super().paintEvent(): TimelineTint's fill
        # is what would draw the background wash, which this overlay never
        # wants -- only the curves themselves should be visible.
        if not self._parent_widget or not self._layer_curves:
            return

        rect = self._current_tint_rect()
        if rect.isEmpty():
            return
        rect = self._graph_rect(rect)
        if rect.isEmpty():
            return

        # Read the live playback range rather than trusting whatever range
        # was current when the points were resolved -- dragging the
        # timeline's min/max doesn't go through any of the runner's
        # callbacks, so this is what keeps an already-resolved curve (and
        # the layer-name tag below) correctly placed against the ruler
        # after a range edit instead of drawing against a stale one. The
        # points themselves are pre-sampled across a much wider domain than
        # the visible range (see AnimLayerWeightsRunner._recompute), so
        # whatever a reframe newly brings into view is already covered
        # without waiting for another recompute.
        start_frame, end_frame = timelineWidgets.get_playback_range()
        span = float(end_frame - start_frame) or 1.0
        margin = min(rect.height() * 0.5, wutil.DPI(3))
        usable_height = max(1.0, rect.height() - margin * 2.0)

        def map_point(frame, value):
            return QtCore.QPointF(
                rect.left() + ((frame - start_frame) / span) * rect.width(),
                rect.bottom() - margin - value * usable_height,
            )

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for layer_curve in self._layer_curves:
            self._paint_layer_curve(painter, layer_curve, map_point)
        # Drawn in its own pass, after every curve, so a label never ends up
        # underneath another layer's line.
        for layer_curve in self._layer_curves:
            # Muting a layer removes its name tag even if it remains selected.
            # Every selected, active layer keeps the tag, including a layer
            # whose weight curve is completely flat.
            if layer_curve.get("selected") and not layer_curve.get("muted"):
                self._paint_layer_label(painter, rect, layer_curve, start_frame, map_point)
        painter.end()

    # Maya 2024 and later's redesigned time slider needs its plotting area
    # pulled in from the raw control rect.
    GRAPH_INSET_2024 = 6

    def _graph_rect(self, rect):
        """The area within ``rect`` actually available for plotting.

        Everything downstream -- curve mapping, the label's flip-side
        midline, its clamped position -- reads from this one rect, so
        insetting it here is the single place that needs to know about the
        Maya-2024-and-later time slider's extra top/bottom chrome.
        """
        if not maya_runtime.is_at_least(2024):
            return rect
        inset = wutil.DPI(self.GRAPH_INSET_2024)
        if rect.height() <= inset * 2:
            return rect
        return rect.adjusted(0, inset, 0, -inset)

    def _paint_layer_curve(self, painter, layer_curve, map_point):
        points = layer_curve.get("points") or ()
        if len(points) < 2:
            return

        # Points are already densely sampled from the real curve evaluation
        # (see _evaluate_weight_curve), so connecting them with straight
        # segments reproduces the actual curve -- sharp corners (stepped
        # tangents) included -- instead of a further curve-fit smoothing
        # them into a shape that no longer matches the real animCurve.
        path = QtGui.QPainterPath()
        path.moveTo(map_point(*points[0]))
        for frame, value in points[1:]:
            path.lineTo(map_point(frame, value))

        pen = QtGui.QPen()
        if layer_curve.get("muted"):
            # A muted layer's weight doesn't drive anything right now, so
            # it recedes into the timeline itself rather than competing
            # with the active curves -- same idea as the pen, just dashed
            # and dark instead of bright, so it still reads as "present but
            # off" rather than disappearing outright.
            pen.setColor(
                self._muted_color(selected=bool(layer_curve.get("selected")))
            )
            pen.setStyle(QtCore.Qt.CustomDashLine)
            pen.setDashPattern(self.MUTED_DASH_PATTERN)
            pen.setWidthF(wutil.DPI(self.NORMAL_WIDTH))
        else:
            selected = bool(layer_curve.get("selected"))
            alpha = self.HIGHLIGHTED_ALPHA if selected else self.NORMAL_ALPHA
            width = self.HIGHLIGHTED_WIDTH if selected else self.NORMAL_WIDTH
            pen.setColor(QtGui.QColor(*self.CURVE_COLOR, alpha))
            pen.setWidthF(wutil.DPI(width))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

    def _muted_color(self, selected=False):
        alpha = self.MUTED_ALPHA if selected else self.UNSELECTED_MUTED_ALPHA
        return QtGui.QColor(*self.MUTED_COLOR, alpha)

    def _paint_layer_label(self, painter, rect, layer_curve, start_frame, map_point):
        name = layer_curve.get("name")
        points = layer_curve.get("points") or ()
        # A single resolved point is enough to anchor the label. Curve drawing
        # itself still requires two points, but selected unmuted layers should
        # never lose their name merely because their weight is flat.
        if not name or not points:
            return

        # Pinned to the left edge of whatever's currently visible, at the
        # height of the curve's own value there -- both re-derived from the
        # live rect/range every paint, so the tag tracks a reframe on its
        # own instead of needing a fresh recompute to catch up.
        anchor = map_point(start_frame, _value_at_frame(points, start_frame))

        font = QtGui.QFont(painter.font())
        font.setPixelSize(int(round(wutil.DPI(self.LABEL_FONT_SIZE))))
        metrics = QtGui.QFontMetricsF(font)
        pad_x, pad_y = wutil.DPI(self.LABEL_PAD_X), wutil.DPI(self.LABEL_PAD_Y)
        box_width = metrics.horizontalAdvance(name) + pad_x * 2
        box_height = metrics.height() + pad_y * 2

        box_left = rect.left() + wutil.DPI(self.LABEL_LEFT_INSET)
        gap = wutil.DPI(self.LABEL_GAP)
        # Flip above/below the curve point based on which half of the strip
        # it falls in, so the tag stays inside the timeline instead of
        # being clipped by a widget only ever a couple dozen pixels tall.
        if anchor.y() <= rect.top() + rect.height() * 0.5:
            box_top = anchor.y() + gap
        else:
            box_top = anchor.y() - gap - box_height
        box_top = max(rect.top(), min(rect.bottom() - box_height, box_top))

        box_rect = QtCore.QRectF(box_left, box_top, box_width, box_height)
        radius = min(box_height * 0.5, wutil.DPI(4))

        alpha = self.HIGHLIGHTED_ALPHA
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(*self.CURVE_COLOR, alpha))
        painter.drawRoundedRect(box_rect, radius, radius)

        painter.setFont(font)
        painter.setPen(self.LABEL_TEXT_COLOR)
        painter.drawText(box_rect, QtCore.Qt.AlignCenter, name)


def _is_authored_attribute_change(msg):
    """Filter an ``MNodeMessage`` bitmask down to edits worth reacting to.

    Excludes plain evaluation/dirty-propagation firings (what a connected,
    animated plug generates on every time change during playback) so only
    an explicit ``setAttr``-style edit or a connection being made/broken --
    a curve getting keyed or unkeyed -- triggers a recompute.
    """
    if om is None:
        return True
    mask = (
        om.MNodeMessage.kAttributeSet
        | om.MNodeMessage.kConnectionMade
        | om.MNodeMessage.kConnectionBroken
    )
    return bool(msg & mask)


class AnimLayerWeightsRunner(QtCore.QObject):
    """Keep the timeline weight-curve plot in sync with the scene's anim layers.

    Callback-driven, no polling. Maya has no selection-changed event for the
    Anim Layer Editor the way it does for scene selection, but ``selected``
    and ``mute`` (like ``weight`` itself) are genuine attributes on the
    animLayer node -- see ``maya.animation.AnimationLayer.refresh()``, which
    already reads them the same way -- so one ``MNodeMessage`` attribute-
    changed callback per layer node covers select/mute/weight edits without
    a polling timer. Layer creation, deletion, and rename go through Maya's
    own ``animLayerRebuild`` / ``animLayerRefresh`` events, the same events
    used by Maya's native Animation Layer Editor. They also fire on undo/redo
    when Maya rebuilds or refreshes that editor state.
    Weight *curve* edits -- keys added, moved, or removed on an already-keyed
    weight -- go through Maya's batched anim-curve-edited callback, the same
    one ``animation_recovery`` already relies on for exactly this reason: it
    fires on authored curve edits (and their undo/redo), not on ordinary
    playback evaluation.
    """

    STRUCTURE_KEY = "background_runner:anim_layer_weights_structure"
    NODE_WATCH_KEY = "background_runner:anim_layer_weights_watch"
    CURVE_EDIT_KEY = "background_runner:anim_layer_weights_curve_edit"
    WATCHED_ATTRIBUTES = frozenset(("selected", "mute", "weight"))

    def __init__(self, manager, parent=None):
        super().__init__(parent or manager)
        self._manager = manager
        self._last_curves_key = None
        self._weight_curve_names = set()
        self._structure_refresh_timer = QtCore.QTimer(self)
        self._structure_refresh_timer.setSingleShot(True)
        self._structure_refresh_timer.setInterval(0)
        self._structure_refresh_timer.timeout.connect(self._apply_layer_structure_change)
        self._curve_refresh_timer = QtCore.QTimer(self)
        self._curve_refresh_timer.setSingleShot(True)
        self._curve_refresh_timer.setInterval(8)
        self._curve_refresh_timer.timeout.connect(self._recompute)

    def start(self):
        for event_name in ("animLayerRebuild", "animLayerRefresh"):
            self._manager.add_scriptjob(
                event=event_name,
                key=self.STRUCTURE_KEY,
                callback=self._schedule_layer_structure_change,
            )
        self._manager.add_anim_curve_edited_callback(
            self._on_curve_edited, key=self.CURVE_EDIT_KEY,
        )
        self._watch_layer_nodes()
        self._recompute(force=True)

    def stop(self):
        self._structure_refresh_timer.stop()
        self._curve_refresh_timer.stop()
        self._manager.disconnect_callbacks(self.STRUCTURE_KEY)
        self._manager.disconnect_callbacks(self.CURVE_EDIT_KEY)
        self._manager.disconnect_callbacks(self.NODE_WATCH_KEY)
        self._manager.clear_managed_widget(ANIM_LAYER_WEIGHTS_TINT_KEY)
        self._last_curves_key = None
        self._weight_curve_names.clear()

    def _schedule_layer_structure_change(self, *_args):
        # Maya can emit both refresh and rebuild for one layer edit. Coalesce
        # them, and wait until the command has finished changing the layer
        # graph before querying names or attaching callbacks to new nodes.
        self._structure_refresh_timer.start()

    def _apply_layer_structure_change(self):
        # The layer set itself changed shape -- rebuild the node watch list
        # from scratch rather than trying to diff it against the old one.
        self._watch_layer_nodes()
        self._recompute()

    def _on_curve_edited(self, *args):
        """Ignore unrelated curves and coalesce Maya's per-key edit bursts."""
        edited = set()
        try:
            curves = args[0]
            for index in range(len(curves)):
                edited.add(om.MFnDependencyNode(curves[index]).name())
        except Exception:
            pass
        if edited and not edited.intersection(self._weight_curve_names):
            return
        if not self._curve_refresh_timer.isActive():
            self._curve_refresh_timer.start()

    def _watch_layer_nodes(self):
        self._manager.disconnect_callbacks(self.NODE_WATCH_KEY)
        self._weight_curve_names.clear()
        for layer_name in animation.scene_layer_names(include_root=False):
            self._manager.add_node_attribute_changed_callback(
                layer_name,
                self._on_layer_attribute_changed,
                key=self.NODE_WATCH_KEY,
            )
            try:
                self._weight_curve_names.update(
                    cmds.keyframe(
                        "{}.weight".format(layer_name), query=True, name=True
                    ) or []
                )
            except Exception:
                pass

    def _on_layer_attribute_changed(self, msg, plug, *_args):
        if not _is_authored_attribute_change(msg):
            return
        try:
            attribute_name = plug.partialName(useLongNames=True)
        except Exception:
            return
        if attribute_name not in self.WATCHED_ATTRIBUTES:
            return
        if msg & (om.MNodeMessage.kConnectionMade | om.MNodeMessage.kConnectionBroken):
            self._schedule_layer_structure_change()
            return
        self._recompute()

    def _recompute(self, force=False):
        start_frame, end_frame = _weight_curve_domain()

        layer_curves = []
        for layer_name in animation.scene_layer_names(include_root=False):
            layer = animation.AnimationLayer(layer_name)
            points = _layer_weight_points(layer_name, start_frame, end_frame)
            if not points:
                continue
            layer_curves.append(
                {
                    "name": layer_name,
                    "selected": bool(layer.selected),
                    "muted": bool(layer.muted),
                    "points": points,
                }
            )

        curves_key = tuple(
            (entry["name"], entry["selected"], entry["muted"], entry["points"])
            for entry in layer_curves
        )
        if not force and curves_key == self._last_curves_key:
            return
        self._last_curves_key = curves_key

        if not layer_curves:
            self._manager.clear_managed_widget(ANIM_LAYER_WEIGHTS_TINT_KEY)
            return

        widget = AnimLayerWeightsTint()
        widget.set_layer_curves(layer_curves)
        self._manager.register_managed_widget(
            widget, key=ANIM_LAYER_WEIGHTS_TINT_KEY, owner=self._manager
        )
        _emit_runner_triggered(self._manager, ANIM_LAYER_WEIGHTS_ID)


class BackgroundRunnerController(QtCore.QObject):
    def __init__(self, manager):
        super().__init__(manager)
        self._manager = manager
        self._services = {
            CHANNELBOX_HIGHLIGHT_ID: ChannelBoxSelectionHighlightRunner(manager, parent=self),
            CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID: ChannelBoxClearOnSelectionChangeRunner(manager, parent=self),
            CAMERA_ORBIT_SELECTION_ID: CameraOrbitSelectionRunner(manager, parent=self),
            HIDE_STATIC_CURVES_ID: HideStaticAnimationCurvesRunner(manager, parent=self),
            ANIM_LAYER_WEIGHTS_ID: AnimLayerWeightsRunner(manager, parent=self),
        }

    def start_enabled(self):
        for runner_id in self.runner_ids():
            if self.is_enabled(runner_id):
                self._start_service(runner_id)

    def shutdown(self):
        for runner_id in self.runner_ids():
            try:
                self._stop_service(runner_id)
            except Exception:
                pass

    def runner_ids(self):
        return tuple(get_runner_specs().keys())

    def is_enabled(self, runner_id):
        spec = get_runner_specs().get(runner_id)
        if not spec:
            return False
        getter = spec.get("get_enabled")
        if callable(getter):
            return bool(getter())
        return get_runner_enabled(runner_id, spec.get("default", False))

    def set_enabled(self, runner_id, enabled):
        spec = get_runner_specs().get(runner_id)
        if not spec:
            return False

        enabled = bool(enabled)
        setter = spec.get("set_enabled")
        if callable(setter):
            setter(enabled)
        else:
            settings.set_setting(_runner_setting_key(runner_id), enabled, namespace=RUNNER_SETTINGS_NAMESPACE)

        if enabled:
            self._start_service(runner_id)
        else:
            self._stop_service(runner_id)

        try:
            self._manager.backgroundRunnerChanged.emit(runner_id, enabled)
        except Exception:
            pass
        return True

    def _start_service(self, runner_id):
        service = self._services.get(runner_id)
        if service is not None:
            service.start()
            return
        starter = (get_runner_specs().get(runner_id) or {}).get("start")
        if callable(starter):
            starter()

    def _stop_service(self, runner_id):
        service = self._services.get(runner_id)
        if service is not None:
            service.stop()
            return
        stopper = (get_runner_specs().get(runner_id) or {}).get("stop")
        if callable(stopper):
            stopper()


def get_controller(manager=None):
    global _CONTROLLER
    if manager is None:
        from TheKeyMachine.core import runtime

        manager = runtime.get_runtime_manager()
    if _CONTROLLER is None or _CONTROLLER.parent() is not manager:
        _CONTROLLER = BackgroundRunnerController(manager)
    return _CONTROLLER


def shutdown_controller():
    global _CONTROLLER
    if _CONTROLLER is not None:
        try:
            _CONTROLLER.shutdown()
        except Exception:
            pass
        try:
            _CONTROLLER.deleteLater()
        except Exception:
            pass
    _CONTROLLER = None


def get_runner_specs() -> Dict[str, Dict[str, object]]:
    from TheKeyMachine.core import runtime
    from TheKeyMachine.tools.animation_recovery import controller as animationRecovery
    from TheKeyMachine.tools.selection import controller as selectionController
    from TheKeyMachine.maya import viewport as mayaViewport

    manager = runtime.get_runtime_manager(start=False)

    def _background_runner_signal(runner_id):
        return changed_signal_for_runner(runner_id, manager=manager)

    specs = {
        ANIMATION_RECOVERY_ID: {
            "id": ANIMATION_RECOVERY_ID,
            "label": "Animation Recovery",
            "icon": icons.animation_recovery,
            "description": "Save scene-scoped animation snapshots after animation and hierarchy changes.",
            "default": False,
            "get_enabled": animationRecovery.is_enabled,
            "set_enabled": animationRecovery.set_persisted_enabled,
            "start": lambda: animationRecovery.start(manager),
            "stop": animationRecovery.shutdown,
            "changed_signal": _background_runner_signal(ANIMATION_RECOVERY_ID),
        },
        HIDE_STATIC_CURVES_ID: {
            "id": HIDE_STATIC_CURVES_ID,
            "label": "Auto Hide Static Animation Curves",
            "icon": icons.remove_static_anim_curves,
            "description": "Automatically hide flat animation curves in the Graph Editor.",
            "default": False,
            "get_enabled": lambda: get_runner_enabled(HIDE_STATIC_CURVES_ID, False),
            "set_enabled": lambda enabled: settings.set_setting(
                _runner_setting_key(HIDE_STATIC_CURVES_ID),
                bool(enabled),
                namespace=RUNNER_SETTINGS_NAMESPACE,
            ),
            "changed_signal": _background_runner_signal(HIDE_STATIC_CURVES_ID),
        },
        CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID: {
            "id": CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID,
            "label": "Channel Box Clear Selection",
            "icon": icons.eraser,
            "description": "Clear selected Channel Box attributes when the Maya selection changes.",
            "default": False,
            "get_enabled": lambda: get_runner_enabled(CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID, False),
            "set_enabled": lambda enabled: settings.set_setting(
                _runner_setting_key(CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID),
                bool(enabled),
                namespace=RUNNER_SETTINGS_NAMESPACE,
            ),
            "changed_signal": _background_runner_signal(CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID),
        },
        CHANNELBOX_HIGHLIGHT_ID: {
            "id": CHANNELBOX_HIGHLIGHT_ID,
            "label": "Channel Box Selection Timeline Highlight",
            "icon": icons.selector,
            "description": "Tint the timeline while a Channel Box attribute is selected.",
            "default": True,
            "get_enabled": lambda: get_runner_enabled(CHANNELBOX_HIGHLIGHT_ID, True),
            "set_enabled": lambda enabled: settings.set_setting(
                _runner_setting_key(CHANNELBOX_HIGHLIGHT_ID),
                bool(enabled),
                namespace=RUNNER_SETTINGS_NAMESPACE,
            ),
            "changed_signal": _background_runner_signal(CHANNELBOX_HIGHLIGHT_ID),
        },
        CAMERA_ORBIT_SELECTION_ID: {
            "id": CAMERA_ORBIT_SELECTION_ID,
            "label": "Rotate Camera Around Selection",
            "icon": icons.follow_cam,
            "description": "Set the active viewport camera rotation point to the center of the current selection.",
            "default": False,
            "get_enabled": lambda: get_runner_enabled(CAMERA_ORBIT_SELECTION_ID, False),
            "set_enabled": lambda enabled: settings.set_setting(
                _runner_setting_key(CAMERA_ORBIT_SELECTION_ID),
                bool(enabled),
                namespace=RUNNER_SETTINGS_NAMESPACE,
            ),
            "changed_signal": _background_runner_signal(CAMERA_ORBIT_SELECTION_ID),
        },
        ANIM_LAYER_WEIGHTS_ID: {
            "id": ANIM_LAYER_WEIGHTS_ID,
            "label": "Anim Layer Weights",
            "icon": icons.customGraph,
            "description": "Plot animation-layer weight curves over the timeline; muted layers show dimmed and dashed.",
            "default": False,
            "get_enabled": lambda: get_runner_enabled(ANIM_LAYER_WEIGHTS_ID, False),
            "set_enabled": lambda enabled: settings.set_setting(
                _runner_setting_key(ANIM_LAYER_WEIGHTS_ID),
                bool(enabled),
                namespace=RUNNER_SETTINGS_NAMESPACE,
            ),
            "changed_signal": _background_runner_signal(ANIM_LAYER_WEIGHTS_ID),
        },
        SELECTOR_TOOLBAR_PIN_ID: {
            "id": SELECTOR_TOOLBAR_PIN_ID,
            "label": "Selected Object Display",
            "icon": icons.selector,
            "description": "Keep the Selected Object Display toolbutton pinned and visible on the toolbar.",
            "default": True,
            "get_enabled": selectionController.is_selector_pinned,
            "set_enabled": selectionController.set_selector_pinned,
            "changed_signal": _background_runner_signal(SELECTOR_TOOLBAR_PIN_ID),
        },
        AUTO_PAUSE_VIEWPORT_ID: {
            "id": AUTO_PAUSE_VIEWPORT_ID,
            "label": "Auto Pause Viewport",
            "icon": icons.auto_pause_viewport,
            "description": "Automatically pause viewport refresh and briefly reopen it after animation key changes.",
            "default": False,
            "get_enabled": mayaViewport.is_auto_pause_enabled,
            "set_enabled": mayaViewport.set_auto_pause_enabled,
            "changed_signal": _background_runner_signal(AUTO_PAUSE_VIEWPORT_ID),
        },
    }
    for runner_id, spec in specs.items():
        spec["command_id"] = RUNNER_COMMAND_IDS.get(runner_id, runner_id)
    return specs
