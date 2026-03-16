import os

from TheKeyMachine.mods.generalMod import USER_FOLDER_PATH

def get_preferences_file():
    scripts_dir = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data", "preferences")
    return os.path.join(scripts_dir, "user_preferences.py")

def get_setting(key, default_value=None):
    config_file = get_preferences_file()
    if os.path.isfile(config_file):
        config = {}
        try:
            with open(config_file, "r") as f:
                content = f.read()
            exec(compile(content, config_file, "exec"), config)
            return config.get(key, default_value)
        except Exception:
            return default_value
    return default_value

def set_setting(key, value):
    config_file = get_preferences_file()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    # Create file if it doesn't exist
    if not os.path.isfile(config_file):
        with open(config_file, "w") as f:
            f.write(f'{key} = {repr(value)}\n')
        return

    # Update existing file
    with open(config_file, "r") as f:
        config_data = f.read()

    new_data = ""
    key_set = False

    for line in config_data.split("\n"):
        if line.strip().startswith(f"{key} ") or line.strip().startswith(f"{key}="):
            new_data += f'{key} = {repr(value)}\n'
            key_set = True
        else:
            new_data += line + "\n"

    if not key_set:
        new_data += f'{key} = {repr(value)}\n'

    # Clean duplicate trailing newlines
    while new_data.endswith("\n\n"):
        new_data = new_data[:-1]

    with open(config_file, "w") as f:
        f.write(new_data)
