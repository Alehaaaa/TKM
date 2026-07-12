"""
TheKeyMachine - Curve-level Slider Operations

Operations that work directly on animation curves and their keys.
"""

import maya.cmds as cmds
import math
import random

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

import TheKeyMachine.core.openMayaUtils as omutils
from TheKeyMachine.core import curveFitting
from . import mode_values, utils


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Curve Target Resolution                                             #
# ---------------------------------------------------------------------------------------------------------------------


def _resolve_targets_for_session(session):
    """Resolve and cache curve targets on the session for the lifetime of one drag."""
    return utils.resolve_curve_targets_for_session(session)


def _ensure_curve_value_cache(session, curve, keys):
    """Caches original values for ALL keyframes on a curve for stable dragging."""
    if curve not in session.cache.original_keyframes:
        cached = None
        curve_fn = omutils._anim_curve_fn(curve)
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
    curve_fn = omutils._anim_curve_fn(curve)
    for time in keys or []:
        time = float(time)
        if time in original_data:
            continue
        value = None
        if curve_fn is not None and om is not None:
            try:
                value = curve_fn.evaluate(om.MTime(time, _time_unit()))
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
    curve_fn = omutils._anim_curve_fn(curve)
    if curve_fn is not None and om is not None:
        try:
            value = curve_fn.evaluate(om.MTime(float(time), _time_unit()))
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


def _selected_cached_values(session, curve, keys):
    original_data = _cached_curve_values(session, curve, keys)
    return {time: original_data[time] for time in keys if time in original_data}


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


def _time_unit():
    if om is None:
        return None
    try:
        return om.MTime.uiUnit()
    except Exception:
        return om.MTime.kFilm


def _apply_value(session, curve, time, value):
    if getattr(session, "preview", False):
        mode_values.apply_curve_value(session, curve, time, value, create=True, allow_cmds_fallback=False)
        return
    mode_values.apply_curve_value(session, curve, time, value, create=True, allow_cmds_fallback=True)


def _set_connect_value(session, curve, time, value):
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


def add_random_keys(session, curves=None, value=0):
    """Adds new keys at random sub-frame intervals within selection."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if len(keys) < 2:
            continue

        if curve not in session.cache.generated_positions:
            min_k, max_k = int(min(keys)), int(max(keys))
            positions = list(range(min_k + 1, max_k))
            random.seed(curve)  # Deterministic shuffle for this curve
            random.shuffle(positions)
            session.cache.generated_positions[curve] = positions

        # Use index-based access instead of pop to remain stable across drag updates
        idx = max(0, int(round(abs(value) * 4.0)))
        for i in range(idx):
            if i < len(session.cache.generated_positions[curve]):
                next_p = session.cache.generated_positions[curve][i]
                curr_v = _cached_value_at_time(session, curve, next_p)
                if curr_v is not None:
                    mode_values.apply_curve_value(session, curve, next_p, curr_v, create=True, allow_cmds_fallback=True)


# ---------------------------------------------------------------------------------------------------------------------
#                                               Direct Curve Operations                                               #
# ---------------------------------------------------------------------------------------------------------------------


def apply_smooth(session, curves=None, factor=1.0):
    """Smooths the curve values toward the average of their block-aware neighbors."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    """Add one smooth sine cycle across the selected key span."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        curve_values = list(original_data.values())
        value_range = (max(curve_values) - min(curve_values)) if curve_values else 0.0
        amplitude = max(value_range * 0.15, 0.001) * max(0.0, min(1.0, factor))
        first_time, last_time = min(keys), max(keys)
        duration = last_time - first_time

        for time in keys:
            if time in original_data:
                init_val = original_data[time]
                phase = ((time - first_time) / duration) * (math.pi * 2.0) if duration else (math.pi * 0.5)
                _apply_value(session, curve, time, init_val + math.sin(phase) * amplitude)


def apply_linear(session, curve_list=None, blend_factor=1.0):
    """Blends keys toward a linear interpolation between the block's contiguous neighbors."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
                    target_v = p_val if p_val is not None else (n_val if n_val is not None else orig_v)
                else:
                    lerp_t = (t - p_time) / (n_time - p_time)
                    target_v = p_val + lerp_t * (n_val - p_val)

                new_v = orig_v + blend_factor * (target_v - orig_v)
                _apply_value(session, curve, t, new_v)


def apply_flat(session, curve_list=None, blend_factor=1.0):
    """Flattens keys toward their average original value."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
                orig = original_data[t]
                new_v = orig + blend_factor * (avg - orig)
                _apply_value(session, curve, t, new_v)


def apply_ease(session, curve_list=None, factor=0.5):
    """Applies easing (in/out) to the curve values."""

    def ease_in(t, p=3):
        return pow(t, p)

    def ease_out(t, p=3):
        return 1 - pow(1 - t, p)

    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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


def apply_scale_selection(session, curves, factor):
    """Scales keyframe values relative to their average."""
    apply_scale(session, curves, factor)


def apply_scale_from_pivot(session, curves=None, pivot_getter=None, factor=1.0):
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
            _set_connect_value(session, curve, time, value + offset)

    if affected_tint_times:
        session.show_tint((min(affected_tint_times), max(affected_tint_times)))


def apply_gap_stitcher(session, curves, amount):
    """Close a boundary gap and feather its offset across the selected block."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
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
    resolved_curves, affected_map = _resolve_targets_for_session(session)
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
    resolved_curves, affected_map = _resolve_targets_for_session(session)
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
    session.show_tint((target_time, target_time), color=(245, 245, 245, 125), center_line=False)

    def _pivot(curve, keys, selected):
        try:
            return float(cmds.keyframe(curve, query=True, eval=True, time=(target_time,))[0])
        except Exception:
            return None

    apply_scale_from_pivot(session, curves, _pivot, factor)


def apply_scale_neighbor_left(session, curves, factor):
    _, target_times_per_curve = _resolve_targets_for_session(session)

    def _pivot(curve, keys, selected):
        original_data = session.cache.original_keyframes.get(curve, {})
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)
        first_key = min(selected)
        p_time, p_val, _n_time, _n_val = _neighbor_values(curve, first_key, target_times_set, all_keys, original_data)
        return p_val if p_time is not None else None

    apply_scale_from_pivot(session, curves, _pivot, factor)


def apply_scale_neighbor_right(session, curves, factor):
    _, target_times_per_curve = _resolve_targets_for_session(session)

    def _pivot(curve, keys, selected):
        original_data = session.cache.original_keyframes.get(curve, {})
        all_keys = sorted(original_data.keys())
        target_times_set = set(keys)
        last_key = max(selected)
        _p_time, _p_val, n_time, n_val = _neighbor_values(curve, last_key, target_times_set, all_keys, original_data)
        return n_val if n_time is not None else None

    apply_scale_from_pivot(session, curves, _pivot, factor)
