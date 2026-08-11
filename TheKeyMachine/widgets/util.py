import maya.cmds as cmds
import maya.OpenMayaUI as omui

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtGui, QtWidgets

from TheKeyMachine.data import icons

def DPI(val):
    return omui.MQtUtil.dpiScale(val)


def DPR(val):
    screen = QtWidgets.QApplication.primaryScreen()
    return val * screen.devicePixelRatio()


def get_screen_resolution():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    screen = app.primaryScreen()
    if screen is None:
        screens = QtGui.QGuiApplication.screens()
        screen = screens[0] if screens else None
    if screen is None:
        return 0, 0

    screen_rect = screen.geometry()
    return screen_rect.width(), screen_rect.height()


def get_maya_qt(ptr=None, qt=QtWidgets.QMainWindow):
    if ptr is None:
        ptr = omui.MQtUtil.mainWindow()
    return QtCompat.wrapInstance(int(ptr), qt)


def get_maya_window_size():
    maya_main_window = get_maya_qt()
    return maya_main_window.width(), maya_main_window.height()


def get_maya_window_geometry():
    maya_main_window = get_maya_qt()
    return maya_main_window.geometry()


def get_control_widget(name, qt_type=QtWidgets.QWidget):
    ptr = omui.MQtUtil.findControl(name)
    if ptr:
        return QtCompat.wrapInstance(int(ptr), qt_type)
    return None


def is_valid_widget(widget, expected_type=None):
    if widget is None:
        return False
    if expected_type is not None and not isinstance(widget, expected_type):
        return False
    try:
        if QtCompat.isValid(widget):
            return True
    except Exception:
        pass
    return False


def event_global_pos(event):
    """Return a mouse event's global integer position across Qt 5 and Qt 6."""
    for method_name in ("globalPosition", "globalPos", "screenPos"):
        method = getattr(event, method_name, None)
        if not callable(method):
            continue
        position = method()
        to_point = getattr(position, "toPoint", None)
        return to_point() if callable(to_point) else position
    return QtGui.QCursor.pos()


def check_visible_layout(layout):
    try:
        try:
            s = cmds.workspaceControl(layout, q=True, visible=True) and not cmds.workspaceControl(layout, q=True, collapse=True)
        except Exception:
            s = cmds.window(layout, q=True, visible=True)
    except Exception:
        s = False
    return s



class BackgroundCallThread(QtCore.QThread):
    """Run a zero-arg callable off the Qt main thread and emit its result.

    Some data a window needs to open (Search and the Hotkeys editor both
    build a catalog of every declared tool, shortcut, and setting) is pure
    Python with no Maya API calls, but walking the whole toolbox is
    perceptible enough that building it synchronously on Maya's main thread
    would visibly hang the UI. Pass the build function in and run it here
    instead of hand-rolling another one-off QThread subclass per caller.
    """

    loaded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            self.loaded.emit(self._func())
        except Exception as exc:
            self.failed.emit(str(exc))


def sync_choice_group_button(registry, group_id, button, parent=None):
    """Put *button* in the exclusive button group for *group_id*, in *registry*.

    A "choice" setting (Bake's tangent mode, Share Keys' Keep Anim Curve
    Shape, the Preferences alignment picker, ...) renders as one checkable
    row per value wherever a command list can show more than one at once --
    the Hotkeys editor's per-section command list and Search's results
    list. Left as plain independent checkboxes, checking one value's row
    would not visually uncheck its sibling rows for the same setting, since
    nothing re-queries them. core.toolMenus.build_declared_menu already
    solves this for the live dropdown with a QActionGroup; this gives every
    other list of these rows the same mutual exclusion via Qt's button-group
    equivalent, keyed by each row's "choice_group" (the setting's own id) so
    unrelated choices sharing one list -- e.g. the Dock section's position
    and area pickers -- never end up in the same group.

    *registry* is a plain ``{group_id: QButtonGroup}`` dict the caller owns
    and resets (to ``{}``) whenever its list is cleared and rebuilt, since a
    QButtonGroup has no way to forget its previous members on its own.
    """
    if not group_id or button is None:
        return
    group = registry.get(group_id)
    if group is None:
        group = QtWidgets.QButtonGroup(parent)
        group.setExclusive(True)
        registry[group_id] = group
    group.addButton(button)


def checkable_row_indicator_style(object_name, radio=False):
    """QSS for a command-list row's leading checkable indicator.

    Shared by the Hotkeys editor's ``HotkeyCommandItemWidget`` and Search's
    ``SearchResultItemWidget`` so their checkable rows stay visually
    identical everywhere the same kind of row appears, using the same dark
    border/fill language as every other checkable control in the app.
    ``make_row_check_control`` below picks this apart from the un-styled
    OS default: Maya's own native theming leaves an un-styled
    ``QRadioButton`` with no visible border against this app's dark
    background (unlike the live dropdown menu's ``QActionGroup`` bullets,
    which Maya itself already renders with a visible ring), so a "choice"
    setting's rows need this explicit round styling as much as a plain
    boolean row needs the square one.
    """
    size = DPI(11)
    if radio:
        # Qt's stylesheet gradients on a compound button's ::indicator
        # (QCheckBox/QRadioButton) are positioned against the *control's*
        # own rect, not the smaller indicator sub-rect the border/
        # border-radius are drawn in -- so as long as the control is wider
        # or taller than its indicator (ours was: a 15x22/15x18 click
        # target around an 11x11 indicator), the gradient's center drifts
        # off the border's center. make_row_check_control below fixes a
        # radio control's own size to exactly this indicator size so both
        # are the same box and the gradient can't drift from the border.
        radius = size / 2.0
        return (
            "#{name}{{background:transparent;spacing:0px;}}"
            "#{name}::indicator{{width:{size}px;height:{size}px;border:1px solid #626262;"
            "border-radius:{radius}px;background:#262626;}}"
            "#{name}::indicator:hover{{border-color:#7d7d7d;background:#303030;}}"
            "#{name}::indicator:checked{{border-color:#9a9a9a;"
            "background:qradialgradient(cx:0.5,cy:0.5,radius:0.5,fx:0.5,fy:0.5,"
            "stop:0 #eeeeee,stop:0.5 #eeeeee,stop:0.58 #363636,stop:1 #363636);}}"
        ).format(name=object_name, size=size, radius=radius)
    return (
        "#{name}{{background:transparent;spacing:0px;}}"
        "#{name}::indicator{{width:{size}px;height:{size}px;border:1px solid #626262;"
        "border-radius:{radius}px;background:#262626;}}"
        "#{name}::indicator:hover{{border-color:#7d7d7d;background:#303030;}}"
        "#{name}::indicator:checked{{image:url({icon});border-color:#7d7d7d;background:#363636;}}"
    ).format(name=object_name, size=size, radius=DPI(3), icon=icons.apply)


def make_row_check_control(parent, object_name, radio=False):
    """Build the leading checkable control for a command-list row.

    Shared by the Hotkeys editor's ``HotkeyCommandItemWidget`` and Search's
    ``SearchResultItemWidget``. A plain boolean setting ("Start with Maya")
    gets a ``QCheckBox``. A row expanded from one value of a "choice"
    setting (see ``mods.hotkeysMod._tool_choice_setting_rows`` and
    ``sync_choice_group_button`` above -- callers pass ``radio=True`` when
    the row carries a "choice_group") gets a real ``QRadioButton`` instead
    of a checkbox stylesheet-hacked into looking like one, so it's the
    semantically correct exclusive-choice control, styled to match this
    app's own dark theme via ``checkable_row_indicator_style`` above --
    the same treatment ``core.toolMenus.build_declared_menu``'s
    ``QActionGroup`` gets for free from Maya's own menu rendering.

    A radio control is also fixed to a small square around its indicator's
    own size here (see the note in ``checkable_row_indicator_style`` about
    why a much looser click target throws its checked-state gradient
    off-center) -- callers keep sizing the plain ``QCheckBox`` case
    themselves, unchanged. The square keeps a couple of pixels of margin
    around the indicator on every side: sized to exactly the indicator's
    own box, the ring's own border was getting clipped by the control's
    edge, since the style reserves a little native paint margin around a
    radio indicator beyond what its CSS width/height declares. That margin
    is even on all four sides, so it can't reintroduce the off-center
    gradient a lopsided box (the original 15x22 control around an 11x11
    indicator) caused.
    """
    control = QtWidgets.QRadioButton(parent) if radio else QtWidgets.QCheckBox(parent)
    control.setObjectName(object_name)
    control.setStyleSheet(checkable_row_indicator_style(object_name, radio=radio))
    if radio:
        control_size = DPI(11) + DPI(4)
        control.setFixedSize(control_size, control_size)
    return control


def bind_choice_row_state(control, choice_group, choice_value):
    """Keep *control* synced to a "choice" setting's live value, not just its own click.

    A choice row's checkbox/radio already reads the true value once, at
    construction (``get_checked`` -- see ``mods.hotkeysMod._tool_choice_setting_rows``),
    so a freshly built list (Search reopened, a Hotkeys section re-entered)
    is always correct without this. What that snapshot can't do is react
    live: pick a different value through the real dropdown menu, a hotkey,
    or another row for the same setting while a list built earlier is still
    on screen, and every *other* row for that setting needs to notice.

    ``core.toolbox.apply_choice_value`` publishes the setting's new value
    under its choice id via ``runtimeManager.set_control_state`` every time
    it actually applies one -- from any of those paths, since they all
    funnel through that one function. This subscribes *control* to that
    same channel via ``tools.common.bind_control_state`` (the app's existing
    generic "shared control state" pub/sub) and flips it checked only when
    the published value matches *choice_value*, so every row for one choice
    setting -- across Search, the Hotkeys editor, and any future list of
    them -- stays live in sync with exactly one publish per apply, no
    per-surface refresh logic anywhere.
    """
    if control is None or not choice_group:
        return None
    from TheKeyMachine.tools import common as toolCommon

    def _apply(value, target=control, want=choice_value):
        toolCommon.set_checked_safely(target, value == want)

    return toolCommon.bind_control_state(control, choice_group, _apply)


def make_inViewMessage(message, icon=None):

    if not icon:
        icon = icons.TheKeyMachine_icon
    else:
        icon = icons.get(icon, icons.path(icon))
    if not icon:
        icon = ""

    from TheKeyMachine.core import i18n
    message = i18n.tr_text(message)

    cmds.inViewMessage(
        amg='<div style="text-align:center"><img src="' + icon + '">\n\n' + message + "\n\n\n",
        pos="midCenter",
        a=0.9,
        fade=True,
        fst=1000,
    )
