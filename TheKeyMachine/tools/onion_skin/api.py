"""Public window entry points, right-click menu builders, and auto-update for Onion Skin."""

from __future__ import absolute_import

from functools import partial

from maya import cmds  # type: ignore

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore

from TheKeyMachine.core import i18n, runtime, settings
from TheKeyMachine.maya import maya_api
from TheKeyMachine.tools import common as tool_common
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.onion_skin import controller, diagnostics
from TheKeyMachine.ui.widgets import util as wutil


_window_instance = None
window_bus = tool_common.WindowStateBus()
SETTINGS_NAMESPACE = controller.SETTINGS_NAMESPACE
STAYS_ON_TOP_KEY = "stays_on_top"
_AUTO_UPDATE_OPTION = "auto_update"
_PERFORMANCE_OPTION = "performance"
_CALLBACK_KEY = "onion_skin:auto_update"


def _t(text):
    return i18n.tr_text(text)


# Every profile bakes the same missing ghosts; they differ only in how
# eagerly they chase edits. Each capture pass jumps Maya's playhead to an
# uncached frame and forces a render, so "performance" here really means
# "how much of that playhead-jumping happens, how soon, and in how big a
# burst" -- Fast keeps bursts small and infrequent so scrubbing/dragging
# stays smooth; Full Accuracy clears the whole backlog in one pass.
PERFORMANCE_PROFILES = {
    "fast": {
        "label": "Fast",
        "description": "Refresh a couple of ghosts at a time and wait longer between passes, so interaction stays smooth.",
        "debounce_ms": 450,
        "batch_sizes": (2, 2),
        "pass_gap_ms": 220,
    },
    "balanced": {
        "label": "Balanced",
        "description": "Refresh nearby ghosts quickly, then catch up on the rest a moment later.",
        "debounce_ms": 180,
        "batch_sizes": (4, 6),
        "pass_gap_ms": 100,
    },
    "accurate": {
        "label": "Full Accuracy",
        "description": "Refresh every ghost immediately after each edit, even if it means more viewport churn.",
        "debounce_ms": 60,
        "batch_sizes": (999,),
        "pass_gap_ms": 0,
    },
}
PERFORMANCE_ORDER = ("fast", "balanced", "accurate")


def _window_class():
    from TheKeyMachine.tools.onion_skin.widgets import OnionSkinWindow

    return OnionSkinWindow


def _emit_window_state(is_open):
    state = bool(is_open)
    try:
        window_bus.stateChanged.emit(state)
    except Exception:
        pass
    runtime.get_runtime_manager().set_tool_state("onion_skin", state)


def is_stay_on_top():
    return bool(
        settings.get_setting(STAYS_ON_TOP_KEY, False, namespace=SETTINGS_NAMESPACE)
    )


def set_stay_on_top(enabled, *_args):
    enabled = bool(enabled)
    settings.set_setting(STAYS_ON_TOP_KEY, enabled, namespace=SETTINGS_NAMESPACE)
    window = get_window()
    if window and wutil.is_valid_widget(window):
        window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, enabled)
        window.show()
        window.raise_()
        window.activateWindow()
    return enabled


def _pick_pose_color(setting_key, title):
    current = controller.get_setting(setting_key)
    color = QtWidgets.QColorDialog.getColor(
        QtGui.QColor(*current),
        get_window(),
        title,
    )
    if not color.isValid():
        return current
    value = [color.red(), color.green(), color.blue()]
    controller.set_setting(setting_key, value, refresh_window=False)
    return value


def pick_past_color(*_args):
    return _pick_pose_color("past_color", "Choose Past Pose Color")


def pick_future_color(*_args):
    return _pick_pose_color("future_color", "Choose Future Pose Color")


def pick_held_color(*_args):
    return _pick_pose_color("absolute_color", "Choose Held Pose Color")


def get_window():
    global _window_instance
    if _window_instance and wutil.is_valid_widget(_window_instance):
        return _window_instance
    _window_instance = None
    return None


def is_window_open():
    window = get_window()
    return bool(window and window.isVisible())


def close_window():
    window = get_window()
    if window and wutil.is_valid_widget(window):
        window.close()
    _emit_window_state(False)


def show_window(reuse_existing=True, popup=False, anchor_button=None):
    global _window_instance
    window = get_window()
    if not (reuse_existing and window and wutil.is_valid_widget(window)):
        close_window()
        window = _window_class()(
            parent=wutil.get_maya_qt(qt=QtWidgets.QWidget),
            popup=popup,
        )
        created_window = window

        def _on_destroyed(*_args):
            global _window_instance
            if _window_instance is created_window:
                _window_instance = None
                _emit_window_state(False)

        window.destroyed.connect(_on_destroyed)
        _window_instance = window
        diagnostics.log("manager created", popup=popup)
    else:
        window.refresh()
        diagnostics.log("manager reused", popup=popup)

    window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, is_stay_on_top())
    if anchor_button and wutil.is_valid_widget(anchor_button):
        window.present_above_toolbar_button(anchor_button)
    elif popup:
        window.present_beside_cursor()
    else:
        window.present_floating_window()
    _emit_window_state(True)
    diagnostics.log("manager shown", popup=popup)
    return window


window_toggle = ToolbarWindowToggle(
    is_window_open,
    lambda anchor_button=None: show_window(
        reuse_existing=True,
        popup=False,
        anchor_button=anchor_button,
    ),
    close_window,
    window_bus.stateChanged,
    tool_id="onion_skin",
)


def bind_toolbar_button(button):
    # The section owns the single right click menu, just as it does for
    # Tracer. Attaching another custom context handler here causes Qt to open
    # a second menu after the first one closes.
    window_toggle.attach_button(button)
    return True


def toggle_window(checked=None, *_args):
    if isinstance(checked, bool):
        return show_window(reuse_existing=True, popup=False) if checked else close_window()
    return window_toggle.toggle()


def refresh_open_window():
    window = get_window()
    if window and wutil.is_valid_widget(window):
        window.refresh()


def show():
    return show_window(reuse_existing=True, popup=False)


def popup():
    return show_window(reuse_existing=True, popup=True)


def populate_nearby_frames_menu(menu, *_args):
    """Rebuild the Nearby Frames submenu -- what used to be the window's
    per-offset rows. Each offset is just an enable/disable setting here (no
    per-offset opacity slider, which is what a menu can't do well); the
    opacity fall-off is picked automatically -- see
    controller.relative_frame_default_opacity.
    """
    menu.clear()
    active = set(int(value) for value in controller.get_setting("relative_frames") or [])
    for offset in controller.NEARBY_FRAME_OFFSETS:
        distance = abs(offset)
        label = "{:+d} Frame{}".format(offset, "" if distance == 1 else "s")
        side = "before" if offset < 0 else "after"
        action = menu.addAction(
            _t(label),
            callback=partial(controller.set_relative_frame_enabled, offset),
            description=_t("Show the pose {} frame{} {} the current one.").format(
                distance, "" if distance == 1 else "s", side
            ),
        )
        action.setCheckable(True)
        action.setChecked(offset in active)
    return menu


# ---------------------------------------------------------------------------
# Auto-update: rebake stale ghosts on their own instead of only whichever
# frame the playhead happens to land on. Onion Skin's render override can
# only ever capture the frame Maya is *currently* evaluating (see
# renderer.OnionSkinRenderOverride.setup()), so "auto" here means this
# controller briefly jumps the playhead to each missing ghost frame, forces
# a capture, then restores it -- the same technique the manual "Refresh"
# button already used for just the current frame, just driven automatically
# and spread across a few frames at a time. See PERFORMANCE_PROFILES above
# for how the three speed settings trade off responsiveness against how
# quickly the whole set of ghosts catches up.
# ---------------------------------------------------------------------------


def get_performance():
    value = str(settings.get_setting(_PERFORMANCE_OPTION, "balanced", namespace=SETTINGS_NAMESPACE))
    return value if value in PERFORMANCE_PROFILES else "balanced"


def performance_choices():
    return [
        {
            "value": key,
            "label": PERFORMANCE_PROFILES[key]["label"],
            "description": PERFORMANCE_PROFILES[key]["description"],
        }
        for key in PERFORMANCE_ORDER
    ]


def set_performance(value, *_args):
    value = value if value in PERFORMANCE_PROFILES else "balanced"
    settings.set_setting(_PERFORMANCE_OPTION, value, namespace=SETTINGS_NAMESPACE)
    # This only changes how future edits get paced -- nothing already
    # cached went stale, so just catch up on whatever's still missing (e.g.
    # a backlog left over from a slower profile) at the new pace instead of
    # evicting and re-baking every ghost that's already fine. See
    # bake_missing_frames_now()'s own docstring for why that path, and not
    # OnionUpdateController.request_refresh(), is the right one here.
    bake_missing_frames_now()
    return value


def is_auto_update():
    return bool(settings.get_setting(_AUTO_UPDATE_OPTION, True, namespace=SETTINGS_NAMESPACE))


def set_auto_update(enabled, *_args):
    enabled = bool(enabled)
    settings.set_setting(_AUTO_UPDATE_OPTION, enabled, namespace=SETTINGS_NAMESPACE)
    sync_auto_update()
    return enabled


def sync_auto_update():
    """Start or stop the background updater to match settings + tool state.

    Called whenever the viewport override itself is switched on/off (see
    controller.set_enabled) and when the Auto Update checkbox changes, so
    the updater is never left running once nothing needs it.
    """
    if controller.is_enabled() and is_auto_update():
        get_update_controller().enable()
    else:
        existing = get_update_controller(create=False)
        if existing is not None:
            existing.disable()


def _bake_frames(renderer, frames):
    """Briefly visit each frame in *frames* so the renderer captures it, then return."""
    if not frames:
        return
    try:
        if cmds.play(query=True, state=True):
            # Baking means repeatedly jumping the playhead -- doing that
            # while Maya is actually playing back would fight the transport
            # and stutter it. Skip this pass; the next edit (or the next
            # scrub once playback stops) will ask again.
            return
    except Exception:
        pass
    original = maya_api.current_time()
    try:
        for frame in frames:
            try:
                cmds.currentTime(frame)
                cmds.refresh(force=True)
            except Exception as exc:
                diagnostics.log_error("auto update bake failed", exc, frame=frame)
    finally:
        if original is not None:
            try:
                cmds.currentTime(original)
                cmds.refresh(force=True)
            except Exception:
                pass


def bake_missing_frames_now():
    """Synchronously bake whatever ghosts the renderer is missing right now.

    Called after a settings or list change that only grows the *set* of
    needed frames -- adding or editing a held pose, toggling a nearby frame
    or Ghost In-Betweens, switching to Neighboring Key Poses, and so on.
    Nothing already cached went stale in these cases (that only happens on
    an actual pose edit -- see OnionUpdateController._on_edit), so this
    never evicts a single already-cached ghost; it just bakes whatever is
    new, immediately, the same direct way the manual Refresh button already
    bakes the current frame. Independent of the Auto Update setting and the
    background scheduler on purpose: this is one deliberate, discrete user
    action, not a stream of edits that needs debouncing, so it shouldn't
    silently no-op just because Auto Update happens to be off.
    """
    renderer = controller.get_renderer(create=False)
    if renderer is None or not controller.is_enabled():
        return
    missing = renderer.missing_required_frames()
    if missing:
        _bake_frames(renderer, missing)


class OnionUpdateController(QtCore.QObject):
    """Watches for pose edits and keeps the onion buffer caught up on its own."""

    def __init__(self, manager):
        super(OnionUpdateController, self).__init__(manager)
        self._manager = manager
        self._enabled = False
        self._generation = 0
        # The debounce/batch timing is the exact same shape Tracer's live
        # refresh needs, so both tools share one implementation -- see
        # tools.common.DebouncedBatchScheduler.
        self._scheduler = tool_common.DebouncedBatchScheduler(self)
        self._scheduler.stepReady.connect(self._apply_bake_pass, QtCore.Qt.QueuedConnection)

    def is_enabled(self):
        return self._enabled

    def enable(self):
        if self._enabled:
            return
        self._enabled = True
        if not self._scheduler.isRunning():
            self._scheduler.start()
        self._install_callbacks()

    def disable(self):
        if not self._enabled:
            return
        self._enabled = False
        self._manager.disconnect_callbacks(_CALLBACK_KEY)
        self._scheduler.cancel()

    def shutdown(self):
        self.disable()
        if self._scheduler.isRunning():
            self._scheduler.stop()
            self._scheduler.wait(1000)

    def _install_callbacks(self):
        self._manager.disconnect_callbacks(_CALLBACK_KEY)
        self._manager.add_anim_curve_edited_callback(self._on_edit, key=_CALLBACK_KEY)
        self._manager.connect_signal(
            self._manager.undo_performed, self._on_edit, key=_CALLBACK_KEY, unique=False,
        )

    def _on_edit(self, *_args):
        self.request_refresh()

    def request_refresh(self, immediate=False):
        if not self._enabled:
            return
        renderer = controller.get_renderer(create=False)
        if renderer is None or not controller.is_enabled():
            return
        # Drop the now-stale ghosts immediately so an old pose never lingers
        # on screen -- the scheduled passes below only fill in what is
        # missing, so a still-cached (but outdated) frame would otherwise
        # never get revisited.
        renderer.invalidate_required_frames()
        profile = PERFORMANCE_PROFILES[get_performance()]
        self._generation = self._scheduler.schedule(
            profile["debounce_ms"], profile["batch_sizes"], profile["pass_gap_ms"], immediate=immediate
        )

    @QtCore.Slot(int, int)
    def _apply_bake_pass(self, batch_size, generation):
        if not self._enabled or generation != self._generation:
            return
        renderer = controller.get_renderer(create=False)
        if renderer is None:
            return
        missing = renderer.missing_required_frames()
        if not missing:
            return
        _bake_frames(renderer, missing[: int(batch_size)])


_UPDATE_CONTROLLER = None


def get_update_controller(create=True):
    global _UPDATE_CONTROLLER
    if _UPDATE_CONTROLLER is None and create:
        _UPDATE_CONTROLLER = OnionUpdateController(runtime.get_runtime_manager())
    return _UPDATE_CONTROLLER


def cleanup():
    close_window()
    controller.shutdown_renderer()
    existing = get_update_controller(create=False)
    if existing is not None:
        existing.shutdown()
