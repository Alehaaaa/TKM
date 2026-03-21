import os
import json

from TheKeyMachine.mods.generalMod import USER_FOLDER_PATH


def get_preferences_file():
    scripts_dir = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data", "preferences")
    return os.path.join(scripts_dir, "user_preferences.json")


def get_setting(key, default_value=None):
    config_file = get_preferences_file()

    # Try reading new json format
    if os.path.isfile(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            return config.get(key, default_value)
        except Exception:
            pass

    return default_value


def set_setting(key, value):
    config_file = get_preferences_file()

    # Ensure directory exists
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    config = {}

    # Load from new format if exists
    if os.path.isfile(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except Exception:
            pass

    config[key] = value

    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
