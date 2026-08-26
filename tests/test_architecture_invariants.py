import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureInvariantTests(unittest.TestCase):
    def test_help_menu_links_to_github_below_documentation(self):
        menu = (
            ROOT / "TheKeyMachine/tools/tkm_menu/__init__.py"
        ).read_text(encoding="utf-8")
        documentation = menu.index('"label": "Documentation"')
        github = menu.index('"label": "GitHub"')
        discord = menu.index('"label": "Discord"')

        self.assertLess(documentation, github)
        self.assertLess(github, discord)
        self.assertIn('"icon": "github"', menu[github:discord])
        self.assertIn("https://github.com/Alehaaaa/TKM", menu[github:discord])
        self.assertTrue((ROOT / "TheKeyMachine/data/icons/github.svg").is_file())

    def test_check_for_updates_is_threaded_without_progress_eta(self):
        definitions = (
            ROOT / "TheKeyMachine/tools/tkm_menu/__init__.py"
        ).read_text(encoding="utf-8")
        check_tool = definitions.split('"check_for_updates": {', 1)[1].split(
            '"install_update": {', 1
        )[0]
        update = (
            ROOT / "TheKeyMachine/tools/update/controller.py"
        ).read_text(encoding="utf-8")
        check = update.split("def check_for_updates(", 1)[1].split(
            "\n\ndef ", 1
        )[0]

        self.assertIn('"progress": False', check_tool)
        self.assertIn("operation.run_worker(", check)
        self.assertNotIn("operation.set_total(", check)
        self.assertNotIn("operation.set_status(", check)

    def test_reload_refreshes_the_root_package_in_place(self):
        source = (ROOT / "TheKeyMachine/__init__.py").read_text(encoding="utf-8")
        reload_source = source.split("def reload():", 1)[1].split(
            "\n\ndef unload", 1
        )[0]

        self.assertIn("package = sys.modules.get(__name__)", reload_source)
        self.assertIn("importlib.reload(package)", reload_source)
        self.assertNotIn("globals()", reload_source)

        self.assertLess(
            reload_source.index("importlib.reload(package)"),
            reload_source.index(
                'importlib.import_module("TheKeyMachine.ui.widgets.toolbar")'
            ),
        )

    def test_worker_implementation_is_private_to_tool_operation(self):
        for path in (ROOT / "TheKeyMachine").rglob("*.py"):
            if path.name == "common.py":
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "_run_worker_thread(",
                source,
                "{} bypasses ToolOperation.run_worker()".format(path),
            )

    def test_operation_is_the_only_refresh_and_undo_lifecycle_owner(self):
        common = (ROOT / "TheKeyMachine/tools/common.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("def suspend_maya_refresh(", common)
        self.assertNotIn("cmds.refresh(query=True", common)
        lifecycle_calls = (
            "cmds.undoInfo(openChunk=True",
            "cmds.undoInfo(closeChunk=True",
            "cmds.refresh(suspend=True",
            "cmds.refresh(suspend=False",
        )
        for path in (ROOT / "TheKeyMachine/tools").rglob("*.py"):
            if path.name == "common.py":
                continue
            source = path.read_text(encoding="utf-8")
            for lifecycle_call in lifecycle_calls:
                self.assertNotIn(
                    lifecycle_call,
                    source,
                    "{} bypasses ToolOperation lifecycle ownership".format(path),
                )

    def test_only_interactive_sessions_open_operations_outside_dispatch(self):
        allowed = {
            "animation_offset/api.py",  # one undo lifecycle while enabled
            "global_curve/controller.py",  # reactive drag/edit callback
            "sliders/session.py",  # one undo lifecycle per slider gesture
        }
        tools_root = ROOT / "TheKeyMachine/tools"
        for path in tools_root.rglob("*.py"):
            if path.name == "common.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            opens_operation = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "tool_operation"
                for node in ast.walk(tree)
            )
            if opens_operation:
                self.assertIn(
                    str(path.relative_to(tools_root)),
                    allowed,
                    "{} opens a lifecycle instead of using dispatch".format(path),
                )

    def test_delayed_feedback_threshold_is_500_ms(self):
        source = (ROOT / "TheKeyMachine/tools/common.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("PROGRESS_SHOW_DELAY_MS = 500", source)

    def test_worker_strategy_skips_known_tiny_coordinators(self):
        source = (ROOT / "TheKeyMachine/tools/common.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("WORKER_MIN_WORK_ITEMS = 8", source)
        self.assertIn('work_items = kwargs.pop("work_items", None)', source)

    def test_worker_reentry_is_serialized_after_operation_cleanup(self):
        common = (ROOT / "TheKeyMachine/tools/common.py").read_text(
            encoding="utf-8"
        )
        trigger = (ROOT / "TheKeyMachine/core/trigger.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def defer_tool_callback(", common)
        self.assertIn("def _schedule_deferred_tool_callback(", common)
        self.assertIn("operation.preserved_time_selection", common)
        self.assertIn("_schedule_deferred_tool_callback()", common)
        self.assertIn(
            'getattr(active_operation, "accepts_deferred_commands", False)',
            trigger,
        )
        self.assertIn('queued["delta"] += queue_delta', common)
        self.assertNotIn("def settle_queue_steps(", common)
        self.assertNotIn("active_operation.accumulate_queue_delta(", trigger)

    def test_nudge_commands_declare_signed_queue_accumulation(self):
        definitions = (
            ROOT / "TheKeyMachine/tools/nudge/__init__.py"
        ).read_text(encoding="utf-8")
        api = (
            ROOT / "TheKeyMachine/tools/nudge/api.py"
        ).read_text(encoding="utf-8")
        self.assertIn('return {"queue_group": "nudge_{}".format(group)', definitions)
        self.assertGreaterEqual(definitions.count("_queued_nudge("), 11)
        self.assertIn('"suspend_refresh": True', definitions)
        self.assertIn('return int(kwargs.pop("steps", default))', api)
        controller = (
            ROOT / "TheKeyMachine/tools/nudge/controller.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(controller.count("operation.run_worker(_apply)"), 4)

    def test_operation_owns_the_shared_batch_processor(self):
        source = (ROOT / "TheKeyMachine/tools/common.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def process(\n", source)
        self.assertIn("self.run_on_main(edit_batch, batch)", source)

    def test_paste_avoids_scene_wide_dirty_and_per_key_tangent_restore(self):
        controller = (
            ROOT / "TheKeyMachine/tools/copy_paste/controller.py"
        ).read_text(encoding="utf-8")
        curves = (
            ROOT / "TheKeyMachine/maya/animation/curves.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("dgdirty(allPlugs=True)", controller)
        self.assertIn("apply_key_tangent_snapshots(", controller)
        self.assertIn("def apply_key_tangent_snapshots(", curves)

    def test_delayed_paste_actions_dispatch_registered_apply_commands(self):
        widgets = (
            ROOT / "TheKeyMachine/tools/copy_paste/widgets.py"
        ).read_text(encoding="utf-8")
        definitions = (
            ROOT / "TheKeyMachine/tools/copy_paste/__init__.py"
        ).read_text(encoding="utf-8")
        self.assertIn("trigger.execute_command(", widgets)
        self.assertIn('"paste_animation_to_apply"', definitions)
        self.assertIn('"paste_pose_to_apply"', definitions)
        self.assertNotIn("apply_callback", widgets)

    def test_confirmed_edits_dispatch_after_ui_only_commands(self):
        api = (
            ROOT / "TheKeyMachine/tools/selection_sets/api.py"
        ).read_text(encoding="utf-8")
        definitions = (
            ROOT / "TheKeyMachine/tools/selection_sets/__init__.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"selection_sets_clear_all_apply"', definitions)
        self.assertIn('"progress": False, "undo": False', definitions)
        self.assertIn('trigger.execute_command(\n                "selection_sets_clear_all_apply"', api)

    def test_smart_euler_is_shared_by_tools_that_change_rotation(self):
        curves = (
            ROOT / "TheKeyMachine/maya/animation/curves.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def apply_smart_euler_filter(", curves)
        for path in (
            ROOT / "TheKeyMachine/tools/attribute_switcher/controller.py",
            ROOT / "TheKeyMachine/tools/align/api.py",
            ROOT / "TheKeyMachine/tools/gimbal_fixer/controller.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn("animation.apply_smart_euler_filter(", source)
            self.assertNotIn("cmds.filterCurve(", source)

        attribute_switcher = (
            ROOT / "TheKeyMachine/tools/attribute_switcher/controller.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "from TheKeyMachine.maya import animation, selection",
            attribute_switcher,
        )

        offset = (
            ROOT / "TheKeyMachine/tools/animation_offset/api.py"
        ).read_text(encoding="utf-8")
        self.assertIn("full_turn = animation.euler_full_turn()", offset)

    def test_attribute_switcher_expands_grouped_rows_for_individual_choices(self):
        widgets = (
            ROOT / "TheKeyMachine/tools/attribute_switcher/widgets.py"
        ).read_text(encoding="utf-8")
        expanded = widgets.split(
            "    def _expanded_multi_entries(", 1
        )[1].split("\n    def _on_attribute_multi_checked", 1)[0]
        checked = widgets.split(
            "    def _on_attribute_multi_checked(", 1
        )[1].split("\n    def _close_multi_switch_dialog", 1)[0]

        self.assertIn("class _StagedAttributeEntry:", widgets)
        self.assertIn("for target, object_data in item.objects_map.items():", expanded)
        self.assertIn("self.controller.build_options_map(", expanded)
        self.assertIn("entries = self._expanded_multi_entries(selected_entries)", checked)
        self.assertIn("if len(entries) < 2:", checked)

    def test_rotation_order_quality_text_is_shared_by_both_pickers(self):
        widgets = (
            ROOT / "TheKeyMachine/tools/attribute_switcher/widgets.py"
        ).read_text(encoding="utf-8")
        analyzer = (
            ROOT / "TheKeyMachine/tools/gimbal_fixer/controller.py"
        ).read_text(encoding="utf-8")
        self.assertIn('labels[index] = "Best"', analyzer)
        self.assertIn('labels[index] = "Good"', analyzer)
        self.assertIn('labels[index] = "OK"', analyzer)
        self.assertNotIn("_ROTATION_ORDER_QUALITY_LABELS", widgets)
        self.assertEqual(
            widgets.count("_rotation_order_option_text("),
            3,
        )

    def test_tool_context_exposes_its_invocation_snapshot(self):
        source = (
            ROOT / "TheKeyMachine/maya/animation/context.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def selection_snapshot(self):", source)
        self.assertIn('return self.get("selection_snapshot")', source)

    def test_tools_use_the_public_tool_context_contract(self):
        context_source = (
            ROOT / "TheKeyMachine/maya/animation/context.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def replace(self, **changes):", context_source)
        self.assertIn("target_info = target_info.replace(", context_source)

        raw_fields = (
            "target_objects", "target_plugs", "selected_channels",
            "selected_curves", "selected_keyframes", "time_context",
            "layer_context", "selection_snapshot",
        )
        for path in (ROOT / "TheKeyMachine/tools").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for field in raw_fields:
                self.assertNotIn(
                    'target_info.get("{}")'.format(field),
                    source,
                    "{} bypasses ToolContext.{}".format(path, field),
                )
                self.assertNotIn(
                    'target_info["{}"]'.format(field),
                    source,
                    "{} bypasses ToolContext.{}".format(path, field),
                )

        animation_tools = (
            ROOT / "TheKeyMachine/tools/animation_tools/controller.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("dict(target_info)", animation_tools)
        self.assertIn("target_info.replace(", animation_tools)

        public_attributes = {
            "selection_snapshot", "time", "layer_scope", "layers",
            "objects", "plugs", "curves", "channels", "selected_keys",
            "source", "has_graph_keys", "replace", "key_times",
            "key_data", "curves_for_plugs", "key_range",
        }
        for path in (ROOT / "TheKeyMachine/tools").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            context_names = set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                call = node.value
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "resolve_context"
                ):
                    continue
                context_names.update(
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                )
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in context_names
                ):
                    continue
                self.assertIn(
                    node.attr,
                    public_attributes,
                    "{} uses unsupported ToolContext.{}".format(
                        path, node.attr
                    ),
                )

    def test_nudge_delegates_snap_to_animation_curve_tools_api(self):
        source = (
            ROOT / "TheKeyMachine/tools/nudge/controller.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _snap_nudged_keys(", source)
        self.assertIn("animationToolsApi.snap,", source)
        self.assertNotIn("bisect_left", source)
        self.assertNotIn("def _collision_targets(", source)
        self.assertNotIn("def _snap_touched_collisions(", source)
        self.assertNotIn("def _on_main(", source)
        self.assertNotIn("def _run_threaded_nudge(", source)
        self.assertNotIn("threading.RLock", source)
        self.assertIn('animation="keys"', source)
        self.assertIn("def _move_active_keyset():", source)
        snap_api = (
            ROOT / "TheKeyMachine/tools/animation_tools/api.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def snap(selected_range=None, **kwargs):", snap_api)

    def test_nudge_snap_collision_toggle_is_shared_and_enabled_by_default(self):
        definitions = (
            ROOT / "TheKeyMachine/tools/nudge/__init__.py"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT / "TheKeyMachine/tools/nudge/controller.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            definitions.count(
                '{"type": "check", "command": "nudge_snap_collision"}'
            ),
            2,
        )
        self.assertIn('"state_key": "nudge_snap_collision"', definitions)
        self.assertIn(
            'settings.get_setting(SNAP_COLLISION_SETTING, True)',
            controller,
        )
        self.assertEqual(controller.count("if not is_snap_collision_enabled():"), 1)

    def test_explicit_snap_key_times_are_not_shadowed_between_curves(self):
        source = (
            ROOT / "TheKeyMachine/tools/animation_tools/controller.py"
        ).read_text(encoding="utf-8")
        snap = source.split("def snap_keyframes(", 1)[1].split(
            "\n\ndef clear_selected_keys", 1
        )[0]

        self.assertIn("explicit_key_times = {", snap)
        self.assertIn("explicit_key_times.get(curve, ())", snap)
        self.assertIn("for rounded_time, bucket_key_times", snap)
        self.assertNotIn("for rounded_time, key_times", snap)

    def test_time_slider_guard_does_not_release_operation_refresh(self):
        timeline = (
            ROOT / "TheKeyMachine/ui/widgets/timeline.py"
        ).read_text(encoding="utf-8")
        guard = timeline.split("def suspend_time_slider_updates():", 1)[1].split(
            "\n\ndef _restore_current_frame", 1
        )[0]
        self.assertIn("slider.setUpdatesEnabled(False)", guard)
        self.assertIn("slider.setUpdatesEnabled(updates_were_enabled)", guard)
        self.assertNotIn("cmds.refresh(", guard)
        self.assertNotIn("manage=", guard)

        nudge = (
            ROOT / "TheKeyMachine/tools/nudge/controller.py"
        ).read_text(encoding="utf-8")
        move_range = nudge.split("            def _move_range():", 1)[1].split(
            "\n            if not edited:", 1
        )[0]
        self.assertIn("_restore_nudged_time_range(", move_range)
        range_branch = nudge.split(
            '        if time_context.mode == "time_slider_range":', 1
        )[1].split("\n        curves = _unique(target_curves)", 1)[0]
        collision_merge = range_branch.index("_snap_nudged_keys(")
        final_restore = range_branch.index(
            "range_restored = False", collision_merge
        )
        self.assertGreater(final_restore, collision_merge)
        self.assertGreaterEqual(nudge.count("update=False"), 4)

    def test_auto_pause_defers_refresh_outside_animation_callback(self):
        source = (
            ROOT / "TheKeyMachine/maya/viewport.py"
        ).read_text(encoding="utf-8")
        callback = source.split(
            "def _on_anim_keyframe_edited(*_args):", 1
        )[1].split("\n\ndef cleanup", 1)[0]
        flush = source.split(
            "def _flush_auto_refresh(generation):", 1
        )[1].split("\n\ndef _on_pre_render", 1)[0]

        self.assertIn("utils.executeDeferred(", source)
        self.assertIn("_schedule_auto_refresh()", callback)
        self.assertNotIn("_remove_callbacks()", callback)
        self.assertIn("_auto_refresh_active = True", flush)
        self.assertIn("_safe_refresh(suspend=True)", flush)

    def test_nested_temporal_control_uses_reparented_dag_path(self):
        source = (
            ROOT / "TheKeyMachine/tools/temporal_controls/api.py"
        ).read_text(encoding="utf-8")
        creation = source.split(
            "def _create_control_for(", 1
        )[1].split("\n\ndef _build_control_hierarchy", 1)[0]
        parenting = source.split(
            "def _parent_nested_control(", 1
        )[1].split("\n\ndef _nested_parent_for", 1)[0]

        self.assertIn("obj = _parent_nested_control(control, obj)", creation)
        self.assertIn("stored_root = TkmSceneNode(obj).get_attr(DELETE_ROOT_ATTR)", parenting)
        self.assertIn("parented = cmds.parent(nested_root, control) or []", parenting)
        self.assertIn("matches = cmds.ls(parented[0], long=True) or []", parenting)
        self.assertIn("_remap_temporal_dag_paths(old_root, nested_root)", parenting)
        self.assertIn("return target_matches[0]", parenting)

        nested_bake = source.split(
            "def _bake_nested_control(", 1
        )[1].split("\n\ndef _constrain_nested_bake_transform", 1)[0]
        self.assertIn('cmds.createNode("transform", name="TKM_nestedBakeCapture#")', nested_bake)
        self.assertIn("_restore_nested_parent(control, obj, original_parent)", nested_bake)
        self.assertIn("_bake_range_to_target(nested_root, CHANNELS, start, end)", nested_bake)

    def test_selection_set_ui_mutations_use_shared_callback_dispatch(self):
        source = (
            ROOT / "TheKeyMachine/tools/selection_sets/widgets.py"
        ).read_text(encoding="utf-8")
        menu = source.split("    def _show_set_menu(", 1)[1].split(
            "\n\ndef make_selection_set_members_dialog", 1
        )[0]
        self.assertIn("menu = cw.MenuWidget(", menu)
        self.assertNotIn("QtWidgets.QMenu(", menu)
        self.assertNotIn(".triggered.connect(", menu)
        self.assertIn("toolCommon.run_tool_callback(", source)

    def test_selection_and_delete_tools_receive_their_operation_explicitly(self):
        selection_api = (
            ROOT / "TheKeyMachine/tools/selection/api.py"
        ).read_text(encoding="utf-8")
        animation_api = (
            ROOT / "TheKeyMachine/tools/animation_tools/api.py"
        ).read_text(encoding="utf-8")
        temporal = (
            ROOT / "TheKeyMachine/tools/temporal_controls/api.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def select_hierarchy(*args, tool_operation=None):", selection_api)
        self.assertIn("def delete_keyframes_before_current_time(*args, tool_operation=None):", animation_api)
        self.assertIn("def bake_controls(*_args, tool_operation=None):", temporal)

    def test_animation_offset_defers_key_sampling_until_edit(self):
        source = (
            ROOT / "TheKeyMachine/tools/animation_offset/api.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"keys": None', source)
        self.assertIn("if keyed_values is None:", source)
        capture = source.split(
            "    def _capture_object_snapshot(self, obj):", 1
        )[1].split("    def _capture_current_values(self):", 1)[0]
        self.assertNotIn("_is_supported_plug", capture)
        activate = source.split("    def activate(self):", 1)[1].split(
            "    def deactivate(self):", 1
        )[0]
        self.assertNotIn("cmds.select(", activate)

    def test_tracer_creation_is_full_resolution_without_a_second_resample(self):
        api = (
            ROOT / "TheKeyMachine/tools/tracer/api.py"
        ).read_text(encoding="utf-8")
        build = api.split("def _build_tracer_scene(", 1)[1].split(
            "\ndef _tracer_sources_for", 1
        )[0]
        self.assertIn("increment=1", build)
        self.assertNotIn("initial_increment", build)
        self.assertNotIn("PERFORMANCE_PROFILES[get_performance()]", build)
        self.assertIn("cmds.disconnectAttr(points_source, points_destination)", build)
        self.assertNotIn("request_refresh(immediate=True)", build)
        wrapper = api.split("def _build_tracer(", 1)[1].split(
            "\ndef _build_tracer_scene", 1
        )[0]
        self.assertIn("controller.cancel_pending()", wrapper)
        self.assertIn("controller.disable()", wrapper)

    def test_tracer_profiles_batch_ranges_without_skipping_frames(self):
        api = (
            ROOT / "TheKeyMachine/tools/tracer/api.py"
        ).read_text(encoding="utf-8")
        profiles = api.split("PERFORMANCE_PROFILES =", 1)[1].split(
            "\nPERFORMANCE_ORDER", 1
        )[0]
        refresh = api.split("def _playback_sample_range(", 1)[1].split(
            "\ndef refresh_tracer", 1
        )[0]
        scheduler = api.split("class _RefreshScheduler", 1)[1].split(
            "\n\nclass TracerUpdateController", 1
        )[0]

        self.assertIn('"batch_radii": (0,)', profiles)
        self.assertIn('"batch_radii": (12, 0)', profiles)
        self.assertIn('"batch_radii": (6, 18, 48, 0)', profiles)
        self.assertNotIn('"increments"', profiles)
        self.assertIn("_evaluate_tracer_range(node_name, start_frame, end_frame)", refresh)
        self.assertIn("cmds.setAttr(increment_plug, 1)", refresh)
        self.assertNotIn("increment + 1", refresh)
        self.assertIn('tuple(profile["batch_radii"])', scheduler)

    def test_tracer_has_no_legacy_live_connection_support(self):
        source = (
            ROOT / "TheKeyMachine/tools/tracer/api.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("def is_physically_connected(", source)
        self.assertNotIn("migrate the old live connection", source)
        tracer_names = source.split("def _tracer_names():", 1)[1].split(
            "\ndef _sync_active_names", 1
        )[0]
        self.assertIn("_stored_tracer_group(candidate)", tracer_names)

    def test_update_is_staged_before_live_package_replacement(self):
        source = (
            ROOT / "TheKeyMachine/tools/update/controller.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _stage_update_archive(", source)
        self.assertIn("def _commit_staged_update(", source)
        self.assertIn("os.replace(tools_folder, backup_folder)", source)

    def test_operation_has_no_transitional_nested_lifecycle(self):
        common = (ROOT / "TheKeyMachine/tools/common.py").read_text(
            encoding="utf-8"
        )
        copy_paste = (
            ROOT / "TheKeyMachine/tools/copy_paste/controller.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Nested tool_operation() lifecycles are not supported", common)
        self.assertNotIn("parent_operation = current_tool_operation()", common)
        self.assertNotIn("_copy_paste_feedback", copy_paste)
        self.assertNotIn('operation["operation"]', copy_paste)
        for path in (ROOT / "TheKeyMachine/tools").rglob("*.py"):
            if path.name == "common.py":
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                ".success =",
                source,
                "{} bypasses ToolOperation.succeed()".format(path),
            )

    def test_saved_animation_formats_require_current_schemas(self):
        copy_paste = (
            ROOT / "TheKeyMachine/tools/copy_paste/controller.py"
        ).read_text(encoding="utf-8")
        animation_layers = (
            ROOT / "TheKeyMachine/tools/animation_layers/controller.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'metadata.get("version") == ANIMATION_SCHEMA_VERSION', copy_paste
        )
        self.assertIn(
            'metadata.get("version") == POSE_SCHEMA_VERSION', copy_paste
        )
        self.assertIn("EXPORT_SCHEMA_VERSION = 1", animation_layers)
        self.assertNotIn("bare list of keys", animation_layers)

    def test_temporal_controls_have_current_space_and_storage_schemas(self):
        api = (
            ROOT / "TheKeyMachine/tools/temporal_controls/api.py"
        ).read_text(encoding="utf-8")
        shapes = (
            ROOT / "TheKeyMachine/tools/temporal_controls/shapes.py"
        ).read_text(encoding="utf-8")
        self.assertIn('{"id": "camera", "label": "Camera Space"}', api)
        self.assertIn("def _active_viewport_camera():", api)
        self.assertIn("def _ensure_camera_space_hierarchy(control):", api)
        self.assertIn("def _camera_space_driver(control, group_kind, camera):", api)
        self.assertIn('if space_mode == "camera":', api)
        self.assertIn("def _camera_space_key_times(control, group_kind):", api)
        self.assertNotIn('json.dumps([])', api)
        self.assertNotIn('"legacy"', api)
        self.assertNotIn('"cross": cross', shapes)

    def test_fast_modes_use_one_super_mode_vocabulary(self):
        temporal = (
            ROOT / "TheKeyMachine/tools/temporal_controls/api.py"
        ).read_text(encoding="utf-8")
        switcher = (
            ROOT / "TheKeyMachine/tools/attribute_switcher/controller.py"
        ).read_text(encoding="utf-8")
        switcher_api = (
            ROOT / "TheKeyMachine/tools/attribute_switcher/api.py"
        ).read_text(encoding="utf-8")
        switcher_lang = (
            ROOT / "TheKeyMachine/tools/attribute_switcher/lang.json"
        ).read_text(encoding="utf-8")

        self.assertIn('SUPER_MODE_SETTING = "super_mode"', temporal)
        self.assertIn('SUPER_MODE_KEY = "rotate_order_super_mode"', switcher)
        self.assertIn('"rotate_order_super_mode"', switcher_api)
        self.assertIn('"rotate_order_super_mode"', switcher_lang)
        old_name = "light" + "ning"
        for path in (ROOT / "TheKeyMachine").rglob("*"):
            if path.suffix not in (".py", ".json", ".md"):
                continue
            self.assertNotIn(
                old_name,
                path.read_text(encoding="utf-8").lower(),
                "{} still uses the retired mode name".format(path),
            )

    def test_temporal_control_animation_sampling_uses_an_isolated_driver(self):
        api = (
            ROOT / "TheKeyMachine/tools/temporal_controls/api.py"
        ).read_text(encoding="utf-8")
        copy_source = api.split(
            "def _copy_source_keys_to_control(", 1
        )[1].split("\n\ndef _capture_channel", 1)[0]
        self.assertIn('cmds.createNode("transform", **sampler_kwargs)', copy_source)
        self.assertIn("cmds.parentConstraint(", copy_source)
        self.assertIn("sampler, control, spatial_key_data", copy_source)
        self.assertNotIn("cmds.pointConstraint(obj, control", copy_source)
        self.assertNotIn("cmds.orientConstraint(obj, control", copy_source)

    def test_animbot_selection_set_conversion_remains_supported(self):
        controller = (
            ROOT / "TheKeyMachine/tools/selection_sets/controller.py"
        ).read_text(encoding="utf-8")
        api = (
            ROOT / "TheKeyMachine/tools/selection_sets/api.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ANIMBOT_SELECTION_SETS_ROOT", controller)
        self.assertIn("def pending_animbot_selection_sets(self):", controller)
        self.assertIn("def convert_animbot_selection_sets(self, entries=None):", controller)
        self.assertIn("controller.pending_animbot_selection_sets()", api)


if __name__ == "__main__":
    unittest.main()
