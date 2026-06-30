"""
Background runner registry.

Background runners are persistent helpers and automatic switches that should be
owned by the RuntimeManager rather than individual toolbar widgets.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from maya import cmds

from TheKeyMachine.Qt import QtCore, QtGui  # type: ignore

import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.core.openMayaUtils as omutils
from TheKeyMachine.data import icons
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi
from TheKeyMachine.widgets import timeline as timelineWidgets


RUNNER_SETTINGS_NAMESPACE = "background_runners"
CHANNELBOX_HIGHLIGHT_ID = "channelbox_selection_highlight"
CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID = "channelbox_clear_on_selection_change"
CAMERA_ORBIT_SELECTION_ID = "camera_orbit_selection"
CHANNELBOX_TINT_KEY = "background_runner:channelbox_selection_highlight"

_CONTROLLER: Optional["BackgroundRunnerController"] = None


def _runner_setting_key(runner_id):
    return "runner_{}".format(runner_id)


def get_runner_enabled(runner_id, default=False):
    return bool(settings.get_setting(_runner_setting_key(runner_id), default, namespace=RUNNER_SETTINGS_NAMESPACE))


def set_runner_enabled(runner_id, enabled):
    controller = get_controller()
    controller.set_enabled(runner_id, enabled)


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


def _get_overshoot_enabled():
    return bool(settings.get_setting("sliders_overshoot", False))


def _set_overshoot_enabled(enabled):
    import TheKeyMachine.core.runtimeManager as runtime

    settings.set_setting("sliders_overshoot", bool(enabled))
    runtime.get_runtime_manager().overshootChanged.emit(bool(enabled))


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


def _set_camera_center_of_interest(camera_transform, camera_shape, center):
    if not camera_transform or not camera_shape:
        return False
    try:
        if not cmds.attributeQuery("centerOfInterest", node=camera_shape, exists=True):
            return False
        camera_position = cmds.xform(camera_transform, query=True, worldSpace=True, translation=True)
        distance = math.sqrt(
            (camera_position[0] - center[0]) ** 2
            + (camera_position[1] - center[1]) ** 2
            + (camera_position[2] - center[2]) ** 2
        )
        return omutils.set_plug_double(camera_shape, "centerOfInterest", distance)
    except Exception:
        return False


def _set_camera_orbit_point_to_selection():
    center = _selection_center()
    if center is None:
        return False

    camera_transform, camera_shape = _current_camera_nodes()
    if not camera_transform and not camera_shape:
        return False

    changed = False
    for node in (camera_shape, camera_transform):
        changed = omutils.set_plug_vector(node, "tumblePivot", center) or changed
        changed = omutils.set_plug_vector(node, "tumblePivotTranslate", center) or changed
    changed = _set_camera_center_of_interest(camera_transform, camera_shape, center) or changed
    changed = omutils.set_plug_vector(camera_transform, "rotatePivot", center) or changed
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
    TRANSFORM_SETTLE_MS = 180

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

    def _schedule_update(self, *_args, delay_ms=0, restart=False):
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
        self._schedule_update(delay_ms=self.TRANSFORM_SETTLE_MS, restart=True)

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


class BackgroundRunnerController(QtCore.QObject):
    def __init__(self, manager):
        super().__init__(manager)
        self._manager = manager
        self._services = {
            CHANNELBOX_HIGHLIGHT_ID: ChannelBoxSelectionHighlightRunner(manager, parent=self),
            CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID: ChannelBoxClearOnSelectionChangeRunner(manager, parent=self),
            CAMERA_ORBIT_SELECTION_ID: CameraOrbitSelectionRunner(manager, parent=self),
        }

    def start_enabled(self):
        for runner_id in self.runner_ids():
            if self.is_enabled(runner_id):
                self._start_service(runner_id)

    def shutdown(self):
        for runner_id in self.runner_ids():
            self._stop_service(runner_id)

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

        if runner_id in self._services:
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

    def _stop_service(self, runner_id):
        service = self._services.get(runner_id)
        if service is not None:
            service.stop()


def get_controller(manager=None):
    global _CONTROLLER
    if manager is None:
        import TheKeyMachine.core.runtimeManager as runtime

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
    import TheKeyMachine.core.runtimeManager as runtime

    manager = runtime.get_runtime_manager(start=False)

    def _background_runner_signal(runner_id):
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

    return {
        CHANNELBOX_HIGHLIGHT_ID: {
            "id": CHANNELBOX_HIGHLIGHT_ID,
            "label": "Highlight Channel Box Selection",
            "menu_label": "Highlight Channel Box Selection",
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
        CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID: {
            "id": CHANNELBOX_CLEAR_ON_SELECTION_CHANGE_ID,
            "label": "Clear Channel Box Selection",
            "menu_label": "Clear Channel Box Selection",
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
        CAMERA_ORBIT_SELECTION_ID: {
            "id": CAMERA_ORBIT_SELECTION_ID,
            "label": "Rotate Camera Around Selection",
            "menu_label": "Rotate Camera Around Selection",
            "icon": icons.camera,
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
        "attribute_switcher_euler_filter": {
            "id": "attribute_switcher_euler_filter",
            "label": "Auto Euler Filter",
            "menu_label": "Auto Euler Filter",
            "icon": icons.euler_filter,
            "description": "Apply Euler filtering after Attribute Switcher changes rotation order.",
            "get_enabled": attributeSwitcherApi.is_euler_filter_enabled,
            "set_enabled": attributeSwitcherApi.set_euler_filter_enabled,
            "changed_signal": manager.eulerFilterChanged,
        },
        "overshoot_sliders": {
            "id": "overshoot_sliders",
            "label": "Overshoot Sliders",
            "menu_label": "Overshoot Sliders",
            "icon": icons.sliders_overshoot,
            "description": "Set slider ranges to -150/150 instead of -100/100.",
            "get_enabled": _get_overshoot_enabled,
            "set_enabled": _set_overshoot_enabled,
            "changed_signal": manager.overshootChanged,
        },
        "custom_graph": {
            "id": "custom_graph",
            "label": "Graph Editor Toolbar",
            "menu_label": "Show Graph Editor Toolbar",
            "icon": icons.customGraph,
            "description": "Show the TKM toolbar in the Graph Editor.",
            "get_enabled": graphToolbarApi.get_graph_toolbar_checkbox_state,
            "set_enabled": lambda enabled: graphToolbarApi.set_graph_toolbar_enabled(bool(enabled), apply=True),
            "changed_signal": graphToolbarApi.custom_graph_bus.graph_toolbar_enabled_changed,
        },
    }
