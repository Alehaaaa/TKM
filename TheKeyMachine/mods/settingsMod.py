import json
import os
from typing import Dict, Iterable, Optional

from TheKeyMachine.mods.generalMod import USER_FOLDER_PATH

_PREFERENCES_ROOT = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data", "preferences")
_DEFAULT_FILENAME = "user_preferences.json"
_LEGACY_FILENAME = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data", "user_preferences.json")


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
    """Ordered list of files to inspect when reading."""
    primary = get_preferences_file(namespace)
    yield primary

    # When working inside a namespace, fall back to the shared file (old behavior) and legacy path.
    if namespace:
        yield os.path.join(_preferences_dir(), _DEFAULT_FILENAME)
        yield _LEGACY_FILENAME
    else:
        yield _LEGACY_FILENAME


def _load_file(config_file: str) -> Optional[Dict]:
    if not os.path.isfile(config_file):
        return None
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def get_setting(key: str, default_value=None, namespace: Optional[str] = None):
    for candidate in _candidate_files(namespace):
        config = _load_file(candidate)
        if config is None:
            continue
        if key in config:
            return config.get(key, default_value)
    return default_value


def set_setting(key: str, value, namespace: Optional[str] = None) -> None:
    config_file = get_preferences_file(namespace=namespace)
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    config = _load_file(config_file) or {}
    config[key] = value

    with open(config_file, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4, sort_keys=True)
