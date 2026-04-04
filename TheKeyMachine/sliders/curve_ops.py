"""
TheKeyMachine - Slider Functions

Core curve manipulation and tweening functions called by sliders.
"""

import maya.cmds as cmds
import random
from . import utils


def _lerp(a, b, t):
    return a + (b - a) * t


def _get_target_keys(curve):
    """Unified key resolver for both selected keys and timeline ranges."""
    _, _, time_range, has_graph_keys = utils.resolve_target_attribute_plugs()
    
    if has_graph_keys:
        return cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
    if time_range:
        return cmds.keyframe(curve, query=True, time=(time_range[0], time_range[1]), timeChange=True) or []
    
    return [cmds.currentTime(query=True)]


def _ensure_curve_cache(curve, keys):
    """Caches original values for ALL keyframes on a curve for stable dragging."""
    if curve not in utils.original_keyframes:
        # Cache every keyframe on the curve to provide stable neighbor lookups
        data = cmds.keyframe(curve, query=True, timeChange=True, valueChange=True) or []
        utils.original_keyframes[curve] = {data[i]: data[i+1] for i in range(0, len(data), 2)}


def _selected_values(curve, keys):
    _ensure_curve_cache(curve, keys)
    original_data = utils.original_keyframes[curve]
    return {t: original_data[t] for t in keys if t in original_data}


def _neighbor_values(curve, time, original_data):
    p_time = cmds.findKeyframe(curve, time=(time,), which="previous")
    n_time = cmds.findKeyframe(curve, time=(time,), which="next")
    orig_val = original_data.get(time)
    p_val = original_data.get(p_time, orig_val) if p_time is not None and p_time != time else orig_val
    n_val = original_data.get(n_time, orig_val) if n_time is not None and n_time != time else orig_val
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


def apply_smooth(curves, factor):
    """Smooths the curve values toward the average of their original neighbors."""
    for curve in curves:
        keys = _get_target_keys(curve)
        if not keys:
            continue
            
        _ensure_curve_cache(curve, keys)
        original_data = utils.original_keyframes[curve]
        
        for time in keys:
            if time not in original_data:
                continue
            
            orig_val = original_data[time]
            
            p_time = cmds.findKeyframe(curve, time=(time,), which="previous")
            n_time = cmds.findKeyframe(curve, time=(time,), which="next")
            
            # Use cached original values for neighbors to ensure stability during dragging
            p_val = original_data.get(p_time, orig_val) if p_time is not None and p_time != time else orig_val
            n_val = original_data.get(n_time, orig_val) if n_time is not None and n_time != time else orig_val
            
            w_p = 1.0 / abs(time - p_time) if p_time is not None and p_time != time else 0
            w_n = 1.0 / abs(n_time - time) if n_time is not None and n_time != time else 0
            
            if w_p + w_n > 0:
                avg = (p_val * w_p + n_val * w_n) / (w_p + w_n)
                res = orig_val + (avg - orig_val) * factor
                _apply_value(curve, time, res)


def apply_noise(curves, factor):
    """Adds random noise to the keys."""
    for curve in curves:
        keys = _get_target_keys(curve)
        if not keys:
            continue
            
        _ensure_curve_cache(curve, keys)
        if curve not in utils.initial_noise_values:
            utils.initial_noise_values[curve] = [random.uniform(-1, 1) for _ in keys]
        
        original_data = utils.original_keyframes[curve]
        noise_seeds = utils.initial_noise_values[curve]
        
        for i, time in enumerate(keys):
            if time in original_data:
                init_val = original_data[time]
                noise = noise_seeds[i] * factor
                _apply_value(curve, time, init_val + noise)


def apply_wave(curves, factor):
    """Applies a wave pattern to the keys."""
    for curve in curves:
        keys = _get_target_keys(curve)
        if not keys:
            continue
            
        _ensure_curve_cache(curve, keys)
        original_data = utils.original_keyframes[curve]
        
        for i, time in enumerate(keys):
            if time in original_data:
                init_val = original_data[time]
                direction = 1 if i % 2 == 0 else -1
                _apply_value(curve, time, init_val + direction * factor)


def apply_linear(curve_list, blend_factor):
    """Blends keys toward a linear interpolation between the selection boundaries."""
    for curve in curve_list:
        keys = _get_target_keys(curve)
        if not keys or len(keys) < 2:
            continue
            
        _ensure_curve_cache(curve, keys)
        original_data = utils.original_keyframes[curve]
        
        min_t, max_t = min(keys), max(keys)
        if min_t == max_t:
            continue
            
        min_v = cmds.keyframe(curve, query=True, time=(min_t,), valueChange=True)[0]
        max_v = cmds.keyframe(curve, query=True, time=(max_t,), valueChange=True)[0]
        
        for t in keys:
            if t in original_data:
                orig_v = original_data[t]
                lerp_t = (t - min_t) / (max_t - min_t)
                linear_v = min_v + lerp_t * (max_v - min_v)
                new_v = orig_v + blend_factor * (linear_v - orig_v)
                _apply_value(curve, t, new_v)


def apply_flat(curve_list, blend_factor):
    """Flattens keys toward their average original value."""
    for curve in curve_list:
        keys = _get_target_keys(curve)
        if not keys:
            continue
            
        _ensure_curve_cache(curve, keys)
        original_data = utils.original_keyframes[curve]
        
        avg = sum(original_data.values()) / len(original_data)
        
        for t in keys:
            if t in original_data:
                orig = original_data[t]
                new_v = orig + blend_factor * (avg - orig)
                _apply_value(curve, t, new_v)


def apply_ease(curve_list, factor):
    """Applies easing (in/out) to the curve values."""
    def ease_in(t, p=3): return pow(t, p)
    def ease_out(t, p=3): return 1 - pow(1 - t, p)

    for curve in curve_list:
        keys = _get_target_keys(curve)
        if not keys or len(keys) < 2:
            continue
            
        _ensure_curve_cache(curve, keys)
        original_data = utils.original_keyframes[curve]
        
        first_t, last_t = min(keys), max(keys)
        total_time = last_t - first_t
        if total_time == 0:
            continue

        first_v = original_data[first_t]
        last_v = original_data[last_t]

        for t in keys:
            if t in original_data:
                t_pos = (t - first_t) / total_time
                if factor < 0.5:
                    f = 1 - (factor * 2)
                    e_pos = ease_in(t_pos, p=f * 3 + 1)
                else:
                    f = (factor - 0.5) * 2
                    e_pos = ease_out(t_pos, p=f * 3 + 1)
                
                target = _lerp(first_v, last_v, e_pos)
                orig_v = original_data[t]
                new_v = _lerp(orig_v, target, f)
                _apply_value(curve, t, new_v)


def apply_scale(curves, factor):
    """Scales keyframe values relative to their average."""
    for curve in curves:
        keys = _get_target_keys(curve)
        if not keys:
            continue
            
        _ensure_curve_cache(curve, keys)
        original_data = utils.original_keyframes[curve]
        
        avg = sum(original_data.values()) / len(original_data)
        
        for t in keys:
            if t in original_data:
                init = original_data[t]
                new_v = avg + (init - avg) * factor
                _apply_value(curve, t, new_v)


def apply_scale_selection(curves, factor):
    """Scales keyframe values relative to their average."""
    apply_scale(curves, factor)


def apply_scale_from_pivot(curves, pivot_getter, factor):
    for curve in curves:
        keys = _get_target_keys(curve)
        if not keys:
            continue
        selected = _selected_values(curve, keys)
        if not selected:
            continue
        pivot = pivot_getter(curve, keys, selected)
        if pivot is None:
            continue
        for t, value in selected.items():
            _apply_value(curve, t, pivot + (value - pivot) * factor)


def apply_pull_push(curves, amount):
    apply_scale(curves, 1.0 + amount)


def apply_connect_neighbors(curves, amount):
    apply_linear(curves, max(0.0, amount))


def apply_gap_stitcher(curves, amount):
    apply_linear(curves, min(1.0, max(0.0, amount) * 1.35))


def apply_simplify(curves, amount):
    apply_smooth(curves, min(1.0, max(0.0, amount)))


def apply_bake(curves, amount):
    count = max(1, int(round(abs(amount) * 4.0)))
    for _ in range(count):
        add_random_keys(curves, amount)


def apply_scale_default(curves, factor):
    apply_scale_from_pivot(curves, lambda curve, keys, selected: _curve_default_value(curve), factor)


def apply_scale_frame(curves, factor):
    current_time = cmds.currentTime(query=True)

    def _pivot(curve, keys, selected):
        try:
            return float(cmds.keyframe(curve, query=True, eval=True, time=(current_time,))[0])
        except Exception:
            return None

    apply_scale_from_pivot(curves, _pivot, factor)


def apply_scale_neighbor_left(curves, factor):
    def _pivot(curve, keys, selected):
        original_data = utils.original_keyframes[curve]
        first_key = min(selected)
        p_time, p_val, _n_time, _n_val = _neighbor_values(curve, first_key, original_data)
        return p_val if p_time is not None else None

    apply_scale_from_pivot(curves, _pivot, factor)


def apply_scale_neighbor_right(curves, factor):
    def _pivot(curve, keys, selected):
        original_data = utils.original_keyframes[curve]
        last_key = max(selected)
        _p_time, _p_val, n_time, n_val = _neighbor_values(curve, last_key, original_data)
        return n_val if n_time is not None else None

    apply_scale_from_pivot(curves, _pivot, factor)


def add_random_keys(curves, value):
    """Adds new keys at random sub-frame intervals within selection."""
    for curve in curves:
        keys = _get_target_keys(curve)
        if len(keys) < 2:
            continue
            
        if curve not in utils.generated_keyframe_positions:
            min_k, max_k = int(min(keys)), int(max(keys))
            positions = list(range(min_k + 1, max_k))
            random.shuffle(positions)
            utils.generated_keyframe_positions[curve] = positions
        
        if utils.generated_keyframe_positions[curve]:
            next_p = utils.generated_keyframe_positions[curve].pop(0)
            curr_v = cmds.keyframe(curve, query=True, eval=True, time=(next_p,))[0]
            cmds.setKeyframe(curve, time=next_p, value=curr_v)
