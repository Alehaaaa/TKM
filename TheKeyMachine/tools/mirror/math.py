"""Pure value and matrix math for the mirror tool and rig analysis."""


MATRIX_SIZE = 16


def normalize_angle_degrees(value):
    """Return an equivalent angle on Maya's compact -180..180 branch."""
    value = float(value)
    normalized = (value + 180.0) % 360.0 - 180.0
    # Keep positive half-turns positive and remove tiny modulo noise around 0.
    if abs(normalized + 180.0) <= 1e-10 and value > 0.0:
        return 180.0
    if abs(normalized) <= 1e-10:
        return 0.0
    return normalized


def normalize_euler_degrees(values):
    """Normalize an Euler channel triple without changing its orientation."""
    return tuple(normalize_angle_degrees(value) for value in values)


def opposite_name_candidates(name, patterns, aliases=()):
    """Return every ordered, de-duplicated opposite-name candidate."""
    namespace, separator, leaf = str(name).rpartition(":")
    candidates = []
    for pattern, opposite_pattern in patterns:
        if pattern not in leaf:
            continue
        candidate_leaf = leaf.replace(pattern, opposite_pattern, 1)
        candidate = f"{namespace}:{candidate_leaf}" if separator else candidate_leaf
        if candidate != name and candidate not in candidates:
            candidates.append(candidate)
        for alias, opposite_alias in aliases:
            if alias not in candidate_leaf:
                continue
            alias_leaf = candidate_leaf.replace(alias, opposite_alias, 1)
            alias_candidate = f"{namespace}:{alias_leaf}" if separator else alias_leaf
            if alias_candidate != name and alias_candidate not in candidates:
                candidates.append(alias_candidate)
    return candidates


def matrix_delta(first, second):
    """Return the component-wise response between two Maya matrices."""
    if len(first) != MATRIX_SIZE or len(second) != MATRIX_SIZE:
        raise ValueError("Mirror analysis requires two 4x4 matrices")
    return tuple(float(value) - float(base) for value, base in zip(first, second))


def reflect_matrix_delta(delta):
    """Reflect a row-vector Maya matrix response across the world YZ plane."""
    if len(delta) != MATRIX_SIZE:
        raise ValueError("Mirror analysis requires a 4x4 matrix response")
    signs = (-1.0, 1.0, 1.0, 1.0)
    return tuple(
        float(delta[row * 4 + column]) * signs[row] * signs[column]
        for row in range(4)
        for column in range(4)
    )


def response_direction(source_response, target_response, epsilon=1e-10):
    """Return the sign that best aligns target response to mirrored source response.

    Central probe responses can differ in magnitude because two rig controls may
    use different unit conversions.  The dot product determines orientation
    without requiring those magnitudes to be equal.
    """
    desired = reflect_matrix_delta(source_response)
    source_energy = sum(value * value for value in desired)
    target_energy = sum(value * value for value in target_response)
    if source_energy <= epsilon or target_energy <= epsilon:
        return None
    alignment = sum(a * b for a, b in zip(desired, target_response))
    if alignment * alignment <= epsilon * source_energy * target_energy:
        return None
    return 1 if alignment > 0.0 else -1


def transform_value(value, direction, source_default=0.0, target_default=0.0):
    """Map a scalar or nested sequence between two controls' default poses."""
    if isinstance(value, list):
        return [
            transform_value(item, direction, source_default, target_default)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            transform_value(item, direction, source_default, target_default)
            for item in value
        )
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    numeric_defaults = (
        isinstance(source_default, (int, float))
        and not isinstance(source_default, bool)
        and isinstance(target_default, (int, float))
        and not isinstance(target_default, bool)
    )
    if direction in (-1, 1) and numeric and numeric_defaults:
        return target_default + direction * (value - source_default)
    if direction == -1 and numeric:
        return -value
    return value
