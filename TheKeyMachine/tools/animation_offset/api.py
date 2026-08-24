from maya import cmds

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtWidgets

from TheKeyMachine.core import runtime
from TheKeyMachine.maya import animation, selection
from TheKeyMachine.data import icons
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.ui.widgets.timeline as timelineWidgets


def _offset_widgets():
    # Deferred: animation_offset.widgets defines the draggable-handle tint
    # QWidget class, which is only ever needed once the tool is actually
    # activated -- not just to register its toolbar button and callbacks.
    from TheKeyMachine.tools.animation_offset import widgets

    return widgets


SUPPORTED_ATTR_TYPES = {
    "bool",
    "double",
    "doubleAngle",
    "doubleLinear",
    "enum",
    "float",
    "long",
    "short",
    "byte",
    "time",
}

SKIPPED_ATTR_TYPES = {
    "string",
    "message",
}

MANIP_CONTEXT_TOKENS = (
    "move",
    "rotate",
    "scale",
    "manip",
)
_CONTROLLER = None
_ROTATION_CHANNELS = {"rx", "ry", "rz", "rotateX", "rotateY", "rotateZ"}


def _attribute_delta(
    attr,
    baseline_value,
    current_value,
    euler_filter_enabled=False,
):
    """Return a channel delta, optionally correcting signed Euler wrapping."""
    delta = current_value - baseline_value
    full_turn = animation.euler_full_turn()
    if (
        euler_filter_enabled
        and attr in _ROTATION_CHANNELS
        and abs(delta) > full_turn * 0.5
    ):
        half_turn = full_turn * 0.5
        return (delta + half_turn) % full_turn - half_turn
    return delta


class AnimationOffsetController(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)

    STATE_IDLE = "idle"
    STATE_ARMED = "armed"
    STATE_APPLYING = "applying"
    STATE_RESNAPSHOT_PENDING = "resnapshot_pending"
    STATE_TRACKING_MANIP = "tracking_manip"

    POLL_INTERVAL_MS = 70
    RESNAPSHOT_DELAY_MS = 120

    def __init__(self, manager):
        super().__init__(manager)
        self._owner = manager
        self._runtime_manager = manager
        self._enabled = False
        self._state = self.STATE_IDLE
        self._time_range = None
        self._tint_key = "animation_offset_range"
        self._selection_signature = ()
        self._snapshot_time = None
        self._baseline = {}
        self._pending_manip_plugs = set()
        self._pending_resnapshot_update_range = False
        self._settling_after_resnapshot = False

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

        self._resnapshot_timer = QtCore.QTimer(self)
        self._resnapshot_timer.setSingleShot(True)
        self._resnapshot_timer.setInterval(self.RESNAPSHOT_DELAY_MS)
        self._resnapshot_timer.timeout.connect(self._perform_deferred_resnapshot)
        
        self._offset_operation_context = None
        self._offset_operation = None
        self._selection_snapshot = None

    def is_enabled(self):
        return self._enabled

    def _selection(self):
        return selection.get_selected_objects(long=True)

    def _selection_signature_value(self, selection=None):
        if selection is None:
            selection = self._selection()
        return tuple(sorted(selection))

    def _current_time(self):
        return int(cmds.currentTime(query=True))

    def _resolve_locked_time_range(self, snapshot=None):
        snapshot = snapshot or self._selection_snapshot
        if snapshot is None:
            return None
        if snapshot.time_slider_range:
            return tuple(snapshot.time_slider_range)
        graph_frames = [
            float(frame) for _curve, frame in snapshot.graph_keyframes
        ]
        if graph_frames:
            return min(graph_frames), max(graph_frames)
        return tuple(snapshot.playback_range)

    def _on_tint_range_changed(self, timerange):
        self._time_range = tuple(timerange)
        self._resnapshot(update_range=False)

    def _is_in_locked_range(self):
        if not self._time_range:
            return False
        current_time = self._current_time()
        return self._time_range[0] <= current_time <= self._time_range[1]

    def _current_context_name(self):
        try:
            return cmds.currentCtx() or ""
        except Exception:
            return ""

    def _is_manip_context(self):
        context_name = self._current_context_name().lower()
        return any(token in context_name for token in MANIP_CONTEXT_TOKENS)

    def _mouse_buttons_down(self):
        app = QtWidgets.QApplication.instance()
        if not app:
            return False
        try:
            buttons = app.mouseButtons()
        except Exception:
            return False
        return bool(buttons & (QtCore.Qt.LeftButton | QtCore.Qt.MiddleButton | QtCore.Qt.RightButton))

    def _is_manip_edit_active(self):
        return self._is_manip_context() and self._mouse_buttons_down()

    def _connect_runtime_manager(self):
        manager = self._runtime_manager
        toolCommon.replace_tracked_connections(
            self,
            "_runtime_manager_relays",
            (
                (manager.selection_changed, self._on_context_changed),
                (manager.time_changed, self._on_context_changed),
                (manager.undo_performed, self._on_context_changed),
                (manager.scene_opened, self._on_scene_reset),
                (manager.scene_new, self._on_scene_reset),
            ),
            parent=self,
        )

    def _disconnect_runtime_manager(self):
        toolCommon.clear_tracked_connections(self, "_runtime_manager_relays")

    def _on_context_changed(self):
        if not self._can_resnapshot_from_event():
            return
        self._request_resnapshot(update_range=False)

    def _on_scene_reset(self):
        if not self._enabled:
            return
        try:
            self._finish_offset_operation()
        except Exception:
            pass
        self.deactivate()

    def _begin_offset_operation(self):
        if self._offset_operation_context is not None:
            return True
        context = toolCommon.tool_operation(
            tool_id="animation_offset",
            label="Animation Offset",
            progress=False,
            undo=True,
            undo_name="Animation Offset",
            suspend_refresh=False,
            show_success_message=False,
            selection_snapshot=self._selection_snapshot,
        )
        operation = context.__enter__()
        self._offset_operation_context = context
        self._offset_operation = operation
        return True

    def _finish_offset_operation(self):
        context = self._offset_operation_context
        if context is None:
            return
        try:
            context.__exit__(None, None, None)
        finally:
            self._offset_operation_context = None
            self._offset_operation = None

    def _iter_candidate_attrs(self, obj):
        try:
            attrs = cmds.listAttr(
                obj,
                keyable=True,
                scalar=True,
                unlocked=True,
                settable=True,
            ) or []
        except Exception:
            attrs = []
        yield from dict.fromkeys(attrs)

    def _get_attr_type(self, plug):
        try:
            return cmds.getAttr(plug, type=True)
        except Exception:
            return None

    def _is_supported_plug(self, plug):
        try:
            if not cmds.objExists(plug):
                return False
            if not cmds.getAttr(plug, settable=True):
                return False
            if cmds.getAttr(plug, lock=True):
                return False
        except Exception:
            return False

        attr_type = self._get_attr_type(plug)
        if attr_type in SKIPPED_ATTR_TYPES:
            return False
        if attr_type not in SUPPORTED_ATTR_TYPES:
            return False
        return True

    def _numeric_value(self, value):
        current = value
        while isinstance(current, (list, tuple)) and len(current) == 1:
            current = current[0]
        if isinstance(current, bool):
            return float(int(current)), True
        if isinstance(current, (list, tuple)):
            return None, False
        if not isinstance(current, (int, float)):
            return None, False
        return float(current), True

    def _get_plug_value(self, plug, time=None):
        try:
            if time is None:
                raw_value = cmds.getAttr(plug)
            else:
                raw_value = cmds.getAttr(plug, time=time)
        except Exception:
            return None, False
        return self._numeric_value(raw_value)

    def _plug_name(self, obj, attr):
        return "{}.{}".format(obj, attr)

    def _get_keyed_values_in_range(self, obj, attr):
        if not self._time_range:
            return {}

        try:
            keyframes = (
                cmds.keyframe(
                    obj,
                    attribute=attr,
                    query=True,
                    time=(self._time_range[0], self._time_range[1]),
                    timeChange=True,
                )
                or []
            )
        except Exception:
            return {}

        keyed_values = {}
        for frame in keyframes:
            try:
                frame_number = int(round(frame))
            except Exception:
                continue
            value, ok = self._get_plug_value(self._plug_name(obj, attr), time=frame_number)
            if not ok:
                continue
            keyed_values[frame_number] = value
        return keyed_values

    def _capture_object_snapshot(self, obj):
        obj_snapshot = {}
        for attr in self._iter_candidate_attrs(obj):
            plug = self._plug_name(obj, attr)
            # _iter_candidate_attrs already asks Maya for keyable, scalar,
            # unlocked, settable attributes. Reading the value is the final
            # numeric/type filter; repeating objExists/settable/lock/type
            # queries here multiplied activation cost by every selected plug.
            current_value, ok = self._get_plug_value(plug)
            if not ok:
                continue

            obj_snapshot[attr] = {
                "current": current_value,
                # Key values are expensive and unnecessary until this exact
                # attribute changes. Capture them lazily in _apply_changes.
                "keys": None,
            }
        return obj_snapshot

    def _capture_current_values(self):
        current_values = {}
        for obj, attrs in self._baseline.items():
            if not cmds.objExists(obj):
                continue
            obj_values = {}
            for attr in attrs.keys():
                plug = self._plug_name(obj, attr)
                value, ok = self._get_plug_value(plug)
                if not ok:
                    continue
                obj_values[attr] = value
            if obj_values:
                current_values[obj] = obj_values
        return current_values

    def _find_changed_plugs(self, current_values):
        changed_plugs = set()
        for obj, attrs in current_values.items():
            baseline_attrs = self._baseline.get(obj, {})
            for attr, current_value in attrs.items():
                baseline_data = baseline_attrs.get(attr)
                if not baseline_data:
                    continue
                baseline_value = baseline_data.get("current")
                if baseline_value is None:
                    continue
                if abs(current_value - baseline_value) > 1e-6:
                    changed_plugs.add((obj, attr))
        return changed_plugs

    def _resnapshot(self, update_range=False, snapshot=None):
        self._selection_snapshot = snapshot or animation.capture_selection_snapshot()
        if update_range or self._time_range is None:
            self._time_range = self._resolve_locked_time_range(
                self._selection_snapshot
            )

        selected_objects = list(self._selection_snapshot.objects)
        self._selection_signature = self._selection_signature_value(
            selected_objects
        )
        self._snapshot_time = self._current_time()
        baseline = {}

        for obj in selected_objects:
            if not cmds.objExists(obj):
                continue
            obj_snapshot = self._capture_object_snapshot(obj)
            if obj_snapshot:
                baseline[obj] = obj_snapshot

        self._baseline = baseline
        self._pending_manip_plugs.clear()
        self._state = self.STATE_ARMED if self._enabled else self.STATE_IDLE

    def _can_resnapshot_from_event(self):
        return self._enabled and self._state != self.STATE_APPLYING

    def _request_resnapshot(self, update_range=False):
        self._finish_offset_operation()
        self._pending_resnapshot_update_range = self._pending_resnapshot_update_range or bool(update_range)
        self._pending_manip_plugs.clear()
        self._settling_after_resnapshot = False
        self._state = self.STATE_RESNAPSHOT_PENDING if self._enabled else self.STATE_IDLE
        self._resnapshot_timer.start()

    def _perform_deferred_resnapshot(self):
        if not self._enabled:
            return
        update_range = self._pending_resnapshot_update_range
        self._pending_resnapshot_update_range = False
        self._resnapshot(update_range=update_range)
        self._settling_after_resnapshot = True

    def _ensure_driver_key(self, obj, attr, current_value):
        current_time = self._current_time()
        try:
            current_keys = (
                cmds.keyframe(
                    obj,
                    attribute=attr,
                    query=True,
                    time=(current_time, current_time),
                    timeChange=True,
                )
                or []
            )
        except Exception:
            current_keys = []

        if any(int(round(frame)) == current_time for frame in current_keys):
            return

        try:
            cmds.setKeyframe(obj, attribute=attr, time=(current_time,), value=current_value)
        except Exception:
            pass

    def _apply_changes(self, changed_plugs):
        if not self._enabled or not changed_plugs:
            return False
        if not self._is_in_locked_range():
            return False

        self._begin_offset_operation()
        self._state = self.STATE_APPLYING
        current_time = self._current_time()
        any_applied = False
        from TheKeyMachine.tools.global_tools import controller as global_tools

        try:
            euler_filter_enabled = global_tools.is_euler_filter_enabled()
        except Exception:
            euler_filter_enabled = False

        try:
            with runtime.suppress_undo_notifications():
                for obj, attr in sorted(changed_plugs):
                    if not cmds.objExists(obj):
                        continue

                    baseline_data = self._baseline.get(obj, {}).get(attr)
                    if not baseline_data:
                        continue

                    plug = self._plug_name(obj, attr)
                    if not self._is_supported_plug(plug):
                        continue

                    current_value, ok = self._get_plug_value(plug)
                    if not ok:
                        continue

                    baseline_current = baseline_data.get("current")
                    if baseline_current is None:
                        continue

                    raw_delta = current_value - baseline_current
                    delta = _attribute_delta(
                        attr,
                        baseline_current,
                        current_value,
                        euler_filter_enabled=euler_filter_enabled,
                    )
                    if abs(delta) <= 1e-6:
                        continue

                    driver_value = baseline_current + delta
                    if abs(delta - raw_delta) > 1e-6:
                        # Keep the current Euler key on the same numeric turn
                        # as the rest of the curve. -179 and 181 represent the
                        # same orientation, but only 181 preserves continuity
                        # when the other keys receive a +2 degree offset.
                        try:
                            cmds.setAttr(plug, driver_value)
                            cmds.setKeyframe(
                                obj,
                                attribute=attr,
                                time=(current_time,),
                                value=driver_value,
                            )
                        except Exception:
                            continue
                    else:
                        self._ensure_driver_key(obj, attr, current_value)

                    keyed_values = baseline_data.get("keys")
                    if keyed_values is None:
                        keyed_values = self._get_keyed_values_in_range(
                            obj, attr
                        )
                        baseline_data["keys"] = keyed_values
                    keyed_values = dict(keyed_values or {})
                    other_frames = [
                        frame for frame in keyed_values.keys() if self._time_range[0] <= frame <= self._time_range[1] and frame != current_time
                    ]

                    for frame in sorted(other_frames):
                        base_value = keyed_values.get(frame)
                        if base_value is None:
                            continue
                        try:
                            cmds.setKeyframe(obj, attribute=attr, time=(frame,), value=base_value + delta)
                            any_applied = True
                        except Exception:
                            continue
        finally:
            self._state = self.STATE_ARMED if self._enabled else self.STATE_IDLE

        try:
            self._resnapshot(update_range=False)
        finally:
            self._finish_offset_operation()
        return any_applied

    def _poll(self):
        if not self._enabled or not QtCompat.isValid(self._owner):
            return
        if self._state in (self.STATE_APPLYING, self.STATE_RESNAPSHOT_PENDING):
            return

        current_selection_signature = self._selection_signature_value()
        if current_selection_signature != self._selection_signature:
            self._request_resnapshot(update_range=False)
            return

        if self._snapshot_time != self._current_time():
            self._pending_manip_plugs.clear()
            self._request_resnapshot(update_range=False)
            return

        current_values = self._capture_current_values()
        if self._settling_after_resnapshot:
            self._settling_after_resnapshot = False
            changed_plugs = self._find_changed_plugs(current_values)
            if changed_plugs:
                self._request_resnapshot(update_range=False)
            return

        if not self._is_in_locked_range():
            if self._state == self.STATE_TRACKING_MANIP and not self._is_manip_edit_active():
                self._pending_manip_plugs.clear()
                self._resnapshot(update_range=False)
            return

        changed_plugs = self._find_changed_plugs(current_values)

        if self._state == self.STATE_TRACKING_MANIP:
            if changed_plugs:
                self._begin_offset_operation()
                self._pending_manip_plugs.update(changed_plugs)

            if not self._is_manip_edit_active():
                pending_plugs = set(self._pending_manip_plugs or changed_plugs)
                self._pending_manip_plugs.clear()
                if pending_plugs:
                    self._apply_changes(pending_plugs)
                else:
                    self._finish_offset_operation()
            return

        if not changed_plugs:
            return

        if self._is_manip_edit_active():
            self._begin_offset_operation()
            self._state = self.STATE_TRACKING_MANIP
            self._pending_manip_plugs.update(changed_plugs)
            return

        self._apply_changes(changed_plugs)

    def activate(self):
        self._enabled = True
        snapshot = animation.capture_selection_snapshot()
        self._selection_snapshot = snapshot
        locked_range = self._resolve_locked_time_range(snapshot)
        if locked_range:
            self._time_range = locked_range
        self._connect_runtime_manager()
        self._resnapshot(
            update_range=self._time_range is None,
            snapshot=snapshot,
        )
        _offset_widgets().show_animation_offset_tint(
            timerange=self._time_range,
            color=COLORS.toolbar.purple.hex,
            owner=self._owner,
            key=self._tint_key,
            center_line=True,
            icon=icons.animation_offset,
            icon_scale=1.15,
            range_changed=self._on_tint_range_changed,
        )
        self._poll_timer.start()

    def deactivate(self):
        self._enabled = False
        self._disconnect_runtime_manager()
        self._poll_timer.stop()
        self._resnapshot_timer.stop()
        self._runtime_manager.clear_managed_widget(self._tint_key)
        self._state = self.STATE_IDLE
        self._selection_signature = ()
        self._snapshot_time = None
        self._baseline = {}
        self._pending_manip_plugs.clear()
        self._pending_resnapshot_update_range = False
        self._settling_after_resnapshot = False
        self._time_range = None
        self._finish_offset_operation()
        self._selection_snapshot = None
        self.stateChanged.emit(False)
        self._runtime_manager.set_tool_state("animation_offset", False)

    def toggle(self, checked=None):
        if checked is None:
            checked = not self._enabled

        checked = bool(checked)
        self._enabled = checked

        if checked:
            try:
                self.activate()
            except Exception:
                self._enabled = False
                self._finish_offset_operation()
                raise
            self.stateChanged.emit(self.is_enabled())
            self._runtime_manager.set_tool_state("animation_offset", self.is_enabled())
        else:
            try:
                self.deactivate()
            finally:
                self._finish_offset_operation()


def get_controller(create=True):
    global _CONTROLLER
    if _CONTROLLER is not None and not QtCompat.isValid(_CONTROLLER):
        _CONTROLLER = None
    if _CONTROLLER is None and create:
        _CONTROLLER = AnimationOffsetController(runtime.get_runtime_manager())
    return _CONTROLLER


def is_enabled():
    controller = get_controller(create=False)
    return bool(controller and controller.is_enabled())


def toggle(checked=None, *_args):
    return get_controller().toggle(checked)


def cleanup():
    global _CONTROLLER
    controller = get_controller(create=False)
    _CONTROLLER = None
    if controller is not None:
        controller.toggle(False)
        controller.deleteLater()
