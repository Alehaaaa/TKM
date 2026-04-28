"""
Managed hotkey UI and hotkey helpers for TheKeyMachine trigger commands.
"""

from __future__ import annotations

import json
import os

from maya import cmds, mel

try:
    from PySide6 import QtCore, QtGui, QtWidgets # type: ignore
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets # type: ignore

import TheKeyMachine.core.runtime_manager as runtime
import TheKeyMachine.core.toolbox as toolbox
import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.mediaMod as media
from TheKeyMachine.widgets import customDialogs as cd
from TheKeyMachine.widgets import customWidgets as cw
from TheKeyMachine.widgets import util as wutil


HOTKEYS_WINDOW_KEY = "tkm_hotkeys_window"
HOTKEYS_EXPORT_DIR = os.path.join(general.USER_FOLDER_PATH, "TheKeyMachine_user_data", "tools", "hotkeys")



def _ensure_hotkey_folder():
    folder = HOTKEYS_EXPORT_DIR
    os.makedirs(folder, exist_ok=True)
    return folder





def _combo_from_assign_command_key_string(key_string):
    if not key_string or len(key_string) < 7:
        return None
    maya_key = key_string[0]
    if not maya_key or maya_key == "NONE":
        return None
    return _normalize_combo(
        {
            "maya_key": maya_key,
            "display_key": str(maya_key).upper() if len(str(maya_key)) == 1 else str(maya_key),
            "alt": key_string[1] == "1",
            "ctrl": key_string[2] == "1",
            "shift": key_string[6] == "1",
        }
    )


def _load_hotkeys_from_maya():
    mapping = {}
    stale_assignments = []

    for index in range(1, (cmds.assignCommand(query=True, numElements=True) or 0) + 1):
        try:
            name = cmds.assignCommand(index, query=True, name=True)
            key_string = cmds.assignCommand(index, query=True, keyString=True)
        except Exception:
            continue
        if not name or not str(name).startswith("TKMTriggerName_"):
            continue
        combo = _combo_from_assign_command_key_string(key_string)
        if not combo:
            continue
        command_name = str(name).replace("TKMTriggerName_", "", 1)
        if not trigger.has_command(command_name):
            stale_assignments.append(combo)
            continue
        mapping[command_name] = combo

    if stale_assignments:
        _clear_stale_hotkey_assignments(stale_assignments)

    return mapping


def _normalize_hotkey_mapping(data):
    mapping = {}
    if not isinstance(data, dict):
        return mapping
    for name, combo in data.items():
        normalized_combo = _normalize_combo(combo)
        if not normalized_combo:
            continue
        command_name = str(name)
        if not trigger.has_command(command_name):
            continue
        if command_name in mapping:
            continue
        mapping[command_name] = normalized_combo
    return mapping


def _save_hotkeys_to_maya():
    try:
        cmds.hotkey(autoSave=True)
    except Exception:
        pass


def _runtime_command_name(command_name):
    return "TKMTriggerRuntime_{}".format(command_name)


def _name_command_name(command_name):
    return "TKMTriggerName_{}".format(command_name)


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


def _trigger_command_string(command_name):
    return "import TheKeyMachine.core as TKM_CORE; TKM_CORE.trigger.invoke({!r})".format(command_name)


def _normalize_combo(combo):
    if not combo:
        return None
    return {
        "maya_key": combo["maya_key"],
        "display_key": combo.get("display_key", combo["maya_key"].upper()),
        "ctrl": bool(combo.get("ctrl")),
        "shift": bool(combo.get("shift")),
        "alt": bool(combo.get("alt")),
    }


def _combo_display(combo):
    if not combo:
        return ""
    parts = []
    if combo.get("ctrl"):
        parts.append("Ctrl")
    if combo.get("shift"):
        parts.append("Shift")
    if combo.get("alt"):
        parts.append("Alt")
    parts.append(combo.get("display_key", combo.get("maya_key", "")))
    return "+".join(part for part in parts if part)


def _combo_key(combo):
    combo = _normalize_combo(combo)
    if not combo:
        return ""
    return "{}|{}|{}|{}".format(combo["maya_key"], int(combo["ctrl"]), int(combo["shift"]), int(combo["alt"]))


def _pixmap_for_icon(icon, size=18):
    if not icon:
        return QtGui.QPixmap()
    return QtGui.QIcon(icon).pixmap(wutil.DPI(size), wutil.DPI(size))


def _text_badge_pixmap(text, size=18):
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
    return pixmap


def _query_current_name_command(combo):
    if not combo:
        return None
    try:
        res = cmds.hotkey(
            keyShortcut=combo["maya_key"],
            alt=bool(combo.get("alt")),
            ctl=bool(combo.get("ctrl")),
            sht=bool(combo.get("shift")),
            query=True,
            name=True,
        )
    except Exception:
        res = None
    if res:
        return res

    try:
        annotation = cmds.hotkeyCheck(
            keyString=combo["maya_key"],
            altModifier=bool(combo.get("alt")),
            ctrlModifier=bool(combo.get("ctrl")),
            shiftModifier=bool(combo.get("shift")),
        )
        if annotation:
            return annotation
    except Exception:
        pass

    try:
        count = cmds.assignCommand(query=True, numElements=True) or 0
    except Exception:
        return None

    for index in range(1, int(count) + 1):
        try:
            key_string = cmds.assignCommand(index, query=True, keyString=True)
        except Exception:
            continue
        assigned_combo = _combo_from_assign_command_key_string(key_string)
        if _combo_key(assigned_combo) != _combo_key(combo):
            continue
        try:
            name = cmds.assignCommand(index, query=True, name=True)
        except Exception:
            name = None
        if name:
            return name
        try:
            annotation = cmds.assignCommand(index, query=True, annotation=True)
        except Exception:
            annotation = None
        if annotation:
            return annotation
    return None


def _clear_hotkey(combo):
    if not combo:
        return
    try:
        cmds.hotkey(
            keyShortcut=combo["maya_key"],
            alt=bool(combo.get("alt")),
            ctl=bool(combo.get("ctrl")),
            sht=bool(combo.get("shift")),
            name="",
        )
    except Exception:
        pass


def _ensure_runtime_binding(command_name, title):
    runtime_name = _runtime_command_name(command_name)
    name_command = _name_command_name(command_name)
    kwargs = {
        "annotation": title,
        "category": "TheKeyMachine",
        "showInHotkeyEditor": False,
        "commandLanguage": "python",
        "command": _trigger_command_string(command_name),
    }
    try:
        if cmds.runTimeCommand(runtime_name, query=True, exists=True):
            cmds.runTimeCommand(runtime_name, edit=True, **kwargs)
        else:
            cmds.runTimeCommand(runtime_name, **kwargs)
    except Exception:
        if cmds.runTimeCommand(runtime_name, query=True, exists=True):
            cmds.runTimeCommand(
                runtime_name,
                edit=True,
                annotation=title,
                category="TheKeyMachine",
                showInHotkeyEditor=False,
                command=_trigger_command_string(command_name),
            )
        else:
            cmds.runTimeCommand(
                runtime_name,
                annotation=title,
                category="TheKeyMachine",
                showInHotkeyEditor=False,
                command=_trigger_command_string(command_name),
            )

    try:
        cmds.nameCommand(name_command, edit=True, annotation=title, command=runtime_name)
    except Exception:
        cmds.nameCommand(name_command, annotation=title, command=runtime_name)
    return name_command


def _assign_hotkey(command_name, title, combo):
    if not combo:
        return
    name_command = _ensure_runtime_binding(command_name, title)
    cmds.hotkey(
        keyShortcut=combo["maya_key"],
        alt=bool(combo.get("alt")),
        ctl=bool(combo.get("ctrl")),
        sht=bool(combo.get("shift")),
        name=name_command,
    )





def _clear_stale_hotkey_assignments(stale_assignments):
    for combo in stale_assignments:
        _clear_hotkey(combo)
    _save_hotkeys_to_maya()


def _qt_key_to_combo(event):
    key = event.key()
    modifiers = event.modifiers()
    if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
        return None
    if key in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete):
        return {}

    letter_map = {getattr(QtCore.Qt, "Key_{}".format(chr(code))): chr(code).lower() for code in range(ord("A"), ord("Z") + 1)}
    digit_map = {getattr(QtCore.Qt, "Key_{}".format(num)): str(num) for num in range(10)}
    special_map = {
        QtCore.Qt.Key_Space: "Space",
        QtCore.Qt.Key_Tab: "Tab",
        QtCore.Qt.Key_Return: "Enter",
        QtCore.Qt.Key_Enter: "Enter",
        QtCore.Qt.Key_Escape: "Escape",
        QtCore.Qt.Key_Left: "Left",
        QtCore.Qt.Key_Right: "Right",
        QtCore.Qt.Key_Up: "Up",
        QtCore.Qt.Key_Down: "Down",
        QtCore.Qt.Key_Home: "Home",
        QtCore.Qt.Key_End: "End",
        QtCore.Qt.Key_PageUp: "PageUp",
        QtCore.Qt.Key_PageDown: "PageDown",
        QtCore.Qt.Key_Insert: "Insert",
        QtCore.Qt.Key_Minus: "-",
        QtCore.Qt.Key_Equal: "=",
        QtCore.Qt.Key_Slash: "/",
        QtCore.Qt.Key_Backslash: "\\",
        QtCore.Qt.Key_BracketLeft: "[",
        QtCore.Qt.Key_BracketRight: "]",
        QtCore.Qt.Key_Semicolon: ";",
        QtCore.Qt.Key_Apostrophe: "'",
        QtCore.Qt.Key_Comma: ",",
        QtCore.Qt.Key_Period: ".",
        QtCore.Qt.Key_QuoteLeft: "`",
    }

    if key in letter_map:
        maya_key = letter_map[key]
        display_key = maya_key.upper()
    elif key in digit_map:
        maya_key = digit_map[key]
        display_key = maya_key
    elif QtCore.Qt.Key_F1 <= key <= QtCore.Qt.Key_F12:
        display_key = "F{}".format(key - QtCore.Qt.Key_F1 + 1)
        maya_key = display_key
    elif key in special_map:
        display_key = maya_key = special_map[key]
    else:
        return None

    return _normalize_combo(
        {
            "maya_key": maya_key,
            "display_key": display_key,
            "ctrl": bool(modifiers & QtCore.Qt.ControlModifier),
            "shift": bool(modifiers & QtCore.Qt.ShiftModifier),
            "alt": bool(modifiers & QtCore.Qt.AltModifier),
        }
    )


def _tooltip_for_assignment(name_command, title_lookup):
    if not name_command:
        return ""
    if name_command.startswith("TKMTriggerName_"):
        command_name = name_command.replace("TKMTriggerName_", "", 1)
        return title_lookup.get(command_name, command_name)
    return str(name_command)


def _assignment_tooltip_data(name_command, title_lookup, icon_lookup):
    if not name_command:
        return None
    description = "Hotkey Conflict.<br>If you Apply changes, it will overwrite this hotkey."
    if name_command.startswith("TKMTriggerName_"):
        command_name = name_command.replace("TKMTriggerName_", "", 1)
        return {
            "text": title_lookup.get(command_name, command_name),
            "description": description,
            "icon": icon_lookup.get(command_name),
        }
    return {
        "text": str(name_command),
        "description": description,
        "icon": ":/mayaIcon.png",
    }


def _native_tooltip_html(tooltip_data):
    if not tooltip_data:
        return ""
    icon = tooltip_data.get("icon")
    title = tooltip_data.get("text", "")
    description = tooltip_data.get("description", "")
    parts = ["<table cellspacing='0' cellpadding='0'>"]
    if icon:
        parts.append(
            "<tr><td style='padding:0 8px 6px 0; vertical-align:top;'><img src='{}' width='24' height='24'></td>"
            "<td style='vertical-align:top;'><b>{}</b></td></tr>".format(icon, title)
        )
    else:
        parts.append("<tr><td><b>{}</b></td></tr>".format(title))
    if description:
        parts.append("<tr><td colspan='2'>{}</td></tr>".format(description))
    parts.append("</table>")
    return "".join(parts)


def _tool_command_row(tool_data):
    command_name = tool_data.get("key") or tool_data.get("id")
    if not command_name:
        return None
    return {
        "command": command_name,
        "title": tool_data.get("status_title") or tool_data.get("label") or _humanize(command_name),
        "icon": tool_data.get("icon"),
        "badge_text": None if tool_data.get("icon") else tool_data.get("text"),
    }


def _variant_command_row(tool_data, variant, shortcut_label=None):
    command_name = variant.get("key") or variant.get("id")
    if not command_name:
        return None
    icon = variant.get("icon") or tool_data.get("icon")
    return {
        "command": command_name,
        "title": shortcut_label
        or variant.get("status_title")
        or variant.get("label")
        or variant.get("description")
        or _humanize(command_name),
        "icon": icon,
        "badge_text": None if icon else variant.get("text") or tool_data.get("text"),
    }


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
    section = {"id": section_id, "title": section_data.get("label", _humanize(section_id)), "icon": None, "commands": []}
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
        for section_id in toolbox.TOOLBAR_SECTION_LAYOUTS.get(layout_id, []):
            if section_id in seen:
                continue
            section_data = toolbox.TOOL_SECTION_DEFINITIONS.get(section_id)
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
                "title": section_data.get("hotkey_label") or section_data.get("label") or _humanize(section_id),
                "icon": section_data.get("icon"),
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


class HotkeyCaptureEdit(QtWidgets.QLineEdit):
    comboChanged = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._combo = None
        self.setPlaceholderText("Type a hotkey")
        self.setReadOnly(True)
        self.setMinimumWidth(wutil.DPI(170))
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.setCursor(QtCore.Qt.IBeamCursor)

    def combo(self):
        return _normalize_combo(self._combo)

    def setCombo(self, combo):
        self._combo = _normalize_combo(combo)
        self.setText(_combo_display(self._combo))

    def keyPressEvent(self, event):
        combo = _qt_key_to_combo(event)
        if combo == {}:
            self.setCombo(None)
            self.comboChanged.emit(None)
            event.accept()
            return
        if combo is None:
            event.accept()
            return
        self.setCombo(combo)
        self.comboChanged.emit(self.combo())
        event.accept()


class HotkeyStatusLabel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        QtWidgets.QLabel.__init__(self, parent)
        self.setAlignment(QtCore.Qt.AlignCenter)

    def clear_status_tooltip(self):
        self.setToolTip("")


class HotkeyCommandRow(QtWidgets.QWidget):
    comboChanged = QtCore.Signal(str, object)
    requestSelect = QtCore.Signal(str)

    def __init__(self, command_data, title_lookup, icon_lookup, row_index=0, accent_color="#5f88a8", parent=None):
        super().__init__(parent)
        self.command_data = command_data
        self.title_lookup = title_lookup
        self.icon_lookup = icon_lookup
        self._row_index = row_index
        self._selected = False
        self._base_bg = "#303030" if (row_index % 2 == 0) else "#292929"
        self._accent_color = accent_color
        self._icon = command_data.get("icon")
        self._pressed_icon = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tool_button = QtWidgets.QPushButton(command_data["title"], self)
        self.tool_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.tool_button.setFlat(True)
        self.tool_button.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        self.tool_button.setMinimumHeight(wutil.DPI(24))
        if self._icon:
            cw.QFlatHoverableIcon.apply(self.tool_button, self._icon, highlight=False)
            self._pressed_icon = cw.QFlatHoverableIcon._color_icon(
                QtGui.QIcon(self._icon), self._accent_color, self.tool_button.iconSize()
            )
        elif command_data.get("badge_text"):
            self.tool_button.setIcon(QtGui.QIcon(_text_badge_pixmap(command_data.get("badge_text"))))
        self.tool_button.clicked.connect(lambda *_: trigger.invoke(self.command_name()))
        self.tool_button.pressed.connect(self._on_tool_pressed)
        self.tool_button.released.connect(self._on_tool_released)
        layout.addWidget(self.tool_button, 1)

        self.status_cell = HotkeyStatusLabel(self)
        self.status_cell.setFixedWidth(wutil.DPI(28))
        layout.addWidget(self.status_cell)

        self.edit = HotkeyCaptureEdit(self)
        self.edit.setMinimumHeight(wutil.DPI(24))
        self.edit.comboChanged.connect(lambda combo, name=command_data["command"]: self.comboChanged.emit(name, combo))
        layout.addWidget(self.edit, 0)

        self.setFixedHeight(wutil.DPI(24))
        for watched in (self, self.tool_button, self.edit, self.status_cell):
            watched.installEventFilter(self)
        self._apply_row_style()

    def command_name(self):
        return self.command_data["command"]

    def combo(self):
        return self.edit.combo()

    def setCombo(self, combo):
        self.edit.setCombo(combo)

    def set_status(self, icon=None, tooltip="", tooltip_data=None):
        self.status_cell.setPixmap(_pixmap_for_icon(icon, size=16) if icon else QtGui.QPixmap())
        if tooltip_data:
            self.status_cell.setToolTip(_native_tooltip_html(tooltip_data))
        elif tooltip:
            self.status_cell.setToolTip(tooltip)
        else:
            self.status_cell.clear_status_tooltip()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._apply_row_style()

    def _apply_row_style(self):
        border = "#6f8ea2" if self._selected else self._base_bg
        row_bg = self._base_bg
        self.setStyleSheet(
            "QWidget{background:%s;border:1px solid %s;}"
            "QPushButton{background:%s;border:none;color:#d0d0d0;text-align:left;padding:0 %spx;font-size:%spx;}"
            "QPushButton:hover{color:#ffffff;}"
            "QPushButton:pressed{color:%s;}"
            "QLabel{background:%s;border:none;}"
            "QLineEdit{background:#202020;border:1px solid #383838;border-radius:%spx;color:#d2d2d2;padding:%spx %spx;}"
            "QLineEdit:focus{border:1px solid #6f8ea2;padding:%spx %spx;}"
            % (
                row_bg,
                border,
                row_bg,
                wutil.DPI(8),
                wutil.DPI(12),
                self._accent_color,
                row_bg,
                wutil.DPI(6),
                wutil.DPI(5),
                wutil.DPI(10),
                wutil.DPI(5),
                wutil.DPI(10),
            )
        )

    def _on_tool_pressed(self):
        if self._pressed_icon is not None:
            self.tool_button.setIcon(self._pressed_icon)

    def _on_tool_released(self):
        if self._icon:
            self.tool_button.setIcon(QtGui.QIcon(self._icon))

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.FocusIn):
            self.requestSelect.emit(self.command_name())
        return super().eventFilter(watched, event)


class TriggerHotkeysDialog(cd.QFlatToolBarWindowDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("TheKeyMachine Hotkeys")
        self.resize(wutil.DPI(980), wutil.DPI(720))

        self._sections, self._title_lookup, self._icon_lookup = _build_command_catalog()
        self._section_lookup = {section["id"]: section for section in self._sections}
        self._stored_mapping = _load_hotkeys_from_maya()
        self._draft_mapping = dict(self._stored_mapping)
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

        main = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setContentsMargins(wutil.DPI(12), wutil.DPI(12), wutil.DPI(12), wutil.DPI(12))
        main_layout.setSpacing(wutil.DPI(8))

        self.addWindowHeader(
            parentLayout=main_layout,
            icon=media.hotkeys_image,
            text="Hotkeys",
            textColor="#d8d8d8",
        )

        content_layout = QtWidgets.QGridLayout()
        content_layout.setHorizontalSpacing(wutil.DPI(12))
        content_layout.setVerticalSpacing(wutil.DPI(8))
        content_layout.setColumnStretch(0, 0)
        content_layout.setColumnStretch(1, 1)
        content_layout.setRowStretch(1, 1)
        main_layout.addLayout(content_layout, 1)

        left_widget = QtWidgets.QWidget(main)
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(0)

        self.section_list = QtWidgets.QListWidget(left_widget)
        self.section_list.setIconSize(QtCore.QSize(wutil.DPI(43), wutil.DPI(43)))
        self.section_list.setMinimumWidth(wutil.DPI(240))
        self.section_list.setStyleSheet(
            (
                "QListWidget{background:#2d2d2d;border:1px solid #3a3a3a;color:#d0d0d0;outline:none;}"
                "QListWidget::item{padding:%spx %spx %spx %spx; margin:0px; border:none; background:transparent;}"
                "QListWidget::item:selected{padding:%spx %spx %spx %spx; margin:0px; border:none; background:#5f88a8; color:#ffffff;}"
                "QListWidget::item:selected:active{padding:%spx %spx %spx %spx;}"
                "QListWidget::item:selected:!active{padding:%spx %spx %spx %spx;}"
            )
            % (
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
                wutil.DPI(8),
                wutil.DPI(12),
            )
        )
        self.section_list.currentItemChanged.connect(self._on_section_changed)
        left_layout.addWidget(self.section_list, 1)

        right_widget = QtWidgets.QWidget(main)
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(0)

        self.command_stack = QtWidgets.QStackedWidget(right_widget)
        self.command_stack.setStyleSheet("QStackedWidget{background:transparent;}")
        right_layout.addWidget(self.command_stack, 1)

        self.tools_title = QtWidgets.QLabel("Tools", main)
        self.tools_title.setStyleSheet("color:#bcbcbc;font-size:%spx;" % wutil.DPI(11))
        self.section_title = QtWidgets.QLabel("Hotkeys", main)
        self.section_title.setStyleSheet("color:#bcbcbc;font-size:%spx;" % wutil.DPI(11))

        content_layout.addWidget(self.tools_title, 0, 0)
        content_layout.addWidget(self.section_title, 0, 1)
        content_layout.addWidget(left_widget, 1, 0)
        content_layout.addWidget(right_widget, 1, 1)

        self.root_layout.insertWidget(0, main, 1)

        self._populate_sections()

        self.setBottomBar(
            buttons=[
                cd.QFlatDialogButton("Import", callback=self.import_hotkeys, icon=media.selection_sets_import_image),
                cd.QFlatDialogButton("Export", callback=self.export_hotkeys, icon=media.selection_sets_export_image),
                cd.QFlatDialogButton("Clear All", callback=self.clear_hotkeys, icon=media.trash_image),
                cd.QFlatDialogButton("Apply", callback=self.apply_hotkeys, icon=media.apply_image, highlight=True),
                cd.QFlatDialogButton("Close", callback=self.request_close, icon=media.close_image),
            ],
            closeButton=False,
            highlight="Apply",
        )

    def _populate_sections(self):
        self.section_list.clear()
        for section in self._sections:
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(section.get("icon") or ""), section["title"])
            item.setData(QtCore.Qt.UserRole, section["id"])
            item.setSizeHint(QtCore.QSize(0, wutil.DPI(62)))
            self.section_list.addItem(item)
        if self.section_list.count():
            self.section_list.setCurrentRow(0)

    def _create_command_list(self, section_id):
        command_list = QtWidgets.QListWidget(self.command_stack)
        command_list.setFrameShape(QtWidgets.QFrame.NoFrame)
        command_list.setSpacing(0)
        command_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        command_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        command_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        command_list.setStyleSheet(
            "QListWidget{background:#242424;border:1px solid #3a3a3a;color:#d0d0d0;outline:none;}"
            "QListWidget::item{padding:0px;margin:0px;border:none;background:transparent;}"
            "QListWidget::item:selected{background:transparent;border:none;}"
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
        combo = self._draft_mapping.get(row.command_name())
        row.setCombo(combo if combo else None)

    def _sync_view_from_draft(self, view):
        for row in view["rows"]:
            self._set_row_combo_from_draft(row)

    def _begin_section_build(self, section_id, commands, batched=False):
        view = self._ensure_section_view(section_id)
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
        batch_size = 18 if self._batched_build else len(self._pending_commands)
        start = self._pending_row_index
        end = min(start + batch_size, len(self._pending_commands))

        command_list.blockSignals(True)
        for row_index in range(start, end):
            command = self._pending_commands[row_index]
            row = HotkeyCommandRow(command, self._title_lookup, self._icon_lookup, row_index=row_index, parent=command_list)
            self._set_row_combo_from_draft(row)
            row.comboChanged.connect(self._on_row_combo_changed)
            row.requestSelect.connect(self._select_command_by_name)
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, command["command"])
            item.setSizeHint(QtCore.QSize(0, wutil.DPI(24)))
            command_list.addItem(item)
            command_list.setItemWidget(item, row)
            self._pending_view["rows"].append(row)
            self._pending_view["items"].append(item)
        command_list.blockSignals(False)

        self._pending_row_index = end
        if command_list.count() and command_list.currentRow() < 0:
            command_list.setCurrentRow(0)

        if self._pending_row_index < len(self._pending_commands):
            command_list.setUpdatesEnabled(True)
            self._build_timer.start(0)
            return

        command_list.setUpdatesEnabled(True)
        self._pending_view["built"] = True
        self._refresh_statuses()
        self._pending_section_id = None
        self._pending_commands = []
        self._pending_row_index = 0
        self._batched_build = False
        self._pending_view = None

    def _on_section_changed(self, current, _previous):
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
            if view["list"].count() and view["list"].currentRow() < 0:
                view["list"].setCurrentRow(0)
            self._refresh_statuses()
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

    def _on_command_item_changed(self, section_id, current, _previous):
        view = self._section_views.get(section_id)
        if not view:
            return
        current_name = current.data(QtCore.Qt.UserRole) if current else None
        for item, row in zip(view["items"], view["rows"]):
            row.set_selected(item.data(QtCore.Qt.UserRole) == current_name)

    def _pending_mapping(self):
        return {name: _normalize_combo(combo) for name, combo in self._draft_mapping.items() if _normalize_combo(combo)}

    def _on_row_combo_changed(self, command_name, combo):
        if combo:
            self._draft_mapping[command_name] = combo
        else:
            self._draft_mapping.pop(command_name, None)
        self._refresh_all_view_statuses()

    def _is_dirty(self):
        return self._pending_mapping() != self._stored_mapping

    def _refresh_statuses(self):
        pending = self._pending_mapping()
        reverse = {}
        for name, combo in pending.items():
            reverse.setdefault(_combo_key(combo), []).append(name)

        for row in self._iter_visible_rows():
            combo = row.combo()
            if not combo:
                row.set_status(None, "")
                continue

            duplicate_names = reverse.get(_combo_key(combo), [])
            current_name_command = _query_current_name_command(combo)
            expected_name_command = _name_command_name(row.command_name())

            if len(duplicate_names) > 1:
                others = [self._title_lookup.get(name, name) for name in duplicate_names if name != row.command_name()]
                row.set_status(
                    media.warning_image,
                    "Also used by: {}".format(", ".join(others)),
                    tooltip_data={
                        "text": ", ".join(others),
                        "description": "Hotkey Conflict.<br>This combination is already used in this editor.",
                        "icon": media.warning_image,
                    },
                )
            elif current_name_command == expected_name_command:
                row.set_status(media.apply_image, "Assigned to {}".format(self._title_lookup.get(row.command_name(), row.command_name())))
            elif current_name_command:
                row.set_status(
                    media.warning_image,
                    "Assigned to {}".format(_tooltip_for_assignment(current_name_command, self._title_lookup)),
                    tooltip_data=_assignment_tooltip_data(current_name_command, self._title_lookup, self._icon_lookup),
                )
            else:
                row.set_status(None, "")

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
        self._draft_mapping = _normalize_hotkey_mapping(data)
        self._on_section_changed(self.section_list.currentItem(), None)

    def export_hotkeys(self):
        result = cmds.fileDialog2(fileMode=0, caption="Export Hotkeys", fileFilter="JSON Files (*.json)")
        if not result:
            return
        path = result[0]
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            with open(path, "w") as fh:
                json.dump(self._pending_mapping(), fh, indent=2, sort_keys=True)
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
        for row in self._iter_visible_rows():
            row.setCombo(None)
        self._refresh_statuses()

    def apply_hotkeys(self):
        pending = self._pending_mapping()
        seen = {}
        duplicates = []
        for command_name, combo in pending.items():
            key = _combo_key(combo)
            if key in seen:
                duplicates.append((command_name, seen[key]))
            else:
                seen[key] = command_name
        if duplicates:
            cmds.warning("Resolve duplicate hotkey combinations before applying.")
            return False

        previous = _load_hotkeys_from_maya()
        for combo in previous.values():
            _clear_hotkey(combo)

        for command_name, combo in pending.items():
            _assign_hotkey(command_name, self._title_lookup.get(command_name, _humanize(command_name)), combo)

        _save_hotkeys_to_maya()
        self._stored_mapping = dict(pending)
        self._draft_mapping = dict(pending)
        self._refresh_all_view_statuses()
        cmds.warning("TheKeyMachine hotkeys applied.")
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
            message="You have unsaved hotkey changes.",
            icon=media.warning_image,
            buttons=[
                cd.QFlatConfirmDialog.Yes,
                cd.QFlatConfirmDialog.No,
            ],
            highlight="Yes",
        )
        self._close_prompt_open = False
        if not result:
            return
        name = result.get("name")
        if name == "Yes":
            if self.apply_hotkeys():
                self._allow_close = True
                self.close()
        elif name == "No":
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


def smart_rotation_manipulator():
    actual_mode = cmds.currentCtx()
    mel.eval("buildRotateMM")
    current_rotate_mode = cmds.manipRotateContext("Rotate", q=True, mode=True)
    if actual_mode == "RotateSuperContext":
        if current_rotate_mode == 0:
            cmds.manipRotateContext("Rotate", e=True, mode=1)
        if current_rotate_mode == 1:
            cmds.manipRotateContext("Rotate", e=True, mode=2)
        if current_rotate_mode == 2:
            cmds.manipRotateContext("Rotate", e=True, mode=0)


def smart_rotation_manipulator_release():
    mel.eval("destroySTRSMarkingMenu RotateTool")


def smart_translate_manipulator():
    actual_mode = cmds.currentCtx()
    mel.eval("buildTranslateMM")
    current_move_mode = cmds.manipMoveContext("Move", q=True, mode=True)
    if actual_mode == "moveSuperContext":
        if current_move_mode == 0:
            cmds.manipMoveContext("Move", e=True, mode=2)
        else:
            cmds.manipMoveContext("Move", e=True, mode=0)


def smart_translate_manipulator_release():
    mel.eval("destroySTRSMarkingMenu MoveTool")
