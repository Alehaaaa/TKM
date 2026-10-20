"""Search catalog, matching, session state, and background loading."""

import re

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.core.workers import BackgroundCallThread


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


# Positional ranking: compile the query as a case-insensitive regex and score
# every searchable term of a command with
#
#     100 / ((1 + match.start()) * (matched_length + 1))
#
# so an earlier, tighter match ranks higher -- an exact prefix of a short name
# wins, while a loose mid-string match still scores > 0 and stays discoverable.
# The score is spread across each row's title, command id, and explicit
# keyword/alias list (its "primary" terms), and falls back to help text at a
# heavily reduced weight so a tooltip-only hit never outranks a name hit.
# Multi-word queries require every token to match somewhere.

# Help-text matches are always ranked below any name/keyword match.
_SECONDARY_WEIGHT = 0.01


def _match_score(regex, text):
    """Positional score for one term; 0.0 when it does not match."""
    if not text:
        return 0.0
    match = regex.search(text)
    if match is None:
        return 0.0
    start = match.start()
    length = match.end() - match.start()
    return 100.0 / ((1 + start) * (length + 1))


def _primary_terms(row):
    """The high-signal strings a row is matched against: its name and aliases."""
    terms = []
    title = str(row.get("title") or "").strip()
    if title:
        terms.append(title)
    command = str(row.get("command") or "").strip()
    if command:
        # Command ids read as snake_case; score them as space-separated words
        # so "world space" matches "worldspace_to_local" the way a user types.
        terms.append(command.replace("_", " "))
    for keyword in row.get("keywords") or ():
        keyword = str(keyword).strip()
        if keyword:
            terms.append(keyword)
    return terms


def _score_row(row, token_regexes):
    """Combined score for *row*, or None if any query token matches nothing."""
    primary = _primary_terms(row)
    secondary = _searchable_tooltip_text(row)
    total = 0.0
    for regex in token_regexes:
        best = 0.0
        for term in primary:
            score = _match_score(regex, term)
            if score > best:
                best = score
        if best == 0.0 and secondary:
            best = _match_score(regex, secondary) * _SECONDARY_WEIGHT
        if best == 0.0:
            return None
        total += best
    return total


def match_score(row, text):
    """Public single-row score used by tests; None means the row is excluded."""
    query = normalize_query(text)
    if not query:
        return None
    token_regexes = [re.compile(re.escape(token), re.IGNORECASE) for token in query.split()]
    return _score_row(row, token_regexes) if token_regexes else None


def ranked_command_rows(rows, text):
    query = normalize_query(text)
    if not query:
        return []
    token_regexes = [re.compile(re.escape(token), re.IGNORECASE) for token in query.split()]
    if not token_regexes:
        return []

    # Very short queries tie many names at the same score, so sort those
    # buckets alphabetically; longer queries keep match order. Either way fall
    # back to catalog order so the result is stable.
    short_query = len(query) < 3
    scored = []
    for order, row in enumerate(rows):
        score = _score_row(row, token_regexes)
        if score is None:
            continue
        scored.append((score, order, row))

    if short_query:
        scored.sort(key=lambda entry: (-entry[0], str(entry[2].get("title") or "").lower(), entry[1]))
    else:
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [row for _score, _order, row in scored]


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
