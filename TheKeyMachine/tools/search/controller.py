"""Search catalog, matching, session state, and background loading."""

import re

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.ui.widgets.util import BackgroundCallThread


SEARCH_WINDOW_KEY = "tkm_search_window"
SEARCH_SETTINGS_NAMESPACE = "search"
SEARCH_TEXT_KEY = "text"
SEARCH_STAYS_ON_TOP_KEY = "stays_on_top"
_POSITION_PROPERTY = "tkm_search_session_position"


def build_command_rows():
    from TheKeyMachine.tools.hotkeys import controller as hotkeys

    sections, _titles, _icons = hotkeys._build_command_catalog()
    rows = []
    seen = set()
    for section in sections:
        for row in section.get("commands", []):
            command = row.get("command")
            if not command or command in seen:
                continue
            seen.add(command)
            rows.append(dict(row))
    return rows


def normalize_query(text):
    return " ".join(str(text).lower().split())


def _searchable_tooltip_text(row):
    """Return the user-facing help text attached to a command row."""
    values = [row.get("description")]
    tooltip = row.get("tooltip")
    if tooltip:
        values.extend(
            (
                getattr(tooltip, "title", ""),
                getattr(tooltip, "first_line", ""),
                tooltip,
            )
        )

    # Most registered tooltips are Tooltip string subclasses, while custom
    # tools can still provide small HTML/XML fragments. Removing tags makes
    # both forms searchable by the words a user actually sees.
    combined = " ".join(str(value) for value in values if value)
    return normalize_query(re.sub(r"<[^>]+>", " ", combined))


def match_rank(row, query):
    title = str(row.get("title") or "")
    command = str(row.get("command") or "")
    title_lower = title.lower()
    command_lower = command.lower().replace("_", " ")
    if not query or title_lower.startswith(query):
        return 0
    if any(word.startswith(query) for word in title_lower.split()):
        return 1
    if query in title_lower:
        return 2
    if query in command_lower:
        return 3
    if query in _searchable_tooltip_text(row):
        return 4
    return None


def ranked_command_rows(rows, text):
    query = normalize_query(text)
    matches = []
    for row in rows:
        rank = match_rank(row, query)
        if rank is not None:
            matches.append((rank, row))
    matches.sort(key=lambda entry: entry[0])
    return [row for _rank, row in matches]


def completion_suffix(typed, title):
    typed = str(typed)
    title = str(title)
    if typed and title.lower().startswith(typed.lower()):
        return title[len(typed):]
    return ""


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


class SearchCatalogThread(BackgroundCallThread):
    def __init__(self, parent=None):
        super().__init__(build_command_rows, parent=parent)
