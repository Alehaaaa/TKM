"""Maya-session-only state for the Search tool."""

from TheKeyMachine.Qt import QtWidgets  # type: ignore


_POSITION_PROPERTY = "tkm_search_session_position"


def get_position():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None
    position = app.property(_POSITION_PROPERTY)
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        return int(position[0]), int(position[1])
    return None


def set_position(x, y):
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.setProperty(_POSITION_PROPERTY, [int(x), int(y)])


def clear_position():
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.setProperty(_POSITION_PROPERTY, None)
