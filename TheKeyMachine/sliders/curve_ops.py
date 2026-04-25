"""
TheKeyMachine - Curve-level Slider Operations

Operations that work directly on animation curves and their keys.
"""

import maya.cmds as cmds
import random

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


def _apply_value(curve, time, value):
    cmds.keyframe(curve, edit=True, time=(time, time), valueChange=value)


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
                _apply_value(curve, time, res)


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
                _apply_value(curve, time, init_val + noise)


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
                _apply_value(curve, time, init_val + direction * factor)


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
                _apply_value(curve, t, new_v)


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
                _apply_value(curve, t, new_v)


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
                _apply_value(curve, t, new_v)


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
                _apply_value(curve, t, new_v)


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
            _apply_value(curve, t, pivot + (value - pivot) * factor)


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
                _apply_value(curve, t, new_v)


def apply_connect_neighbors(session, curves, amount):
    apply_linear(session, curves, max(0.0, amount))


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
