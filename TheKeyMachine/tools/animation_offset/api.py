from maya import cmds

try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import isValid
except Exception:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import isValid

import TheKeyMachine.core.runtime_manager as runtime
import TheKeyMachine.mods.mediaMod as media
from TheKeyMachine.tools import colors as toolColors
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.timeline as timelineWidgets
from TheKeyMachine.widgets import util as wutil


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


class AnimationOffsetController(QtCore.QObject):
    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner
        self._runtime_manager = runtime.get_runtime_manager()
        self._enabled = False
        self._state = "idle"
        self._time_range = None
        self._tint_key = "animation_offset_range"
        self._selection_signature = ()
        self._baseline = {}
        self._last_values = {}
        self._pending_manip_plugs = set()
        self._tint_color = toolColors.purple

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(70)
        self._poll_timer.timeout.connect(self._poll)

    def is_enabled(self):
        return self._enabled

    def _selection(self):
        return wutil.get_selected_objects(long=True)

    def _selection_signature_value(self, selection=None):
        if selection is None:
            selection = self._selection()
        return tuple(sorted(selection))

    def _current_time(self):
        return int(cmds.currentTime(query=True))

    def _resolve_locked_time_range(self):
        selected_range = timelineWidgets.get_selected_time_slider_range()
        if selected_range:
            return selected_range
        return timelineWidgets.get_playback_range()

    def _resolve_tint_color(self):
        return self._tint_color

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
        return bool(
            buttons
            & (
                QtCore.Qt.LeftButton
                | QtCore.Qt.MiddleButton
                | QtCore.Qt.RightButton
            )
        )

    def _is_manip_edit_active(self):
        return self._is_manip_context() and self._mouse_buttons_down()

    def _connect_runtime_manager(self):
        manager = self._runtime_manager
        try:
            manager.selection_changed.connect(self._on_selection_changed)
        except Exception:
            pass
        try:
            manager.time_changed.connect(self._on_time_changed)
        except Exception:
            pass
        try:
            manager.undo_performed.connect(self._on_undo_performed)
        except Exception:
            pass
        try:
            manager.scene_opened.connect(self._on_scene_reset)
        except Exception:
            pass
        try:
            manager.scene_new.connect(self._on_scene_reset)
        except Exception:
            pass

    def _disconnect_runtime_manager(self):
        manager = self._runtime_manager
        try:
            manager.selection_changed.disconnect(self._on_selection_changed)
        except Exception:
            pass
        try:
            manager.time_changed.disconnect(self._on_time_changed)
        except Exception:
            pass
        try:
            manager.undo_performed.disconnect(self._on_undo_performed)
        except Exception:
            pass
        try:
            manager.scene_opened.disconnect(self._on_scene_reset)
        except Exception:
            pass
        try:
            manager.scene_new.disconnect(self._on_scene_reset)
        except Exception:
            pass

    def _on_selection_changed(self):
        if not self._enabled or self._state == "applying":
            return
        self._resnapshot(update_range=False)

    def _on_time_changed(self):
        if not self._enabled or self._state == "applying":
            return
        self._resnapshot(update_range=False)

    def _on_undo_performed(self):
        if not self._enabled or self._state == "applying":
            return
        self._resnapshot(update_range=False)

    def _on_scene_reset(self):
        if not self._enabled:
            return
        self.deactivate()
        try:
            toolCommon.close_undo_chunk()
        except Exception:
            pass

    def _iter_candidate_attrs(self, obj):
        seen = set()
        for attr in cmds.listAttr(obj, keyable=True) or []:
            children = []
            try:
                children = cmds.attributeQuery(attr, node=obj, listChildren=True) or []
            except Exception:
                children = []
            leaf_attrs = children or [attr]
            for leaf_attr in leaf_attrs:
                if leaf_attr in seen:
                    continue
                seen.add(leaf_attr)
                yield leaf_attr

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
            keyframes = cmds.keyframe(
                obj,
                attribute=attr,
                query=True,
                time=(self._time_range[0], self._time_range[1]),
                timeChange=True,
            ) or []
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
            if not self._is_supported_plug(plug):
                continue

            current_value, ok = self._get_plug_value(plug)
            if not ok:
                continue

            obj_snapshot[attr] = {
                "current": current_value,
                "keys": self._get_keyed_values_in_range(obj, attr),
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

    def _resnapshot(self, update_range=False):
        if update_range or self._time_range is None:
            self._time_range = self._resolve_locked_time_range()

        selection = self._selection()
        self._selection_signature = self._selection_signature_value(selection)
        baseline = {}

        for obj in selection:
            if not cmds.objExists(obj):
                continue
            obj_snapshot = self._capture_object_snapshot(obj)
            if obj_snapshot:
                baseline[obj] = obj_snapshot

        self._baseline = baseline
        self._last_values = self._capture_current_values()
        self._pending_manip_plugs.clear()
        self._state = "armed" if self._enabled else "idle"

    def _ensure_driver_key(self, obj, attr, current_value):
        current_time = self._current_time()
        try:
            current_keys = cmds.keyframe(
                obj,
                attribute=attr,
                query=True,
                time=(current_time, current_time),
                timeChange=True,
            ) or []
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

        self._state = "applying"
        current_time = self._current_time()
        any_applied = False

        try:
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

                delta = current_value - baseline_current
                if abs(delta) <= 1e-6:
                    continue

                self._ensure_driver_key(obj, attr, current_value)

                keyed_values = dict(baseline_data.get("keys") or {})
                other_frames = [
                    frame
                    for frame in keyed_values.keys()
                    if self._time_range[0] <= frame <= self._time_range[1] and frame != current_time
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
            self._state = "armed" if self._enabled else "idle"

        self._resnapshot(update_range=False)
        return any_applied

    def _poll(self):
        if not self._enabled or not isValid(self._owner):
            return
        if self._state == "applying":
            return

        current_selection_signature = self._selection_signature_value()
        if current_selection_signature != self._selection_signature:
            self._resnapshot(update_range=False)
            return

        current_values = self._capture_current_values()
        self._last_values = current_values

        if not self._is_in_locked_range():
            if self._state == "tracking_manip" and not self._is_manip_edit_active():
                self._pending_manip_plugs.clear()
                self._resnapshot(update_range=False)
            return

        changed_plugs = self._find_changed_plugs(current_values)

        if self._state == "tracking_manip":
            if changed_plugs:
                self._pending_manip_plugs.update(changed_plugs)

            if not self._is_manip_edit_active():
                pending_plugs = set(self._pending_manip_plugs or changed_plugs)
                self._pending_manip_plugs.clear()
                self._apply_changes(pending_plugs)
            return

        if not changed_plugs:
            return

        if self._is_manip_edit_active():
            self._state = "tracking_manip"
            self._pending_manip_plugs.update(changed_plugs)
            return

        self._apply_changes(changed_plugs)

    def activate(self):
        self._enabled = True
        cmds.select(wutil.get_selected_objects())
        self._connect_runtime_manager()
        self._resnapshot(update_range=True)
        timelineWidgets.show_timeline_tint(
            timerange=self._time_range,
            color=self._resolve_tint_color(),
            duration_ms=None,
            owner=self._owner,
            key=self._tint_key,
            center_line=True,
            icon_path=media.animation_offset_image,
            icon_scale=1.15,
        )
        self._poll_timer.start()

    def deactivate(self):
        self._enabled = False
        self._disconnect_runtime_manager()
        self._poll_timer.stop()
        timelineWidgets.clear_timeline_tint(self._tint_key)
        self._state = "idle"
        self._selection_signature = ()
        self._baseline = {}
        self._last_values = {}
        self._pending_manip_plugs.clear()
        self._time_range = None

    def toggle(self, checked=None, button_widget=None):
        if checked is None:
            checked = not self._enabled

        checked = bool(checked)
        self._enabled = checked

        if button_widget and isValid(button_widget) and hasattr(button_widget, "get_tint_color"):
            try:
                tint_color = button_widget.get_tint_color()
            except Exception:
                tint_color = None
            if tint_color is not None:
                self._tint_color = tint_color

        if button_widget and isValid(button_widget):
            button_widget.blockSignals(True)
            button_widget.setChecked(checked)
            button_widget.blockSignals(False)

        if checked:
            toolCommon.open_undo_chunk(tool_id="animation_offset")
            self.activate()
        else:
            self.deactivate()
            try:
                toolCommon.close_undo_chunk()
            except Exception:
                pass
