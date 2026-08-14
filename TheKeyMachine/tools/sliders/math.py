"""Pure interpolation and key-neighbor calculations shared by slider tools."""


def block_neighbors(time, target_times, all_keys):
    """Return the bounding keys outside the selected continuous block."""
    current = float(time)
    if current in all_keys:
        index = all_keys.index(current)
        left = index
        while left > 0 and all_keys[left - 1] in target_times:
            left -= 1
        previous = all_keys[left - 1] if left > 0 else all_keys[left]

        right = index
        while right < len(all_keys) - 1 and all_keys[right + 1] in target_times:
            right += 1
        following = all_keys[right + 1] if right < len(all_keys) - 1 else all_keys[right]
        return previous, following

    previous_keys = [key for key in all_keys if key < current]
    following_keys = [key for key in all_keys if key > current]
    previous = previous_keys[-1] if previous_keys else (all_keys[0] if all_keys else current)
    following = following_keys[0] if following_keys else (all_keys[-1] if all_keys else current)
    return previous, following


def lerp(start, end, amount):
    while isinstance(start, (list, tuple)) and len(start) == 1:
        start = start[0]
    while isinstance(end, (list, tuple)) and len(end) == 1:
        end = end[0]
    if isinstance(start, (list, tuple)) and isinstance(end, (list, tuple)):
        return [lerp(a, b, amount) for a, b in zip(start, end)]
    return start + (end - start) * amount


def lerp_towards(left, right, amount, current):
    while isinstance(left, (list, tuple)) and len(left) == 1:
        left = left[0]
    while isinstance(right, (list, tuple)) and len(right) == 1:
        right = right[0]
    while isinstance(current, (list, tuple)) and len(current) == 1:
        current = current[0]
    if amount < 0.0:
        return lerp(left, current, amount + 1.0)
    if amount > 0.0:
        return lerp(current, right, amount)
    return current
