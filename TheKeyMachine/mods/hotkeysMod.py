"""
Managed hotkey UI and hotkey helpers for TheKeyMachine trigger commands.
"""

from __future__ import annotations

import json
import os

from maya import cmds

from TheKeyMachine.Qt import QtCompat, QtCore, QtGui, QtWidgets  # type: ignore

import TheKeyMachine.core.runtimeManager as runtime
import TheKeyMachine.core.toolbox as toolbox
import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.mods.generalMod as general
from TheKeyMachine.data import icons
from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import customDialogs as cd
from TheKeyMachine.widgets import util as wutil


HOTKEYS_WINDOW_KEY = "tkm_hotkeys_window"
HOTKEYS_EXPORT_DIR = os.path.join(general.USER_FOLDER_PATH, "TheKeyMachine_user_data", "tools", "hotkeys")
HOTKEY_COMMAND_PREFIX = "TKMTriggerName_"
STATUS_REFRESH_DELAY_MS = 100
COMMAND_BATCH_SIZE = 18
SHIFTED_SYMBOL_BASE_KEYS = {
    "_": "-",
    "+": "=",
    "?": "/",
    "|": "\\",
    ":": ";",
    '"': "'",
    "<": ",",
    ">": ".",
    "{": "[",
    "}": "]",
    "~": "`",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
}
SHIFTED_SYMBOL_BY_BASE_KEY = {base: symbol for symbol, base in SHIFTED_SYMBOL_BASE_KEYS.items()}
KEY_TEXT_ALIASES = {
    "space": "Space",
    "tab": "Tab",
    "enter": "Enter",
    "return": "Enter",
    "escape": "Escape",
    "esc": "Escape",
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "page up": "PageUp",
    "pagedown": "PageDown",
    "page down": "PageDown",
    "insert": "Insert",
    "ins": "Insert",
    "delete": "Delete",
    "del": "Delete",
    "backspace": "Backspace",
    "comma": ",",
    "period": ".",
    "dot": ".",
    "minus": "-",
    "dash": "-",
    "hyphen": "-",
    "underscore": "_",
    "plus": "+",
    "equals": "=",
    "equal": "=",
    "slash": "/",
    "backslash": "\\",
    "semicolon": ";",
    "colon": ":",
    "apostrophe": "'",
    "quote": '"',
    "doublequote": '"',
    "bracketleft": "[",
    "leftbracket": "[",
    "bracketright": "]",
    "rightbracket": "]",
    "braceleft": "{",
    "leftbrace": "{",
    "braceright": "}",
    "rightbrace": "}",
    "grave": "`",
    "backtick": "`",
    "tilde": "~",
}
PRINTABLE_KEY_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`-=[]\\;',./~!@#$%^&*()_+{}|:\"<>?")
SHORTCUT_DISPLAY_KEY_ALIASES = {
    "+": "Plus",
}



def _ensure_hotkey_folder():
    folder = HOTKEYS_EXPORT_DIR
    os.makedirs(folder, exist_ok=True)
    return folder





def _combo_from_assign_command_key_string(key_string):
    if not key_string or len(key_string) < 7:
        return None
    key = key_string[0]
    if not key or key == "NONE":
        return None
    return _combo_from_maya_flags(
        str(key).upper() if len(str(key)) == 1 else str(key),
        ctrl=key_string[2] == "1",
        shift=key_string[6] == "1",
        alt=key_string[1] == "1",
    )


def _is_tkm_name_command(name):
    return bool(name and str(name).startswith(HOTKEY_COMMAND_PREFIX))


def _command_from_name_command(name):
    if not _is_tkm_name_command(name):
        return None
    return str(name).replace(HOTKEY_COMMAND_PREFIX, "", 1)


def _iter_mapping_combos(mapping):
    for command_name, shortcuts in (mapping or {}).items():
        if not shortcuts:
            continue
        shortcut = shortcuts[0]
        if shortcut and _combo_from_shortcut(shortcut):
            yield command_name, shortcut


def _copy_hotkey_mapping(mapping):
    return {name: [shortcut] for name, shortcut in _iter_mapping_combos(mapping)}


def _combo_owners(mapping):
    owners = {}
    for command_name, combo in _iter_mapping_combos(mapping):
        owners.setdefault(_combo_key(combo), []).append(command_name)
    return owners


def _duplicate_combo_owners(mapping):
    return {ckey: names for ckey, names in _combo_owners(mapping).items() if len(names) > 1}


def _iter_assign_command_entries():
    for index in range(1, (cmds.assignCommand(query=True, numElements=True) or 0) + 1):
        try:
            name = cmds.assignCommand(index, query=True, name=True)
            key_string = cmds.assignCommand(index, query=True, keyString=True)
        except Exception:
            continue
        combo = _combo_from_assign_command_key_string(key_string)
        if name and combo:
            yield str(name), _shortcut_from_combo(combo)


def _assign_command_owners():
    owners = {}
    for name, combo in _iter_assign_command_entries():
        owners.setdefault(_combo_key(combo), []).append(name)
    return owners


def _load_hotkeys_from_maya():
    mapping = {}
    stale_assignments = []

    for name, combo in _iter_assign_command_entries():
        command_name = _command_from_name_command(name)
        if not command_name:
            continue
        if not trigger.has_command(command_name):
            stale_assignments.append(combo)
            continue
        mapping.setdefault(command_name, [])
        if _combo_key(combo) not in {_combo_key(existing) for existing in mapping[command_name]}:
            mapping[command_name].append(combo)

    if stale_assignments:
        _clear_stale_hotkey_assignments(stale_assignments)

    return _copy_hotkey_mapping(mapping)


def shortcut_for_command(command_name):
    shortcuts = _load_hotkeys_from_maya().get(command_name) or []
    return shortcuts[0] if shortcuts else ""


def _hotkey_mapping_from_data(data):
    mapping = {}
    if not isinstance(data, dict):
        return mapping
    for name, shortcuts in data.items():
        command_name = str(name)
        if not trigger.has_command(command_name):
            continue
        if isinstance(shortcuts, str):
            shortcuts = [shortcuts]
        if not isinstance(shortcuts, list) or not shortcuts:
            continue
        shortcuts = [shortcut for shortcut in shortcuts if isinstance(shortcut, str) and _combo_from_shortcut(shortcut)]
        if shortcuts:
            mapping[command_name] = [shortcuts[0]]
    return mapping


def _hotkey_mapping_to_data(mapping):
    data = {}
    for command_name, shortcuts in mapping.items():
        if not shortcuts:
            continue
        data[command_name] = shortcuts[0]
    return data


def _save_hotkeys_to_maya():
    try:
        cmds.hotkey(autoSave=True)
    except Exception:
        pass


def _name_command_name(command_name):
    return "{}{}".format(HOTKEY_COMMAND_PREFIX, command_name)


def _mel_python_command(command):
    escaped = str(command).replace("\\", "\\\\").replace('"', '\\"')
    return 'python("{}")'.format(escaped)


def _humanize(name):
    return str(name).replace("_", " ").strip().title()


def _slider_value_suffix(value):
    if value < 0:
        return "neg{}".format(abs(value))
    return str(value)


def _slider_value_label(value):
    if value > 0:
        return "+{}%".format(value)
    return "{}%".format(value)


def _shortcut_mask(shortcut):
    keys = shortcut.get("keys")
    if keys == "Click":
        return 0
    if not isinstance(keys, (list, tuple)):
        return None

    mask = 0
    if QtCore.Qt.Key_Shift in keys:
        mask |= 1
    if QtCore.Qt.Key_Control in keys:
        mask |= 4
    if QtCore.Qt.Key_Alt in keys:
        mask |= 8
    return mask


def _normalize_combo(combo):
    if not combo:
        return None
    if isinstance(combo, str):
        return _combo_from_shortcut(combo)
    key = combo.get("key")
    if not key:
        return None
    key = str(key).upper() if len(str(key)) == 1 and str(key).isalpha() else str(key)
    shift = bool(combo.get("shift"))
    if key in SHIFTED_SYMBOL_BASE_KEYS:
        shift = False
    return {
        "key": key,
        "ctrl": bool(combo.get("ctrl")),
        "shift": shift,
        "alt": bool(combo.get("alt")),
    }


def _combo_from_maya_flags(key, ctrl=False, shift=False, alt=False):
    key = str(key or "")
    if shift and key in SHIFTED_SYMBOL_BY_BASE_KEY:
        return _normalize_combo(
            {
                "key": SHIFTED_SYMBOL_BY_BASE_KEY[key],
                "ctrl": ctrl,
                "shift": False,
                "alt": alt,
            }
        )
    return _normalize_combo({"key": key, "ctrl": ctrl, "shift": shift, "alt": alt})


def _shortcut_from_combo(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return ""
    parts = []
    key = combo.get("key", "")
    if combo.get("ctrl"):
        parts.append("Ctrl")
    if combo.get("shift"):
        parts.append("Shift")
    if combo.get("alt"):
        parts.append("Alt")
    parts.append(SHORTCUT_DISPLAY_KEY_ALIASES.get(key, key))
    return "+".join(part for part in parts if part)


def _combo_from_shortcut(shortcut):
    if isinstance(shortcut, dict):
        return _normalize_combo(shortcut)
    if not isinstance(shortcut, str):
        return None
    parts = [part.strip() for part in shortcut.split("+") if part.strip()]
    if not parts:
        return None

    key_text = parts[-1]
    modifiers = {part.lower() for part in parts[:-1]}
    ctrl_aliases = {"control", "ctrl", "ctl"}
    shift_aliases = {"shift"}
    alt_aliases = {"alt", "option"}
    known_modifiers = ctrl_aliases | shift_aliases | alt_aliases
    if any(modifier not in known_modifiers for modifier in modifiers):
        return None

    lower_key = key_text.lower()
    if len(key_text) == 1 and key_text.isalpha():
        key = key_text.upper()
    elif len(key_text) == 1 and key_text.isdigit():
        key = key_text
    elif len(key_text) == 1 and key_text in PRINTABLE_KEY_CHARS:
        key = key_text
    elif lower_key in KEY_TEXT_ALIASES:
        key = KEY_TEXT_ALIASES[lower_key]
    elif lower_key.startswith("f") and lower_key[1:].isdigit() and 1 <= int(lower_key[1:]) <= 12:
        key = "F{}".format(int(lower_key[1:]))
    else:
        return None

    return _combo_from_maya_flags(
        key,
        ctrl=bool(modifiers & ctrl_aliases),
        shift=bool(modifiers & shift_aliases),
        alt=bool(modifiers & alt_aliases),
    )


def _combo_key(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return ""
    return "{}|{}|{}|{}".format(
        _maya_key_shortcut(combo),
        int(combo["ctrl"]),
        int(_maya_shift_required(combo)),
        int(combo["alt"]),
    )


def _maya_key_shortcut(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return ""
    key = str(combo.get("key") or "")
    if key in SHIFTED_SYMBOL_BASE_KEYS:
        return SHIFTED_SYMBOL_BASE_KEYS[key]
    if len(key) == 1 and key.isalpha():
        return key.lower()
    return key


def _maya_shift_required(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return False
    return bool(combo.get("shift")) or str(combo.get("key") or "") in SHIFTED_SYMBOL_BASE_KEYS


def _maya_key_shortcut_candidates(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return []
    display_key = str(combo.get("key") or "")
    candidates = [_maya_key_shortcut(combo), display_key, SHIFTED_SYMBOL_BASE_KEYS.get(display_key)]
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _hotkey_flag_kwargs(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return {}
    return {
        "keyShortcut": _maya_key_shortcut(combo),
        "alt": bool(combo.get("alt")),
        "ctl": bool(combo.get("ctrl")),
        "sht": _maya_shift_required(combo),
    }


def _text_badge_qicon(text, size=18):
    pixmap = QtGui.QPixmap(wutil.DPI(size + 8), wutil.DPI(size))
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtGui.QColor("#d0d0d0"))
    font = QtGui.QFont()
    font.setBold(True)
    font.setPixelSize(wutil.DPI(10))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, text or "")
    painter.end()
    return QtGui.QIcon(pixmap)


def _scaled_icon(path, size=10):
    dim = wutil.DPI(size)
    pixmap = QtGui.QIcon(path).pixmap(dim, dim)
    return QtGui.QIcon(pixmap)


def _first_assignment_result(result):
    if not result:
        return None
    if isinstance(result, (list, tuple)):
        for item in result:
            value = _first_assignment_result(item)
            if value:
                return value
        return None
    return str(result)


def _query_hotkey_assignment(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return None
    for key_shortcut in _maya_key_shortcut_candidates(combo):
        flags = _hotkey_flag_kwargs(combo)
        flags["keyShortcut"] = key_shortcut
        for query_flag in ("name", "releaseName"):
            try:
                kwargs = dict(flags)
                kwargs.update({"query": True, query_flag: True})
                result = _first_assignment_result(cmds.hotkey(**kwargs))
                if result:
                    return result
            except Exception:
                continue
    return None


def _query_hotkey_check_assignment(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return None
    modifier_kwargs = {
        "altModifier": bool(combo.get("alt")),
        "ctrlModifier": bool(combo.get("ctrl")),
        "shiftModifier": _maya_shift_required(combo),
    }
    for key_shortcut in _maya_key_shortcut_candidates(combo):
        try:
            result = _first_assignment_result(cmds.hotkeyCheck(keyString=key_shortcut, **modifier_kwargs))
            if result:
                return result
        except Exception:
            continue
    return None


def _query_current_name_command(combo):
    """
    Queries Maya to find which command (if any) is assigned to the given combo.
    """
    combo = _normalize_combo(combo)
    if not combo:
        return None
    return _query_hotkey_assignment(combo) or _query_hotkey_check_assignment(combo)


def _clear_hotkey(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return
    flags = _hotkey_flag_kwargs(combo)
    for command_flag in ("name", "releaseName"):
        try:
            kwargs = dict(flags)
            kwargs[command_flag] = ""
            cmds.hotkey(**kwargs)
        except Exception:
            pass


def _ensure_name_command_binding(command_name, title):
    name_command = _name_command_name(command_name)
    command = _mel_python_command(trigger.command_string(command_name))
    try:
        cmds.nameCommand(name_command, edit=True, annotation=title, command=command)
    except Exception:
        cmds.nameCommand(name_command, annotation=title, command=command)
    return name_command


def _assign_hotkey(command_name, title, combo):
    combo = _normalize_combo(combo)
    if not combo:
        return
    name_command = _ensure_name_command_binding(command_name, title)
    kwargs = _hotkey_flag_kwargs(combo)
    kwargs["name"] = name_command
    cmds.hotkey(**kwargs)


def _ensure_writable_hotkey_set():
    current_set = cmds.hotkeySet(q=True, current=True)
    if current_set != "Maya_Default":
        return None

    all_sets = cmds.hotkeySet(q=True, hotkeySetArray=True)
    user_sets = [s for s in all_sets if s != "Maya_Default"]
    if user_sets:
        cmds.hotkeySet(user_sets[0], edit=True, current=True)
    else:
        new_set = "TheKeyMachine_Hotkeys"
        cmds.hotkeySet(new_set, source="Maya_Default")
        cmds.hotkeySet(new_set, edit=True, current=True)
    return cmds.hotkeySet(q=True, current=True)


def _clear_hotkey_mapping(mapping):
    for _command_name, combo in _iter_mapping_combos(mapping):
        _clear_hotkey(combo)


def _assign_hotkey_mapping(mapping, title_lookup):
    for command_name, combo in _iter_mapping_combos(mapping):
        title = title_lookup.get(command_name, _humanize(command_name))
        _clear_hotkey(combo)
        _assign_hotkey(command_name, title, combo)





def _clear_stale_hotkey_assignments(stale_assignments):
    for combo in stale_assignments:
        _clear_hotkey(combo)
    _save_hotkeys_to_maya()


def _qt_key_constant(name):
    return getattr(QtCore.Qt, name, None)


def _qt_special_key_map():
    pairs = [
        ("Key_Space", "Space"),
        ("Key_Tab", "Tab"),
        ("Key_Return", "Enter"),
        ("Key_Enter", "Enter"),
        ("Key_Escape", "Escape"),
        ("Key_Left", "Left"),
        ("Key_Right", "Right"),
        ("Key_Up", "Up"),
        ("Key_Down", "Down"),
        ("Key_Home", "Home"),
        ("Key_End", "End"),
        ("Key_PageUp", "PageUp"),
        ("Key_PageDown", "PageDown"),
        ("Key_Insert", "Insert"),
        ("Key_Backspace", "Backspace"),
        ("Key_Delete", "Delete"),
        ("Key_Minus", "-"),
        ("Key_Underscore", "_"),
        ("Key_Equal", "="),
        ("Key_Plus", "+"),
        ("Key_Slash", "/"),
        ("Key_Question", "?"),
        ("Key_Backslash", "\\"),
        ("Key_Bar", "|"),
        ("Key_BracketLeft", "["),
        ("Key_BraceLeft", "{"),
        ("Key_BracketRight", "]"),
        ("Key_BraceRight", "}"),
        ("Key_Semicolon", ";"),
        ("Key_Colon", ":"),
        ("Key_Apostrophe", "'"),
        ("Key_QuoteDbl", '"'),
        ("Key_Comma", ","),
        ("Key_Less", "<"),
        ("Key_Period", "."),
        ("Key_Greater", ">"),
        ("Key_QuoteLeft", "`"),
        ("Key_AsciiTilde", "~"),
    ]
    return {key: text for key_name, text in pairs for key in [_qt_key_constant(key_name)] if key is not None}


def _qt_key_to_combo(event):
    key = event.key()
    modifiers = event.modifiers()
    if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
        return None
    if key in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete):
        return {}

    letter_map = {getattr(QtCore.Qt, "Key_{}".format(chr(code))): chr(code) for code in range(ord("A"), ord("Z") + 1)}
    digit_map = {getattr(QtCore.Qt, "Key_{}".format(num)): str(num) for num in range(10)}
    special_map = _qt_special_key_map()
    typed_text = event.text() if hasattr(event, "text") else ""

    if typed_text and len(typed_text) == 1 and typed_text in PRINTABLE_KEY_CHARS and not typed_text.isalnum():
        key_text = typed_text
    elif key in letter_map:
        key_text = letter_map[key]
    elif typed_text and len(typed_text) == 1 and typed_text in PRINTABLE_KEY_CHARS:
        key_text = typed_text.upper() if typed_text.isalpha() else typed_text
    elif key in digit_map:
        key_text = digit_map[key]
    elif QtCore.Qt.Key_F1 <= key <= QtCore.Qt.Key_F12:
        key_text = "F{}".format(key - QtCore.Qt.Key_F1 + 1)
    elif key in special_map:
        key_text = special_map[key]
    else:
        return None

    return _normalize_combo(
        {
            "key": key_text,
            "ctrl": bool(modifiers & QtCore.Qt.ControlModifier),
            "shift": bool(modifiers & QtCore.Qt.ShiftModifier),
            "alt": bool(modifiers & QtCore.Qt.AltModifier),
        }
    )


def _tooltip_for_assignment(name_command, title_lookup):
    if not name_command:
        return ""
    command_name = _command_from_name_command(name_command)
    if command_name:
        return title_lookup.get(command_name, command_name)
    return str(name_command)


def _assignment_tooltip_data(name_command, title_lookup, icon_lookup):
    if not name_command:
        return None
    description = "Hotkey Conflict.<br>If you Apply changes, it will overwrite this hotkey."
    command_name = _command_from_name_command(name_command)
    if command_name:
        return {"text": title_lookup.get(command_name, command_name), "description": description, "icon": icon_lookup.get(command_name)}
    return {"text": str(name_command), "description": description, "icon": ":/mayaIcon.png"}


def _status_tooltip_html(tooltip_data):
    if not tooltip_data:
        return ""
    icon = tooltip_data.get("icon")
    title = tooltip_data.get("text", "")
    description = tooltip_data.get("description", "")
    icon_row = "<tr><td align='left'><img src='{}' width='32' height='32'></td></tr>".format(icon) if icon else ""
    title_row = "<tr><td align='left' style='padding-top:2px;'><span style='font-size:10pt;'><b>{}</b></span></td></tr>".format(title) if title else ""
    body_row = "<tr><td align='left' style='padding-top:10px;'>{}</td></tr>".format(description) if description else ""
    return "<table cellspacing='0' cellpadding='0'>{}{}{}</table>".format(icon_row, title_row, body_row)


def _tool_data_for_command(command_name):
    if not command_name:
        return {}
    try:
        return toolbox.get_tool(command_name)
    except Exception:
        return {}


def _command_row_from_data(command_name, primary_data, fallback_data=None, title_override=None):
    if not command_name:
        return None
    primary_data = primary_data or {}
    fallback_data = fallback_data or {}
    icon = primary_data.get("icon") or fallback_data.get("icon")
    title = (
        title_override
        or primary_data.get("status_title")
        or primary_data.get("label")
        or fallback_data.get("status_title")
        or fallback_data.get("label")
        or fallback_data.get("description")
        or _humanize(command_name)
    )
    return {
        "command": command_name,
        "command_id": command_name,
        "command_label": title,
        "command_icon": icon,
        "title": title,
        "icon": icon,
        "badge_text": None if icon else primary_data.get("text") or fallback_data.get("text"),
        "description": (
            primary_data.get("status_description")
            or primary_data.get("description")
            or fallback_data.get("status_description")
            or fallback_data.get("description")
        ),
        "tooltip_template": (
            primary_data.get("tooltip_template")
            or fallback_data.get("tooltip_template")
        ),
        "shortcuts": primary_data.get("shortcuts", fallback_data.get("shortcuts", [])),
        "checkable": bool(primary_data.get("checkable", primary_data.get("type") == "check")),
        "callback": primary_data.get("callback") or fallback_data.get("callback"),
        "get_checked": (
            primary_data.get("get_checked")
            or primary_data.get("get_checked_fn")
            or fallback_data.get("get_checked")
            or fallback_data.get("get_checked_fn")
        ),
        "set_checked": (
            primary_data.get("set_checked")
            or primary_data.get("set_checked_fn")
            or fallback_data.get("set_checked")
            or fallback_data.get("set_checked_fn")
        ),
        "changed_signal": primary_data.get("changed_signal") or fallback_data.get("changed_signal"),
        "bind_checked_fn": primary_data.get("bind_checked_fn") or fallback_data.get("bind_checked_fn"),
        "state_key": primary_data.get("state_key") or fallback_data.get("state_key"),
    }


def _tool_command_row(tool_data):
    command_name = tool_data.get("key") or tool_data.get("id")
    return _command_row_from_data(command_name, _tool_data_for_command(command_name) or tool_data, fallback_data=tool_data)


def _variant_command_row(tool_data, variant, shortcut_label=None):
    command_name = variant.get("key") or variant.get("id")
    exact_data = _tool_data_for_command(command_name)
    fallback_data = dict(tool_data or {})
    fallback_data.update(variant or {})
    return _command_row_from_data(
        command_name,
        exact_data or variant,
        fallback_data=fallback_data,
        title_override=shortcut_label,
    )


def _append_section_row(section, seen, title_lookup, icon_lookup, trigger_commands, row):
    if not row:
        return
    command_name = row.get("command")
    if not command_name or command_name in seen:
        return
    if command_name not in trigger_commands and not trigger.has_command(command_name):
        return
    trigger_commands.add(command_name)
    section["commands"].append(row)
    seen.add(command_name)
    title_lookup[command_name] = row["title"]
    icon_lookup[command_name] = row.get("icon")


def _append_section_tool_rows(section, seen, title_lookup, icon_lookup, trigger_commands, tool_id):
    tool_data = toolbox.get_tool(tool_id)
    if tool_data.get("pinnable") is False:
        return
    _append_section_row(section, seen, title_lookup, icon_lookup, trigger_commands, _tool_command_row(tool_data))
    shortcut_labels_by_mask = {}
    for shortcut in tool_data.get("shortcuts", [])[1:]:
        shortcut_mask = _shortcut_mask(shortcut)
        if shortcut_mask is None:
            continue
        shortcut_labels_by_mask[shortcut_mask] = shortcut.get("label")

    for variant in tool_data.get("shortcut_variants", []):
        shortcut_label = shortcut_labels_by_mask.get(int(variant.get("mask", -1)))
        _append_section_row(
            section,
            seen,
            title_lookup,
            icon_lookup,
            trigger_commands,
            _variant_command_row(tool_data, variant, shortcut_label=shortcut_label),
        )


def _append_toolbox_item_rows(section, seen, title_lookup, icon_lookup, trigger_commands, item):
    if item == "separator":
        return

    if isinstance(item, dict) and item.get("group"):
        group = toolbox.get_tool_section(item["group"], resolve_items=False)
        if group:
            for group_item in group.get("items", []):
                _append_toolbox_item_rows(section, seen, title_lookup, icon_lookup, trigger_commands, group_item)
        return

    if isinstance(item, dict) and item.get("section"):
        child_section = toolbox.get_tool_section(item["section"], resolve_items=False)
        if child_section:
            for child_item in child_section.get("items", []):
                _append_toolbox_item_rows(section, seen, title_lookup, icon_lookup, trigger_commands, child_item)
        return

    if not isinstance(item, dict):
        return

    item_key = item.get("key") or item.get("id")
    if item_key:
        _append_section_tool_rows(section, seen, title_lookup, icon_lookup, trigger_commands, item_key)
        return

    if item.get("type") == "widget":
        tool_key = item.get("key") or item.get("id")
        if tool_key and tool_key in toolbox.TOOL_DEFINITIONS:
            _append_section_tool_rows(section, seen, title_lookup, icon_lookup, trigger_commands, tool_key)
        return


def _slider_modes_from_section(section_data):
    modes_attr = section_data.get("modes_attr")
    if not modes_attr:
        return []
    sliders_module = __import__("TheKeyMachine.sliders", fromlist=[modes_attr])
    return getattr(sliders_module, modes_attr, [])


def _slider_mode_icon(mode):
    icon = mode.get("icon")
    if isinstance(icon, str) and os.path.splitext(icon)[1]:
        return icon
    return None


def _iter_slider_percentage_rows(slider_type, mode):
    mode_icon = _slider_mode_icon(mode)
    mode_badge = str(mode.get("icon") or "")

    for value in trigger.SLIDER_BUTTON_VALUES:
        value_title = mode["label"] if int(value) == 0 else "{} {}".format(mode["label"], _slider_value_label(value))
        yield {
            "command": "slider_{}_{}_{}".format(slider_type, mode["key"], _slider_value_suffix(value)),
            "title": value_title,
            "icon": mode_icon,
            "badge_text": None if mode_icon else mode_badge,
        }


def _append_slider_mode_rows(section, slider_type, mode):
    if not isinstance(mode, dict) or not mode.get("key"):
        return

    mode_icon = _slider_mode_icon(mode)
    if not section["icon"] and mode_icon:
        section["icon"] = mode_icon

    for row in _iter_slider_percentage_rows(slider_type, mode):
        section["commands"].append(row)


def _build_slider_hotkey_section(section_id, section_data):
    slider_type = section_data.get("slider_type") or section_id.split("_", 1)[0]
    section = {
        "id": section_id,
        "title": section_data.get("label", _humanize(section_id)),
        "icon": toolbox.get_section_icon(section_id),
        "commands": [],
    }
    modes = _slider_modes_from_section(section_data)
    for mode in modes:
        _append_slider_mode_rows(section, slider_type, mode)
    return section


def _iter_hotkey_tool_sections():
    seen = set()

    for section_id, section_data in toolbox.TOOL_SECTION_DEFINITIONS.items():
        if section_data.get("hotkey_only") and section_data.get("hotkeys") is not False:
            seen.add(section_id)
            yield section_id, section_data

    for layout_id in ("main", "graph"):
        for section_data in toolbox.get_toolbar_sections(layout_id, resolve_items=False):
            section_id = section_data.get("id")
            if section_id in seen:
                continue
            if not section_data or section_data.get("hotkeys") is False:
                continue
            seen.add(section_id)
            yield section_id, section_data


def _build_command_catalog():
    trigger_commands = set(trigger.list_commands())
    title_lookup = {}
    icon_lookup = {}
    sections = []

    for section_id, section_data in _iter_hotkey_tool_sections():
        if section_data.get("type") == "slider":
            section = _build_slider_hotkey_section(section_id, section_data)
        else:
            section = {
                "id": section_id,
                "title": section_data.get("label") or _humanize(section_id),
                "icon": toolbox.get_section_icon(section_id),
                "commands": [],
            }
            seen = set()

            for item in section_data.get("items", []):
                _append_toolbox_item_rows(section, seen, title_lookup, icon_lookup, trigger_commands, item)

        filtered = [row for row in section["commands"] if row["command"] in trigger_commands]
        if not filtered:
            continue
        section["commands"] = filtered
        if not section.get("icon"):
            section["icon"] = next((row.get("icon") for row in filtered if row.get("icon")), None)
        sections.append(section)
        for row in filtered:
            title_lookup[row["command"]] = row["title"]
            icon_lookup[row["command"]] = row.get("icon")

    return sections, title_lookup, icon_lookup


class HotkeyStatusResolver(object):
    def __init__(self, draft_mapping, title_lookup, icon_lookup):
        self.draft_mapping = _copy_hotkey_mapping(draft_mapping)
        self.title_lookup = title_lookup
        self.icon_lookup = icon_lookup
        self.maya_hotkeys = _load_hotkeys_from_maya()
        self.draft_combo_owners = _combo_owners(self.draft_mapping)
        self.assign_command_owners = _assign_command_owners()
        self.external_cache = {}

    def status_for(self, command_name, combo):
        combo = _shortcut_from_combo(combo) if combo else None
        if not combo:
            return None, "", None

        ckey = _combo_key(combo)
        duplicate_names = self.draft_combo_owners.get(ckey, [])
        if len(duplicate_names) > 1:
            others = [self.title_lookup.get(name, name) for name in duplicate_names if name != command_name]
            return (
                icons.warning,
                "Also used by {}".format(", ".join(others)),
                {
                    "text": ", ".join(others),
                    "description": "Draft Conflict.<br>This combination is used by multiple tools in your current changes.",
                    "icon": icons.warning,
                },
            )

        applied_combos = self.maya_hotkeys.get(command_name) or []
        if any(_combo_key(applied) == ckey for applied in applied_combos):
            return icons.success, "Hotkey applied and active.", None

        current_assignment = self._external_assignment(combo, ckey)
        current_tkm_assignment = _command_from_name_command(current_assignment)
        if current_assignment and current_tkm_assignment != command_name:
            return (
                icons.warning,
                "Assigned to {}".format(_tooltip_for_assignment(current_assignment, self.title_lookup)),
                _assignment_tooltip_data(current_assignment, self.title_lookup, self.icon_lookup),
            )

        return None, "", None

    def _external_assignment(self, combo, ckey):
        assignment = self._assign_command_assignment(ckey)
        if assignment:
            return assignment
        if ckey not in self.external_cache:
            self.external_cache[ckey] = _query_current_name_command(combo)
        return self.external_cache[ckey]

    def _assign_command_assignment(self, ckey):
        for assignment in self.assign_command_owners.get(ckey, []):
            command_name = _command_from_name_command(assignment)
            if command_name in self.draft_mapping:
                continue
            return assignment
        return None


class HotkeyCaptureEdit(QtWidgets.QLineEdit):
    comboChanged = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._combo = None
        self._updating = False
        self.setPlaceholderText("Type a hotkey")
        self.setReadOnly(False)
        self.setFixedWidth(wutil.DPI(120))
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.setCursor(QtCore.Qt.IBeamCursor)
        self.setCursorPosition(0)
        self._clear_button = QtWidgets.QToolButton(self)
        self._clear_button.setObjectName("HotkeyCaptureClearButton")
        self._clear_button.setAutoRaise(True)
        self._clear_button.setCursor(QtCore.Qt.ArrowCursor)
        self._clear_button.setIcon(_scaled_icon(icons.close, 14))
        self._clear_button.setIconSize(QtCore.QSize(wutil.DPI(14), wutil.DPI(14)))
        self._clear_button.setFixedSize(wutil.DPI(14), wutil.DPI(14))
        self._clear_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self._clear_button.setStyleSheet(
            "#HotkeyCaptureClearButton{background:transparent;border:none;padding:0px;margin:0px;}"
            "#HotkeyCaptureClearButton:hover{background:rgba(255,255,255,0.08);border-radius:%spx;}"
            % wutil.DPI(3)
        )
        self._clear_button.clicked.connect(self.clear_hotkey)
        self._set_clear_button_visible(False)
        self.textChanged.connect(self._on_text_changed)
        self._position_clear_button()

    def _position_clear_button(self):
        button = getattr(self, "_clear_button", None)
        if not button:
            return
        margin = wutil.DPI(3)
        x = self.width() - button.width() - margin
        y = max(0, int((self.height() - button.height()) / 2))
        button.move(x, y)

    def _set_clear_button_visible(self, visible):
        button = getattr(self, "_clear_button", None)
        try:
            if button is not None and QtCompat.isValid(button):
                button.setVisible(bool(visible))
        except RuntimeError:
            self._clear_button = None

    def _on_text_changed(self, text):
        self._set_clear_button_visible(bool(text))
        if self._updating or text:
            return
        if self._combo is None:
            return
        self._combo = None
        self.comboChanged.emit(None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_clear_button()

    def clear_hotkey(self):
        self.setCombo(None)
        self.comboChanged.emit(None)

    def combo(self):
        return self._combo

    def setCombo(self, combo):
        self._updating = True
        try:
            self._combo = _shortcut_from_combo(combo) if combo else None
            self.setText(self._combo or "")
            self.setCursorPosition(len(self.text()))
        finally:
            self._updating = False

    def keyPressEvent(self, event):
        combo = _qt_key_to_combo(event)
        if combo == {}:
            self.clear_hotkey()
            event.accept()
            return
        if combo is None:
            event.accept()
            return
        shortcut = _shortcut_from_combo(combo)
        self.setCombo(shortcut)
        self.comboChanged.emit(self.combo())
        event.accept()


class HotkeySelectableItemWidget(QtWidgets.QWidget):
    clicked = QtCore.Signal()

    def __init__(self, parent=None, base_color=None, selected_color=None):
        super().__init__(parent)
        self._selected = False
        self.setObjectName("HotkeySelectableItemWidget")
        self.setProperty("rowSelected", False)
        self.setProperty("rowBase", base_color or "#2b2b2b")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#HotkeySelectableItemWidget{background:%s;}"
            "#HotkeySelectableItemWidget[rowSelected='true']{background:%s;}"
            % ((base_color or "#2b2b2b"), (selected_color or base_color or "#2b2b2b"))
        )

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("rowSelected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._selected:
            return
        option = QtWidgets.QStyleOptionFocusRect()
        option.initFrom(self)
        option.rect = self.rect()
        option.state |= QtWidgets.QStyle.State_HasFocus
        keyboard_focus = getattr(QtWidgets.QStyle, "State_KeyboardFocusChange", None)
        if keyboard_focus is not None:
            option.state |= keyboard_focus
        option.backgroundColor = self.palette().color(QtGui.QPalette.Window)
        painter = QtGui.QPainter(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_FrameFocusRect, option, painter, self)


class HotkeySectionItemWidget(HotkeySelectableItemWidget):
    def __init__(self, section, row_index=0, parent=None):
        super().__init__(
            parent,
            base_color="#2b2b2b" if row_index % 2 == 0 else "#2e2e2e",
            selected_color="#5f88a8",
        )
        self.section_id = section["id"]

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(10), 0)
        layout.setSpacing(wutil.DPI(8))

        icon_label = QtWidgets.QLabel(self)
        icon_label.setFixedSize(wutil.DPI(43), wutil.DPI(43))
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        if section.get("icon"):
            icon_label.setPixmap(QtGui.QIcon(section.get("icon")).pixmap(wutil.DPI(43), wutil.DPI(43)))
        layout.addWidget(icon_label)

        self.title_label = QtWidgets.QLabel(section["title"], self)
        self.title_label.setObjectName("HotkeySectionTitle")
        self.title_label.setStyleSheet("#HotkeySectionTitle{background:transparent;color:#d0d0d0;font-size:%spx;}" % wutil.DPI(11))
        layout.addWidget(self.title_label, 1)
        for watched in (icon_label, self.title_label):
            watched.installEventFilter(self)

    def set_selected(self, selected):
        super().set_selected(selected)
        self.title_label.setStyleSheet(
            "#HotkeySectionTitle{background:transparent;color:%s;font-size:%spx;}"
            % ("#ffffff" if selected else "#d0d0d0", wutil.DPI(11))
        )

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.clicked.emit()
        return super().eventFilter(watched, event)


class HotkeyCommandItemWidget(HotkeySelectableItemWidget):
    comboChanged = QtCore.Signal(str, object)
    requestSelect = QtCore.Signal(str)
    invokeRequested = QtCore.Signal(str)
    TITLE_STYLESHEET = (
        "QPushButton#HotkeyCommandTitle{background:transparent;border:none;border-radius:0px;color:#d0d0d0;font-size:%spx;text-align:left;padding:0px %spx;}"
        "QPushButton#HotkeyCommandTitle:pressed{background-color:#1f1f1f;border:none;border-radius:0px;}"
    )

    def __init__(self, command_data, row_index=0, parent=None):
        super().__init__(parent, base_color="#2b2b2b" if row_index % 2 == 0 else "#2e2e2e")
        self.command_data = command_data
        self._hovered = False
        self._tooltip_source_key = "hotkey-row:{}".format(self.command_name())

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(8), 0, wutil.DPI(8), 0)
        layout.setSpacing(wutil.DPI(5))

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setFixedSize(wutil.DPI(22), wutil.DPI(22))
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_path = command_data.get("icon")
        if icon_path:
            self.icon_label.setPixmap(QtGui.QIcon(icon_path).pixmap(wutil.DPI(20), wutil.DPI(20)))
        elif command_data.get("badge_text"):
            self.icon_label.setPixmap(_text_badge_qicon(command_data.get("badge_text")).pixmap(wutil.DPI(20), wutil.DPI(20)))
        layout.addWidget(self.icon_label, 0)

        self.check_box = None
        if command_data.get("checkable"):
            self.check_box = QtWidgets.QCheckBox(self)
            self.check_box.setObjectName("HotkeyCommandCheckBox")
            self.check_box.setFixedSize(wutil.DPI(15), wutil.DPI(22))
            self.check_box.setFocusPolicy(QtCore.Qt.NoFocus)
            self.check_box.setStyleSheet(
                "#HotkeyCommandCheckBox{background:transparent;spacing:0px;}"
                "#HotkeyCommandCheckBox::indicator{width:%spx;height:%spx;border:1px solid #626262;border-radius:%spx;background:#262626;}"
                "#HotkeyCommandCheckBox::indicator:hover{border-color:#7d7d7d;background:#303030;}"
                "#HotkeyCommandCheckBox::indicator:checked{image:url(%s);border-color:#7d7d7d;background:#363636;}"
                % (wutil.DPI(11), wutil.DPI(11), wutil.DPI(3), icons.apply)
            )
            callback = self.command_data.get("callback") or trigger.get_command(self.command_name())
            toolCommon.connect_tool_control(
                self.check_box,
                (lambda *_args, cb=callback: cb()) if callable(callback) else None,
                checkable=True,
                getter=self._check_state_getter(),
                setter=self.command_data.get("set_checked"),
                state_key=self.command_data.get("state_key"),
            )
            layout.addWidget(self.check_box, 0)
            layout.setSpacing(wutil.DPI(5))

        self.hotkey_button = QtWidgets.QPushButton(command_data["title"], self)
        self.hotkey_button.setFlat(True)
        self.hotkey_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.hotkey_button.setObjectName("HotkeyCommandTitle")
        self.hotkey_button.setStyleSheet(self.TITLE_STYLESHEET % (wutil.DPI(12), wutil.DPI(6)))
        self.hotkey_button.setMinimumHeight(wutil.DPI(22))
        self.hotkey_button.clicked.connect(lambda: self.invokeRequested.emit(self.command_name()))
        layout.addWidget(self.hotkey_button, 1)

        self.status_label = QtWidgets.QLabel(self)
        self.status_label.setObjectName("HotkeyStatusIcon")
        self.status_label.setFixedWidth(wutil.DPI(28))
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.edit = HotkeyCaptureEdit(self)
        self._style_edit(self.edit)
        self.edit.comboChanged.connect(lambda value: self.comboChanged.emit(self.command_name(), value))
        layout.addWidget(self.edit, 0)

        self.clicked.connect(lambda: self.requestSelect.emit(self.command_name()))
        for watched in self._selection_targets():
            watched.setMouseTracking(True)
            watched.installEventFilter(self)

    def command_name(self):
        return self.command_data["command"]

    def _check_state_getter(self):
        getter = self.command_data.get("get_checked")
        return getter if callable(getter) else None

    def combos(self):
        combo = self.combo()
        return [combo] if combo else []

    def combo(self):
        return self.edit.combo()

    def _style_edit(self, edit):
        edit.setObjectName("HotkeyCaptureField")
        edit.setMinimumHeight(wutil.DPI(22))
        edit.setStyleSheet(
            "#HotkeyCaptureField{background:#282828;border-radius:%spx;color:#bdbdbd;padding:%spx %spx;padding-right:%spx;}"
            "#HotkeyCaptureField:focus{background:#bdbdbd;color:#282828;}"
            % (wutil.DPI(6), wutil.DPI(3), wutil.DPI(6), wutil.DPI(16))
        )

    def setCombos(self, combos):
        combos = combos or []
        self.edit.setCombo(combos[0] if combos else None)

    def setCombo(self, combo):
        self.edit.setCombo(combo)

    def set_status(self, icon=None, tooltip="", tooltip_data=None):
        self.status_label.setPixmap(QtGui.QIcon(icon).pixmap(wutil.DPI(20), wutil.DPI(20)) if icon else QtGui.QPixmap())
        self.status_label.setToolTip(_status_tooltip_html(tooltip_data) if tooltip_data else (tooltip or ""))

    def set_selected(self, selected):
        super().set_selected(selected)
        self.hotkey_button.setStyleSheet(self.TITLE_STYLESHEET % (wutil.DPI(12), wutil.DPI(6)))

    def _hover_targets(self):
        return (self.hotkey_button,)

    def _selection_targets(self):
        targets = [self.hotkey_button, self.icon_label, self.status_label, self.edit]
        if self.check_box is not None:
            targets.append(self.check_box)
        return tuple(targets)

    def _set_hovered(self, hovered):
        hovered = bool(hovered)
        if self._hovered == hovered:
            return
        self._hovered = hovered

    def _contains_cursor(self):
        button = getattr(self, "hotkey_button", None)
        if not button or not wutil.is_valid_widget(button):
            return False
        return QtCore.QRect(button.mapToGlobal(QtCore.QPoint(0, 0)), button.size()).contains(QtGui.QCursor.pos())

    def _tooltip_data(self):
        return {
            "text": self.command_data.get("title"),
            "description": self.command_data.get("description"),
            "shortcuts": self.command_data.get("shortcuts", []),
            "tooltip_template": self.command_data.get("tooltip_template"),
            "icon": self.command_data.get("icon"),
            "command_id": self.command_data.get("command_id") or self.command_name(),
            "command_label": self.command_data.get("command_label") or self.command_data.get("title"),
            "command_icon": self.command_data.get("command_icon") or self.command_data.get("icon"),
        }

    def _show_tooltip(self):
        if not QFlatTooltipManager.enabled:
            return
        data = self._tooltip_data()
        if not (data.get("text") or data.get("description") or data.get("tooltip_template")):
            return
        if QFlatTooltipManager.is_current_source(self._tooltip_source_key):
            return
        QFlatTooltipManager.hide()
        QFlatTooltipManager.delayed_show(
            anchor_widget=self.hotkey_button,
            source_key=self._tooltip_source_key,
            target_pos=QtGui.QCursor.pos,
            **data
        )

    def _refresh_hover_state(self):
        if self._contains_cursor():
            return
        self._set_hovered(False)
        if QFlatTooltipManager.is_current_source(self._tooltip_source_key):
            QFlatTooltipManager.hide()

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        QtCore.QTimer.singleShot(0, self._refresh_hover_state)
        super().leaveEvent(event)

    def eventFilter(self, watched, event):
        if watched in self._selection_targets() and event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.FocusIn):
            self.requestSelect.emit(self.command_name())
        if watched in self._hover_targets():
            if event.type() == QtCore.QEvent.Enter:
                self._set_hovered(True)
                self._show_tooltip()
            elif event.type() == QtCore.QEvent.Leave:
                QtCore.QTimer.singleShot(0, self._refresh_hover_state)
        return super().eventFilter(watched, event)


class HotkeyItemList(QtWidgets.QListWidget):
    pass


class TriggerHotkeysDialog(cd.QFlatToolBarWindowDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("TheKeyMachine Hotkeys")
        self.resize(wutil.DPI(980), wutil.DPI(720))

        self._initialize_state()
        main = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setSpacing(wutil.DPI(8))
        self.addWindowHeader(
            parentLayout=main_layout,
            icon=icons.hotkeys,
            text="Hotkeys",
            textColor="#d8d8d8",
        )

        content_layout = self._build_content(main)
        main_layout.addLayout(content_layout, 1)
        self.root_layout.insertWidget(0, main, 1)
        self._populate_sections()
        self._build_bottom_bar()

    def _initialize_state(self):
        self._sections, self._title_lookup, self._icon_lookup = _build_command_catalog()
        self._section_lookup = {section["id"]: section for section in self._sections}
        self._stored_mapping = _load_hotkeys_from_maya()
        self._draft_mapping = _copy_hotkey_mapping(self._stored_mapping)
        self._section_views = {}
        self._current_section_id = None
        self._pending_section_id = None
        self._pending_commands = []
        self._pending_row_index = 0
        self._batched_build = False
        self._pending_view = None
        self._allow_close = False
        self._close_prompt_open = False
        self._build_timer = QtCore.QTimer(self)
        self._build_timer.setSingleShot(True)
        self._build_timer.timeout.connect(self._populate_next_batch)

    def _build_content(self, parent):
        content_layout = QtWidgets.QGridLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setHorizontalSpacing(wutil.DPI(12))
        content_layout.setVerticalSpacing(wutil.DPI(8))
        content_layout.setColumnStretch(0, 0)
        content_layout.setColumnStretch(1, 1)
        content_layout.setRowStretch(1, 1)

        left_widget = self._build_section_panel(parent)
        right_widget = self._build_command_panel(parent)
        self.tools_title = QtWidgets.QLabel("Tools", parent)
        self.tools_title.setObjectName("HotkeyToolsTitle")
        self.tools_title.setStyleSheet("#HotkeyToolsTitle{color:#bcbcbc;font-size:%spx;}" % wutil.DPI(11))
        self.section_title = QtWidgets.QLabel("Hotkeys", parent)
        self.section_title.setObjectName("HotkeySectionHeader")
        self.section_title.setStyleSheet("#HotkeySectionHeader{color:#bcbcbc;font-size:%spx;}" % wutil.DPI(11))

        content_layout.addWidget(self.tools_title, 0, 0)
        content_layout.addWidget(self.section_title, 0, 1)
        content_layout.addWidget(left_widget, 1, 0)
        content_layout.addWidget(right_widget, 1, 1)
        return content_layout

    def _build_section_panel(self, parent):
        widget = QtWidgets.QWidget(parent)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.section_list = HotkeyItemList(widget)
        self.section_list.setObjectName("HotkeySectionList")
        self.section_list.setMinimumWidth(wutil.DPI(240))
        self.section_list.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.section_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        palette = self.section_list.palette()
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#5f88a8"))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
        self.section_list.setPalette(palette)
        self.section_list.setStyleSheet(
            "#HotkeySectionList{background:#2d2d2d;border:1px solid #3a3a3a;color:#d0d0d0;}"
            "#HotkeySectionList::item{margin:0px;padding:0px;border:none;}"
            "#HotkeySectionList::item:selected{margin:0px;padding:0px;border:none;}"
        )
        self.section_list.currentItemChanged.connect(self._on_section_changed)
        layout.addWidget(self.section_list, 1)
        return widget

    def _build_command_panel(self, parent):
        widget = QtWidgets.QWidget(parent)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.command_stack = QtWidgets.QStackedWidget(widget)
        self.command_stack.setObjectName("HotkeyCommandStack")
        self.command_stack.setStyleSheet("#HotkeyCommandStack{background:transparent;}")
        layout.addWidget(self.command_stack, 1)
        return widget

    def _build_bottom_bar(self):
        self.setBottomBar(
            buttons=[
                cd.QFlatDialogButton("Import Hotkeys", callback=self.import_hotkeys, icon=icons.get('import')),
                cd.QFlatDialogButton("Export Hotkeys", callback=self.export_hotkeys, icon=icons.get('export')),
                cd.QFlatDialogButton("Clear TKM Hotkeys", callback=self.clear_hotkeys, icon=icons.trash),
                cd.QFlatDialogButton("Apply", callback=self.apply_hotkeys, icon=icons.apply),
                cd.QFlatDialogButton("Close", callback=self.request_close, icon=icons.close),
            ],
            closeButton=False,
            highlight="Apply",
        )

    def _populate_sections(self):
        self.section_list.clear()
        for row_index, section in enumerate(self._sections):
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, section["id"])
            item.setSizeHint(QtCore.QSize(0, wutil.DPI(43)))
            self.section_list.addItem(item)
            widget = HotkeySectionItemWidget(section, row_index=row_index, parent=self.section_list)
            widget.clicked.connect(lambda sid=section["id"]: self._select_section_by_id(sid))
            self.section_list.setItemWidget(item, widget)
        if self.section_list.count():
            self.section_list.setCurrentRow(0)

    def _select_section_by_id(self, section_id):
        for index in range(self.section_list.count()):
            item = self.section_list.item(index)
            if item and item.data(QtCore.Qt.UserRole) == section_id:
                self.section_list.setCurrentRow(index)
                break

    def _create_command_list(self, section_id):
        command_list = HotkeyItemList(self.command_stack)
        command_list.setObjectName("HotkeyCommandList")
        command_list.setFrameShape(QtWidgets.QFrame.StyledPanel)
        command_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        command_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        command_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        command_palette = command_list.palette()
        command_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(0, 0, 0, 0))
        command_palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#d0d0d0"))
        command_list.setPalette(command_palette)
        command_list.setStyleSheet(
            "#HotkeyCommandList{background:#2b2b2b;border:1px solid #3a3a3a;color:#d0d0d0;}"
            "#HotkeyCommandList::item{margin:0px;padding:0px;}"
        )
        command_list.currentItemChanged.connect(
            lambda current, previous, sid=section_id: self._on_command_item_changed(sid, current, previous)
        )
        self.command_stack.addWidget(command_list)
        return command_list

    def _ensure_section_view(self, section_id):
        view = self._section_views.get(section_id)
        if view:
            return view
        view = {
            "list": self._create_command_list(section_id),
            "rows": [],
            "items": [],
            "built": False,
        }
        self._section_views[section_id] = view
        return view

    def _active_view(self):
        if not self._current_section_id:
            return None
        return self._section_views.get(self._current_section_id)

    def _set_row_combo_from_draft(self, row):
        row.setCombos(self._draft_mapping.get(row.command_name()) or [])

    def _sync_view_from_draft(self, view):
        for row in view["rows"]:
            self._set_row_combo_from_draft(row)

    def _sync_all_views_from_draft(self):
        for view in self._section_views.values():
            if view.get("built"):
                self._sync_view_from_draft(view)

    def _clear_command_view(self, view):
        view["list"].clear()
        view["rows"] = []
        view["items"] = []
        view["built"] = False

    def _begin_section_build(self, section_id, commands, batched=False):
        view = self._ensure_section_view(section_id)
        self._clear_command_view(view)
        self._pending_section_id = section_id
        self._pending_commands = list(commands)
        self._pending_row_index = 0
        self._pending_view = view
        self._batched_build = bool(batched)
        view["list"].clearSelection()
        view["list"].setUpdatesEnabled(False)
        self._populate_next_batch()

    def _populate_next_batch(self):
        if not self._pending_section_id or not self._pending_view:
            return

        command_list = self._pending_view["list"]
        batch_size = COMMAND_BATCH_SIZE if self._batched_build else len(self._pending_commands)
        start = self._pending_row_index
        end = min(start + batch_size, len(self._pending_commands))

        command_list.blockSignals(True)
        for row_index in range(start, end):
            command = self._pending_commands[row_index]
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, command["command"])
            item.setSizeHint(QtCore.QSize(0, wutil.DPI(28)))
            command_list.addItem(item)

            row = HotkeyCommandItemWidget(command, row_index=row_index, parent=command_list)
            row.comboChanged.connect(self._on_row_combo_changed)
            row.requestSelect.connect(self._select_command_by_name)
            row.invokeRequested.connect(self._invoke_command)
            command_list.setItemWidget(item, row)
            self._set_row_combo_from_draft(row)
            self._pending_view["rows"].append(row)
            self._pending_view["items"].append(item)
        command_list.blockSignals(False)

        self._pending_row_index = end
        if self._pending_row_index < len(self._pending_commands):
            command_list.setUpdatesEnabled(True)
            self._build_timer.start(0)
            return

        command_list.setUpdatesEnabled(True)
        command_list.clearSelection()
        command_list.setCurrentRow(-1)
        self._pending_view["built"] = True
        self._refresh_statuses()
        self._pending_section_id = None
        self._pending_commands = []
        self._pending_row_index = 0
        self._batched_build = False
        self._pending_view = None

    def _on_section_changed(self, current, _previous):
        self._sync_section_selection()
        if not current:
            return
        section_id = current.data(QtCore.Qt.UserRole)
        if section_id == self._current_section_id:
            return
        section = self._section_lookup.get(section_id)
        if not section:
            return
        self._build_timer.stop()
        self._pending_section_id = None
        self._pending_commands = []
        self._pending_row_index = 0
        self._batched_build = False
        self._pending_view = None
        self.section_title.setText(section["title"])
        view = self._ensure_section_view(section_id)
        self._current_section_id = section_id
        self.command_stack.setCurrentWidget(view["list"])
        if view["built"]:
            self._sync_view_from_draft(view)
            self._refresh_statuses()
            view["list"].clearSelection()
            view["list"].setCurrentRow(-1)
            return
        self._begin_section_build(
            section_id,
            section["commands"],
            batched=section_id.endswith("_slider") or section_id.startswith("slider_"),
        )

    def _iter_visible_rows(self):
        view = self._active_view()
        return list(view["rows"]) if view else []

    def _select_command_by_name(self, command_name):
        view = self._active_view()
        if not view:
            return
        for index, item in enumerate(view["items"]):
            if item.data(QtCore.Qt.UserRole) == command_name:
                view["list"].setCurrentRow(index)
                break

    def _section_id_for_command(self, command_name):
        for section in self._sections:
            for command in section.get("commands", []):
                if command.get("command") == command_name:
                    return section.get("id")
        return None

    def focus_command(self, command_name):
        section_id = self._section_id_for_command(command_name)
        if not section_id:
            return False

        self._select_section_by_id(section_id)

        def _focus_when_ready():
            view = self._section_views.get(section_id)
            if not view or not view.get("built"):
                QtCore.QTimer.singleShot(40, _focus_when_ready)
                return
            for index, item in enumerate(view["items"]):
                if item.data(QtCore.Qt.UserRole) != command_name:
                    continue
                view["list"].setCurrentRow(index)
                view["list"].scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                row = view["rows"][index]
                row.edit.setFocus(QtCore.Qt.OtherFocusReason)
                row.edit.selectAll()
                return

        QtCore.QTimer.singleShot(0, _focus_when_ready)
        return True

    def _sync_section_selection(self):
        current = self.section_list.currentItem()
        for index in range(self.section_list.count()):
            item = self.section_list.item(index)
            widget = self.section_list.itemWidget(item)
            if widget:
                widget.set_selected(item is current)

    def _on_command_item_changed(self, section_id, current, _previous):
        view = self._section_views.get(section_id)
        if not view:
            return
        for item, row in zip(view["items"], view["rows"]):
            row.set_selected(item is current)

    def _pending_mapping(self):
        return _copy_hotkey_mapping(self._draft_mapping)

    def _invoke_command(self, command_name):
        if trigger.has_command(command_name):
            trigger.execute_command(command_name)

    def _on_row_combo_changed(self, command_name, combo):
        if combo:
            self._draft_mapping[command_name] = [combo]
        else:
            self._draft_mapping.pop(command_name, None)
        self._refresh_all_view_statuses()

    def _is_dirty(self):
        return self._pending_mapping() != self._stored_mapping

    def _discard_hotkey_changes(self):
        self._draft_mapping = _copy_hotkey_mapping(self._stored_mapping)
        self._sync_all_views_from_draft()
        self._refresh_all_view_statuses()

    def _refresh_statuses(self):
        """
        Refreshes visible row icons for the single-hotkey draft model.
        """
        resolver = HotkeyStatusResolver(self._pending_mapping(), self._title_lookup, self._icon_lookup)

        for row in self._iter_visible_rows():
            icon, tooltip, tooltip_data = resolver.status_for(row.command_name(), row.combo())
            row.set_status(icon, tooltip, tooltip_data=tooltip_data)

    def _refresh_all_view_statuses(self):
        active_section_id = self._current_section_id
        for section_id, view in self._section_views.items():
            if not view.get("built"):
                continue
            self._current_section_id = section_id
            self._refresh_statuses()
        self._current_section_id = active_section_id

    def import_hotkeys(self):
        result = cmds.fileDialog2(fileMode=1, caption="Import Hotkeys", fileFilter="JSON Files (*.json)")
        if not result:
            return
        try:
            with open(result[0], "r") as fh:
                data = json.load(fh)
        except Exception as exc:
            cmds.warning("Could not import hotkeys: {}".format(exc))
            return
        if not isinstance(data, dict):
            cmds.warning("Invalid hotkey file.")
            return
        self._draft_mapping = _hotkey_mapping_from_data(data)
        self._sync_all_views_from_draft()
        self._refresh_all_view_statuses()

    def export_hotkeys(self):
        result = cmds.fileDialog2(fileMode=0, caption="Export Hotkeys", fileFilter="JSON Files (*.json)")
        if not result:
            return
        path = result[0]
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w") as fh:
                json.dump(_hotkey_mapping_to_data(self._pending_mapping()), fh, indent=2, sort_keys=True)
        except Exception as exc:
            cmds.warning("Could not export hotkeys: {}".format(exc))

    def clear_hotkeys(self):
        result = cd.QFlatConfirmDialog.question(
            self,
            "Clear hotkeys",
            title="Clear current hotkeys?",
            message="This will clear the hotkeys currently shown in the editor. You can still cancel before applying.",
            buttons=[cd.QFlatConfirmDialog.Yes, cd.QFlatConfirmDialog.Cancel],
            highlight="Yes",
        )
        if not result or result.get("name") != "Yes":
            return

        self._draft_mapping = {}
        self._sync_all_views_from_draft()
        self._refresh_all_view_statuses()

    def apply_hotkeys(self):
        """
        Applies all hotkeys in the current draft to Maya.
        """
        pending = self._pending_mapping()

        duplicates = _duplicate_combo_owners(pending)
        if duplicates:
            cmds.warning("Duplicate hotkeys found. Resolve conflicts before applying.")
            self._refresh_all_view_statuses()
            return False

        writable_set = _ensure_writable_hotkey_set()
        if writable_set:
            cmds.warning("Switched to writable hotkey set: {}".format(writable_set))

        _clear_hotkey_mapping(_load_hotkeys_from_maya())
        _assign_hotkey_mapping(pending, self._title_lookup)
        _save_hotkeys_to_maya()
        self._stored_mapping = _copy_hotkey_mapping(pending)
        self._draft_mapping = _copy_hotkey_mapping(self._stored_mapping)
        self._sync_all_views_from_draft()

        # Use a small delay to ensure Maya is ready for status queries
        self._refresh_all_view_statuses()
        QtCore.QTimer.singleShot(STATUS_REFRESH_DELAY_MS, self._refresh_all_view_statuses)
        return True

    def request_close(self):
        if self._close_prompt_open:
            return
        if not self._is_dirty():
            self._allow_close = True
            self.close()
            return

        self._close_prompt_open = True
        result = cd.QFlatConfirmDialog.question(
            self,
            "Unsaved hotkeys",
            title="Save hotkey changes?",
            message="You have unsaved hotkey changes. Save them, discard them, or cancel and keep editing.",
            icon=icons.warning,
            buttons=[
                cd.QFlatDialogButton("Save", positive=True, icon=icons.apply),
                cd.QFlatDialogButton("Discard", positive=False, icon=icons.trash),
                cd.QFlatDialogButton("Cancel", positive=False, icon=icons.cancel),
            ],
            highlight="Save",
        )
        self._close_prompt_open = False
        if not result:
            return
        name = result.get("name")
        if name == "Save":
            if self.apply_hotkeys():
                self._allow_close = True
                self.close()
        elif name == "Discard":
            self._discard_hotkey_changes()
            self._allow_close = True
            self.close()

    def closeEvent(self, event):
        if self._allow_close:
            self._allow_close = False
            super().closeEvent(event)
            return
        if self._is_dirty():
            event.ignore()
            self.request_close()
            return
        super().closeEvent(event)


def show_hotkeys_window(*_args):
    manager = runtime.get_runtime_manager()
    existing = getattr(manager, "_managed_widgets", {}).get(HOTKEYS_WINDOW_KEY)
    if existing and wutil.is_valid_widget(existing):
        existing.show()
        existing.raise_()
        existing.activateWindow()
        return existing

    dialog = TriggerHotkeysDialog(parent=wutil.get_maya_qt())
    manager.register_managed_widget(dialog, key=HOTKEYS_WINDOW_KEY)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def show_hotkeys_window_for_command(command_name):
    dialog = show_hotkeys_window()
    if dialog and command_name:
        dialog.focus_command(command_name)
    return dialog
