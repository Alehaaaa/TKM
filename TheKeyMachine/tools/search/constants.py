"""Shared constants for the Search tool."""

SEARCH_WINDOW_KEY = "tkm_search_window"
SEARCH_SETTINGS_NAMESPACE = "search"
SEARCH_TEXT_KEY = "text"
# Kept for compatibility with integrations that imported the old persistent key.
# Search positions now live only in search.session_state.
SEARCH_POSITION_KEY = "position"
SEARCH_STAYS_ON_TOP_KEY = "stays_on_top"
