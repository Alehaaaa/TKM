import json
import os
from typing import Dict, Iterable, Optional

from TheKeyMachine.core.application import USER_FOLDER_PATH

_PREFERENCES_ROOT = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data", "preferences")
_DEFAULT_FILENAME = "user_preferences.json"

# get_setting() is called from nearly every tool controller, often more than
# once per invocation (e.g. checking several preference keys), and every
# TKM toolbar click routes through tool_operation()/settings lookups. Without
# caching, every one of those calls re-reads and re-parses the whole
# preferences file from disk -- the "small lag on every click" users notice.
# Cache by mtime (a cheap stat) so repeated reads skip the file entirely
# until something on disk actually changes.
_FILE_CACHE: Dict[str, "tuple[Optional[float], Optional[Dict]]"] = {}


def _preferences_dir() -> str:
    """Return (and lazily create) the folder that stores preference json files."""
    os.makedirs(_PREFERENCES_ROOT, exist_ok=True)
    return _PREFERENCES_ROOT


def _normalize_namespace(namespace: Optional[str]) -> Optional[str]:
    if not namespace:
        return None
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(namespace))
    safe = safe.strip("_") or "preferences"
    return safe.lower()


def get_preferences_file(namespace: Optional[str] = None) -> str:
    directory = _preferences_dir()
    filename = _DEFAULT_FILENAME
    safe_namespace = _normalize_namespace(namespace)
    if safe_namespace:
        filename = f"{safe_namespace}.json"
    return os.path.join(directory, filename)


def _candidate_files(namespace: Optional[str]) -> Iterable[str]:
    yield get_preferences_file(namespace)


def _load_file(config_file: str) -> Optional[Dict]:
    try:
        mtime = os.path.getmtime(config_file)
    except OSError:
        _FILE_CACHE.pop(config_file, None)
        return None

    cached_mtime, cached_config = _FILE_CACHE.get(config_file, (None, None))
    if cached_config is not None and cached_mtime == mtime:
        return cached_config

    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except Exception:
        return None
    _FILE_CACHE[config_file] = (mtime, config)
    return config


def _store_cache(config_file: str, config: Dict) -> None:
    try:
        mtime = os.path.getmtime(config_file)
    except OSError:
        mtime = None
    _FILE_CACHE[config_file] = (mtime, config)


def get_setting(key: str, default_value=None, namespace: Optional[str] = None):
    for candidate in _candidate_files(namespace):
        config = _load_file(candidate)
        if config is None:
            continue
        if key in config:
            return config.get(key, default_value)
    return default_value


def set_setting(key: str, value, namespace: Optional[str] = None) -> None:
    set_settings({key: value}, namespace=namespace)


def set_settings(values: Dict[str, object], namespace: Optional[str] = None) -> None:
    """Persist several settings with a single preferences file update."""
    if not values:
        return
    config_file = get_preferences_file(namespace=namespace)
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    config = _load_file(config_file) or {}
    config.update(values)

    with open(config_file, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4, sort_keys=True)
    _store_cache(config_file, config)
