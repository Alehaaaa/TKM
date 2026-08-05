from contextlib import contextmanager
from functools import lru_cache
import inspect
import threading
import time
import traceback
import warnings

import maya.cmds as cmds  # type: ignore
import maya.mel as mel  # type: ignore

from TheKeyMachine.core.Qt import QtCore, QtGui  # type: ignore

from TheKeyMachine.data import icons
from TheKeyMachine.widgets import util as wutil
from TheKeyMachine.mods import settingsMod as settings


# Set TKM_DEBUG_TIMING=true in TheKeyMachine/.env (or the process
# environment) to print a per-phase breakdown of every tool_operation() to
# the Script Editor -- lets a reported "hang before the tool actually runs"
# be pinned to an exact phase (progress/tint setup, undo chunk, refresh
# suspension, or the callback itself) instead of guessed at. Uses the same
# .env reader as TKM_TOOL_DEBUG (see core/debug.py) rather than a second,
# duplicated parser. Read once at import -- tool_operation() runs on every
# click, so this must not become another uncached per-click file read;
# reload TheKeyMachine after changing the flag to pick up a new value.
def _debug_timing_enabled():
    try:
        from TheKeyMachine.core import debug as _debug

        return _debug.env_flag("TKM_DEBUG_TIMING")
    except Exception:
        return False


_DEBUG_TIMING = _debug_timing_enabled()


def debug_timing_enabled():
    """Public accessor for _DEBUG_TIMING so other modules can add their own
    fine-grained timing probes without reaching into a private module var."""
    return _DEBUG_TIMING


def debug_timing_log(label, **phases_ms):
    """Print one [TKM timing] breakdown line if TKM_DEBUG_TIMING is on.

    Shared by tool_operation()'s own phase breakdown and any controller that
    wants to instrument further inside its callback (e.g. to split a slow
    "callback" phase into its own sub-phases) -- one format, one place.
    """
    if not _DEBUG_TIMING:
        return
    parts = " ".join(
        "{}={:.1f}ms".format(name, value) for name, value in phases_ms.items()
    )
    print("[TKM timing] {}: {}".format(label, parts))


UNDO_PREFIX = "TKM"
FLOATING_TOOL_ANCHOR_GAP = wutil.DPI(12)
_ACTIVE_PROGRESS_STACK = []
_TOOL_DURATION_ESTIMATES = {}
_REFRESH_SUSPEND_DEPTH = 0
_REFRESH_WAS_SUSPENDED = False


def finish_active_progress():
    """Stop every TKM-owned progress display and cancel its delayed timers."""
    active = list(_ACTIVE_PROGRESS_STACK)
    _ACTIVE_PROGRESS_STACK[:] = []
    for progress in reversed(active):
        try:
            progress.exclude_from_estimates = True
            progress.finish()
        except Exception:
            pass


def mark_non_tool_action(callback):
    """Mark a UI-only callback so dispatch skips progress and undo handling."""
    if callable(callback):
        callback._tkm_non_tool_action = True
    return callback


def format_eta(seconds):
    try:
        seconds = max(0, int(round(float(seconds))))
    except Exception:
        return ""
    if seconds < 60:
        unit = "second" if seconds == 1 else "seconds"
        return "{} {} left".format(seconds, unit)
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        minute_unit = "minute" if minutes == 1 else "minutes"
        second_unit = "second" if seconds == 1 else "seconds"
        return "{} {} {} {} left".format(
            minutes, minute_unit, seconds, second_unit
        )
    hours, minutes = divmod(minutes, 60)
    hour_unit = "hour" if hours == 1 else "hours"
    minute_unit = "minute" if minutes == 1 else "minutes"
    return "{} {} {} {} left".format(hours, hour_unit, minutes, minute_unit)


def _quantize_eta_seconds(seconds):
    """Round a raw remaining-time estimate to a "round" display value.

    A countdown that ticks 47s, 46s, 44s, 39s, 41s... reads as broken even
    when the underlying estimate is reasonable -- people expect a steady,
    coarse number, not an exact one. Coarser buckets the longer the
    remaining time is, since precision that far out is noise anyway.
    """
    seconds = max(0.0, float(seconds))
    if seconds < 10:
        step = 1
    elif seconds < 60:
        step = 5
    else:
        step = 15
    return step * round(seconds / step)


class _EtaEstimator(object):
    """Turns noisy per-step timing into a steady remaining-time prediction.

    ``AdaptiveProgress`` used to recompute "elapsed / done * remaining"
    from scratch on every status refresh. That ratio is exact but swings
    wildly step to step (one slightly slow or fast item shifts the whole
    projection), which is what made the ETA fluctuate enough to feel
    useless. This keeps an exponentially smoothed seconds-per-unit rate
    instead of the raw instantaneous one, and only lets the *displayed*
    number change when it's actually moved meaningfully or enough time has
    passed -- a steady prediction rather than a live-recalculated one.
    """

    # Weight given to each new sample when smoothing the rate. Low enough
    # that a single unusually slow/fast step barely nudges the estimate.
    _RATE_SMOOTHING = 0.2
    # Don't refresh the displayed number more often than this even if the
    # underlying estimate keeps moving -- caps how "live" it looks.
    _MIN_REFRESH_MS = 1000

    def __init__(self):
        self._rate_per_unit = None
        self._last_sampled_value = None
        self._displayed_seconds = None
        self._last_refresh_ms = -1

    def reset(self):
        self._rate_per_unit = None
        self._last_sampled_value = None
        self._displayed_seconds = None
        self._last_refresh_ms = -1

    def estimate(self, elapsed_ms, value, max_value):
        """Return a steady remaining-seconds figure, or None if not ready."""
        if not value or not max_value or value >= max_value:
            return None

        elapsed_seconds = max(0.001, elapsed_ms / 1000.0)
        # _status_text() (and therefore this) gets called both when value
        # actually advances (step()) and on the plain polling timer
        # (_poll_status(), on a fixed interval regardless of progress). Only
        # take a new rate sample when value has moved since the last one --
        # otherwise a stall between steps would look like "still working at
        # a slower and slower rate" every single poll tick and drag the
        # smoothed rate around on timing noise rather than real work.
        if value != self._last_sampled_value:
            instantaneous_rate = elapsed_seconds / float(value)
            if self._rate_per_unit is None:
                self._rate_per_unit = instantaneous_rate
            else:
                self._rate_per_unit += self._RATE_SMOOTHING * (
                    instantaneous_rate - self._rate_per_unit
                )
            self._last_sampled_value = value

        if self._rate_per_unit is None:
            return None
        remaining = self._rate_per_unit * max(0, max_value - value)

        displayed = self._displayed_seconds
        stale = (
            displayed is None
            or elapsed_ms - self._last_refresh_ms >= self._MIN_REFRESH_MS
        )
        moved_enough = displayed is not None and abs(remaining - displayed) >= max(
            2.0, displayed * 0.2
        )
        if stale or moved_enough:
            displayed = _quantize_eta_seconds(remaining)
            self._displayed_seconds = displayed
            self._last_refresh_ms = elapsed_ms
        return displayed


class AdaptiveProgress(object):
    def __init__(
        self,
        label,
        max_value=0,
        interruptable=True,
        show_after_ms=500,
        min_steps=40,
        update_interval_ms=250,
        estimated_seconds=None,
    ):
        self.label = label or "Processing"
        self.max_value = max(0, int(max_value or 0))
        self._bar_max = self.max_value if self.max_value > 0 else 100
        self.interruptable = bool(interruptable)
        self.show_after_ms = max(0, int(show_after_ms or 0))
        self.min_steps = max(1, int(min_steps or 1))
        self.update_interval_ms = max(100, int(update_interval_ms or 1000))
        self.estimated_seconds = float(estimated_seconds) if estimated_seconds else None
        self.value = 0
        self._eta = _EtaEstimator()
        self._bar = None
        self._active = False
        self._finished = False
        self._cancelled = False
        self.exclude_from_estimates = False
        self._last_status_update_ms = -1
        self._last_progress_update_ms = -1
        self._last_status_label = self.label
        self._exact_status_text = None
        self._timer = QtCore.QElapsedTimer()
        self._timer.start()
        self._show_timer = QtCore.QTimer()
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._delayed_start)
        self._status_timer = QtCore.QTimer()
        self._status_timer.setInterval(self.update_interval_ms)
        self._status_timer.timeout.connect(self._poll_status)

    def set_total(self, max_value, reset=False):
        """Declare or revise the amount of work without replacing the processor."""
        self.max_value = max(0, int(max_value or 0))
        self._bar_max = self.max_value if self.max_value > 0 else 100
        if reset:
            self.value = 0
            self._timer.restart()
            self._eta.reset()
        elif self.max_value:
            self.value = min(self.value, self.max_value)
        if self._active and self._bar:
            try:
                cmds.progressBar(
                    self._bar,
                    edit=True,
                    maxValue=self._bar_max,
                    progress=min(self.value, self._bar_max),
                    status=self._status_text(),
                )
            except Exception:
                pass
        return self

    def set_status(self, status, exact=False):
        if status:
            if exact:
                self._exact_status_text = status
            else:
                self.label = status
                self._exact_status_text = None
        if self._active and self._bar:
            try:
                cmds.progressBar(self._bar, edit=True, status=self._status_text())
            except Exception:
                pass
        return self

    def __enter__(self):
        _ACTIVE_PROGRESS_STACK.append(self)
        if self._show_timer:
            self._show_timer.start(self.show_after_ms)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.finish()
        finally:
            if _ACTIVE_PROGRESS_STACK and _ACTIVE_PROGRESS_STACK[-1] is self:
                _ACTIVE_PROGRESS_STACK.pop()
            elif self in _ACTIVE_PROGRESS_STACK:
                _ACTIVE_PROGRESS_STACK.remove(self)

    def _should_show(self):
        if self._active:
            return False
        return self._timer.elapsed() >= self.show_after_ms

    def _delayed_start(self):
        self._ensure_started(force=True)

    def _ensure_started(self, force=False):
        if self._active or self._finished:
            return
        if not force and not self._should_show():
            return
        try:
            self._bar = mel.eval("$tmp = $gMainProgressBar")
            cmds.progressBar(
                self._bar,
                edit=True,
                beginProgress=True,
                isInterruptable=self.interruptable,
                status=self._status_text(),
                maxValue=self._bar_max,
            )
            self._active = True
            self._last_status_update_ms = self._timer.elapsed()
            self._last_progress_update_ms = self._last_status_update_ms
            self._status_timer.start()
        except Exception:
            self._bar = None

    def start(self, force=False):
        was_active = self._active
        self._ensure_started(force=force)
        if was_active or not self._active:
            return
        # Synchronous Maya commands can block the event loop immediately after
        # beginProgress. Flush one paint pass so an explicitly started standard
        # tool operation is visible before its work begins.
        try:
            app = QtCore.QCoreApplication.instance()
            if app is not None:
                app.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass

    def _status_text(self):
        if self._exact_status_text:
            return self._exact_status_text

        title = format_tool_label(self.label)
        if self.max_value:
            # Total is already known (most TKM tools compute it upfront), so
            # there's nothing to "estimate" -- show real N/Total progress
            # from the first frame instead of a placeholder that implies an
            # open-ended wait most operations never actually have.
            if self.value > 0:
                remaining = self._eta.estimate(self._timer.elapsed(), self.value, self.max_value)
                eta = format_eta(remaining) if remaining is not None else ""
                if eta:
                    return "{}... about {}".format(title, eta)
            return "{}... {}/{}".format(title, self.value, self.max_value)

        # Total is genuinely unknown here. Most operations still finish in
        # well under a second, so lead with the plain label instead of
        # "estimating time" -- only start saying that once enough time has
        # actually passed that a bare label would look stuck.
        elapsed_seconds = max(0.0, self._timer.elapsed() / 1000.0)
        if self.estimated_seconds and self.estimated_seconds > elapsed_seconds:
            # A fixed prior estimate counting straight down is already
            # steady (nothing here is being recomputed from live samples);
            # just quantize it so it doesn't tick by exact seconds either.
            eta = format_eta(_quantize_eta_seconds(self.estimated_seconds - elapsed_seconds))
            if eta:
                return "{}... about {}".format(title, eta)
        if elapsed_seconds >= 1.0:
            elapsed = int(round(elapsed_seconds))
            return "{}... estimating time ({} seconds elapsed)".format(
                title, elapsed
            )
        return title

    @property
    def elapsed_seconds(self):
        return max(0.0, self._timer.elapsed() / 1000.0)

    def step(self, amount=1, status=None, exact_status=None):
        amount = int(amount or 1)
        if self.max_value:
            self.value = min(self.max_value, self.value + amount)
            display_value = self.value
        else:
            self.value += amount
            display_value = self.value % self._bar_max
        self._ensure_started()
        if not self._active or not self._bar:
            return False
        try:
            if exact_status:
                self._exact_status_text = exact_status
            elif status:
                self.label = status
                self._exact_status_text = None
            now = self._timer.elapsed()
            progress_due = (
                status
                or exact_status
                or self._last_progress_update_ms < 0
                or now - self._last_progress_update_ms >= 50
                or (self.max_value and self.value >= self.max_value)
            )
            if not progress_due:
                return self._cancelled
            status_due = (
                status
                or exact_status
                or self._last_status_update_ms < 0
                or now - self._last_status_update_ms >= self.update_interval_ms
                or (self.max_value and self.value >= self.max_value)
            )
            kwargs = {"edit": True, "progress": display_value}
            if status_due:
                kwargs["status"] = self._status_text()
                self._last_status_update_ms = now
                self._last_status_label = self.label
            cmds.progressBar(self._bar, **kwargs)
            self._last_progress_update_ms = now
            self._cancelled = bool(cmds.progressBar(self._bar, query=True, isCancelled=True))
        except Exception:
            self._cancelled = False
        return self._cancelled

    def _poll_status(self):
        if not self._active or not self._bar:
            return
        try:
            cmds.progressBar(self._bar, edit=True, status=self._status_text())
            self._cancelled = bool(cmds.progressBar(self._bar, query=True, isCancelled=True))
        except Exception:
            pass

    advance = step

    def iterate(self, iterable, total=None, status=None):
        """Yield work items and advance once after each completed item."""
        if total is None:
            try:
                total = len(iterable)
            except (TypeError, AttributeError):
                total = None
        if total is not None:
            self.set_total(total)
        if status:
            self.set_status(status)
        for item in iterable:
            if self.cancelled:
                break
            yield item
            self.step()

    @property
    def cancelled(self):
        return self._cancelled

    def finish(self):
        self._finished = True
        for timer in (self._show_timer, self._status_timer):
            if not timer:
                continue
            timer.stop()
            try:
                timer.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass
            timer.deleteLater()
        self._show_timer = None
        self._status_timer = None
        if self._active and self._bar:
            try:
                cmds.progressBar(self._bar, edit=True, endProgress=True)
            except Exception:
                pass
        self._active = False
        self._bar = None


def _acquire_refresh_suspension():
    """Suspend Maya refresh without disturbing suspension owned elsewhere."""
    global _REFRESH_SUSPEND_DEPTH, _REFRESH_WAS_SUSPENDED
    if _REFRESH_SUSPEND_DEPTH == 0:
        try:
            _REFRESH_WAS_SUSPENDED = bool(cmds.refresh(query=True, suspend=True))
        except Exception:
            _REFRESH_WAS_SUSPENDED = False
        if not _REFRESH_WAS_SUSPENDED:
            try:
                cmds.refresh(suspend=True)
            except Exception:
                return False
    _REFRESH_SUSPEND_DEPTH += 1
    return True


def _release_refresh_suspension(acquired):
    global _REFRESH_SUSPEND_DEPTH, _REFRESH_WAS_SUSPENDED
    if not acquired:
        return
    _REFRESH_SUSPEND_DEPTH = max(0, _REFRESH_SUSPEND_DEPTH - 1)
    if _REFRESH_SUSPEND_DEPTH or _REFRESH_WAS_SUSPENDED:
        return
    try:
        cmds.refresh(suspend=False)
    except Exception:
        pass


@contextmanager
def suspend_maya_refresh(enabled=True):
    """Nest-safe context for temporarily suspending Maya viewport refresh."""
    acquired = _acquire_refresh_suspension() if enabled else False
    try:
        yield acquired
    finally:
        _release_refresh_suspension(acquired)


# --- threaded tool operations -------------------------------------------------
#
# A synchronous tool that loops over Maya cmds calls on the main thread never
# gives Qt a chance to dispatch a queued Cancel click on the progress bar
# until the loop itself pauses to check -- so cancellation can be "checked"
# every step and still not actually register in time. Running the callback
# on a worker thread instead keeps the main thread's event loop free the
# entire time the tool is working, so a Cancel press gets processed (and
# operation.cancelled reflects it) immediately instead of only between
# batches.
#
# Maya's cmds/OpenMaya API is not safe to call from a non-main thread, so a
# threaded callback can't just keep calling cmds directly -- every actual
# scene edit has to hop back onto the main thread via
# ToolOperation.run_on_main(). This is opt-in per tool (see
# core/trigger.py's OperationPolicy.threaded): a callback that hasn't been
# migrated to route its Maya calls through run_on_main() must not be marked
# threaded, or it will call cmds off the main thread and can crash Maya.

_MAIN_THREAD_MARSHAL = None


class _MainThreadMarshal(QtCore.QObject):
    """Runs a callable on the main/GUI thread and blocks the caller for it.

    Instantiated once, lazily, the first time it's needed -- always from the
    main thread (tool_operation() only ever starts from a UI action), so its
    own affinity is correct without an explicit moveToThread().
    """

    _request = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self._request.connect(self._run, QtCore.Qt.QueuedConnection)

    def _run(self, job):
        fn, args, kwargs, event, box = job
        try:
            box["value"] = fn(*args, **kwargs)
        except Exception as exc:
            # Printed here, at the true point of failure on the main
            # thread, since the exception re-raised on the worker thread
            # below will only show the marshal round trip in its own
            # traceback, not where inside fn it actually broke.
            print(traceback.format_exc())
            box["error"] = exc
        finally:
            event.set()

    def call(self, fn, *args, **kwargs):
        if QtCore.QThread.currentThread() is self.thread():
            # Already on the main thread (e.g. a threaded=True tool whose
            # callback also has a non-threaded code path) -- run inline,
            # no round trip, no risk of deadlocking on our own event loop.
            return fn(*args, **kwargs)

        event = threading.Event()
        box = {}
        self._request.emit((fn, args, kwargs, event, box))
        event.wait()
        if "error" in box:
            raise box["error"]
        return box.get("value")


def _get_main_thread_marshal():
    global _MAIN_THREAD_MARSHAL
    if _MAIN_THREAD_MARSHAL is None:
        _MAIN_THREAD_MARSHAL = _MainThreadMarshal()
    return _MAIN_THREAD_MARSHAL


class _ToolWorkerThread(QtCore.QThread):
    """Runs one callable off the GUI thread and reports back via signals."""

    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(object)

    def __init__(self, fn, args, kwargs, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            self.failed.emit((exc, traceback.format_exc()))
            return
        self.succeeded.emit(result)


def run_on_worker_thread(fn, *args, **kwargs):
    """Run ``fn`` on a worker thread; block the caller without blocking Qt.

    From the caller's point of view this behaves like calling ``fn``
    directly -- it returns fn's result, or re-raises its exception, once
    fn has finished. The difference is that a local QEventLoop, not the
    call stack, is what's waiting: the main thread's event loop keeps
    running (painting, dispatching a progress bar Cancel click) the whole
    time fn executes elsewhere.

    ``fn`` must not call Maya's cmds/OpenMaya API directly -- it should
    route those calls through the ``tool_operation`` it was handed (see
    ToolOperation.run_on_main), which marshals them back onto this thread.
    """
    worker = _ToolWorkerThread(fn, args, kwargs)
    loop = QtCore.QEventLoop()
    outcome = {}

    def _on_succeeded(result):
        outcome["value"] = result
        loop.quit()

    def _on_failed(payload):
        outcome["error"] = payload
        loop.quit()

    worker.succeeded.connect(_on_succeeded)
    worker.failed.connect(_on_failed)
    worker.start()
    loop.exec_()
    worker.wait()
    worker.deleteLater()

    if "error" in outcome:
        exc, traceback_text = outcome["error"]
        print(traceback_text)
        raise exc
    return outcome.get("value")


# Tool progress stays invisible for quick actions and only opens once an
# operation has run long enough for progress and ETA feedback to be useful.
PROGRESS_SHOW_DELAY_MS = 150


# Shared "is this taking too long" heuristic. Long operations use threading
# to stay responsive while they run; interactive
# controls that call some per-tick command on every input event (sliders
# today) can't thread their way out of a slow tick the same way -- there's
# nothing to cancel mid-tick -- so instead they fall back from applying
# every tick live ("autorefresh") to applying once on release
# ("post-release refresh") the moment a tick stops keeping up. One
# threshold/one guard class for that decision, shared by every control that
# needs it, instead of each reimplementing its own elapsed-time check.
SLOW_OPERATION_MS = 150


class SlowOperationGuard(object):
    """Detects when repeated live updates have gotten too slow to keep live.

    Usage: create one per interaction (e.g. per slider drag), call
    ``reset()`` when the interaction starts, and wrap each live-update tick
    in ``with guard.measure(): ...``. Once any tick is slow, ``is_slow``
    latches True for the rest of the interaction -- a command that's slow
    once tends to be slow again (same busy scene, same heavy rig), and
    flipping live updates back on mid-interaction would be a worse surprise
    than staying in post-release mode for the rest of it.
    """

    def __init__(self, threshold_ms=SLOW_OPERATION_MS):
        self.threshold_ms = threshold_ms
        self._is_slow = False

    def reset(self):
        self._is_slow = False

    @property
    def is_slow(self):
        return self._is_slow

    @contextmanager
    def measure(self):
        timer = QtCore.QElapsedTimer()
        timer.start()
        try:
            yield
        finally:
            if timer.elapsed() >= self.threshold_ms:
                self._is_slow = True


class ToolOperation(object):
    def __init__(self, tool_id=None, label=None, progress=None, tint_session=None, anchor_widget=None):
        self.tool_id = tool_id
        self.label = label or humanize_tool_name(tool_id) or "Processing"
        self.progress = progress
        self.tint_session = tint_session
        self.anchor_widget = anchor_widget
        self.undo_chunk_opened = False
        self.success = False
        self.timerange = None
        self.success_message = None
        self.refresh_suspended = False
        self.preserved_time_selection = None

    @property
    def cancelled(self):
        # A plain bool read -- safe from a threaded operation's worker
        # thread without marshaling. It's kept current by AdaptiveProgress's
        # own main-thread timer/step polling regardless of which thread
        # this property is read from.
        progress = self.progress
        return bool(progress and progress.cancelled)

    def run_on_main(self, fn, *args, **kwargs):
        """Run ``fn`` on the main thread and return its result.

        A threaded tool's callback (see core/trigger.py's
        OperationPolicy.threaded / common.run_on_worker_thread) must route
        every Maya cmds/OpenMaya call through this -- Maya's API is not
        safe to call directly from the worker thread the callback runs on.
        Safe and cheap to call unconditionally: when already on the main
        thread it just calls ``fn`` inline, no round trip.
        """
        return _get_main_thread_marshal().call(fn, *args, **kwargs)

    def step(self, amount=1, status=None, exact_status=None):
        if not self.progress:
            return False
        return self.run_on_main(
            self.progress.step,
            amount=amount,
            status=status,
            exact_status=exact_status,
        )

    def start(self):
        if self.progress:
            self.run_on_main(self.progress.start)

    def set_total(self, total, reset=False):
        if self.progress:
            self.run_on_main(self.progress.set_total, total, reset=reset)
        return self

    def set_status(self, status, exact=False):
        if self.progress:
            self.run_on_main(self.progress.set_status, status, exact=exact)
        return self

    def iterate(self, iterable, total=None, status=None):
        """Yield work items and advance once after each completed item.

        Implemented here (rather than delegating to
        ``AdaptiveProgress.iterate()``) so every step goes through
        ``run_on_main``/``cancelled`` above and stays safe to drive from a
        threaded operation's worker thread, not just the main thread.
        """
        if not self.progress:
            for item in iterable:
                yield item
            return
        if total is None:
            try:
                total = len(iterable)
            except (TypeError, AttributeError):
                total = None
        if total is not None:
            self.set_total(total)
        if status:
            self.set_status(status)
        for item in iterable:
            if self.cancelled:
                break
            yield item
            self.step()


_TOOL_OPERATION_STACK = []


def current_tool_operation():
    if not _TOOL_OPERATION_STACK:
        return None
    return _TOOL_OPERATION_STACK[-1]


def _current_undo_operation(exclude=None):
    for operation in reversed(_TOOL_OPERATION_STACK):
        if operation is exclude:
            continue
        if getattr(operation, "undo_chunk_opened", False):
            return operation
    return None


def _begin_operation_tint(tint=None, timerange=None, default_mode="current_frame", tint_key=None, tint_color=None, owner=None):
    if not tint or tint == "none":
        return None
    try:
        from TheKeyMachine.widgets import timeline as timeline_widgets
    except Exception:
        return None
    try:
        if tint == "range" and timerange:
            return timeline_widgets.begin_timeline_tint(
                timerange=timerange,
                color=tint_color,
                owner=owner,
                key=tint_key,
            )
        if tint in ("current", "context"):
            return timeline_widgets.begin_timeline_context(
                default_mode=default_mode,
                color=tint_color,
                owner=owner,
                key=tint_key,
            )
    except Exception:
        return None
    return None


def ensure_operation_tint(operation, tint=None, timerange=None, default_mode="current_frame", tint_key=None, tint_color=None):
    """Give an already-open ``ToolOperation`` a timeline tint if it doesn't have one yet.

    Lets a command that reused the dispatcher's operation (instead of opening
    its own via ``tool_operation()``) still ask for tint/timerange context,
    without duplicating ``tool_operation()``'s own tint-begin logic -- both
    paths route through the same ``_begin_operation_tint()``.
    """
    if operation is None or operation.tint_session:
        return
    if timerange:
        operation.timerange = timerange
    operation.tint_session = _begin_operation_tint(
        tint=tint,
        timerange=timerange,
        default_mode=default_mode,
        tint_key=tint_key or operation.tool_id,
        tint_color=tint_color,
        owner=operation.anchor_widget,
    )


@contextmanager
def tool_operation(
    tool_id=None,
    label=None,
    progress_max=0,
    progress=True,
    interruptable=True,
    undo=False,
    undo_name=None,
    tint=None,
    timerange=None,
    default_mode="current_frame",
    tint_key=None,
    tint_color=None,
    anchor_widget=None,
    show_success_message=True,
    suspend_refresh=True,
    preserve_time_selection=False,
):
    _t_start = time.perf_counter() if _DEBUG_TIMING else None

    # tool_operation() only ever starts from the main thread (a UI action,
    # hotkey, or shelf click) -- never from a threaded operation's own
    # worker thread. Touching the marshal singleton here, this early,
    # guarantees it's constructed (and therefore thread-affined) on the
    # main thread before a threaded=True operation could spawn a worker
    # that needs it.
    _get_main_thread_marshal()

    # Several tools nest a second tool_operation() call inside their own
    # callback as a helper (the "merge into parent" branch just below) --
    # that's fine on the main thread, but unlike operation.step()/set_total()
    # etc., tool_operation() itself (tint, undo chunk, refresh suspension)
    # is not marshaled, so entering it from a threaded=True tool's worker
    # thread would call Maya/Qt directly off the main thread. Fail loudly
    # here instead of letting that corrupt Maya state or crash unpredictably
    # later -- a threaded callback that needs a nested tool_operation() has
    # to call it via operation.run_on_main() instead.
    _app = QtCore.QCoreApplication.instance()
    if _app is not None and QtCore.QThread.currentThread() is not _app.thread():
        raise RuntimeError(
            "tool_operation() was entered from a non-main thread. A "
            "threaded=True tool's callback must not call tool_operation() "
            "(directly or via a helper) from its worker thread -- route "
            "Maya/Qt work through operation.run_on_main() instead."
        )

    if tint_color is None and tool_id:
        try:
            from TheKeyMachine.core import toolbox

            tint_color = toolbox.get_tool_tint_color(tool_id)
        except Exception:
            tint_color = None

    _t_tint_color = time.perf_counter() if _DEBUG_TIMING else None

    preserved_time_selection = None
    if preserve_time_selection:
        try:
            from TheKeyMachine.core import animation_context

            preserved_time_selection = (
                animation_context.capture_time_slider_selection()
            )
        except Exception:
            preserved_time_selection = None

    parent_operation = current_tool_operation()
    if parent_operation is not None:
        # core/trigger.py's dispatcher already opened the one real operation
        # for this user action (tool_id = the registered command name)
        # before calling the callback. Every command implementation that
        # opens tool_operation() again while that's live -- directly, or via
        # a per-module helper like _run_key_command / _copy_paste_operation /
        # tangents/api.py's _run() -- is re-wrapping itself, not composing a
        # genuinely separate tool (audited: no dispatched command invokes a
        # *different* registered command synchronously as a sub-step). Merge
        # into the live operation instead of nesting a second one, so every
        # command gets exactly one ToolOperation, one undo chunk, one tint
        # session, and one TKM_DEBUG_TIMING line per click -- regardless of
        # how many internal helpers it routes through.
        if label:
            parent_operation.set_status(label)
        if progress_max and parent_operation.progress:
            parent_operation.progress.set_total(progress_max, reset=True)
        if timerange:
            parent_operation.timerange = timerange
        if (
            preserve_time_selection
            and preserved_time_selection
            and not parent_operation.preserved_time_selection
        ):
            parent_operation.preserved_time_selection = preserved_time_selection
        ensure_operation_tint(
            parent_operation,
            tint=tint,
            timerange=timerange,
            default_mode=default_mode,
            tint_key=tint_key or tool_id,
            tint_color=tint_color,
        )
        yield parent_operation
        return

    progress_obj = None
    owns_progress = False
    estimate_key = str(tool_id or label or "Processing")
    if progress:
        progress_obj = AdaptiveProgress(
            label or humanize_tool_name(tool_id) or "Processing",
            progress_max,
            interruptable=interruptable,
            show_after_ms=PROGRESS_SHOW_DELAY_MS,
            min_steps=10,
            update_interval_ms=250,
            estimated_seconds=_TOOL_DURATION_ESTIMATES.get(estimate_key),
        )
        owns_progress = True
    _t_progress = time.perf_counter() if _DEBUG_TIMING else None
    tint_session = _begin_operation_tint(
        tint=tint,
        timerange=timerange,
        default_mode=default_mode,
        tint_key=tint_key or tool_id,
        tint_color=tint_color,
        owner=anchor_widget,
    )
    _t_tint_session = time.perf_counter() if _DEBUG_TIMING else None
    operation = ToolOperation(
        tool_id=tool_id,
        label=label,
        progress=progress_obj,
        tint_session=tint_session,
        anchor_widget=anchor_widget,
    )
    operation.preserved_time_selection = preserved_time_selection
    if timerange:
        operation.timerange = timerange
    chunk_opened = False
    _TOOL_OPERATION_STACK.append(operation)

    refresh_suspended = False
    operation_completed = False
    if suspend_refresh:
        refresh_suspended = _acquire_refresh_suspension()
        operation.refresh_suspended = refresh_suspended
    _t_refresh = time.perf_counter() if _DEBUG_TIMING else None

    try:
        if undo:
            existing_undo_operation = _current_undo_operation(exclude=operation)
            if existing_undo_operation is None:
                chunk_opened = open_undo_chunk(
                    undo_name or make_undo_chunk_name(tool_id=tool_id, title=label)
                )
                operation.undo_chunk_opened = bool(chunk_opened)
        _t_undo = time.perf_counter() if _DEBUG_TIMING else None
        with progress_obj if owns_progress else _null_context():
            if progress_obj:
                progress_obj.start(force=False)
            _t_before_callback = time.perf_counter() if _DEBUG_TIMING else None
            yield operation
            if _DEBUG_TIMING:
                _t_after_callback = time.perf_counter()
                debug_timing_log(
                    tool_id or label or "?",
                    tint_color=(_t_tint_color - _t_start) * 1000,
                    progress_setup=(_t_progress - _t_tint_color) * 1000,
                    tint_session=(_t_tint_session - _t_progress) * 1000,
                    refresh_suspend=(_t_refresh - _t_tint_session) * 1000,
                    undo_chunk=(_t_undo - _t_refresh) * 1000,
                    callback=(_t_after_callback - _t_before_callback) * 1000,
                    total_before_callback=(_t_before_callback - _t_start) * 1000,
                )
        operation_completed = True
            
        if operation.success:
            if tint == "range" and operation.timerange and not operation.tint_session:
                from TheKeyMachine.widgets import timeline as timeline_widgets
                try:
                    operation.tint_session = timeline_widgets.begin_timeline_tint(
                        timerange=operation.timerange,
                        color=tint_color,
                        owner=anchor_widget,
                        key=tint_key or tool_id,
                    )
                except Exception:
                    pass
            if show_success_message:
                try:
                    wutil.make_inViewMessage(operation.success_message or label or "Operation Successful")
                except Exception:
                    pass
    finally:
        if (
            operation_completed
            and owns_progress
            and progress_obj
            and not progress_obj.cancelled
            and not progress_obj.exclude_from_estimates
        ):
            elapsed = progress_obj.elapsed_seconds
            if elapsed >= 0.2:
                previous = _TOOL_DURATION_ESTIMATES.get(estimate_key)
                _TOOL_DURATION_ESTIMATES[estimate_key] = elapsed if previous is None else (previous * 0.7 + elapsed * 0.3)
        if _TOOL_OPERATION_STACK and _TOOL_OPERATION_STACK[-1] is operation:
            _TOOL_OPERATION_STACK.pop()
        elif operation in _TOOL_OPERATION_STACK:
            _TOOL_OPERATION_STACK.remove(operation)
        if operation.tint_session:
            try:
                operation.tint_session.finish()
            except Exception:
                pass
        _release_refresh_suspension(refresh_suspended)
        close_undo_chunk(chunk_opened)
        if operation.preserved_time_selection:
            try:
                from TheKeyMachine.core import animation_context

                animation_context.restore_time_slider_selection(
                    operation.preserved_time_selection
                )
            except Exception:
                pass


@contextmanager
def _null_context():
    yield None


def _button_tool_id(button):
    for attr in ("tool_id", "command_id", "objectName"):
        value = getattr(button, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value:
            return str(value)
    return ""


def _button_operation_label(button, tool_id=""):
    try:
        tooltip = button.toolTip()
    except Exception:
        tooltip = ""
    title = get_tooltip_title(tooltip) or get_tool_summary(tooltip)
    return title or humanize_tool_name(tool_id) or "Processing"


def _supported_callback_kwargs(callback, kwargs, injected_keys=None):
    injected_keys = set(injected_keys or [])
    try:
        signature = inspect.signature(callback)
    except Exception:
        return {
            key: value
            for key, value in kwargs.items()
            if key not in injected_keys
        }
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if accepts_kwargs:
        return kwargs
    return {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }


def run_tool_callback(button, callback, *args, **kwargs):
    if not callable(callback):
        return None
    tool_id = kwargs.pop("_tkm_tool_id", None) or _button_tool_id(button)
    label = (
        kwargs.pop("_tkm_tool_label", None)
        or _button_operation_label(button, tool_id)
    )
    # Registered/proxy commands own their operation at dispatch. Forward UI
    # metadata instead of wrapping them a second time.
    if getattr(callback, "_tkm_trigger_proxy", False) or getattr(callback, "_tkm_tool_dispatch", False):
        call_kwargs = dict(kwargs)
        call_kwargs["_tkm_tool_label"] = label
        call_kwargs["_tkm_anchor_widget"] = button
        return callback(*args, **call_kwargs)

    non_tool_action = bool(getattr(callback, "_tkm_non_tool_action", False))
    policy = None
    if tool_id and not non_tool_action:
        try:
            from TheKeyMachine.core import trigger

            policy = trigger.operation_policy(tool_id)
        except Exception:
            policy = None
    with tool_operation(
        tool_id=tool_id,
        label=label,
        anchor_widget=button,
        progress=(policy.progress if policy is not None else not non_tool_action),
        undo=(policy.undo if policy is not None else not non_tool_action),
        suspend_refresh=(policy.suspend_refresh if policy is not None else True),
    ) as operation:
        call_kwargs = dict(kwargs)
        call_kwargs.setdefault("anchor_widget", button)
        call_kwargs.setdefault("tool_operation", operation)
        call_kwargs = _supported_callback_kwargs(
            callback,
            call_kwargs,
            injected_keys=("anchor_widget", "tool_operation"),
        )
        if policy is not None and policy.threaded:
            return run_on_worker_thread(callback, *args, **call_kwargs)
        return callback(*args, **call_kwargs)

def _split_lines(raw):
    return str(raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _first_sentence(text):
    value = clean_tool_text(text)
    if not value:
        return ""
    for index, char in enumerate(value):
        if char in ".!?":
            return value[: index + 1].strip()
    return value


def _humanize_compound_word(raw):
    text = str(raw or "").replace("_", " ").replace("-", " ")
    result = []
    prev = ""
    for char in text:
        if prev and prev.isalnum() and char.isupper() and not prev.isupper():
            result.append(" ")
        result.append(char)
        prev = char
    return "".join(result)


def _tooltip_parts(raw):
    """Extract (title, first_line) from a Tooltip (mods.tooltipsMod).

    Uses attribute access rather than isinstance to avoid a circular import
    (tooltipsMod already imports this module). Expects a Tooltip;
    falls back gracefully to a plain string.
    """
    if not raw:
        return "", ""

    # Tooltip (from mods.tooltipsMod) exposes .title and .first_line
    if hasattr(raw, "title") and hasattr(raw, "first_line"):
        return clean_tool_text(raw.title), clean_tool_text(raw.first_line)

    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, str):
                first_line = clean_tool_text(item)
                if first_line:
                    return "", first_line
        return "", ""

    # Plain string fallback for ad-hoc tooltip text.
    return "", clean_tool_text(raw)


def clean_tool_text(raw):
    if not raw:
        return ""
    return " ".join(str(raw).split()).strip()


def humanize_tool_name(raw):
    if not raw:
        return ""
    value = _humanize_compound_word(raw)
    return clean_tool_text(value).title()


def get_tool_summary(raw):
    if not raw:
        return ""

    _, tooltip_summary = _tooltip_parts(raw)
    if tooltip_summary:
        return _first_sentence(tooltip_summary)

    parts = [clean_tool_text(part) for part in _split_lines(raw)]
    first_line = next((part for part in parts if part), "")
    if not first_line:
        return ""
    return _first_sentence(first_line)


def get_tooltip_title(raw):
    if not raw:
        return ""
    title, _ = _tooltip_parts(raw)
    return title


def get_tooltip_summary(raw):
    if not raw:
        return ""
    _, summary = _tooltip_parts(raw)
    if summary:
        return summary
    return get_tool_summary(raw)


def resolve_status_metadata(title="", description="", tooltip=None, status_title=None, status_description=None, fallback_title=""):
    resolved_title = clean_tool_text(
        status_title or title or get_tooltip_title(tooltip) or fallback_title
    )
    resolved_description = status_description
    if resolved_description is None:
        resolved_description = description or get_tooltip_summary(tooltip) or ""
    return resolved_title, resolved_description


def format_tool_label(title, description="", prefix=UNDO_PREFIX):
    clean_title = clean_tool_text(title) or "Tool"
    if prefix:
        return f"{prefix} - {clean_title}"
    return clean_title


@lru_cache(maxsize=256)
def _get_tool_definition(tool_id):
    if not tool_id:
        return None
    try:
        import TheKeyMachine.core.toolbox as toolbox

        return toolbox.get_tool(tool_id)
    except Exception:
        return None


try:
    # toolbox.get_tool()'s label/tooltip can now depend on the active
    # language (see core/i18n.py), which this lru_cache -- keyed only by
    # tool_id -- predates and knows nothing about. Without this, switching
    # languages would leave undo chunk names and operation status text
    # showing whichever language was cached first until the process cache
    # happened to evict that tool_id.
    from TheKeyMachine.core import i18n as _i18n

    _i18n.bus.languageChanged.connect(_get_tool_definition.cache_clear)
except Exception:
    pass


def resolve_undo_metadata(tool_id=None, title=None, description="", tooltip=None):
    resolved_title = title or ""
    resolved_description = description or ""

    tool = _get_tool_definition(tool_id)
    if tool:
        resolved_title = (
            tool.get("status_title")
            or tool.get("label")
            or tool.get("text")
            or resolved_title
        )
        resolved_description = (
            tool.get("status_description")
            or tool.get("description")
            or resolved_description
        )
        tooltip = tool.get("tooltip") or tooltip

    if tooltip:
        resolved_title, resolved_description = resolve_status_metadata(
            title=resolved_title,
            description=resolved_description,
            tooltip=tooltip,
            status_title=resolved_title or None,
            status_description=resolved_description or None,
            fallback_title=tool_id or "tool",
        )

    resolved_title = resolved_title or humanize_tool_name(tool_id or "tool")
    return resolved_title, resolved_description


def make_undo_chunk_name(tool_id=None, title=None, description="", tooltip=None):
    resolved_title, _resolved_description = resolve_undo_metadata(
        tool_id=tool_id,
        title=title,
        description=description,
        tooltip=tooltip,
    )
    return format_tool_label(resolved_title)


def open_undo_chunk(chunk_name=None):
    kargs = {}
    if chunk_name:
        kargs = {"chunkName": chunk_name}
    try:
        cmds.undoInfo(openChunk=True, **kargs)
        return True
    except Exception:
        return False


def close_undo_chunk(chunk_opened=True):
    if not chunk_opened:
        return
    try:
        cmds.undoInfo(closeChunk=True)
    except Exception:
        pass


class _SignalRelay(QtCore.QObject):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def trigger(self, *args):
        if self._callback is None:
            return
        self._callback(*args)


class _EventFilterRelay(QtCore.QObject):
    def __init__(self, widget, event_type, callback, parent=None):
        super().__init__(parent)
        self._widget = widget
        self._event_type = event_type
        self._callback = callback

    def eventFilter(self, watched, event):
        if watched is self._widget and event.type() == self._event_type and self._callback:
            return bool(self._callback(event))
        return False

    def detach(self):
        if self._widget:
            try:
                self._widget.removeEventFilter(self)
            except Exception:
                pass
        self._widget = None


def safe_signal_connect(signal, slot):
    try:
        signal.connect(slot)
        return True
    except Exception:
        return False


def set_checked_safely(widget, checked):
    if not widget:
        return False
    method = getattr(widget, "set_checked_safely", None)
    if callable(method):
        return method(checked)
    block_signals = getattr(widget, "blockSignals", None)
    previous = False
    if callable(block_signals):
        try:
            previous = widget.blockSignals(True)
        except Exception:
            previous = False
    try:
        widget.setChecked(bool(checked))
        return True
    except Exception:
        return False
    finally:
        if callable(block_signals):
            try:
                widget.blockSignals(previous)
            except Exception:
                pass


def connect_action(action, callback):
    if action is None or callback is None:
        return action
    try:
        action.triggered.connect(callback)
    except Exception:
        pass
    return action


def connect_checkable_action(action, getter=None, setter=None, signal=None):
    if action is None:
        return action
    try:
        action.setCheckable(True)
    except Exception:
        return action
    if callable(getter):
        set_checked_safely(action, getter())
    if setter is not None:
        try:
            action.triggered.connect(setter)
        except Exception:
            pass

    if signal is not None and callable(getter):
        def _sync(*_args, target=action, state_fn=getter):
            set_checked_safely(target, state_fn())

        replace_tracked_connection(
            action,
            "_tkm_checkable_action_sync",
            signal,
            _sync,
            parent=action,
        )
    return action


def add_floating_window_actions(menu, stays_on_top_getter, stays_on_top_setter, restore_position=None):
    """Add the standard floating-window actions to a tool context menu.

    ``restore_position`` is optional: skip it for windows that always open
    in the same place (e.g. anchored above their toolbar button) and have
    no draggable/saved geometry worth resetting.
    """
    always_on_top_action = menu.addAction(
        QtGui.QIcon(icons.settings),
        "Always on Top",
        description="Keep this floating window above other Maya windows.",
    )
    connect_checkable_action(
        always_on_top_action,
        stays_on_top_getter,
        stays_on_top_setter,
    )

    if restore_position is None:
        return always_on_top_action, None

    restore_position_action = menu.addAction(
        QtGui.QIcon(icons.refresh),
        "Restore Position",
        description="Restore this floating window to its default position.",
    )
    connect_action(restore_position_action, lambda *_: restore_position())
    return always_on_top_action, restore_position_action


def checked_state_getter(data):
    if not isinstance(data, dict):
        return None
    return (
        data.get("get_checked_fn")
        or data.get("get_checked")
        or data.get("is_checked_fn")
        or data.get("is_checked")
    )


def checked_state_setter(data):
    if not isinstance(data, dict):
        return None
    return data.get("set_checked")


def sync_checked(control, getter):
    if control is None:
        return False
    method = getattr(control, "sync_checked_state", None)
    if callable(method):
        return method()
    if not callable(getter):
        return False
    try:
        return set_checked_safely(control, bool(getter()))
    except Exception:
        return False


def publish_control_state(state_key, value):
    if not state_key:
        return value
    try:
        import TheKeyMachine.core.runtimeManager as runtime
        return runtime.get_runtime_manager().set_control_state(str(state_key), value)
    except Exception:
        return value


def deactivate_other_manipulator_tools(active_tool):
    """Deactivate other checkable TKM tools that own Maya manipulation state."""
    from TheKeyMachine.tools.depth_mover import api as depthMoverApi
    from TheKeyMachine.tools.micro_move import api as microMoveApi
    from TheKeyMachine.tools.temp_pivot import api as tempPivotApi

    tools = (
        ("micro_move", microMoveApi.is_enabled, microMoveApi.toggle),
        ("depth_mover", depthMoverApi.is_enabled, depthMoverApi.toggle),
        ("temp_pivot", tempPivotApi.is_temp_pivot_active, tempPivotApi.toggle),
    )
    for tool_id, is_enabled, toggle in tools:
        if tool_id == active_tool:
            continue
        if is_enabled():
            toggle(False)


def bind_control_state(control, state_key, apply_fn, attr_name="_tkm_control_state_sync"):
    if control is None or not state_key or not callable(apply_fn):
        return None
    try:
        import TheKeyMachine.core.runtimeManager as runtime
        manager = runtime.get_runtime_manager()
    except Exception:
        return None

    def _sync(changed_key, value, key=str(state_key), callback=apply_fn):
        if changed_key == key:
            callback(value)

    relay = replace_tracked_connection(
        control,
        attr_name,
        manager.controlStateChanged,
        _sync,
        parent=control,
    )
    if manager.has_control_state(str(state_key)):
        apply_fn(manager.get_control_state(str(state_key)))
    return relay


def bind_checked_signal(control, signal, getter, state_key=None, attr_name="_tkm_checked_state_sync"):
    if control is None or signal is None or not callable(getter):
        return None

    def _sync(*_args, target=control, state_fn=getter):
        state = bool(state_fn())
        set_checked_safely(target, state)
        publish_control_state(state_key, state)

    return replace_tracked_connection(
        control,
        attr_name,
        signal,
        _sync,
        parent=control,
    )


def bind_tool_state_signal(control, state_key, attr_name="_tkm_tool_state_sync"):
    if control is None or not state_key:
        return None
    def _apply(state, target=control):
        set_checked_safely(target, bool(state))

    relay = bind_control_state(
        control,
        state_key,
        _apply,
        attr_name=attr_name,
    )
    return relay


def configure_checkable_control(control, checkable=None, getter=None, changed_signal=None, state_key=None):
    if control is None:
        return control
    configure_method = getattr(control, "configure_check_state", None)
    if callable(configure_method):
        return configure_method(checkable=checkable, getter=getter, changed_signal=changed_signal, state_key=state_key)
    if checkable is not None:
        try:
            control.setCheckable(bool(checkable))
        except Exception:
            return control
    try:
        is_checkable = bool(control.isCheckable())
    except Exception:
        is_checkable = bool(checkable)
    if is_checkable:
        initial_state = bool(getter()) if callable(getter) else bool(control.isChecked())
        set_checked_safely(control, initial_state)
        bind_checked_signal(control, changed_signal, getter, state_key=state_key)
        bind_tool_state_signal(control, state_key)
        publish_control_state(state_key, initial_state)
    return control


def trigger_tool_callback(button, callback, *args, **kwargs):
    trigger_fn = getattr(button, "triggerToolCallback", None)
    if callable(trigger_fn):
        try:
            return trigger_fn(callback, *args, **kwargs)
        except TypeError:
            return trigger_fn(callback)
    if callable(callback):
        try:
            return callback(*args, **kwargs)
        except TypeError:
            return callback()
    return None


def _connect_control_trigger(control, callback):
    signal = getattr(control, "clicked", None) or getattr(control, "triggered", None)
    if signal is None:
        return False
    try:
        signal.connect(callback)
        return True
    except Exception:
        return False


def connect_tool_control(
    control,
    callback=None,
    *,
    checkable=None,
    getter=None,
    setter=None,
    changed_signal=None,
    bind_fn=None,
    state_key=None,
):
    binding_owns_trigger = False
    configure_method = getattr(control, "configure_check_state", None)
    if callable(configure_method):
        configure_method(
            checkable=checkable,
            getter=getter,
            setter=setter,
            changed_signal=changed_signal,
            bind_fn=bind_fn,
            state_key=state_key,
        )
        binding_owns_trigger = bool(getattr(control, "_tkm_check_binding_owns_trigger", False))
        if binding_owns_trigger:
            callback = None
    else:
        configure_checkable_control(control, checkable=checkable, getter=getter, changed_signal=changed_signal, state_key=state_key)

        if callable(bind_fn):
            try:
                if bind_fn(control) is True:
                    binding_owns_trigger = True
                    callback = None
            except Exception:
                pass

    if callback is None and callable(setter) and not binding_owns_trigger:
        callback = setter

    if callback is None or control is None:
        return control

    try:
        is_checkable = bool(control.isCheckable())
    except Exception:
        is_checkable = bool(checkable)

    if is_checkable:
        def _checked_cb(*args, cb=callback, target=control, state_fn=getter, set_fn=setter):
            checked = bool(args[0]) if args else bool(target.isChecked())
            set_state = getattr(target, "set_checked_state", None)
            if cb is not None:
                result = trigger_tool_callback(target, cb, checked)
            elif callable(set_state) and callable(set_fn):
                result = set_state(checked, apply=True)
            else:
                result = None
            state = bool(state_fn()) if callable(state_fn) else checked
            set_checked_safely(target, state)
            publish_control_state(state_key, state)
            return result

        _connect_control_trigger(control, _checked_cb)
        return control

    def _clicked_cb(*_args, cb=callback, target=control):
        return trigger_tool_callback(target, cb)

    _connect_control_trigger(control, _clicked_cb)
    return control


_USE_DESCRIPTOR_CALLBACK = object()


def connect_control_from_data(control, data, callback=_USE_DESCRIPTOR_CALLBACK):
    data = data or {}
    try:
        tool_id = data.get("key") or data.get("id") or data.get("command_id")
        if tool_id:
            control.tool_id = tool_id
            control.command_id = tool_id
    except Exception:
        pass
    resolved_callback = data.get("callback") if callback is _USE_DESCRIPTOR_CALLBACK else callback
    checkable = bool(data.get("checkable", data.get("type") in {"check", "setting"}))
    getter = checked_state_getter(data)
    setter = checked_state_setter(data)
    changed_signal = data.get("changed_signal")
    bind_fn = data.get("bind_checked_fn")
    state_key = data.get("state_key")

    if checkable or resolved_callback is not None or getter or changed_signal or bind_fn:
        connect_tool_control(
            control,
            resolved_callback,
            checkable=checkable,
            getter=getter,
            setter=setter,
            changed_signal=changed_signal,
            bind_fn=bind_fn,
            state_key=state_key,
        )
    return control


def connect_window_toggle_control(control, toggle, *, menu_factory=None, context_attr="_tkm_window_toggle_context_menu"):
    if menu_factory is None:
        if toggle:
            toggle.attach_button(control)
        return control
    bind_toolbar_button_context_menu(toggle, control, context_attr, menu_factory)
    return control


def clear_tracked_connection(owner, attr_name):
    relay = getattr(owner, attr_name, None)
    if relay is None:
        return False
    setattr(owner, attr_name, None)
    try:
        detach = getattr(relay, "detach", None)
        if callable(detach):
            detach()
        relay.deleteLater()
    except Exception:
        pass
    return True


def invalidate_cached_window_on_language_change(dialog, clear_ref):
    """Force a cached singleton window to rebuild fresh on its next open.

    Windows like the About/Donate/Version History/Hotkeys/Workspaces dialogs
    translate their static chrome (title, headers, buttons) once at
    construction, then get cached as a module-level singleton and simply
    re-shown on every later "open" call -- so a language switch while the
    window is closed (but not deleted -- these all set
    ``WA_DeleteOnClose=False``) never gets picked up on reopen. Hooking the
    same ``i18n.bus.languageChanged`` signal every already-open toolbar
    button listens to (see ``core.toolWidgets._bind_toolbar_translation_refresh``)
    and tearing the cached instance down here means the next open call finds
    no valid cached widget and builds a fresh one, picking up the current
    language for free -- no per-dialog ``refresh_translations()`` method to
    keep in sync by hand.

    ``clear_ref`` is a zero-arg callback that nulls out the caller's own
    module-level singleton variable (a plain Python global can't be passed
    by reference, so each caller supplies its own tiny setter).
    """
    from TheKeyMachine.core import i18n

    def _on_language_changed(*_args, dialog=dialog, clear_ref=clear_ref):
        clear_ref()
        try:
            dialog.close()
        finally:
            try:
                dialog.deleteLater()
            except Exception:
                pass

    replace_tracked_connection(
        dialog,
        "_tkm_singleton_language_invalidation",
        i18n.bus.languageChanged,
        _on_language_changed,
        parent=dialog,
    )


def replace_tracked_connection(owner, attr_name, signal, callback, parent=None):
    clear_tracked_connection(owner, attr_name)
    relay = _SignalRelay(callback, parent=parent)
    if not safe_signal_connect(signal, relay.trigger):
        try:
            relay.deleteLater()
        except Exception:
            pass
        return None
    setattr(owner, attr_name, relay)
    return relay


def disconnect_signal(signal):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            signal.disconnect()
            return True
        except Exception:
            return False


def set_custom_context_menu_handler(widget, attr_name, callback):
    if not widget:
        return None
    widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    disconnect_signal(widget.customContextMenuRequested)
    return replace_tracked_connection(
        widget,
        attr_name,
        widget.customContextMenuRequested,
        callback,
        parent=widget,
    )


def set_custom_context_menu(widget, attr_name, menu_factory):
    def _show_context_menu(pos, w=widget, factory=menu_factory):
        if not w:
            return
        menu = factory(w)
        if not menu:
            return
        exec_fn = getattr(menu, "exec", None) or getattr(menu, "exec_", None)
        if exec_fn:
            exec_fn(w.mapToGlobal(pos))

    return set_custom_context_menu_handler(widget, attr_name, _show_context_menu)


def set_event_handler(widget, attr_name, event_type, callback):
    if not widget:
        return None
    clear_tracked_connection(widget, attr_name)
    relay = _EventFilterRelay(widget, event_type, callback, parent=widget)
    widget.installEventFilter(relay)
    setattr(widget, attr_name, relay)
    return relay


def set_mouse_press_handler(widget, attr_name, callback):
    return set_event_handler(widget, attr_name, QtCore.QEvent.MouseButtonPress, callback)


def bind_toolbar_button_context_menu(toggle, button, attr_name, menu_factory):
    if toggle:
        toggle.attach_button(button)
    if not button:
        return None
    return set_custom_context_menu(button, attr_name, menu_factory)


def clear_tracked_connections(owner, attr_name):
    relays = getattr(owner, attr_name, None)
    if not relays:
        setattr(owner, attr_name, [])
        return False
    setattr(owner, attr_name, [])
    for relay in relays:
        try:
            relay.deleteLater()
        except Exception:
            pass
    return True


def replace_tracked_connections(owner, attr_name, pairs, parent=None):
    clear_tracked_connections(owner, attr_name)
    relays = []
    for signal, callback in pairs:
        relay = _SignalRelay(callback, parent=parent)
        if safe_signal_connect(signal, relay.trigger):
            relays.append(relay)
        else:
            try:
                relay.deleteLater()
            except Exception:
                pass
    setattr(owner, attr_name, relays)
    return relays


class ToolbarWindowToggle(QtCore.QObject):
    """Keeps any number of controls in sync with one floating window.

    ``tool_id`` should be the same registered trigger command this toggle's
    tool also exposes to hotkeys/shelf/search (e.g. ``"attribute_switcher"``)
    -- passing it routes every open/close through the same ``tool_operation()``
    dispatch primitive every other command uses (matching that command's own
    progress/undo policy, usually none for a window toggle) instead of a
    wholly separate wrapping mechanism, while still calling this toggle's own
    anchor-button-aware open/close functions rather than re-invoking the
    command by name (which would lose the button-anchored popup position).
    """

    def __init__(self, is_open_fn, open_fn, close_fn, state_signal=None, tool_id=None, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._syncing = False
        self._is_open_fn = is_open_fn
        self._open_fn = open_fn
        self._close_fn = close_fn
        self._tool_id = tool_id
        if state_signal is not None:
            state_signal.connect(self._on_window_state_changed)

    @staticmethod
    def _eligible_anchor(button):
        if not button or not wutil.is_valid_widget(button):
            return None
        if button.property("tkm_window_anchor") is False:
            return None
        return button if button.isVisible() else None

    def anchor_button(self):
        """Return the latest visible control explicitly eligible as a window anchor."""
        for button_id, button in reversed(list(self._buttons.items())):
            if not wutil.is_valid_widget(button):
                self._buttons.pop(button_id, None)
                continue
            anchor = self._eligible_anchor(button)
            if anchor is not None:
                return anchor
        return None

    def _open_from_source(self, source_button=None):
        call_kwargs = _supported_callback_kwargs(
            self._open_fn,
            {"anchor_button": self._eligible_anchor(source_button)},
            injected_keys=("anchor_button",),
        )
        return self._open_fn(**call_kwargs)

    def attach_button(self, button):
        if not button:
            return
        button_id = id(button)
        self._buttons[button_id] = button
        button.setCheckable(True)
        self._set_button_checked(button, self._is_open())
        replace_tracked_connection(
            button,
            "_tkm_window_toggle_relay",
            button.toggled,
            lambda checked, target=button: self._on_button_toggled(target, checked),
            parent=button,
        )
        replace_tracked_connection(
            button,
            "_tkm_window_toggle_destroyed_relay",
            button.destroyed,
            lambda *_args, key=button_id: self._on_button_destroyed(key),
            parent=button,
        )

    def _is_open(self):
        try:
            return bool(self._is_open_fn())
        except Exception:
            return False

    def _set_button_checked(self, button, checked):
        if not button or not wutil.is_valid_widget(button):
            return
        self._syncing = True
        try:
            set_checked_safely(button, checked)
        finally:
            self._syncing = False

    def _reconcile_button_state(self):
        is_open = self._is_open()
        for button_id, button in list(self._buttons.items()):
            if not wutil.is_valid_widget(button):
                self._buttons.pop(button_id, None)
                continue
            self._set_button_checked(button, is_open)

    def _run(self, fn, *, context):
        """Run one open/close action through the shared dispatch primitive.

        Every registered trigger command's body runs inside a
        ``tool_operation()``; this is the same call, using this toggle's own
        ``tool_id`` so TKM_DEBUG_TIMING and any future per-tool policy line
        up with the identical command reachable via hotkey/shelf/search.
        Window toggles need neither progress nor an undo chunk, matching the
        ``"check"``-type policy those commands already declare in trigger.py.
        ``report.safe_execute`` still does the actual error containment --
        centralizing here just means it (and the dispatch wrap) happens once
        instead of being copy-pasted at every call site below.
        """
        import TheKeyMachine.mods.reportMod as report

        with tool_operation(
            tool_id=self._tool_id,
            progress=False,
            undo=False,
            suspend_refresh=False,
            show_success_message=False,
        ):
            return report.safe_execute(fn, context=context)

    def _on_button_toggled(self, _button, checked):
        if self._syncing:
            return
        if checked:
            self._run(lambda: self._open_from_source(_button), context="toolbar window toggle open")
        else:
            self._run(self._close_fn, context="toolbar window toggle close")
        self._reconcile_button_state()

    def _on_button_destroyed(self, button_id):
        self._buttons.pop(button_id, None)

    def open(self, source_button=None):
        if not self._is_open_fn():
            result = self._run(lambda: self._open_from_source(source_button), context="toolbar window toggle open")
            self._reconcile_button_state()
            return result

    def close(self):
        if self._is_open_fn():
            result = self._run(self._close_fn, context="toolbar window toggle close")
            self._reconcile_button_state()
            return result

    def toggle(self, source_button=None):
        if self._is_open_fn():
            result = self._run(self._close_fn, context="toolbar window toggle close")
        else:
            result = self._run(lambda: self._open_from_source(source_button), context="toolbar window toggle open")
        self._reconcile_button_state()
        return result

    def _on_window_state_changed(self, is_open):
        for button_id, button in list(self._buttons.items()):
            if not wutil.is_valid_widget(button):
                self._buttons.pop(button_id, None)
                continue
            self._set_button_checked(button, is_open)


class WindowStateBus(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)


class FloatingToolWindowMixin:
    @staticmethod
    def _clamped_window_origin(x, y, width, height, screen_geometry):
        """Return a top-left position constrained to one screen's available area."""
        max_x = screen_geometry.right() - min(width, screen_geometry.width()) + 1
        max_y = screen_geometry.bottom() - min(height, screen_geometry.height()) + 1
        return QtCore.QPoint(
            max(screen_geometry.left(), min(x, max_x)),
            max(screen_geometry.top(), min(y, max_y)),
        )

    def _current_screen_geometry(self):
        if not wutil.is_valid_widget(self):
            return None
        frame_geo = self.frameGeometry()
        anchor = frame_geo.center() if frame_geo.isValid() else QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(anchor) or QtGui.QGuiApplication.primaryScreen()
        if not screen:
            return None
        return screen.availableGeometry()

    def clamp_to_screen(self, screen_geometry):
        if not wutil.is_valid_widget(self):
            return False
        if screen_geometry is None:
            return False

        width = min(self.width(), screen_geometry.width())
        height = min(self.height(), screen_geometry.height())
        position = self._clamped_window_origin(
            self.x(), self.y(), width, height, screen_geometry
        )

        if width != self.width() or height != self.height():
            self.setGeometry(position.x(), position.y(), width, height)
        else:
            self.move(position)
        return True

    def clamp_to_current_screen(self):
        return self.clamp_to_screen(self._current_screen_geometry())

    def move_above_toolbar_button(self, button=None, gap=None):
        """Move above a toolbar button without changing window visibility."""
        if not wutil.is_valid_widget(self):
            return False

        if not button or not wutil.is_valid_widget(button) or not button.isVisible():
            return False

        self.adjustSize()
        width = self.width()
        height = self.height()

        top_left = button.mapToGlobal(QtCore.QPoint(0, 0))
        button_rect = QtCore.QRect(top_left, button.size())
        anchor_point = button_rect.center()

        screen = QtGui.QGuiApplication.screenAt(anchor_point) or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return False
        geo = screen.availableGeometry()
        gap = FLOATING_TOOL_ANCHOR_GAP if gap is None else gap

        x = anchor_point.x() - width // 2
        y = button_rect.top() - height - gap

        if y < geo.top():
            y = button_rect.bottom() + gap

        position = self._clamped_window_origin(x, y, width, height, geo)
        self.move(position)
        return True

    def move_beside_cursor(self, gap=None):
        """Move beside the cursor, preferring its right side on the active screen."""
        if not wutil.is_valid_widget(self):
            return False

        self.adjustSize()
        width = self.width()
        height = self.height()
        cursor_position = QtGui.QCursor.pos()
        screen = (
            QtGui.QGuiApplication.screenAt(cursor_position)
            or QtGui.QGuiApplication.primaryScreen()
        )
        if screen is None:
            return False

        gap = FLOATING_TOOL_ANCHOR_GAP if gap is None else gap
        screen_geometry = screen.availableGeometry()
        x = cursor_position.x() + gap
        if x + width - 1 > screen_geometry.right():
            x = cursor_position.x() - width - gap
        y = cursor_position.y() - height // 2
        self.move(
            self._clamped_window_origin(
                x, y, width, height, screen_geometry
            )
        )
        return True

    def present_floating_window(self):
        """Show and focus a floating tool after its geometry has been resolved."""
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def present_above_toolbar_button(self, button=None, gap=None):
        """Present at a toolbar anchor, falling back to the cursor when unavailable."""
        placed = self.move_above_toolbar_button(button=button, gap=gap)
        if not placed:
            self.move_beside_cursor(gap=gap)
        self.present_floating_window()
        return placed

    def present_beside_cursor(self, gap=None):
        """Present beside the cursor using the shared screen-safe placement."""
        self.move_beside_cursor(gap=gap)
        return self.present_floating_window()

    def _init_floating_window_behavior(self):
        self._hovered = False
        self._auto_transparency = self._auto_transparency_setting_enabled()
        self.setProperty("tkm_floating_widget", True)
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_Hover, True)

        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._apply_transparency)

        self.settings_timer = QtCore.QTimer(self)
        self.settings_timer.timeout.connect(self._check_settings)
        self.settings_timer.start(500)

    def _auto_transparency_setting_enabled(self):
        raise NotImplementedError

    def _stays_on_top_setting_enabled(self):
        raise NotImplementedError

    def _geometry_settings_key(self):
        raise NotImplementedError

    def _geometry_settings_namespace(self):
        raise NotImplementedError

    def _save_geometry_setting(self):
        try:
            key = self._geometry_settings_key()
            namespace = self._geometry_settings_namespace()
        except NotImplementedError:
            return
        settings.set_setting(
            key,
            [self.pos().x(), self.pos().y(), self.width(), self.height()],
            namespace=namespace,
        )

    def _restore_saved_geometry(self):
        try:
            key = self._geometry_settings_key()
            namespace = self._geometry_settings_namespace()
        except NotImplementedError:
            return False
        saved_geom = settings.get_setting(
            key,
            namespace=namespace,
        )
        if not saved_geom:
            return False
        if len(saved_geom) == 4:
            x, y, width, height = saved_geom
            self.setGeometry(x, y, width, height)
        elif len(saved_geom) >= 2:
            self.move(saved_geom[0], saved_geom[1])
        self.clamp_to_current_screen()
        return True

    def _check_settings(self):
        new_state = self._auto_transparency_setting_enabled()
        if new_state != self._auto_transparency:
            self._auto_transparency = new_state
            self.update_transparency_state(self._hovered)

    def _apply_transparency(self):
        if self._hovered:
            return
        self.setWindowOpacity(0.45 if self._auto_transparency else 1.0)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update_transparency_state(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update_transparency_state(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.clamp_to_current_screen()
        if hasattr(self, "fade_timer"):
            self.update_transparency_state(self.rect().contains(self.mapFromGlobal(QtGui.QCursor.pos())))

    def update_transparency_state(self, hovered):
        if not hasattr(self, "fade_timer"):
            return
        self._hovered = hovered
        self.fade_timer.stop()
        if not self._auto_transparency:
            self.setWindowOpacity(1.0)
            return

        self.setWindowOpacity(0.80)
        if not hovered:
            self.fade_timer.start(800)

    def apply_stay_on_top_setting(self):
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, self._stays_on_top_setting_enabled())
        self.setGeometry(geometry)
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()

    def hideEvent(self, event):
        self._save_geometry_setting()
        super().hideEvent(event)
