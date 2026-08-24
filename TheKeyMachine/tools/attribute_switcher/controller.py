"""Scene analysis and mutation for the Attribute Switcher."""

from maya import cmds

from TheKeyMachine.core import runtime
from TheKeyMachine.maya import runtime as maya_runtime
from TheKeyMachine.maya import maya_api
from TheKeyMachine.tools import registry
from TheKeyMachine.maya import animation, selection
from TheKeyMachine.core import settings
from TheKeyMachine.tools.gimbal_fixer.controller import GimbalAnalyzer
from TheKeyMachine.tools import common as toolCommon


ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE = "attribute_switcher_window"
ATTRIBUTE_SWITCHER_GEOMETRY_KEY = "attribute_switcher_geometry"
ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY = "attribute_switcher_stays_on_top"
SUPER_MODE_KEY = "rotate_order_super_mode"

ROTATE_ORDER_OPTIONS = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")
APPLY_BATCH_SIZE = 8

# Flipped to True for the rest of the Maya session the first time Super
# mode's general (non-rotateOrder) fast path disagrees with the proven,
# DG-evaluated Normal-mode result during its one-time-per-operation safety
# check (see _verify_super_switch_sample) -- every switch falls back to
# Normal mode from that point on, since a mismatch means the math can't be
# trusted for this scene/rig.
_SUPER_MODE_SUSPENDED = False


def _as_bool(value):
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value) if isinstance(value, (bool, int)) else False


def _chunks(items, size=APPLY_BATCH_SIZE):
    items = list(items or [])
    size = max(1, int(size or 1))
    for index in range(0, len(items), size):
        yield items[index:index + size]


class AttributeSwitcherController:
    """Own Maya state, analysis, settings, and scene edits for one view."""

    ROTATE_AXES = ("rotateX", "rotateY", "rotateZ")

    # Channels Super mode's general fast path can compensate directly, and
    # the plain anim-curve type each must be driven by if animated at all.
    _FAST_SWITCH_CHANNELS = (
        ("translateX", "animCurveTL"),
        ("translateY", "animCurveTL"),
        ("translateZ", "animCurveTL"),
        ("rotateX", "animCurveTA"),
        ("rotateY", "animCurveTA"),
        ("rotateZ", "animCurveTA"),
        ("scaleX", "animCurveTU"),
        ("scaleY", "animCurveTU"),
        ("scaleZ", "animCurveTU"),
    )

    # Pivot/rotate-axis attributes that must be at their default (zero) and
    # unanimated for the plain-matrix decomposition to be valid -- see
    # _switch_fast_eligible.
    _FAST_SWITCH_ZERO_ATTRS = (
        "rotatePivotX", "rotatePivotY", "rotatePivotZ",
        "rotatePivotTranslateX", "rotatePivotTranslateY", "rotatePivotTranslateZ",
        "scalePivotX", "scalePivotY", "scalePivotZ",
        "scalePivotTranslateX", "scalePivotTranslateY", "scalePivotTranslateZ",
        "rotateAxisX", "rotateAxisY", "rotateAxisZ",
    )

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

    def super_mode_enabled(self):
        """Whether the Attribute Switcher uses fast, math-only shortcuts
        instead of the frame-by-frame, world-matrix-preserving path.

        Defaults to off (Normal mode): the slower path that works with
        every rig, including animation layers, driven keys, and
        expressions. Super mode is an explicit opt-in from the toolbar
        button's right-click menu.
        """
        return _as_bool(self._setting(SUPER_MODE_KEY, False))

    def _super_mode_active(self):
        """Whether Super mode's fast paths should actually be attempted.

        Separate from ``super_mode_enabled`` so a live safety-check failure
        (see ``_verify_super_switch_sample``) can force Normal mode for the
        rest of the session without touching the user's saved preference.
        """
        return self.super_mode_enabled() and not _SUPER_MODE_SUSPENDED

    @staticmethod
    def _suspend_super_mode():
        global _SUPER_MODE_SUSPENDED
        if not _SUPER_MODE_SUSPENDED:
            cmds.warning(
                "TheKeyMachine: Attribute Switcher Super mode failed its "
                "startup safety check and has been disabled for the rest "
                "of this session -- using Normal mode instead."
            )
        _SUPER_MODE_SUSPENDED = True

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
        return selection.get_selected_objects(long=long)

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
        nodes = list(nodes or [])
        # Gimbal analysis walks every keyed rotation frame for all six orders.
        # A grouped row cannot display per-control results, so doing that work
        # while opening the switcher makes large selections unnecessarily slow.
        # Multi-switch explicitly requests the analysis when its dialog opens.
        analyze_gimbal = show_rotate_order and len(nodes) == 1
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
                    catalog,
                    node,
                    attribute,
                    show_rotate_order,
                    analyze_gimbal,
                )
        return catalog

    def _analyze_attribute(
        self,
        catalog,
        node,
        attribute,
        show_rotate_order,
        analyze_gimbal=True,
    ):
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
        xform_target = (
            node
            if attribute == "rotateOrder"
            else self.detect_xform_target(node, attribute)
        )
        existing = entry["objects"].get(xform_target)
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
            "switch_node": node,
            "type": attribute_type,
            "min": float(minimum),
            "max": float(maximum),
        }
        if catalog_key == "rotateOrder" and show_rotate_order and analyze_gimbal:
            object_data["gimbal"] = self.analyzer.analyze(node)
        entry["objects"][xform_target] = object_data

    def analyze_group_gimbal(self, objects_data):
        """Analyze a staged rotate-order group and return combined ranks.

        The score for an order is the worst score among the controls, which
        makes the displayed recommendation safe for the complete group being
        switched. Individual results remain cached only to avoid repeat work.
        """
        objects_data = objects_data or {}
        per_object = {}
        for node, data in objects_data.items():
            gimbal = data.get("gimbal")
            if gimbal is None:
                gimbal = self.analyzer.analyze(node)
                data["gimbal"] = gimbal
            per_object[node] = gimbal or {}

        any_data = next(iter(objects_data.values()), {})
        orders = list(any_data.get("enum") or ROTATE_ORDER_OPTIONS)
        percentages = []
        for order in orders:
            scores = [
                result[order]["percentage"]
                for result in per_object.values()
                if order in result and "percentage" in result[order]
            ]
            percentages.append(max(scores) if scores else 0)

        labels = self.analyzer.classify_percentages(percentages)
        combined = {
            order: {
                "percentage": percentages[index],
                "label": labels[index],
            }
            for index, order in enumerate(orders)
        }
        return combined

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
    def _downstream_nodes(source):
        """Return direct DG destinations for a node or plug."""
        try:
            return cmds.listConnections(
                source,
                source=False,
                destination=True,
                skipConversionNodes=True,
            ) or []
        except (TypeError, RuntimeError, ValueError):
            try:
                return cmds.listConnections(
                    source, source=False, destination=True
                ) or []
            except Exception:
                return []

    @staticmethod
    def _is_transform(node):
        try:
            return cmds.nodeType(node) in ("transform", "joint")
        except Exception:
            return False

    @classmethod
    def _controller_descendants(cls, root, max_depth=8):
        """Find the nearest curve controller below a driven transform."""
        queue = [(root, 0)]
        visited = set()
        matches = []
        nearest_depth = None
        while queue:
            node, depth = queue.pop(0)
            if node in visited or depth > max_depth:
                continue
            visited.add(node)
            try:
                shapes = cmds.listRelatives(
                    node,
                    shapes=True,
                    noIntermediate=True,
                    fullPath=True,
                ) or []
            except Exception:
                shapes = []
            if any(
                cmds.nodeType(shape) == "nurbsCurve"
                for shape in shapes
            ):
                if nearest_depth is None:
                    nearest_depth = depth
                if depth == nearest_depth:
                    matches.append(node)
                continue
            if nearest_depth is not None or depth == max_depth:
                continue
            try:
                children = cmds.listRelatives(
                    node, children=True, type="transform", fullPath=True
                ) or []
            except Exception:
                children = []
            queue.extend((child, depth + 1) for child in children)
        return matches

    @classmethod
    def detect_xform_target(cls, switch_node, attribute, max_nodes=256):
        """Infer the control whose world pose a switch should preserve.

        Space-switch attributes often live on a settings/spacer control while
        their DG output drives an offset group above the animated control. Walk
        only downstream from the switch plug, stop at driven transforms, and
        use a unique nearest curve-controller descendant. Ambiguous networks
        deliberately fall back to the attribute owner.
        """
        plug = "{}.{}".format(switch_node, attribute)
        queue = list(cls._downstream_nodes(plug))
        visited = set()
        driven = []
        while queue and len(visited) < max_nodes:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            if cls._is_transform(node):
                driven.append(node)
                continue
            queue.extend(cls._downstream_nodes(node))

        candidates = []
        for transform in driven:
            controls = cls._controller_descendants(transform)
            candidates.extend(controls or [transform])
        candidates = list(dict.fromkeys(candidates))
        return candidates[0] if len(candidates) == 1 else switch_node

    @staticmethod
    def build_options_map(objects_data):
        options = {}
        for node, data in objects_data.items():
            for index, label in enumerate(data["enum"]):
                entry = options.setdefault(
                    label,
                    {
                        "objects": [],
                        "index": index,
                        "attrs": {},
                        "switch_nodes": {},
                    },
                )
                entry["objects"].append(node)
                entry["attrs"][node] = data.get("attr")
                entry["switch_nodes"][node] = data.get("switch_node", node)
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

    @staticmethod
    def _normalize_switch(value, attribute, all_frames):
        if attribute != "rotateOrder":
            return value, all_frames
        if isinstance(value, (str, bytes)) and " " in value.strip():
            value = value.split(" ")[0]
        return value, True

    @staticmethod
    def _on_main(operation, fn, *args):
        """Call ``fn`` on the main thread if ``operation`` says we're not
        already there; otherwise call it inline.

        Every helper below that's reachable from the worker thread
        apply_switch/apply_switches dispatch onto (see ToolOperation.run_worker
        in tools/common.py) must route its cmds/OpenMaya touches through
        this -- calling them directly off the main thread can crash Maya.
        ``operation.run_on_main`` already collapses to a plain inline call
        when it's invoked from the main thread, so this is free to call
        even for the non-threaded/analysis code paths.
        """
        return operation.run_on_main(fn, *args) if operation else fn(*args)

    def apply_switch(
        self,
        value,
        attribute,
        options,
        all_frames_override=None,
        _manage_session=True,
        _prepared_frames=None,
        tool_operation=None,
    ):
        all_frames = (
            all_frames_override
            if all_frames_override is not None
            else self.view.all_frames
        )
        value, all_frames = self._normalize_switch(value, attribute, all_frames)

        targets = self._sort_targets_by_influence(
            options[value]["objects"]
        )
        target_attributes = options[value]["attrs"]
        target_switch_nodes = options[value].get("switch_nodes", {})
        enum_index = options[value].get("index", value)
        operation = toolCommon.require_tool_operation(tool_operation)
        if operation.selection_snapshot is None:
            operation.selection_snapshot = animation.capture_selection_snapshot()
        temporary_keys = {}
        try:
            if _manage_session:
                self.disconnect_runtime()

            # The actual frame-by-frame Maya work runs on a worker thread
            # so the main thread's Qt event loop stays free to dispatch a
            # Cancel press (progress-bar click or Esc) while it's working
            # -- a tight loop of cmds calls on the main thread never gives
            # Qt a chance to notice one until the loop itself pauses to
            # check. This call blocks until the worker finishes, without
            # blocking the event loop the way running it inline here
            # would. See ToolOperation.run_worker() /
            # ToolOperation.run_on_main for the mechanics.
            operation.run_worker(
                self._apply_switch_worker,
                operation,
                value,
                attribute,
                targets,
                target_attributes,
                target_switch_nodes,
                enum_index,
                all_frames,
                temporary_keys,
                _prepared_frames,
                not _manage_session,
            )

            if self.view.euler_filter and _manage_session:
                self.apply_euler_filter(targets)
        finally:
            self._remove_temporary_keys(temporary_keys)
            if _manage_session:
                self.connect_runtime()
                self.view.refresh(force=True)
        if _manage_session:
            cmds.showWindow("MayaWindow")

    def _apply_switch_worker(
        self,
        operation,
        value,
        attribute,
        targets,
        target_attributes,
        target_switch_nodes,
        enum_index,
        all_frames,
        temporary_keys,
        prepared_frames,
        step_operation,
    ):
        """Runs off the main thread -- see apply_switch's run_worker()
        call. Every Maya touch reachable from here (directly or through the
        helpers this calls) must go through operation.run_on_main()/
        self._on_main() rather than calling cmds/maya_api directly.
        """
        if attribute == "rotateOrder":
            # Rotate order only ever reinterprets an object's own local
            # rx/ry/rz -- unlike every other switchable attribute (space
            # switches, IK/FK, ...) it has no dependency on world space,
            # parenting, or constraints. In Super mode, eligible
            # targets are converted with pure Euler math instead of the
            # frame-by-frame, world-matrix-preserving path below. Only
            # targets that aren't safe for that (driven keys, layers,
            # expressions), or every target when Super mode is off
            # (Normal mode), fall back to it.
            remaining_targets = targets
            if self._super_mode_active():
                remaining_targets = self._switch_rotate_order_super(
                    targets, target_attributes, value, operation, step_operation
                )
            if remaining_targets:
                self._apply_frame_scoped(
                    remaining_targets,
                    attribute,
                    enum_index,
                    target_attributes,
                    target_switch_nodes,
                    True,
                    operation,
                    temporary_keys,
                    step_operation,
                    prepared_frames=prepared_frames,
                )
        else:
            self._apply_frame_scoped(
                targets,
                attribute,
                enum_index,
                target_attributes,
                target_switch_nodes,
                all_frames,
                operation,
                temporary_keys,
                step_operation,
                prepared_frames=prepared_frames,
            )

    def _apply_frame_scoped(
        self,
        targets,
        attribute,
        enum_index,
        target_attributes,
        target_switch_nodes,
        all_frames,
        operation,
        temporary_keys,
        step_operation,
        prepared_frames=None,
    ):
        """World-matrix-preserving switch, scoped to a keyframe range.

        Shared by every switchable attribute that genuinely depends on world
        space (space switches, IK/FK, ...) and by rotateOrder's fallback for
        targets that aren't safe for the pure-math Super mode path (driven
        keys, animation layers, expressions).
        """
        if prepared_frames is None:
            prepared_frames = self._prepare_frame_scoped(
                targets,
                all_frames,
                owns_progress=not step_operation,
            )
        if not prepared_frames["complete"]:
            return
        keyframes = prepared_frames["keyframes"]
        transforms = prepared_frames["transforms"]
        if isinstance(keyframes, dict) and keyframes:
            active_targets = set(targets)
            transforms = {
                frame: {
                    target: matrix
                    for target, matrix in frame_transforms.items()
                    if target in active_targets
                }
                for frame, frame_transforms in transforms.items()
            }
            transforms = {
                frame: frame_transforms
                for frame, frame_transforms in transforms.items()
                if frame_transforms
            }
            if not transforms:
                return
            self._apply_multiple_frames(
                attribute,
                enum_index,
                {frame: keyframes[frame] for frame in transforms},
                target_attributes,
                target_switch_nodes,
                transforms=transforms,
            )
        elif isinstance(keyframes, list) and keyframes:
            if not self._on_main(operation, maya_api.set_current_time, keyframes[0]):
                return
            frame_transforms = transforms.get(keyframes[0], {})
            for target in targets:
                if target not in frame_transforms:
                    continue
                self._on_main(
                    operation,
                    self._set_preserving_transform,
                    target,
                    target_switch_nodes.get(target, target),
                    target_attributes[target],
                    enum_index,
                    frame_transforms.get(target),
                )
            if operation is not None and step_operation:
                operation.step()
        else:
            current_time = prepared_frames["frame"]
            frame_transforms = transforms.get(current_time, {})
            for target in targets:
                if target not in frame_transforms:
                    continue
                target_attribute = target_attributes[target]
                switch_node = target_switch_nodes.get(target, target)
                self._on_main(
                    operation,
                    self._ensure_temporary_key,
                    switch_node,
                    target_attribute,
                    current_time,
                    temporary_keys,
                )
                self._on_main(
                    operation,
                    self._set_preserving_transform,
                    target,
                    switch_node,
                    target_attribute,
                    enum_index,
                    frame_transforms.get(target),
                )
            if operation is not None and step_operation:
                operation.step()

    @staticmethod
    def _ensure_temporary_key(switch_node, target_attribute, current_time, temporary_keys):
        """Give an unkeyed channel a temporary key at ``current_time`` so
        the frame-scoped switch below has something to preserve; the key
        is removed again in ``_remove_temporary_keys`` once the switch is
        done.
        """
        plug = "{}.{}".format(switch_node, target_attribute)
        if not (cmds.keyframe(plug, query=True, keyframeCount=True) or 0):
            temporary_keys.setdefault(switch_node, {}).setdefault(
                target_attribute, []
            ).append(current_time)
            cmds.keyframe(plug)

    def _prepare_frame_scoped(
        self,
        targets,
        all_frames,
        owns_progress=False,
        matrix_cache=None,
        keyframes=None,
    ):
        """Collect frame work and snapshot world matrices before any edits.

        Safe to call from either the main thread or (via
        apply_switch/apply_switches' worker-thread dispatch) a worker
        thread: every cmds/OpenMaya touch below routes through
        self._on_main(), which collapses to a plain inline call when
        there's no thread to hop from.
        """
        operation = toolCommon.current_tool_operation()
        if keyframes is None:
            def _collect():
                timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
                selected_range = cmds.timeControl("timeControl1", q=True, ra=True)
                return self._collect_keyframes(
                    targets, all_frames, timeline_selection, selected_range
                )
            keyframes = self._on_main(operation, _collect)
        transforms = {}
        matrix_cache = matrix_cache if matrix_cache is not None else {}
        complete = True
        current_frame = (
            keyframes[0]
            if isinstance(keyframes, list) and keyframes
            else self._on_main(operation, self._current_time)
        )

        def snapshot(frame, frame_targets):
            def _snapshot():
                result = {}
                for target in frame_targets:
                    cache_key = (target, frame)
                    if cache_key not in matrix_cache:
                        matrix_cache[cache_key] = maya_api.world_matrix_at_time(
                            target, frame
                        )
                    matrix = matrix_cache[cache_key]
                    if matrix is not None:
                        result[target] = matrix
                return result
            return self._on_main(operation, _snapshot)

        if isinstance(keyframes, dict) and keyframes:
            if operation:
                if owns_progress:
                    work_units = sum(len(frame_targets) for frame_targets in keyframes.values())
                    operation.set_total(max(1, work_units * 2), reset=True)
                operation.set_status("Saving Positions")
            for frame, frame_targets in keyframes.items():
                if operation and operation.cancelled:
                    complete = False
                    break
                transforms[frame] = {}
                for target_batch in _chunks(frame_targets):
                    if operation and operation.cancelled:
                        complete = False
                        break
                    transforms[frame].update(snapshot(frame, target_batch))
                    if operation:
                        operation.step(amount=len(target_batch))
                if not complete:
                    break
        else:
            transforms[current_frame] = snapshot(current_frame, targets)

        return {
            "frame": current_frame,
            "complete": complete,
            "keyframes": keyframes,
            "transforms": transforms,
        }

    @staticmethod
    def _current_time():
        current = maya_api.current_time()
        return current if current is not None else cmds.currentTime(query=True)

    # Rotate order -- super-mode (fast) path ----------------------------------

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

    def _rotate_order_needs_frame_scope(self, targets, new_order):
        """True if switching ``targets`` to ``new_order`` will touch the
        slower, frame-scoped world-matrix-preserving path at all.

        Mirrors the eligibility checks in ``_switch_rotate_order_super``
        without mutating anything, so callers can tell upfront whether a
        rotate-order switch will actually scrub the timeline (and therefore
        needs a tint) or will be handled entirely by the pure-math Super
        mode path.
        """
        if not self._super_mode_active():
            return True
        for target in targets:
            try:
                old_order = ROTATE_ORDER_OPTIONS[cmds.getAttr(target + ".rotateOrder")]
            except Exception:
                return True
            if old_order == new_order:
                continue
            if not self._rotate_order_fast_eligible(target):
                return True
        return False

    def _switch_rotate_order_super(
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

        Each target's reorder is marshaled onto the main thread as one
        unit (self._on_main), and ``operation.cancelled`` is checked
        between targets -- this used to run every target with no
        cancellation check at all, which is why a Cancel press during a
        Super mode rotate-order switch never stopped it. Any target not
        yet reached when cancellation is noticed is handed to the slower
        fallback path too, which will itself see the cancellation and stop
        immediately without doing any further work.
        """
        def _reorder_target(target, rotate_order_attr):
            try:
                old_order = ROTATE_ORDER_OPTIONS[cmds.getAttr(target + ".rotateOrder")]
            except Exception:
                return False

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
                return True

            if not self._rotate_order_fast_eligible(target):
                return False

            try:
                self._reorder_rotation_keys(target, old_order, new_order)
                cmds.setAttr(
                    "{}.{}".format(target, rotate_order_attr),
                    ROTATE_ORDER_OPTIONS.index(new_order),
                )
            except Exception:
                return False
            return True

        targets = list(targets)
        slow_targets = []
        for index, target in enumerate(targets):
            if operation is not None and operation.cancelled:
                slow_targets.extend(targets[index:])
                break
            rotate_order_attr = target_attributes.get(target, "rotateOrder")
            converted = self._on_main(operation, _reorder_target, target, rotate_order_attr)
            if not converted:
                slow_targets.append(target)
            elif operation is not None and step_operation:
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
            new_values = maya_api.reorder_euler_rotation(
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
            new_values = maya_api.reorder_euler_rotation(
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

        timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
        selected_range = cmds.timeControl("timeControl1", q=True, ra=True)
        plans = []
        total_cost = 0
        for value, attribute, options, all_frames in requests:
            normalized_value, frame_all = self._normalize_switch(
                value, attribute, all_frames
            )
            try:
                targets = self._sort_targets_by_influence(
                    options[normalized_value]["objects"]
                )
                option_data = options[normalized_value]
            except (KeyError, TypeError):
                continue
            needs_scope = (
                self._rotate_order_needs_frame_scope(targets, normalized_value)
                if attribute == "rotateOrder"
                else True
            )
            # A fully fast-path rotate-order conversion edits its curves
            # directly. It never needs a timeline frame map or world-matrix
            # snapshots, so collecting them would waste most of the time this
            # path is intended to save on large selections.
            keyframes = (
                self._collect_keyframes(
                    targets, frame_all, timeline_selection, selected_range
                )
                if needs_scope
                else {}
            )
            frame_target_count = (
                sum(len(frame_targets) for frame_targets in keyframes.values())
                if isinstance(keyframes, dict)
                else 0
            )
            save_cost = frame_target_count if needs_scope else 0
            apply_cost = frame_target_count
            if attribute == "rotateOrder" and self._super_mode_active():
                apply_cost += len(targets)
            total_cost += save_cost + max(1, apply_cost)
            plans.append(
                {
                    "value": normalized_value,
                    "attribute": attribute,
                    "all_frames": frame_all,
                    "targets": targets,
                    "target_attributes": option_data["attrs"],
                    "target_switch_nodes": option_data.get("switch_nodes", {}),
                    "enum_index": option_data.get("index", normalized_value),
                    "keyframes": keyframes,
                    "needs_scope": needs_scope,
                    "frames": None,
                }
            )

        if not plans:
            return

        # One tint covers every frame the dispatcher-owned operation will
        # scrub through. Rotate-order plans handled entirely by the pure-math
        # Super mode path never move the playhead, so they are excluded.
        tint_frames = [
            frame
            for plan in plans
            if plan["needs_scope"] and isinstance(plan["keyframes"], dict)
            for frame in plan["keyframes"]
        ]
        timerange = (min(tint_frames), max(tint_frames)) if tint_frames else None
        if timerange and maya_runtime.supports_playback_selection():
            cmds.playbackOptions(sv=False)

        operation = toolCommon.require_tool_operation()
        if operation.selection_snapshot is None:
            operation.selection_snapshot = animation.capture_selection_snapshot()
        operation.set_total(total_cost).set_status("Switch Multiple Attributes")
        toolCommon.ensure_operation_tint(
            operation,
            tint="range" if timerange else None,
            timerange=timerange,
            tint_key="attribute_switcher_range",
            tint_color=registry.get_tool_tint_color("attribute_switcher"),
        )
        self.disconnect_runtime()
        try:
            scoped_plans = [plan for plan in plans if plan["needs_scope"]]
            if scoped_plans:
                operation.set_status("Saving Positions")
                matrix_cache = {}

                def _save_all_positions():
                    for plan in scoped_plans:
                        if operation.cancelled:
                            break
                        plan["frames"] = self._prepare_frame_scoped(
                            plan["targets"],
                            plan["all_frames"],
                            matrix_cache=matrix_cache,
                            keyframes=plan["keyframes"],
                        )

                operation.run_worker(_save_all_positions)

            if not operation.cancelled:
                operation.set_status("Applying Positions")

            applied_targets = []

            def _apply_all_plans():
                for plan in plans:
                    if operation.cancelled:
                        break
                    temporary_keys = {}
                    try:
                        self._apply_switch_worker(
                            operation,
                            plan["value"],
                            plan["attribute"],
                            plan["targets"],
                            plan["target_attributes"],
                            plan["target_switch_nodes"],
                            plan["enum_index"],
                            plan["all_frames"],
                            temporary_keys,
                            plan["frames"],
                            True,
                        )
                    finally:
                        self._on_main(
                            operation,
                            self._remove_temporary_keys,
                            temporary_keys,
                        )
                    if not operation.cancelled:
                        applied_targets.extend(plan["targets"])

            if not operation.cancelled:
                operation.run_worker(_apply_all_plans)

            if (
                not operation.cancelled
                and self.view.euler_filter
                and applied_targets
            ):
                operation.set_status("Euler Filtering")
                self.apply_euler_filter(list(dict.fromkeys(applied_targets)))
        finally:
            self.connect_runtime()
            self.view.refresh(force=True)
        cmds.showWindow("MayaWindow")

    @staticmethod
    def _set_preserving_transform(
        target, switch_node, attribute, value, transform
    ):
        cmds.setAttr("{}.{}".format(switch_node, attribute), value)
        cmds.xform(target, ws=True, matrix=transform)

    # General switches -- super-mode (fast) path -----------------------------
    #
    # Space switches, IK/FK, and every other non-rotateOrder switchable
    # attribute can depend on an arbitrary rig network (a constraint, a
    # blendMatrix setup, a custom solver -- anything), so unlike rotate
    # order there's no universal closed-form formula for "what local values
    # keep this world matrix" that's independent of the rig. What *is*
    # universal is that a node's parentInverseMatrix plug reflects whatever
    # is driving its parent space right now, however that's implemented --
    # so it can be read through a scoped MDGContext (no playhead move, no
    # scene-wide DG evaluation, same trick _prepare_frame_scoped already
    # uses for worldMatrix) to compute the compensating local matrix
    # ourselves instead of asking cmds.xform to do it live at each frame.
    #
    # The catch is turning that local matrix into channel values: Maya's
    # own transform node formula folds in rotate/scale pivots and rotate
    # axis, and doing that by hand is exactly the kind of easy-to-get-
    # subtly-wrong math this tool can't afford. So this only ever engages
    # for nodes with default (zero) pivots and rotate axis -- where the
    # local matrix decomposes into translate/rotate/scale the plain way,
    # with no pivot algebra to reproduce -- and joints are excluded
    # entirely (jointOrient and segment scale compensate need more care
    # than this shortcut attempts). Everything else falls back to the
    # proven, frame-by-frame path above, exactly like rotateOrder falls
    # back for targets _rotate_order_fast_eligible rejects.

    def _switch_fast_eligible(self, node):
        """True when Super mode's rig-agnostic matrix shortcut is safe for
        ``node``: a plain transform (not a joint), with default pivots and
        rotate axis, inheriting its parent's transform, where every
        translate/rotate/scale channel is either static or driven by a
        single plain anim curve.
        """
        try:
            if cmds.nodeType(node) != "transform":
                return False
            if not cmds.getAttr(node + ".inheritsTransform"):
                return False
            for attr in self._FAST_SWITCH_ZERO_ATTRS:
                plug = "{}.{}".format(node, attr)
                if cmds.keyframe(plug, query=True, keyframeCount=True):
                    return False
                if abs(cmds.getAttr(plug)) > 1e-9:
                    return False
        except Exception:
            return False

        for axis, curve_type in self._FAST_SWITCH_CHANNELS:
            plug = "{}.{}".format(node, axis)
            try:
                if cmds.getAttr(plug, lock=True):
                    return False
                source = cmds.listConnections(plug, source=True, destination=False)
            except Exception:
                return False
            if not source:
                continue
            if len(source) != 1 or cmds.nodeType(source[0]) != curve_type:
                return False
        return True

    @staticmethod
    def _node_rotate_order(node):
        try:
            return ROTATE_ORDER_OPTIONS[cmds.getAttr(node + ".rotateOrder")]
        except Exception:
            return "xyz"

    @staticmethod
    def _write_switch_attribute(target, attribute, value, frame):
        """Set the switch attribute at ``frame``, never creating a new key.

        Mirrors exactly what the slow path's plain ``cmds.setAttr`` does
        (edit an existing key at this exact time, or set the static/global
        value) so behavior stays identical whichever path handles a given
        target. Returns whether the plug actually ended up at ``value``.
        """
        plug = "{}.{}".format(target, attribute)
        existing = cmds.keyframe(plug, query=True, time=(frame, frame), timeChange=True)
        try:
            if existing:
                cmds.keyframe(plug, edit=True, time=(frame, frame), valueChange=value)
            else:
                cmds.setAttr(plug, value)
        except Exception:
            return False
        try:
            return abs(float(cmds.getAttr(plug, time=frame)) - float(value)) <= 1e-6
        except Exception:
            return False

    @staticmethod
    def _write_keyed_or_static(plug, frame, value):
        """Set ``plug`` at ``frame``: edit its existing key if there is
        one, add a new key there (mirroring cmds.xform's own auto-key
        behavior on animated channels) if the channel is animated
        elsewhere but not here, or just set the value directly if the
        channel has no keys anywhere.
        """
        try:
            if not cmds.keyframe(plug, query=True, keyframeCount=True):
                cmds.setAttr(plug, value)
                return
            if not cmds.keyframe(plug, query=True, time=(frame, frame), timeChange=True):
                cmds.setKeyframe(
                    plug, time=(frame, frame), value=cmds.getAttr(plug, time=frame)
                )
            cmds.keyframe(plug, edit=True, time=(frame, frame), valueChange=value)
        except Exception:
            pass

    def _write_decomposed_transform(self, target, decomposed, frame):
        channels = (
            ("translateX", decomposed["translate"][0]),
            ("translateY", decomposed["translate"][1]),
            ("translateZ", decomposed["translate"][2]),
            ("rotateX", decomposed["rotate"][0]),
            ("rotateY", decomposed["rotate"][1]),
            ("rotateZ", decomposed["rotate"][2]),
            ("scaleX", decomposed["scale"][0]),
            ("scaleY", decomposed["scale"][1]),
            ("scaleZ", decomposed["scale"][2]),
        )
        for axis, value in channels:
            self._write_keyed_or_static("{}.{}".format(target, axis), frame, value)

    def _compute_super_switch(self, target, target_attribute, value, baseline, frame):
        """Compute translate/rotate/scale that keep ``baseline`` (a world
        matrix captured before the switch) once ``target_attribute``
        becomes ``value`` at ``frame`` -- purely through matrix math, no
        playhead move. Returns None if anything about it can't be trusted.

        Reads the node's rotateOrder *after* writing the switch attribute
        (cheap either way) rather than accepting it as a precomputed
        argument, so this stays correct even in the edge case where the
        switch being applied *is* rotateOrder itself (having fallen
        through here because a target failed rotate order's own
        Euler-math eligibility) -- decomposing against the stale,
        pre-switch rotate order would silently produce the wrong values.
        """
        if not self._write_switch_attribute(target, target_attribute, value, frame):
            return None
        rotate_order = self._node_rotate_order(target)
        new_parent_inverse = maya_api.parent_inverse_matrix_at_time(target, frame)
        if new_parent_inverse is None:
            return None
        local_matrix = maya_api.multiply_matrices(baseline, new_parent_inverse)
        if local_matrix is None:
            return None
        return maya_api.decompose_local_matrix(local_matrix, rotate_order)

    def _apply_super_switch(self, targets, attribute, value, target_attributes, transforms, operation):
        """Apply the fast path to every target in ``targets`` across every
        frame in ``transforms``. Returns the subset actually completed --
        any target that fails even once is dropped entirely (not just for
        the failing frame) so the caller's normal per-frame fallback redoes
        *all* of its frames from the untouched baseline, rather than
        leaving a partial mix of fast- and slow-computed keys behind.

        Every frame's worth of writes is marshaled onto the main thread as
        one batch (self._on_main), and ``operation.cancelled`` is checked
        between frames -- this used to run every frame with no cancellation
        check at all, which is why a Cancel press during a Super mode
        switch never stopped it.
        """
        failed = set()

        def _apply_frame(frame, frame_transforms, target_batch):
            for target in target_batch:
                if target in failed:
                    continue
                baseline = frame_transforms.get(target)
                if baseline is None:
                    continue
                target_attribute = (
                    target_attributes[target] if target_attributes else attribute
                )
                decomposed = self._compute_super_switch(
                    target, target_attribute, value, baseline, frame
                )
                if decomposed is None:
                    failed.add(target)
                    continue
                self._write_decomposed_transform(target, decomposed, frame)

        for frame, frame_transforms in (transforms or {}).items():
            if operation and operation.cancelled:
                break
            for target_batch in _chunks(targets):
                if operation and operation.cancelled:
                    break
                self._on_main(operation, _apply_frame, frame, frame_transforms, target_batch)
                if operation:
                    operation.step(amount=len(target_batch))
        return targets - failed

    @staticmethod
    def _snapshot_channel(plug, frame):
        """Capture enough state to safely undo a probe write to ``plug`` at
        ``frame``: whether a key already existed exactly there, and the
        value (of that key, or the live/static value otherwise).
        """
        has_key = bool(
            cmds.keyframe(plug, query=True, time=(frame, frame), timeChange=True)
        )
        try:
            value = cmds.getAttr(plug, time=frame)
        except Exception:
            value = None
        return {"plug": plug, "had_key": has_key, "value": value}

    @staticmethod
    def _restore_channel(snapshot, frame):
        plug = snapshot["plug"]
        value = snapshot["value"]
        try:
            if snapshot["had_key"]:
                cmds.keyframe(plug, edit=True, time=(frame, frame), valueChange=value)
                return
            if cmds.keyframe(plug, query=True, time=(frame, frame), timeChange=True):
                # The probe inserted a key that wasn't there before --
                # remove it entirely instead of leaving a stray keyframe.
                cmds.cutKey(plug, time=(frame, frame))
            if value is not None:
                cmds.setAttr(plug, value)
        except Exception:
            pass

    _FAST_SWITCH_PROBE_AXES = (
        "translateX", "translateY", "translateZ",
        "rotateX", "rotateY", "rotateZ",
        "scaleX", "scaleY", "scaleZ",
    )

    def _verify_super_switch_sample(
        self, candidates, attribute, value, target_attributes, transforms, restore_time,
        tolerance=1e-3,
    ):
        """Cross-check the fast path against the proven slow path for one
        (target, frame) sample before trusting it for a whole operation.

        This math can't be exercised against real Maya scenes ahead of
        time, so every batch pays for one extra DG-evaluated frame as a
        live guardrail: if the two paths disagree beyond tolerance, Super
        mode is disabled for the rest of this session (see
        ``_suspend_super_mode``) and this call falls back to Normal mode.
        Every probe write is fully undone before returning either way.
        """
        sample = None
        for frame, frame_transforms in (transforms or {}).items():
            for target in candidates:
                if target in frame_transforms:
                    sample = (target, frame, frame_transforms[target])
                    break
            if sample:
                break
        if sample is None:
            return True

        target, frame, baseline = sample
        target_attribute = target_attributes[target] if target_attributes else attribute

        axes = self._FAST_SWITCH_PROBE_AXES
        switch_plug = "{}.{}".format(target, target_attribute)
        snapshots = [
            self._snapshot_channel("{}.{}".format(target, axis), frame) for axis in axes
        ]
        switch_snapshot = self._snapshot_channel(switch_plug, frame)

        ok = False
        try:
            fast_result = self._compute_super_switch(
                target, target_attribute, value, baseline, frame
            )
            if fast_result is None:
                return False

            if not maya_api.set_current_time(frame):
                return False
            self._set_preserving_transform(
                target, target, target_attribute, value, baseline
            )
            slow = {
                axis: cmds.getAttr("{}.{}".format(target, axis)) for axis in axes
            }

            fast = dict(zip(axes[0:3], fast_result["translate"]))
            fast.update(zip(axes[3:6], fast_result["rotate"]))
            fast.update(zip(axes[6:9], fast_result["scale"]))
            ok = all(abs(fast[axis] - slow[axis]) <= tolerance for axis in axes)
        except Exception:
            ok = False
        finally:
            for snapshot in snapshots:
                self._restore_channel(snapshot, frame)
            self._restore_channel(switch_snapshot, frame)
            maya_api.set_current_time(restore_time)

        if not ok:
            self._suspend_super_mode()
        return ok

    def _apply_multiple_frames(
        self,
        attribute,
        value,
        keyframes,
        target_attributes=None,
        target_switch_nodes=None,
        transforms=None,
    ):
        """Safe to call from either the main thread or (via
        apply_switch/apply_switches' worker-thread dispatch) a worker
        thread -- every cmds/OpenMaya touch below routes through
        self._on_main(), which collapses to a plain inline call when
        there's no thread to hop from.
        """
        operation = toolCommon.current_tool_operation()
        current_time = self._on_main(operation, self._current_time)
        try:
            frames = list(keyframes)
            if operation and frames:
                # ensure_operation_tint() is a no-op if the operation
                # already has a tint -- e.g. apply_switches() already gave
                # the shared "attribute_switcher_multi" operation one
                # covering every staged switch's frames up front, so this
                # only actually opens one here for a standalone switch. If
                # Maya's playbackOptions guard below matters, it's cheap
                # enough to just repeat per call rather than track whether
                # it's already been set once for this operation.
                def _begin_range():
                    if maya_runtime.supports_playback_selection():
                        cmds.playbackOptions(sv=False)
                    toolCommon.ensure_operation_tint(
                        operation,
                        tint="range",
                        timerange=(frames[0], frames[-1]),
                        tint_key="attribute_switcher_range",
                        tint_color=registry.get_tool_tint_color("attribute_switcher"),
                    )
                self._on_main(operation, _begin_range)
            if operation:
                operation.set_status("Applying Positions")

            fast_targets = set()
            if self._super_mode_active():
                def _collect_candidates():
                    all_targets = {
                        target
                        for frame_transforms in (transforms or {}).values()
                        for target in frame_transforms
                    }
                    return {
                        target for target in all_targets
                        if self._switch_fast_eligible(target)
                        and (target_switch_nodes or {}).get(target, target) == target
                    }
                candidates = self._on_main(operation, _collect_candidates)
                verified = bool(candidates) and self._on_main(
                    operation,
                    self._verify_super_switch_sample,
                    candidates, attribute, value, target_attributes, transforms,
                    current_time,
                )
                if candidates and verified:
                    fast_targets = self._apply_super_switch(
                        candidates, attribute, value, target_attributes,
                        transforms, operation,
                    )

            for frame, frame_transforms in (transforms or {}).items():
                if operation and operation.cancelled:
                    break
                relevant = {
                    target: transform
                    for target, transform in frame_transforms.items()
                    if target not in fast_targets
                }
                if relevant:
                    relevant_items = list(relevant.items())
                    for relevant_batch in _chunks(relevant_items):
                        if operation and operation.cancelled:
                            break
                        batch_relevant = dict(relevant_batch)
                        self._on_main(
                            operation,
                            self._apply_relevant_at_frame,
                            frame, batch_relevant, attribute, value, target_attributes,
                            target_switch_nodes,
                        )
                        if operation:
                            operation.step(amount=len(batch_relevant))
                elif operation and not fast_targets:
                    operation.step()
        finally:
            self._on_main(operation, maya_api.set_current_time, current_time)

    def _apply_relevant_at_frame(
        self,
        frame,
        relevant,
        attribute,
        value,
        target_attributes,
        target_switch_nodes,
    ):
        if not maya_api.set_current_time(frame):
            return
        for target, transform in relevant.items():
            target_attribute = (
                target_attributes[target] if target_attributes else attribute
            )
            switch_node = (target_switch_nodes or {}).get(target, target)
            self._set_preserving_transform(
                target, switch_node, target_attribute, value, transform
            )

    @staticmethod
    def _collect_keyframes(targets, all_frames, timeline_selection, selected_range):
        if not timeline_selection and not all_frames:
            current = maya_api.current_time()
            return [
                current if current is not None else cmds.currentTime(query=True)
            ]
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
        operation = toolCommon.current_tool_operation()
        target_info = animation.resolve_context(
            default_mode="all_animation",
            include_channels=True,
            include_shapes=False,
        )
        curves = []
        for target in targets:
            plugs = [
                "{}.{}".format(target, attribute)
                for attribute in ("rx", "ry", "rz")
                if cmds.objExists("{}.{}".format(target, attribute))
            ]
            curves.extend(
                animation.layer_graph.curves_for_plugs(
                    plugs,
                    include_all_layers=True,
                )
            )
        curves = list(dict.fromkeys(curves))
        if curves:
            with animation.preserve_key_selection():
                animation.apply_smart_euler_filter(
                    curves,
                    target_info,
                    operation=operation,
                )
