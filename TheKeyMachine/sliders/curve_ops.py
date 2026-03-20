"""
TheKeyMachine - Slider Functions

Core curve manipulation and tweening functions called by sliders.
"""

import maya.cmds as cmds
import random
from . import utils

def apply_smooth(curves, factor):
    """Smooths the selected curves' keyframes."""
    for curve in curves:
        keyframes = cmds.keyframe(curve, query=True, selected=True, valueChange=True)
        if not keyframes:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
        
        keys = cmds.keyframe(curve, query=True, selected=True)
        for key in keys:
            time = cmds.keyframe(curve, query=True, time=(key, key))[0]
            val = cmds.keyframe(curve, query=True, time=(key, key), valueChange=True)[0]
            
            p_time = cmds.findKeyframe(curve, time=(time,), which="previous")
            p_val = cmds.keyframe(curve, query=True, time=(p_time, p_time), valueChange=True)[0] if p_time is not None else val
            
            n_time = cmds.findKeyframe(curve, time=(time,), which="next")
            n_val = cmds.keyframe(curve, query=True, time=(n_time, n_time), valueChange=True)[0] if n_time is not None else val
            
            w_p = 1.0 / abs(time - p_time) if p_time is not None and p_time != time else 0
            w_n = 1.0 / abs(n_time - time) if n_time is not None and n_time != time else 0
            
            if w_p + w_n > 0:
                avg = (p_val * w_p + n_val * w_n) / (w_p + w_n)
                res = val + (avg - val) * factor
                cmds.keyframe(curve, edit=True, time=(time, time), valueChange=res)

def apply_noise(curves, factor):
    """Adds random noise to the selected curves."""
    for curve in curves:
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
        if not keyframes or len(keyframes) % 2 != 0:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
            utils.initial_noise_values[curve] = [random.uniform(-1, 1) for _ in range(len(keyframes) // 2)]
        
        for i in range(0, len(keyframes), 2):
            time = keyframes[i]
            init_val = utils.original_keyframes[curve][i + 1]
            noise = utils.initial_noise_values[curve][i // 2] * factor
            cmds.keyframe(curve, edit=True, time=(time, time), valueChange=init_val + noise)

def apply_wave(curves, factor):
    """Applies a wave pattern to the curves."""
    for curve in curves:
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
        if not keyframes or len(keyframes) % 2 != 0:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
        
        for i in range(0, len(keyframes), 2):
            time = keyframes[i]
            init_val = utils.original_keyframes[curve][i + 1]
            direction = 1 if (i // 2) % 2 == 0 else -1
            cmds.keyframe(curve, edit=True, time=(time, time), valueChange=init_val + direction * factor)

def apply_linear(curve_list, blend_factor):
    """Blends curves toward a linear interpolation."""
    for curve in curve_list:
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
        if not keyframes or len(keyframes) < 4:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
        
        min_t, min_v = keyframes[0], keyframes[1]
        max_t, max_v = keyframes[-2], keyframes[-1]
        
        for i in range(2, len(keyframes) - 2, 2):
            t_curr = keyframes[i]
            orig_v = utils.original_keyframes[curve][i + 1]
            t = (t_curr - min_t) / (max_t - min_t)
            new_v = min_v + t * (max_v - min_v)
            cmds.keyframe(curve, edit=True, time=(t_curr, t_curr), valueChange=orig_v + blend_factor * (new_v - orig_v))

def apply_flat(curve_list, blend_factor):
    """Flattens the curves toward their average values."""
    for curve in curve_list:
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
        if not keyframes:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
        
        values = [keyframes[i] for i in range(1, len(keyframes), 2)]
        avg = sum(values) / len(values)
        
        for i in range(0, len(keyframes), 2):
            t = keyframes[i]
            orig = utils.original_keyframes[curve][i + 1]
            cmds.keyframe(curve, edit=True, time=(t, t), valueChange=orig + blend_factor * (avg - orig))

def apply_ease(curve_list, factor):
    """Applies easing (in/out) to the curves."""
    def ease_in(t, p=3): return pow(t, p)
    def ease_out(t, p=3): return 1 - pow(1 - t, p)
    def lerp(a, b, t): return a + (b - a) * t

    for curve in curve_list:
        keyframes = cmds.keyframe(curve, query=True, selected=True, valueChange=True)
        if not keyframes:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
        
        keys = cmds.keyframe(curve, query=True, selected=True)
        first, last = keys[0], keys[-1]
        total = last - first
        if total == 0:
            continue

        for i, k in enumerate(keys):
            t_pos = (k - first) / total
            if factor < 0.5:
                f = 1 - (factor * 2)
                e_pos = ease_in(t_pos, p=f * 3 + 1)
            else:
                f = (factor - 0.5) * 2
                e_pos = ease_out(t_pos, p=f * 3 + 1)
            
            target = lerp(utils.original_keyframes[curve][0], utils.original_keyframes[curve][-1], e_pos)
            new_v = lerp(utils.original_keyframes[curve][i], target, f)
            cmds.keyframe(curve, edit=True, time=(k, k), valueChange=new_v)

def apply_scale(curves, factor):
    """Scales curves globally from their average."""
    for curve in curves:
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
        if not keyframes:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
            
        vals = [utils.original_keyframes[curve][i] for i in range(1, len(utils.original_keyframes[curve]), 2)]
        avg = sum(vals) / len(vals)
        for i in range(0, len(keyframes), 2):
            t = keyframes[i]
            init = utils.original_keyframes[curve][i+1]
            new_v = avg + (init - avg) * factor
            cmds.keyframe(curve, edit=True, time=(t, t), valueChange=new_v)

def apply_scale_selection(curves, factor):
    """Scales only the selected part of the curves."""
    for curve in curves:
        keyframes = cmds.keyframe(curve, query=True, timeChange=True, valueChange=True)
        selected_keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
        if not keyframes or len(keyframes) % 2 != 0:
            continue
        if curve not in utils.original_keyframes:
            utils.original_keyframes[curve] = keyframes.copy()
        
        ref = selected_keyframes if selected_keyframes and len(selected_keyframes) % 2 == 0 else utils.original_keyframes[curve]
        mean_v = sum(ref[i + 1] for i in range(0, len(ref), 2)) / (len(ref) / 2)
        
        for i in range(0, len(keyframes), 2):
            t = keyframes[i]
            init = utils.original_keyframes[curve][i + 1]
            new_v = mean_v + (init - mean_v) * factor
            cmds.keyframe(curve, edit=True, time=(t, t), valueChange=new_v)

def add_random_keys(curves, value):
    """Adds new keys at random sub-frame intervals within selection."""
    for curve in curves:
        if curve not in utils.generated_keyframe_positions:
            keys = cmds.keyframe(curve, query=True, selected=True, timeChange=True)
            if not keys:
                continue
            positions = []
            for i in range(1, len(keys)):
                positions.extend(range(int(keys[i-1]) + 1, int(keys[i])))
            random.shuffle(positions)
            utils.generated_keyframe_positions[curve] = positions
        
        if utils.generated_keyframe_positions[curve]:
            next_p = utils.generated_keyframe_positions[curve].pop(0)
            curr_v = cmds.keyframe(curve, query=True, eval=True, time=(next_p,))[0]
            cmds.setKeyframe(curve, time=next_p, value=curr_v)
