"""Shared shape-preserving animation-curve resampling utilities."""

from __future__ import annotations

import math

from maya import cmds

from TheKeyMachine.core import openMayaUtils as omutils


def evaluate(curve, frame):
    values = cmds.keyframe(curve, query=True, eval=True, time=(frame, frame)) or []
    return float(values[0]) if values else None


def sample_times(start, end, interval):
    start = float(start)
    end = float(end)
    interval = float(interval)
    frames = []
    frame = start
    epsilon = max(1e-8, interval * 1e-8)
    while frame <= end + epsilon:
        frames.append(frame)
        frame += interval
    if not frames or abs(frames[-1] - end) > epsilon:
        frames.append(end)
    return sorted(set(int(value) if int(value) == value else value for value in frames))


def bouncy_tangent_angles(curve, time, angle_adjustment_factor=1.3):
    """Return contextual bounce angles in Maya's native tangent units.

    Maya tangent vectors use seconds for x and attribute-specific internal
    units for y. Asking Maya for the Linear target avoids incorrect frame/value
    slope conversions, then scaling tan(angle) amplifies the actual slope.
    """
    time_range = (float(time), float(time))
    in_types = cmds.keyTangent(curve, query=True, time=time_range, inTangentType=True) or []
    out_types = cmds.keyTangent(curve, query=True, time=time_range, outTangentType=True) or []
    locks = cmds.keyTangent(curve, query=True, time=time_range, lock=True) or []
    if not in_types or not out_types:
        return 0.0, 0.0
    was_locked = bool(locks[0]) if locks else False
    in_angles = cmds.keyTangent(curve, query=True, time=time_range, inAngle=True) or [0.0]
    out_angles = cmds.keyTangent(curve, query=True, time=time_range, outAngle=True) or [0.0]
    try:
        cmds.keyTangent(curve, edit=True, time=time_range, lock=False)
        cmds.keyTangent(curve, edit=True, time=time_range, inTangentType="linear", outTangentType="linear")
        in_angles = cmds.keyTangent(curve, query=True, time=time_range, inAngle=True) or [0.0]
        out_angles = cmds.keyTangent(curve, query=True, time=time_range, outAngle=True) or [0.0]
    except Exception:
        pass
    finally:
        cmds.keyTangent(
            curve, edit=True, time=time_range,
            inTangentType=in_types[0], outTangentType=out_types[0], lock=was_locked,
        )

    def _amplify(angle):
        slope = math.tan(math.radians(float(angle)))
        return math.degrees(math.atan(slope * float(angle_adjustment_factor)))

    return _amplify(in_angles[0]), _amplify(out_angles[0])


def fit_hermite_span(curve, start, end, start_value, end_value):
    """Fit endpoint slopes for a cubic Hermite span by constrained least squares."""
    duration = float(end) - float(start)
    if duration <= 0:
        return 0.0, 0.0

    original_keys = cmds.keyframe(curve, query=True, time=(start, end), timeChange=True) or []
    count = max(9, int(math.ceil(duration * 4.0)) + 1)
    times = {float(start) + duration * index / float(count - 1) for index in range(1, count - 1)}
    times.update(float(frame) for frame in original_keys if start < float(frame) < end)

    aa = ab = bb = ar = br = 0.0
    for frame in sorted(times):
        value = evaluate(curve, frame)
        if value is None:
            continue
        u = (frame - float(start)) / duration
        u2 = u * u
        u3 = u2 * u
        h00 = 2.0 * u3 - 3.0 * u2 + 1.0
        h01 = -2.0 * u3 + 3.0 * u2
        a = duration * (u3 - 2.0 * u2 + u)
        b = duration * (u3 - u2)
        residual = value - (h00 * start_value + h01 * end_value)
        aa += a * a
        ab += a * b
        bb += b * b
        ar += a * residual
        br += b * residual

    determinant = aa * bb - ab * ab
    if abs(determinant) <= 1e-12:
        secant = (end_value - start_value) / duration
        return secant, secant
    return (ar * bb - br * ab) / determinant, (br * aa - ar * ab) / determinant


def detail_priority_with_scores(curve, key_times):
    """Rank interior keys by their contribution to the sampled curve shape.

    This is a hierarchical Ramer-Douglas-Peucker-style ranking in graph space.
    Keys furthest from the constant-slope chord across their current span rank
    first. The chord may be flat, rising, or falling. Ties on steady runs
    prefer the midpoint, producing clean, even reductions.
    """
    frames = sorted(set(float(frame) for frame in key_times))
    if len(frames) <= 2:
        return [], {}
    values = {frame: evaluate(curve, frame) for frame in frames}

    def _span_candidate(first_index, last_index):
        if last_index - first_index <= 1:
            return None
        start = frames[first_index]
        end = frames[last_index]
        start_value = values.get(start)
        end_value = values.get(end)
        if start_value is None or end_value is None or end == start:
            return None

        midpoint = (start + end) * 0.5
        interior_indices = list(range(first_index + 1, last_index))
        if not interior_indices:
            return None

        sample_count = max(9, int(math.ceil((end - start) * 4.0)) + 1)
        probe_times = {
            start + (end - start) * index / float(sample_count - 1)
            for index in range(1, sample_count - 1)
        }
        probe_times.update(frames[index] for index in interior_indices)
        deviations = []
        sampled_values = []
        for frame in probe_times:
            value = values.get(frame) if frame in values else evaluate(curve, frame)
            if value is None:
                continue
            sampled_values.append(value)
            ratio = (frame - start) / (end - start)
            chord_value = start_value + (end_value - start_value) * ratio
            deviations.append((abs(value - chord_value), -abs(frame - midpoint), frame))
        if not deviations:
            return None

        deviation, center_bias, detail_time = max(deviations)
        value_scale = max(
            max(sampled_values + [start_value, end_value]) - min(sampled_values + [start_value, end_value]),
            abs(end_value - start_value),
            1e-6,
        )
        normalized_deviation = deviation / value_scale
        split_index = min(
            interior_indices,
            key=lambda index: (abs(frames[index] - detail_time), abs(frames[index] - midpoint)),
        )
        return normalized_deviation, end - start, center_bias, split_index, first_index, last_index

    ranked = []
    scores = {}
    pending = [_span_candidate(0, len(frames) - 1)]
    pending = [candidate for candidate in pending if candidate is not None]
    while pending:
        candidate = max(pending)
        pending.remove(candidate)
        deviation, _duration, _center_bias, split_index, first_index, last_index = candidate
        frame = frames[split_index]
        ranked.append(frame)
        scores[frame] = deviation
        for child in (
            _span_candidate(first_index, split_index),
            _span_candidate(split_index, last_index),
        ):
            if child is not None:
                pending.append(child)
    # Protect sudden slope/curvature changes globally. Python's stable sort
    # retains the even hierarchical ordering for equally steady spans.
    ranked.sort(key=lambda frame: scores.get(frame, 0.0), reverse=True)
    return ranked, scores


def detail_priority(curve, key_times):
    return detail_priority_with_scores(curve, key_times)[0]


def capture(curves, target_times):
    """Capture values and fitted broken tangent rotations at target times."""
    result = {}
    target_times = sorted(set(float(frame) for frame in target_times))
    for curve in dict.fromkeys(curves or []):
        samples = {}
        for frame in target_times:
            value = evaluate(curve, frame)
            if value is not None:
                in_types = cmds.keyTangent(curve, query=True, time=(frame, frame), inTangentType=True) or []
                out_types = cmds.keyTangent(curve, query=True, time=(frame, frame), outTangentType=True) or []
                in_angles = cmds.keyTangent(curve, query=True, time=(frame, frame), inAngle=True) or []
                out_angles = cmds.keyTangent(curve, query=True, time=(frame, frame), outAngle=True) or []
                tangent_locks = cmds.keyTangent(curve, query=True, time=(frame, frame), lock=True) or []
                samples[frame] = {
                    "value": value,
                    "in_angle": None,
                    "out_angle": None,
                    "in_type": in_types[0] if in_types else None,
                    "out_type": out_types[0] if out_types else None,
                    "original_in_angle": in_angles[0] if in_angles else None,
                    "original_out_angle": out_angles[0] if out_angles else None,
                    "tangents_locked": bool(tangent_locks[0]) if tangent_locks else False,
                }

        frames = sorted(samples)
        for start, end in zip(frames, frames[1:]):
            out_slope, in_slope = fit_hermite_span(
                curve, start, end, samples[start]["value"], samples[end]["value"]
            )
            samples[start]["out_angle"] = math.degrees(math.atan(out_slope))
            samples[end]["in_angle"] = math.degrees(math.atan(in_slope))

        if frames:
            first = samples[frames[0]]
            last = samples[frames[-1]]
            first["in_angle"] = first["out_angle"] if first["out_angle"] is not None else 0.0
            last["out_angle"] = last["in_angle"] if last["in_angle"] is not None else 0.0
            result[curve] = samples
    return result


def apply(shape_data, set_values=True, change=None, preserve_tangent_types=False):
    """Apply captured values and fitted tangent rotations to existing curves."""
    for curve, samples in (shape_data or {}).items():
        if not cmds.objExists(curve):
            continue
        curve_fn = omutils.anim_curve_fn(curve) if change is not None else None
        if curve_fn is not None:
            for frame, sample in samples.items():
                index = omutils.anim_curve_key_index(curve_fn, frame)
                if index is None:
                    index = omutils.add_anim_curve_key(curve_fn, frame, change=change)
                if set_values:
                    omutils.set_anim_curve_value_by_index(curve_fn, index, sample["value"], change=change)
                if not preserve_tangent_types:
                    omutils.set_anim_curve_tangents(
                        curve_fn,
                        frame,
                        sample["in_angle"],
                        sample["out_angle"],
                        change=change,
                    )
            continue
        if not preserve_tangent_types:
            try:
                cmds.keyTangent(curve, edit=True, weightedTangents=False)
            except (RuntimeError, ValueError, TypeError):
                pass
        for frame, sample in samples.items():
            try:
                if set_values:
                    cmds.setKeyframe(curve, time=(frame,), value=sample["value"])
                if preserve_tangent_types:
                    _apply_preserved_tangent_rotation(curve, frame, sample)
                    continue
                cmds.keyTangent(
                    curve,
                    edit=True,
                    time=(frame, frame),
                    lock=False,
                    inTangentType="fixed",
                    outTangentType="fixed",
                )
                cmds.keyTangent(
                    curve,
                    edit=True,
                    time=(frame, frame),
                    absolute=True,
                    inAngle=sample["in_angle"],
                    outAngle=sample["out_angle"],
                )
            except (RuntimeError, ValueError, TypeError):
                continue


def _angle_changed(original, fitted, tolerance=0.1):
    return original is not None and fitted is not None and abs(float(original) - float(fitted)) > tolerance


def _apply_preserved_tangent_rotation(curve, frame, sample):
    """Rotate existing fixed tangents without disturbing automatic tangent state."""
    rotate_in = sample.get("in_type") == "fixed" and _angle_changed(
        sample.get("original_in_angle"), sample.get("in_angle")
    )
    rotate_out = sample.get("out_type") == "fixed" and _angle_changed(
        sample.get("original_out_angle"), sample.get("out_angle")
    )
    if not rotate_in and not rotate_out:
        return

    was_locked = bool(sample.get("tangents_locked"))
    if was_locked:
        # A locked key can only remain locked when both sides are fixed and the
        # fitted curve asks for one common slope.
        common_rotation = rotate_in and rotate_out and abs(sample["in_angle"] - sample["out_angle"]) <= 0.1
        if not common_rotation:
            if not (rotate_in and rotate_out):
                return
            cmds.keyTangent(curve, edit=True, time=(frame, frame), lock=False)

    angle_kwargs = {"absolute": True}
    if rotate_in:
        angle_kwargs["inAngle"] = sample["in_angle"]
    if rotate_out:
        angle_kwargs["outAngle"] = sample["out_angle"]
    cmds.keyTangent(curve, edit=True, time=(frame, frame), **angle_kwargs)
