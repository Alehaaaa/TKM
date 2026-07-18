"""
TheKeyMachine - Curve-level Slider Operations

Operations that work directly on animation curves and their keys.
"""

import maya.cmds as cmds
import random

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

import TheKeyMachine.core.openMayaUtils as omutils
from TheKeyMachine.core import curveFitting
from TheKeyMachine.sliders import mode_values, utils


def _ensure_curve_value_cache(session, curve, keys):
    """Caches original values for ALL keyframes on a curve for stable dragging."""
    if curve not in session.cache.original_keyframes:
        cached = None
        curve_fn = omutils.anim_curve_fn(curve)
        if curve_fn is not None:
            try:
                num_keys = curve_fn.numKeys() if callable(curve_fn.numKeys) else curve_fn.numKeys
                cached = {
                    float(curve_fn.input(i).value): curve_fn.value(i)
                    for i in range(num_keys)
                }
            except Exception:
                pass
        if cached is None:
            data = cmds.keyframe(curve, query=True, timeChange=True, valueChange=True) or []
            cached = {float(data[i]): data[i + 1] for i in range(0, len(data), 2)}
        session.cache.original_keyframes[curve] = cached

    # Current-frame targets are valid even without an existing key. Cache the
    # evaluated drag-start value so every value slider treats that virtual key
    # exactly like an existing selected key, then creates it through _apply_value.
    original_data = session.cache.original_keyframes[curve]
    curve_fn = omutils.anim_curve_fn(curve)
    for time in keys or []:
        time = float(time)
        if time in original_data:
            continue
        value = None
        if curve_fn is not None and om is not None:
            try:
                value = curve_fn.evaluate(om.MTime(time, omutils.time_unit()))
            except Exception:
                pass
        if value is None:
            try:
                values = cmds.keyframe(curve, query=True, eval=True, time=(time, time)) or []
                value = float(values[0]) if values else None
            except Exception:
                pass
        if value is not None:
            original_data[time] = value


def _cached_curve_values(session, curve, keys):
    _ensure_curve_value_cache(session, curve, keys)
    return session.cache.original_keyframes[curve]


def _cached_value_at_time(session, curve, time):
    original_data = _cached_curve_values(session, curve, [time])
    if time in original_data:
        return original_data[time]
    curve_fn = omutils.anim_curve_fn(curve)
    if curve_fn is not None and om is not None:
        try:
            value = curve_fn.evaluate(om.MTime(float(time), omutils.time_unit()))
            original_data[time] = value
            return value
        except Exception:
            pass
    try:
        values = cmds.keyframe(curve, query=True, eval=True, time=(time, time)) or []
        if values:
            value = float(values[0])
            original_data[time] = value
            return value
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------------------------------------------------
#                                                    Curve Value Helpers                                              #
# ---------------------------------------------------------------------------------------------------------------------


# Redundant helpers removed, using utils instead


def _neighbor_values(curve, time, target_times_set, all_keys, original_data):
    p_time, n_time = utils.get_block_neighbors(time, target_times_set, all_keys)
    orig_val = original_data.get(time, original_data.get(p_time, 0.0))
    p_val = original_data.get(p_time, orig_val)
    n_val = original_data.get(n_time, orig_val)
    return p_time, p_val, n_time, n_val


def _apply_value(session, curve, time, value):
    if getattr(session, "preview", False):
        mode_values.apply_curve_value(session, curve, time, value, create=True, allow_cmds_fallback=False)
        return
    mode_values.apply_curve_value(session, curve, time, value, create=True, allow_cmds_fallback=True)


def _curve_default_value(curve):
    try:
        output = cmds.listConnections(f"{curve}.output", source=False, destination=True, plugs=True) or []
        if not output:
            return 0.0
        plug = output[0]
        node, attr = plug.split(".", 1)
        defaults = cmds.attributeQuery(attr, node=node, listDefault=True)
        if defaults:
            return float(defaults[0])
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------------------------------------------------
#                                               Direct Curve Operations                                               #
# ---------------------------------------------------------------------------------------------------------------------


def apply_smooth(session, curves=None, factor=1.0):
    """Smooths the curve values toward the average of their block-aware neighbors."""
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)

        for time in keys:
            if time not in original_data:
                continue

            orig_val = original_data[time]
            p_time, p_val, n_time, n_val = _neighbor_values(curve, time, target_times_set, all_keys, original_data)

            w_p = 1.0 / abs(time - p_time) if p_time is not None and p_time != time else 0
            w_n = 1.0 / abs(n_time - time) if n_time is not None and n_time != time else 0

            if w_p + w_n > 0:
                avg = (p_val * w_p + n_val * w_n) / (w_p + w_n)
                res = orig_val + (avg - orig_val) * factor
                _apply_value(session, curve, time, res)


def apply_rough(session, curves=None, factor=1.0):
    """Push keys away from the neighbor trend only when that trend has motion."""
    factor = 1.0 + max(0.0, factor)
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)

        for time in keys:
            if time not in original_data:
                continue

            orig_val = original_data[time]
            p_time, p_val, n_time, n_val = _neighbor_values(curve, time, target_times_set, all_keys, original_data)
            if p_time is None or n_time is None or p_time == n_time:
                continue
            if p_val is None or n_val is None or abs(n_val - p_val) <= 0.000001:
                continue

            lerp_t = (time - p_time) / (n_time - p_time)
            pivot = p_val + lerp_t * (n_val - p_val)
            _apply_value(session, curve, time, pivot + (orig_val - pivot) * factor)


def apply_noise(session, curves=None, factor=1.0):
    """Add stable random noise scaled to each curve's value range."""
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        curve_values = list(original_data.values())
        value_range = (max(curve_values) - min(curve_values)) if curve_values else 0.0
        amplitude = max(value_range * 0.15, 0.001) * max(0.0, min(1.0, factor))
        if curve not in session.cache.initial_noise:
            session.cache.initial_noise[curve] = [random.uniform(-1, 1) for _ in keys]

        noise_seeds = session.cache.initial_noise[curve]

        for i, time in enumerate(keys):
            if time in original_data:
                init_val = original_data[time]
                noise = noise_seeds[i] * amplitude
                _apply_value(session, curve, time, init_val + noise)


def apply_wave(session, curves=None, factor=1.0):
    """Offset consecutive keys with an alternating positive/negative wave."""
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = sorted(set(target_times_per_curve.get(curve, [])))
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        target_values = [original_data[time] for time in keys if time in original_data]
        if not target_values:
            continue

        value_range = max(target_values) - min(target_values)
        if abs(value_range) <= 0.000001:
            max_amplitude = omutils.anim_curve_attr_value_to_curve_value(curve, 1.0)
        else:
            max_amplitude = value_range * 3.0
        amplitude = max_amplitude * max(0.0, min(1.0, factor))

        for index, time in enumerate(keys):
            if time not in original_data:
                continue
            direction = 1.0 if index % 2 == 0 else -1.0
            _apply_value(session, curve, time, original_data[time] + direction * amplitude)


def apply_ease(session, curve_list=None, factor=0.5):
    """Applies easing (in/out) to the curve values."""

    def ease_in(t, p=3):
        return pow(t, p)

    def ease_out(t, p=3):
        return 1 - pow(1 - t, p)

    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys or len(keys) < 2:
            continue

        original_data = _cached_curve_values(session, curve, keys)

        first_t, last_t = min(keys), max(keys)
        total_time = last_t - first_t
        if total_time == 0:
            continue

        first_v = original_data.get(first_t)
        last_v = original_data.get(last_t)
        if first_v is None or last_v is None:
            continue

        for t in keys:
            if t in original_data:
                t_pos = (t - first_t) / total_time
                if factor < 0.5:
                    f = 1 - (factor * 2)
                    e_pos = ease_in(t_pos, p=f * 3 + 1)
                else:
                    f = (factor - 0.5) * 2
                    e_pos = ease_out(t_pos, p=f * 3 + 1)

                target = utils.lerp(first_v, last_v, e_pos)
                orig_v = original_data[t]
                new_v = utils.lerp(orig_v, target, f)
                _apply_value(session, curve, t, new_v)


def apply_scale(session, curves=None, factor=1.0):
    """Scales keyframe values relative to their average."""
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        selected_vals = {t: original_data[t] for t in keys if t in original_data}
        if not selected_vals:
            continue
        avg = sum(selected_vals.values()) / len(selected_vals)

        for t in keys:
            if t in original_data:
                init = original_data[t]
                new_v = avg + (init - avg) * factor
                _apply_value(session, curve, t, new_v)


def apply_scale_from_pivot(session, curves=None, pivot_getter=None, factor=1.0):
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue
        original_data = _cached_curve_values(session, curve, keys)
        selected = {t: original_data[t] for t in keys if t in original_data}
        if not selected:
            continue
        pivot = pivot_getter(curve, keys, selected)
        if pivot is None:
            continue
        for t, value in selected.items():
            _apply_value(session, curve, t, pivot + (value - pivot) * factor)


# ---------------------------------------------------------------------------------------------------------------------
#                                                  Composite Operations                                               #
# ---------------------------------------------------------------------------------------------------------------------


def apply_pull_push(session, curves=None, amount=0.0):
    """Pulls keys toward the interpolated neighbor line or pushes them away."""
    factor = 1.0 + amount
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)

        for t in keys:
            if t in original_data:
                orig_v = original_data[t]
                p_time, p_val, n_time, n_val = _neighbor_values(curve, t, target_times_set, all_keys, original_data)

                if p_time is None or n_time is None or p_time == n_time:
                    pivot = p_val if p_val is not None else (n_val if n_val is not None else orig_v)
                else:
                    lerp_t = (t - p_time) / (n_time - p_time)
                    pivot = p_val + lerp_t * (n_val - p_val)

                new_v = pivot + (orig_v - pivot) * factor
                _apply_value(session, curve, t, new_v)


def _implicit_connect_block(direction, current_time, all_keys):
    left_keys = [time for time in all_keys if time < current_time]
    right_keys = [time for time in all_keys if time > current_time]

    if direction < 0:
        if not left_keys:
            return [], None
        # The target is left of the current key, so shift the current key and
        # the entire opposite (right) side by one uniform offset.
        return [time for time in all_keys if time >= current_time], left_keys[-1]

    if not right_keys:
        return [], None
    # The target is right of the current key, so shift the current key and the
    # entire opposite (left) side by one uniform offset.
    return [time for time in all_keys if time <= current_time], right_keys[0]


def apply_connect_neighbors(session, curves, amount):
    """Shift the affected block vertically so its edge connects to a neighbor."""
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    direction = -1 if amount < 0 else 1
    factor = min(1.0, max(0.0, abs(amount)))
    current_time = float(cmds.currentTime(query=True))
    has_selected_range = bool(session.targets.has_graph_keys or session.targets.time_range)
    affected_tint_times = []

    for curve in resolved_curves:
        resolved_keys = sorted(float(t) for t in (target_times_per_curve.get(curve, []) or []))
        if not resolved_keys:
            continue

        original_data = _cached_curve_values(session, curve, resolved_keys)
        _cached_value_at_time(session, curve, current_time)
        all_keys = sorted(original_data.keys())

        if has_selected_range:
            keys = resolved_keys
            target_times_set = set(keys)
            if direction < 0:
                anchor_time = min(keys)
                neighbor_time, _right_time = utils.get_block_neighbors(anchor_time, target_times_set, all_keys)
            else:
                anchor_time = max(keys)
                _left_time, neighbor_time = utils.get_block_neighbors(anchor_time, target_times_set, all_keys)
        else:
            keys, neighbor_time = _implicit_connect_block(direction, current_time, all_keys)
            anchor_time = current_time

        for time in keys:
            _cached_value_at_time(session, curve, time)

        if neighbor_time is None or neighbor_time == anchor_time:
            continue

        anchor_value = _cached_value_at_time(session, curve, anchor_time)
        neighbor_value = _cached_value_at_time(session, curve, neighbor_time)
        if anchor_value is None or neighbor_value is None:
            continue

        affected_tint_times.extend(keys)
        offset = (neighbor_value - anchor_value) * factor
        for time in keys:
            value = _cached_value_at_time(session, curve, time)
            if value is None:
                continue
            _apply_value(session, curve, time, value + offset)

    if affected_tint_times:
        session.show_tint((min(affected_tint_times), max(affected_tint_times)))


def apply_gap_stitcher(session, curves, amount):
    """Close a boundary gap and feather its offset across the selected block."""
    resolved_curves, target_times_per_curve = utils.resolve_curve_targets_for_session(session)
    direction = -1 if amount < 0.0 else 1
    blend = min(1.0, max(0.0, abs(float(amount))))
    affected_times = []
    for curve in resolved_curves:
        keys = sorted(float(time) for time in (target_times_per_curve.get(curve, []) or []))
        if not keys:
            continue
        original_data = _cached_curve_values(session, curve, keys)
        all_keys = sorted(original_data)
        selected_set = set(keys)
        anchor = keys[0] if direction < 0 else keys[-1]
        previous_time, next_time = utils.get_block_neighbors(anchor, selected_set, all_keys)
        neighbor = previous_time if direction < 0 else next_time
        if neighbor is None or neighbor == anchor:
            continue
        anchor_value = _cached_value_at_time(session, curve, anchor)
        neighbor_value = _cached_value_at_time(session, curve, neighbor)
        if anchor_value is None or neighbor_value is None:
            continue
        full_offset = neighbor_value - anchor_value
        count = len(keys)
        for index, time in enumerate(keys):
            value = _cached_value_at_time(session, curve, time)
            if value is None:
                continue
            if count == 1:
                feather = 1.0
            elif direction < 0:
                feather = 1.0 - (index / float(count - 1))
            else:
                feather = index / float(count - 1)
            _apply_value(session, curve, time, value + full_offset * feather * blend)
            affected_times.append(time)
    if affected_times:
        session.show_tint((min(affected_times), max(affected_times)))


def apply_simplify(session, curves, amount):
    """Progressively remove keys and refit each surviving cubic span."""
    resolved_curves, affected_map = utils.resolve_curve_targets_for_session(session)
    amount = min(1.0, max(0.0, float(amount)))
    for curve in resolved_curves:
        keys = sorted(set(float(time) for time in affected_map.get(curve, [])))
        if len(keys) <= 2:
            continue

        priority_cache_key = (curve, "simplify_detail_priority", tuple(keys))
        priority_data = session.cache.auxiliary.get(priority_cache_key)
        if priority_data is None:
            priority_data = curveFitting.detail_priority_with_scores(curve, keys)
            session.cache.auxiliary[priority_cache_key] = priority_data
        priority, detail_scores = priority_data

        removable = len(keys) - 2
        steady_count = sum(1 for frame in priority if detail_scores.get(frame, 0.0) <= 0.01)
        if steady_count:
            steady_phase_end = 0.35
            if amount <= steady_phase_end:
                remove_count = int(round(steady_count * amount / steady_phase_end))
            else:
                detail_progress = (amount - steady_phase_end) / (1.0 - steady_phase_end)
                remove_count = steady_count + int(round((removable - steady_count) * detail_progress))
        else:
            remove_count = int(round(removable * amount))
        keep_count = max(2, len(keys) - min(removable, remove_count))
        if keep_count == len(keys):
            continue

        kept_set = {keys[0], keys[-1]}
        kept_set.update(priority[: max(0, keep_count - 2)])
        kept = sorted(kept_set)
        removed = [time for time in keys if time not in kept_set]
        shape = curveFitting.capture([curve], kept)
        if session.preview and session.anim_change is not None:
            curve_fn = omutils.anim_curve_fn(curve)
            # Remove backwards so API key indices remain stable.
            for time in reversed(removed):
                omutils.remove_anim_curve_key(curve_fn, time, change=session.anim_change)
            curveFitting.apply(
                shape,
                set_values=False,
                change=session.anim_change,
                preserve_tangent_types=True,
            )
        else:
            for time in removed:
                cmds.cutKey(curve, time=(time, time), clear=True)
            curveFitting.apply(shape, set_values=False, preserve_tangent_types=True)

    if session.targets.time_range:
        session.show_tint(session.targets.time_range)


def apply_bake(session, curves, amount):
    """Progressively insert uniform, shape-preserving keys up to every frame."""
    resolved_curves, affected_map = utils.resolve_curve_targets_for_session(session)
    amount = min(1.0, max(0.0, float(amount)))
    if amount <= 0.0:
        return
    for curve in resolved_curves:
        keys = sorted(set(float(time) for time in affected_map.get(curve, [])))
        if len(keys) < 2:
            continue
        existing = set(cmds.keyframe(curve, query=True, time=(keys[0], keys[-1]), timeChange=True) or [])
        full_frame_targets = curveFitting.sample_times(keys[0], keys[-1], 1)
        missing = [frame for frame in full_frame_targets if frame not in existing]
        add_count = min(len(missing), int(round(len(missing) * amount)))
        if add_count <= 0:
            continue
        if add_count == len(missing):
            targets = missing
        elif add_count == 1:
            targets = [missing[len(missing) // 2]]
        else:
            target_indices = {
                int(round(index * (len(missing) - 1) / float(add_count - 1)))
                for index in range(add_count)
            }
            targets = [frame for index, frame in enumerate(missing) if index in target_indices]
        if session.preview and session.anim_change is not None:
            curve_fn = omutils.anim_curve_fn(curve)
            for frame in targets:
                omutils.add_anim_curve_key(curve_fn, frame, change=session.anim_change)
        else:
            for frame in targets:
                cmds.setKeyframe(curve, time=(frame,), insert=True)

    if session.targets.time_range:
        session.show_tint(session.targets.time_range)


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Pivot Scale Operations                                              #
# ---------------------------------------------------------------------------------------------------------------------


def apply_scale_default(session, curves, factor):
    apply_scale_from_pivot(session, curves, lambda curve, keys, selected: _curve_default_value(curve), factor)


def apply_scale_frame(session, curves, factor):
    left_frame = getattr(session, "left_target_frame", None)
    right_frame = getattr(session, "right_target_frame", None)
    current_time = cmds.currentTime(query=True)
    target_time = right_frame if factor >= 1.0 else left_frame
    if target_time is None:
        target_time = left_frame if left_frame is not None else right_frame
    if target_time is None:
        target_time = current_time
    session.show_target_tint((target_time, target_time))

    def _pivot(curve, keys, selected):
        try:
            return float(cmds.keyframe(curve, query=True, eval=True, time=(target_time,))[0])
        except Exception:
            return None

    apply_scale_from_pivot(session, curves, _pivot, factor)


def apply_scale_neighbor_left(session, curves, factor):
    _, target_times_per_curve = utils.resolve_curve_targets_for_session(session)

    def _pivot(curve, keys, selected):
        original_data = session.cache.original_keyframes.get(curve, {})
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)
        first_key = min(selected)
        p_time, p_val, _n_time, _n_val = _neighbor_values(curve, first_key, target_times_set, all_keys, original_data)
        return p_val if p_time is not None else None

    apply_scale_from_pivot(session, curves, _pivot, factor)


def apply_scale_neighbor_right(session, curves, factor):
    _, target_times_per_curve = utils.resolve_curve_targets_for_session(session)

    def _pivot(curve, keys, selected):
        original_data = session.cache.original_keyframes.get(curve, {})
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)
        last_key = max(selected)
        _p_time, _p_val, n_time, n_val = _neighbor_values(curve, last_key, target_times_set, all_keys, original_data)
        return n_val if n_time is not None else None

    apply_scale_from_pivot(session, curves, _pivot, factor)

"""
TheKeyMachine - Time Operations

Slider modes that modify keyframe timing (offsetting and staggering).
"""

import maya.cmds as cmds
from TheKeyMachine.core import curveFitting
from TheKeyMachine.sliders import mode_values, utils


def _curve_owner(curve):
    try:
        plugs = cmds.listConnections(
            "{}.output".format(curve), source=False, destination=True, plugs=True
        ) or []
    except Exception:
        plugs = []
    if not plugs:
        return curve
    return plugs[0].split(".", 1)[0]


def apply_time_offset(session, curves=None, amount=0.0):
    """Shift animation shape in time while preserving every destination key time."""
    resolved_curves, affected_map = utils.resolve_curve_targets_for_session(session)
    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue
        source_times = [float(destination_time) - float(amount) for destination_time in keys]
        source_shape = curveFitting.capture([curve], source_times).get(curve, {})
        for destination_time, source_time in zip(keys, source_times):
            # Positive drag moves the visible shape later, so each fixed key
            # samples an earlier point from the untouched source curve.
            source_sample = source_shape.get(float(source_time), {})
            source_value = source_sample.get("value")
            if source_value is None:
                continue
            mode_values.apply_curve_value(
                session, curve, destination_time, source_value,
                create=False, allow_cmds_fallback=True,
            )
            if session.preview or len(keys) < 2:
                continue
            # Preserve automatic tangent types. Only already-manual sides are
            # rotated to the fitted shifted shape, matching bake keep-shape.
            try:
                key_range = (destination_time, destination_time)
                in_type = (
                    cmds.keyTangent(curve, query=True, time=key_range, inTangentType=True) or [None]
                )[0]
                out_type = (
                    cmds.keyTangent(curve, query=True, time=key_range, outTangentType=True) or [None]
                )[0]
                angle_kwargs = {"absolute": True}
                if in_type == "fixed" and source_sample.get("in_angle") is not None:
                    angle_kwargs["inAngle"] = source_sample["in_angle"]
                if out_type == "fixed" and source_sample.get("out_angle") is not None:
                    angle_kwargs["outAngle"] = source_sample["out_angle"]
                if len(angle_kwargs) > 1:
                    cmds.keyTangent(curve, edit=True, time=key_range, **angle_kwargs)
            except Exception:
                pass


def apply_time_stagger(session, curves=None, amount=0.0):
    """Stagger whole-object key timing while keeping each object's channels together."""
    resolved_curves, affected_map = utils.resolve_curve_targets_for_session(session)
    if not resolved_curves:
        return
        
    owner_order = []
    for curve in resolved_curves:
        owner = _curve_owner(curve)
        if owner not in owner_order:
            owner_order.append(owner)
    owner_offsets = {owner: index * amount for index, owner in enumerate(owner_order)}

    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue
            
        if (curve, "times") not in session.cache.auxiliary:
            session.cache.auxiliary[(curve, "times")] = list(keys)
        orig_times = session.cache.auxiliary[(curve, "times")]
        stagger_offset = owner_offsets[_curve_owner(curve)]
        
        indexed_keys = list(enumerate(keys))
        indexed_keys.sort(key=lambda item: item[1], reverse=stagger_offset > 0.0)
        updated = {}
        for j, t in indexed_keys:
            orig_t = orig_times[j]
            new_t = orig_t + stagger_offset
            cmds.keyframe(curve, edit=True, time=(t, t), timeChange=new_t)
            updated[j] = new_t
        for j, new_t in updated.items():
            keys[j] = new_t

from TheKeyMachine.data import colors as toolColors
from TheKeyMachine.sliders import utils


CURVE_OPERATIONS = {
    "connect_neighbors": (apply_connect_neighbors, "percent"),
    "ease_in_out": (apply_ease, "ease"),
    "gap_stitcher": (apply_gap_stitcher, "percent"),
    "noise_wave": ((apply_noise, apply_wave), "signed_percent"),
    "pull_push": (apply_pull_push, "percent"),
    "simplify_bake": ((apply_simplify, apply_bake), "signed_percent"),
    "smooth_rough": ((apply_smooth, apply_rough), "signed_percent"),
    "scale_average": (apply_scale, "scale"),
    "scale_default": (apply_scale_default, "scale"),
    "scale_frame": (apply_scale_frame, "scale"),
    "scale_neighbor_left": (apply_scale_neighbor_left, "scale"),
    "scale_neighbor_right": (apply_scale_neighbor_right, "scale"),
}
TIME_OPERATIONS = {
    "time_offsetter": apply_time_offset,
    "time_offsetter_stagger": apply_time_stagger,
}


def _find_mode(mode_key):
    from TheKeyMachine.tools.slider_blend import MODES
    return next((mode for mode in MODES if hasattr(mode, "key") and mode.key == mode_key), None)


def create_session(mode_key):
    mode = _find_mode(mode_key)
    if mode is None:
        raise ValueError("Unknown Blend slider mode: {}".format(mode_key))
    return utils.SliderSession(
        mode_key, title=mode.label,
        description=mode.description,
        tooltip=mode.tooltip,
        tint_color=toolColors.TOOLBAR_GREEN,
    )


def _curve_value(operation, value):
    function, value_type = operation
    if value_type == "signed_percent":
        negative, positive = function
        return (negative if value < 0 else positive), abs(value) / 100.0
    if value_type == "ease":
        return function, (value + 100) / 200.0
    if value_type == "scale":
        return function, 1.0 + value / 100.0
    return function, value / 100.0


def execute(mode, value, session=None):
    mode_data = _find_mode(mode)
    if mode_data is None:
        raise ValueError("Unknown Blend slider mode: {}".format(mode))
    standalone = session is None
    session = session or create_session(mode)
    if session.mode != mode:
        session.switch_mode(mode, title=mode_data.label, description=mode_data.description, tooltip=mode_data.tooltip)
    try:
        if session.preview and mode in ("simplify_bake", "time_offsetter"):
            session.undo_preview_changes()
        if session.preview and mode == "time_offsetter_stagger":
            session.ensure_undo_open()
            session.command_preview = True
        if not session.preview:
            session.ensure_undo_open()
        if mode in CURVE_OPERATIONS:
            function, amount = _curve_value(CURVE_OPERATIONS[mode], value)
            function(session, None, amount)
        elif mode in TIME_OPERATIONS:
            TIME_OPERATIONS[mode](session, None, value / 10.0)
        return session
    finally:
        if standalone:
            session.finish()

