"""Tool catalog and matching logic for Search."""

from __future__ import annotations


def build_command_rows():
    """Return unique commands from the catalog shared with the Hotkeys window."""
    from TheKeyMachine.mods import hotkeysMod

    sections, _titles, _icons = hotkeysMod._build_command_catalog()
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


def match_rank(row, query):
    """Return a relevance tier, or None when the row does not match."""
    title = str(row.get("title") or "")
    command = str(row.get("command") or "")
    title_lower = title.lower()
    command_lower = command.lower().replace("_", " ")
    if not query:
        return 0
    if title_lower.startswith(query):
        return 0
    if any(word.startswith(query) for word in title_lower.split()):
        return 1
    if query in title_lower:
        return 2
    if query in command_lower:
        return 3
    return None


def ranked_command_rows(rows, text):
    """Filter and rank command rows for the user's current text."""
    query = normalize_query(text)
    matches = []
    for row in rows:
        rank = match_rank(row, query)
        if rank is not None:
            matches.append((rank, row))
    # Python's sort is stable, so equal-relevance matches retain the catalog's
    # section, tool, variant, and slider-value order.
    matches.sort(key=lambda entry: entry[0])
    return [row for _rank, row in matches]


def completion_suffix(typed, title):
    """Return the untyped title suffix when the selection is a prefix match."""
    typed = str(typed)
    title = str(title)
    if typed and title.lower().startswith(typed.lower()):
        return title[len(typed):]
    return ""
