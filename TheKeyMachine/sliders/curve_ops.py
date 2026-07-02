"""
TheKeyMachine - Curve-level Slider Operations

Operations that work directly on animation curves and their keys.
"""

import maya.cmds as cmds
import random

import TheKeyMachine.core.openMayaUtils as omutils
from . import utils


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Curve Target Resolution                                             #
# ---------------------------------------------------------------------------------------------------------------------


def _resolve_targets_for_session(session):
    """Resolve and cache curve targets on the session for the lifetime of one drag."""
    if not session.targets.resolved:
        curves, times_map, time_range, has_graph_keys = utils.resolve_curve_targets()
        session.targets.curves = curves
        session.targets.affected_map = times_map
        session.targets.time_range = time_range
        session.targets.has_graph_keys = has_graph_keys
        session.targets.resolved = True
    return session.targets.curves, session.targets.affected_map


def _ensure_curve_value_cache(session, curve, keys):
    """Caches original values for ALL keyframes on a curve for stable dragging."""
    if curve not in session.cache.original_keyframes:
        data = cmds.keyframe(curve, query=True, timeChange=True, valueChange=True) or []
        session.cache.original_keyframes[curve] = {float(data[i]): data[i + 1] for i in range(0, len(data), 2)}


def _cached_curve_values(session, curve, keys):
    _ensure_curve_value_cache(session, curve, keys)
    return session.cache.original_keyframes[curve]


def _cached_value_at_time(session, curve, time):
    original_data = _cached_curve_values(session, curve, [time])
    if time in original_data:
        return original_data[time]
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


def _apply_value(session, curve, time, value):
    if getattr(session, "preview", False):
        omutils.set_anim_curve_key_value(curve, time, value)
        return
    cmds.keyframe(curve, edit=True, time=(time, time), valueChange=value)


def _set_connect_value(session, curve, time, value):
    if getattr(session, "preview", False):
        omutils.set_anim_curve_key_value(curve, time, value)
        return
    cmds.setKeyframe(curve, time=(time,), value=value)


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
                curr_v = cmds.keyframe(curve, query=True, eval=True, time=(next_p,))[0]
                cmds.setKeyframe(curve, time=next_p, value=curr_v)


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


def apply_noise(session, curves=None, factor=1.0):
    """Adds random noise to the keys."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)
        if curve not in session.cache.initial_noise:
            session.cache.initial_noise[curve] = [random.uniform(-1, 1) for _ in keys]

        noise_seeds = session.cache.initial_noise[curve]

        for i, time in enumerate(keys):
            if time in original_data:
                init_val = original_data[time]
                noise = noise_seeds[i] * factor
                _apply_value(session, curve, time, init_val + noise)


def apply_wave(session, curves=None, factor=1.0):
    """Applies a wave pattern to the keys."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
    for curve in resolved_curves:
        keys = target_times_per_curve.get(curve, [])
        if not keys:
            continue

        original_data = _cached_curve_values(session, curve, keys)

        for i, time in enumerate(keys):
            if time in original_data:
                init_val = original_data[time]
                direction = 1 if i % 2 == 0 else -1
                _apply_value(session, curve, time, init_val + direction * factor)


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


def _selected_tint_range(target_times_per_curve):
    frames = []
    for keys in (target_times_per_curve or {}).values():
        frames.extend(keys or [])
    if not frames:
        return None
    return min(frames), max(frames)


def _connect_neighbor_tint_range(direction, current_time, neighbor_times):
    candidates = [time for time in neighbor_times if time is not None]
    if not candidates:
        return None
    if direction < 0:
        neighbor = min(candidates)
    else:
        neighbor = max(candidates)
    return min(current_time, neighbor), max(current_time, neighbor)


def _implicit_connect_block(direction, current_time, all_keys):
    left_keys = [time for time in all_keys if time < current_time]
    right_keys = [time for time in all_keys if time > current_time]

    if direction < 0:
        if not left_keys:
            return [], None
        next_time = right_keys[0] if right_keys else current_time
        block = [current_time]
        block.extend(time for time in all_keys if current_time < time <= next_time)
        return sorted(set(block)), left_keys[-1]

    if not right_keys:
        return [], None
    previous_time = left_keys[-1] if left_keys else current_time
    block = [time for time in all_keys if previous_time <= time < current_time]
    block.append(current_time)
    return sorted(set(block)), right_keys[0]


def apply_connect_neighbors(session, curves, amount):
    """Shift the affected block vertically so its edge connects to a neighbor."""
    resolved_curves, target_times_per_curve = _resolve_targets_for_session(session)
    direction = -1 if amount < 0 else 1
    factor = min(1.0, max(0.0, abs(amount)))
    current_time = float(cmds.currentTime(query=True))
    has_selected_range = bool(session.targets.has_graph_keys or session.targets.time_range)
    neighbor_tint_times = []

    if has_selected_range:
        session.show_tint(session.targets.time_range or _selected_tint_range(target_times_per_curve))

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

        if not has_selected_range:
            neighbor_tint_times.append(neighbor_time)

        offset = (neighbor_value - anchor_value) * factor
        for time in keys:
            value = _cached_value_at_time(session, curve, time)
            if value is None:
                continue
            _set_connect_value(session, curve, time, value + offset)

    if not has_selected_range:
        session.show_tint(_connect_neighbor_tint_range(direction, current_time, neighbor_tint_times))


def apply_gap_stitcher(session, curves, amount):
    apply_linear(session, curves, min(1.0, max(0.0, amount) * 1.35))


def apply_simplify(session, curves, amount):
    apply_smooth(session, curves, min(1.0, max(0.0, amount)))


def apply_bake(session, curves, amount):
    count = max(1, int(round(abs(amount) * 4.0)))
    for _ in range(count):
        add_random_keys(session, curves, amount)


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Pivot Scale Operations                                              #
# ---------------------------------------------------------------------------------------------------------------------


def apply_scale_default(session, curves, factor):
    apply_scale_from_pivot(session, curves, lambda curve, keys, selected: _curve_default_value(curve), factor)


def apply_scale_frame(session, curves, factor):
    current_time = cmds.currentTime(query=True)

    def _pivot(curve, keys, selected):
        try:
            return float(cmds.keyframe(curve, query=True, eval=True, time=(current_time,))[0])
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
