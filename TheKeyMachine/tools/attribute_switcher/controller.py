"""Scene analysis and mutation for the Attribute Switcher."""

from maya import cmds

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.core import openMayaUtils as open_maya
from TheKeyMachine.core import toolbox
import TheKeyMachine.mods.selectionMod as selectionMod
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools.gimbal_fixer.controller import GimbalAnalyzer
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import timeline as timelineWidgets


ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE = "attribute_switcher_window"
ATTRIBUTE_SWITCHER_GEOMETRY_KEY = "attribute_switcher_geometry"
ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY = "attribute_switcher_stays_on_top"
ROTATE_ORDER_LIGHTNING_MODE_KEY = "rotate_order_lightning_mode"

ROTATE_ORDER_OPTIONS = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")


def _as_bool(value):
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value) if isinstance(value, (bool, int)) else False


class AttributeSwitcherController:
    """Own Maya state, analysis, settings, and scene edits for one view."""

    ROTATE_AXES = ("rotateX", "rotateY", "rotateZ")

    def __init__(self, view):
        self.view = view
        self.analyzer = GimbalAnalyzer()
        self.runtime_manager = runtime.get_runtime_manager()
        self._callbacks_connected = False

    # Settings -------------------------------------------------------------

    def load_settings(self):
        return {
            "namespace_display": _as_bool(self._setting("namespace_display", False)),
            "all_frames": _as_bool(self._setting("all_frames", False)),
            "euler_filter": _as_bool(self._setting("euler_filter", True)),
            "show_rotate_order": _as_bool(self._setting("show_rotate_order", True)),
        }

    @staticmethod
    def _setting(key, default=None):
        return settings.get_setting(
            key, default, namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
        )

    def set_setting(self, key, state, refresh=False):
        state = bool(state)
        settings.set_setting(
            key, state, namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
        )
        setattr(self.view, key, state)
        if key == "euler_filter":
            self.runtime_manager.eulerFilterChanged.emit(state)
        if refresh:
            self.view.refresh(force=True)

    def saved_geometry(self):
        return self._setting(ATTRIBUTE_SWITCHER_GEOMETRY_KEY)

    def save_geometry(self, geometry):
        settings.set_setting(
            ATTRIBUTE_SWITCHER_GEOMETRY_KEY,
            geometry,
            namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
        )

    def stays_on_top(self):
        return _as_bool(self._setting(ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY, False))

    def rotate_order_lightning_enabled(self):
        """Whether rotate order conversion uses the fast, math-only path.

        Defaults to off (Normal mode): the frame-by-frame, world-matrix-
        preserving conversion that works with every rig, including
        animation layers, driven keys, and expressions. Lightning mode is
        an explicit opt-in from the toolbar button's right-click menu.
        """
        return _as_bool(self._setting(ROTATE_ORDER_LIGHTNING_MODE_KEY, False))

    # Runtime and selection ------------------------------------------------

    def connect_runtime(self):
        if self._callbacks_connected:
            return
        toolCommon.replace_tracked_connections(
            self.view,
            "_runtime_manager_relays",
            (
                (self.runtime_manager.selection_changed, self.view.refresh),
                (self.runtime_manager.time_changed, self.view.refresh),
                (self.runtime_manager.undo_performed, self.view.refresh),
                (self.runtime_manager.scene_opened, self.view.refresh),
                (self.runtime_manager.scene_new, self.view.refresh),
            ),
            parent=self.view,
        )
        self._callbacks_connected = True

    def disconnect_runtime(self):
        if not self._callbacks_connected:
            return
        toolCommon.clear_tracked_connections(self.view, "_runtime_manager_relays")
        self._callbacks_connected = False

    @staticmethod
    def selected_nodes(long=False):
        return selectionMod.get_selected_objects(long=long)

    @staticmethod
    def select(nodes):
        cmds.select(nodes, replace=True)

    @staticmethod
    def object_exists(node):
        return cmds.objExists(node)

    @staticmethod
    def warning(message):
        cmds.warning(message)

    # Analysis -------------------------------------------------------------

    def analyze(self, nodes, show_rotate_order=True):
        """Return switchable connected attributes grouped across nodes."""
        catalog = {}
        for node in nodes:
            attributes = cmds.listAttr(node, ud=True) or []
            attributes = [
                attr
                for attr in attributes
                if not cmds.attributeQuery(attr, node=node, hidden=True)
            ]
            if (
                show_rotate_order
                and cmds.attributeQuery("rotateOrder", node=node, exists=True)
                and "rotateOrder" not in attributes
            ):
                attributes.append("rotateOrder")

            for attribute in attributes:
                self._analyze_attribute(
                    catalog, node, attribute, show_rotate_order
                )
        return catalog

    def _analyze_attribute(self, catalog, node, attribute, show_rotate_order):
        try:
            attribute_type = cmds.attributeQuery(
                attribute, node=node, attributeType=True
            )
        except Exception:
            return

        is_enum = attribute_type == "enum"
        if not is_enum and attribute_type not in ("bool", "long", "double", "float"):
            return

        options, minimum, maximum = self._attribute_range(
            node, attribute, attribute_type
        )
        if options is None:
            return
        if attribute != "rotateOrder" and not self._is_connected(node, attribute):
            return

        catalog_key = attribute
        if is_enum and attribute != "rotateOrder":
            if tuple(option.lower() for option in options) == ROTATE_ORDER_OPTIONS:
                catalog_key = "rotateOrder"

        entry = catalog.setdefault(
            catalog_key,
            {
                "objects": {},
                "long": cmds.attributeQuery(attribute, node=node, niceName=True),
            },
        )
        existing = entry["objects"].get(node)
        if existing:
            if attribute == "rotateOrder":
                existing["attr"] = attribute
            return

        plug = "{}.{}".format(node, attribute)
        current_value = float(cmds.getAttr(plug))
        keyed_values = sorted(
            set(
                float(value)
                for value in (
                    cmds.keyframe(plug, query=True, valueChange=True) or []
                )
            )
        )
        object_data = {
            "enum": options,
            "marked": keyed_values or [current_value],
            "keyed_values": keyed_values,
            "current": current_value,
            "attr": attribute,
            "type": attribute_type,
            "min": float(minimum),
            "max": float(maximum),
        }
        if catalog_key == "rotateOrder" and show_rotate_order:
            object_data["gimbal"] = self.analyzer.analyze(node)
        entry["objects"][node] = object_data

    @staticmethod
    def _attribute_range(node, attribute, attribute_type):
        if attribute_type == "enum":
            raw = cmds.attributeQuery(attribute, node=node, listEnum=True) or []
            if not raw:
                return None, 0, 0
            options = []
            for value in raw[0].split(":"):
                label = value.split("=", 1)[0].strip()
                if any(character.isalnum() for character in label):
                    options.append(label)
            if len(set(options)) < 2:
                return None, 0, 0
            return options, 0, 0

        if attribute_type == "bool":
            return [], 0, 1
        if not (
            cmds.attributeQuery(attribute, node=node, minExists=True)
            and cmds.attributeQuery(attribute, node=node, maxExists=True)
        ):
            return None, 0, 0
        minimum = cmds.attributeQuery(attribute, node=node, minimum=True)[0]
        maximum = cmds.attributeQuery(attribute, node=node, maximum=True)[0]
        return [], minimum, maximum

    @staticmethod
    def _is_connected(node, attribute):
        plug = "{}.{}".format(node, attribute)
        try:
            if cmds.connectionInfo(plug, isDestination=True):
                return True
            if cmds.connectionInfo(plug, isSource=True):
                return True
            return bool(
                cmds.listConnections(plug, s=True, d=True, plugs=True) or []
            )
        except Exception:
            return False

    @staticmethod
    def build_options_map(objects_data):
        options = {}
        for node, data in objects_data.items():
            for index, label in enumerate(data["enum"]):
                entry = options.setdefault(
                    label, {"objects": [], "index": index, "attrs": {}}
                )
                entry["objects"].append(node)
                entry["attrs"][node] = data.get("attr")
        return options

    # Scene edits ----------------------------------------------------------

    @staticmethod
    def _long_dag_path(target):
        try:
            matches = cmds.ls(target, long=True) or []
        except Exception:
            matches = []
        return str(matches[0] if matches else target).rstrip("|")

    @classmethod
    def _sort_targets_by_influence(cls, targets):
        """Order descendants before ancestors while preserving unrelated order."""
        targets = list(targets or [])
        paths = [cls._long_dag_path(target) for target in targets]

        def influence(index):
            parent_prefix = paths[index] + "|"
            return sum(
                1
                for other_index, other_path in enumerate(paths)
                if other_index != index and other_path.startswith(parent_prefix)
            )

        return [
            target
            for _score, _index, target in sorted(
                (influence(index), index, target)
                for index, target in enumerate(targets)
            )
        ]

    @classmethod
    def _sort_requests_by_influence(cls, requests):
        """Order multi-switch requests from least to most DAG influence."""
        requests = list(requests or [])
        request_paths = []
        for value, _attribute, options, _all_frames in requests:
            try:
                targets = options[value]["objects"]
            except (KeyError, TypeError):
                targets = []
            request_paths.append(
                {cls._long_dag_path(target) for target in targets}
            )

        all_paths = set().union(*request_paths) if request_paths else set()

        def influence(index):
            own_paths = request_paths[index]
            return len(
                {
                    other_path
                    for other_path in all_paths - own_paths
                    if any(
                        other_path.startswith(parent_path + "|")
                        for parent_path in own_paths
                    )
                }
            )

        return [
            request
            for _score, _index, request in sorted(
                (influence(index), index, request)
                for index, request in enumerate(requests)
            )
        ]

    def apply_active_changes(self, active_widgets):
        for (attribute, _), (item, options) in active_widgets.items():
            self.apply_switch(item.currentText(), attribute, options)

    def apply_switch(
        self,
        value,
        attribute,
        options,
        all_frames_override=None,
        _manage_session=True,
    ):
        all_frames = (
            all_frames_override
            if all_frames_override is not None
            else self.view.all_frames
        )
        if attribute == "rotateOrder":
            if isinstance(value, (str, bytes)) and " " in value.strip():
                value = value.split(" ")[0]
            all_frames = True

        targets = self._sort_targets_by_influence(
            options[value]["objects"]
        )
        target_attributes = options[value]["attrs"]
        enum_index = options[value].get("index", value)
        operation_manager = None
        operation = None
        temporary_keys = {}
        try:
            operation_manager = toolCommon.tool_operation(
                tool_id="attribute_switcher",
                label="Attribute Switcher",
                progress=True,
                undo=True,
            )
            operation = operation_manager.__enter__()
            if _manage_session:
                self.disconnect_runtime()

            sorted_targets = targets
            if attribute == "rotateOrder":
                # Rotate order only ever reinterprets an object's own local
                # rx/ry/rz -- unlike every other switchable attribute (space
                # switches, IK/FK, ...) it has no dependency on world space,
                # parenting, or constraints. In Lightning mode, eligible
                # targets are converted with pure Euler math instead of the
                # frame-by-frame, world-matrix-preserving path below. Only
                # targets that aren't safe for that (driven keys, layers,
                # expressions), or every target when Lightning mode is off
                # (Normal mode), fall back to it.
                remaining_targets = targets
                if self.rotate_order_lightning_enabled():
                    remaining_targets = self._switch_rotate_order_lightning(
                        targets, target_attributes, value, operation, not _manage_session
                    )
                if remaining_targets:
                    self._apply_frame_scoped(
                        remaining_targets,
                        attribute,
                        enum_index,
                        target_attributes,
                        True,
                        operation,
                        temporary_keys,
                        not _manage_session,
                    )
            else:
                self._apply_frame_scoped(
                    targets,
                    attribute,
                    enum_index,
                    target_attributes,
                    all_frames,
                    operation,
                    temporary_keys,
                    not _manage_session,
                )

            if self.view.euler_filter:
                self.apply_euler_filter(sorted_targets)
        finally:
            self._remove_temporary_keys(temporary_keys)
            if _manage_session:
                self.connect_runtime()
                self.view.refresh(force=True)
            if operation_manager and operation is not None:
                try:
                    operation_manager.__exit__(None, None, None)
                except Exception:
                    pass
        cmds.showWindow("MayaWindow")

    def _apply_frame_scoped(
        self,
        targets,
        attribute,
        enum_index,
        target_attributes,
        all_frames,
        operation,
        temporary_keys,
        step_operation,
    ):
        """World-matrix-preserving switch, scoped to a keyframe range.

        Shared by every switchable attribute that genuinely depends on world
        space (space switches, IK/FK, ...) and by rotateOrder's fallback for
        targets that aren't safe for the pure-math lightning path (driven
        keys, animation layers, expressions).
        """
        timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
        selected_range = cmds.timeControl("timeControl1", q=True, ra=True)
        keyframes = self._collect_keyframes(
            targets, all_frames, timeline_selection, selected_range
        )
        if isinstance(keyframes, dict) and keyframes:
            self._apply_multiple_frames(
                attribute,
                enum_index,
                keyframes,
                target_attributes,
                owns_progress=not step_operation,
            )
        elif isinstance(keyframes, list) and keyframes:
            cmds.currentTime(keyframes[0])
            for target in targets:
                self._set_preserving_transform(
                    target, target_attributes[target], enum_index
                )
            if operation is not None and step_operation:
                operation.step()
        else:
            current_time = cmds.currentTime(query=True)
            for target in targets:
                target_attribute = target_attributes[target]
                plug = "{}.{}".format(target, target_attribute)
                if not (cmds.keyframe(plug, query=True, keyframeCount=True) or 0):
                    temporary_keys.setdefault(target, {}).setdefault(
                        target_attribute, []
                    ).append(current_time)
                    cmds.keyframe(plug)
                self._set_preserving_transform(
                    target, target_attribute, enum_index
                )
            if operation is not None and step_operation:
                operation.step()

    # Rotate order -- lightning path -----------------------------------------

    def _rotate_order_fast_eligible(self, node):
        """True when every rotate channel is static or driven by a single
        plain anim curve. Animation layers, driven keys, expressions, or
        constraints insert extra nodes between the curve and the plug and
        need the slower, world-space-preserving fallback instead of the
        pure-math conversion.
        """
        for axis in self.ROTATE_AXES:
            plug = "{}.{}".format(node, axis)
            try:
                if cmds.getAttr(plug, lock=True):
                    return False
                source = cmds.listConnections(plug, source=True, destination=False)
            except Exception:
                return False
            if not source:
                continue
            if len(source) != 1 or cmds.nodeType(source[0]) != "animCurveTA":
                return False
        return True

    def _switch_rotate_order_lightning(
        self, targets, target_attributes, new_order, operation, step_operation
    ):
        """Reorder keyed rotations purely mathematically wherever it's safe.

        Rotate order only ever reinterprets an object's own rx/ry/rz -- it
        has no dependency on world space, parenting, or constraints -- so
        eligible targets are converted by reading/writing anim curve values
        directly through time-sampled getAttr/keyframe calls, never moving
        the playhead or forcing a dependency-graph evaluation. That is what
        makes this so much faster than the generic world-matrix-preserving
        path used for every other switchable attribute, which genuinely does
        need the DG evaluated at each frame.

        Returns the subset of ``targets`` that were not eligible and still
        need the slower fallback.
        """
        slow_targets = []
        for target in targets:
            try:
                old_order = ROTATE_ORDER_OPTIONS[cmds.getAttr(target + ".rotateOrder")]
            except Exception:
                slow_targets.append(target)
                continue

            rotate_order_attr = target_attributes.get(target, "rotateOrder")
            if old_order == new_order:
                # Nothing to reorder, but the attribute itself may still be
                # a distinct plug alias (rare) -- keep it in sync.
                try:
                    cmds.setAttr(
                        "{}.{}".format(target, rotate_order_attr),
                        ROTATE_ORDER_OPTIONS.index(new_order),
                    )
                except Exception:
                    pass
                continue

            if not self._rotate_order_fast_eligible(target):
                slow_targets.append(target)
                continue

            try:
                self._reorder_rotation_keys(target, old_order, new_order)
                cmds.setAttr(
                    "{}.{}".format(target, rotate_order_attr),
                    ROTATE_ORDER_OPTIONS.index(new_order),
                )
            except Exception:
                slow_targets.append(target)
                continue

            if operation is not None and step_operation:
                operation.step()
        return slow_targets

    def _reorder_rotation_keys(self, target, old_order, new_order):
        """Convert rx/ry/rz between rotate orders without touching the DG."""
        key_times = set()
        for axis in self.ROTATE_AXES:
            times = cmds.keyframe(
                "{}.{}".format(target, axis), query=True, timeChange=True
            )
            if times:
                key_times.update(times)

        if not key_times:
            values = [
                cmds.getAttr("{}.{}".format(target, axis))
                for axis in self.ROTATE_AXES
            ]
            new_values = open_maya.reorder_euler_rotation(
                values[0], values[1], values[2], old_order, new_order
            )
            for axis, value in zip(self.ROTATE_AXES, new_values):
                cmds.setAttr("{}.{}".format(target, axis), value)
            return

        # A channel that was static up to now can still need distinct
        # per-frame values after reordering -- the conversion mixes all
        # three axes together -- so every rotate channel needs a key at
        # every collected time before the values are rewritten.
        for axis in self.ROTATE_AXES:
            plug = "{}.{}".format(target, axis)
            existing = set(cmds.keyframe(plug, query=True, timeChange=True) or [])
            for frame in sorted(key_times - existing):
                cmds.setKeyframe(
                    plug, time=(frame, frame), value=cmds.getAttr(plug, time=frame)
                )

        for frame in sorted(key_times):
            values = [
                cmds.getAttr("{}.{}".format(target, axis), time=frame)
                for axis in self.ROTATE_AXES
            ]
            new_values = open_maya.reorder_euler_rotation(
                values[0], values[1], values[2], old_order, new_order
            )
            for axis, value in zip(self.ROTATE_AXES, new_values):
                cmds.keyframe(
                    "{}.{}".format(target, axis),
                    edit=True,
                    time=(frame, frame),
                    valueChange=value,
                )

    def apply_switches(self, requests):
        """Apply a staged group of attribute switches as one operation."""
        requests = list(requests or [])
        if not requests:
            return
        requests = self._sort_requests_by_influence(requests)

        # Precompute the real amount of work up front. Each request's own
        # "All Keyframes" pass (_apply_multiple_frames) used to call
        # set_total(..., reset=True) on this shared/merged operation, which
        # wiped out progress made by earlier requests every time -- the
        # progress bar and ETA would jump back to 0% per attribute instead of
        # tracking the whole batch. Establishing one combined total here, and
        # having per-request work only step (never reset) it, keeps progress
        # monotonic across every request regardless of scope.
        timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
        selected_range = cmds.timeControl("timeControl1", q=True, ra=True)
        total_cost = 0
        for value, attribute, options, all_frames in requests:
            try:
                targets = options[value]["objects"]
            except (KeyError, TypeError):
                total_cost += 1
                continue
            if attribute == "rotateOrder":
                # Most targets take the pure-math lightning path (one step
                # per target, see _switch_rotate_order_lightning) instead of
                # the frame-by-frame world-matrix pass, so estimate on
                # object count rather than keyframe count.
                total_cost += max(1, len(targets))
                continue
            keyframes = self._collect_keyframes(
                targets, all_frames, timeline_selection, selected_range
            )
            total_cost += len(keyframes) * 2 if isinstance(keyframes, dict) else 1
        total_cost = total_cost or len(requests)

        with toolCommon.tool_operation(
            tool_id="attribute_switcher_multi",
            label="Switch Multiple Attributes",
            progress=True,
            progress_max=total_cost,
            undo=True,
        ) as operation:
            self.disconnect_runtime()
            try:
                for value, attribute, options, all_frames in requests:
                    if operation.cancelled:
                        break
                    self.apply_switch(
                        value,
                        attribute,
                        options,
                        all_frames_override=all_frames,
                        _manage_session=False,
                    )
            finally:
                self.connect_runtime()
                self.view.refresh(force=True)

    @staticmethod
    def _set_preserving_transform(target, attribute, value, transform=None):
        transform = transform or cmds.xform(target, q=True, ws=True, matrix=True)
        cmds.setAttr("{}.{}".format(target, attribute), value)
        cmds.xform(target, ws=True, matrix=transform)

    def _apply_multiple_frames(
        self, attribute, value, keyframes, target_attributes=None, owns_progress=True
    ):
        tint = None
        current_time = cmds.currentTime(q=True)
        try:
            if int(cmds.about(v=1)) >= 2024:
                cmds.playbackOptions(sv=False)
            frames = list(keyframes)
            tint = timelineWidgets.begin_timeline_tint(
                timerange=(frames[0], frames[-1]),
                color=toolbox.get_tool_tint_color("attribute_switcher"),
                owner=self.view,
                key="attribute_switcher_range",
            )
            operation = toolCommon.current_tool_operation()
            if operation:
                # Only claim/reset the shared operation's total when this call
                # owns it outright (a standalone switch). When driven by
                # apply_switches() the total already reflects every staged
                # request combined -- resetting it here would wipe out
                # progress already made by earlier requests in the batch.
                if owns_progress:
                    operation.set_total(len(frames) * 2, reset=True)
                operation.set_status("Saving Positions")

            transforms = {}
            interrupted = False
            for frame, targets in keyframes.items():
                if operation and operation.cancelled:
                    interrupted = True
                    break
                transforms[frame] = {
                    target: open_maya.world_matrix_at_time(target, frame)
                    for target in targets
                }
                transforms[frame] = {
                    target: matrix
                    for target, matrix in transforms[frame].items()
                    if matrix is not None
                }
                if operation:
                    operation.step()

            if not interrupted:
                if operation:
                    operation.set_status("Applying Positions")
                for frame, frame_transforms in transforms.items():
                    cmds.currentTime(frame)
                    for target, transform in frame_transforms.items():
                        target_attribute = (
                            target_attributes[target]
                            if target_attributes
                            else attribute
                        )
                        self._set_preserving_transform(
                            target, target_attribute, value, transform
                        )
                    if operation:
                        operation.step()
        finally:
            cmds.currentTime(current_time)
            if tint:
                tint.finish()

    @staticmethod
    def _collect_keyframes(targets, all_frames, timeline_selection, selected_range):
        if not timeline_selection and not all_frames:
            return [cmds.currentTime(query=True)]
        keys_by_target = {
            target: set(cmds.keyframe(target, query=True) or [])
            for target in targets
        }
        all_keys = sorted(set().union(*keys_by_target.values()))
        keyframes = {
            frame: [
                target
                for target in targets
                if frame in keys_by_target[target]
            ]
            for frame in all_keys
        }
        if timeline_selection:
            keyframes = {
                frame: frame_targets
                for frame, frame_targets in keyframes.items()
                if selected_range[0] <= frame < selected_range[1]
            }
        return keyframes

    @staticmethod
    def _remove_temporary_keys(temporary_keys):
        for target, attributes in temporary_keys.items():
            for attribute, frames in attributes.items():
                for frame in frames:
                    cmds.cutKey("{}.{}".format(target, attribute), time=(frame,))

    @staticmethod
    def apply_euler_filter(targets):
        curves = []
        for target in targets:
            plugs = [
                "{}.{}".format(target, attribute)
                for attribute in ("rx", "ry", "rz")
                if cmds.objExists("{}.{}".format(target, attribute))
            ]
            curves.extend(selectionMod.get_anim_curves_from_plugs(plugs))
        curves = list(set(curves))
        if curves:
            cmds.filterCurve(*curves)
