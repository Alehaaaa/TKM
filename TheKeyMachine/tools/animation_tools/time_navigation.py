"""Undo-free, refireable time navigation for Anim Curve Tools."""

from __future__ import annotations

try:
    from TheKeyMachine.core import openMayaUtils as omutils
except ImportError:  # pragma: no cover - imported outside the package
    omutils = None


_pending_actions = []
_flush_scheduled = False
_idle_callback_id = None
_TIME_TOLERANCE = 0.000001


def _queue(kind, amount, context=()):
    global _flush_scheduled

    try:
        amount = int(amount)
    except (TypeError, ValueError, OverflowError):
        return False
    if not amount:
        return False
    context = context if kind == "curve_key" else ()
    if kind == "curve_key" and not context:
        return False

    signature = (kind, context)
    if _pending_actions and _pending_actions[-1][:2] == signature:
        combined = _pending_actions[-1][2] + amount
        if combined:
            _pending_actions[-1] = (kind, context, combined)
        else:
            _pending_actions.pop()
    else:
        _pending_actions.append((kind, context, amount))

    if not _pending_actions or _flush_scheduled:
        return True
    _flush_scheduled = True
    _schedule_flush()
    return True


def request_frame_step(amount):
    """Queue an unclamped frame step and combine rapid repeated requests."""
    return _queue("frame", amount)


def request_curve_key_step(amount, curves, time_range=None):
    """Queue a native step through selected animation curves."""
    curves = tuple(dict.fromkeys(curves or []))
    if not curves:
        return False
    normalized_range = None
    if time_range:
        try:
            normalized_range = tuple(sorted((
                float(time_range[0]),
                float(time_range[1]),
            )))
        except (IndexError, TypeError, ValueError):
            normalized_range = None
    return _queue("curve_key", amount, (curves, normalized_range))


def accumulate_pending_key_step(amount):
    """Add to an already queued key step without querying curve data again."""
    if not _pending_actions or _pending_actions[-1][0] != "curve_key":
        return False
    try:
        amount = int(amount)
    except (TypeError, ValueError, OverflowError):
        return False
    if not amount:
        return True

    kind, times, pending_amount = _pending_actions[-1]
    combined = pending_amount + amount
    if combined:
        _pending_actions[-1] = (kind, times, combined)
    else:
        _pending_actions.pop()
    return True


def _schedule_flush():
    global _idle_callback_id
    _idle_callback_id = (
        omutils.add_event_callback("idle", _flush_from_idle)
        if omutils else None
    )
    if _idle_callback_id is None:
        flush_pending_navigation()


def _flush_from_idle(*_args):
    global _idle_callback_id
    callback_id = _idle_callback_id
    _idle_callback_id = None
    if omutils:
        omutils.remove_callback(callback_id)
    return flush_pending_navigation()


def flush_pending_navigation(*_args):
    """Apply the accumulated navigation batch with one Maya API time change."""
    global _flush_scheduled

    actions = list(_pending_actions)
    _pending_actions[:] = []
    _flush_scheduled = False
    if not actions or omutils is None:
        return False

    current = omutils.current_time()
    if current is None:
        return False
    for kind, context, amount in actions:
        if kind == "frame":
            current += amount
        elif kind == "curve_key":
            curves, time_range = context
            destination = omutils.step_anim_curve_key_time(
                curves,
                current,
                amount,
                time_range=time_range,
                tolerance=_TIME_TOLERANCE,
            )
            current = destination if destination is not None else current + amount
    return omutils.set_current_time(current)


def cancel_pending_navigation():
    """Discard queued work when the TKM runtime is shutting down."""
    global _flush_scheduled, _idle_callback_id
    if omutils:
        omutils.remove_callback(_idle_callback_id)
    _idle_callback_id = None
    _pending_actions[:] = []
    _flush_scheduled = False
