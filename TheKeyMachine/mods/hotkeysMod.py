"""
Managed hotkey UI and hotkey helpers for TheKeyMachine trigger commands.
"""

from __future__ import annotations

from collections import OrderedDict
import json
import os

import maya.cmds as cmds
import maya.mel as mel

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

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


HOTKEY_SECTION_ICONS = {
    "windows": media.tool_icon,
    "manipulators": media.depth_mover_image,
    "selection": media.select_rig_controls_image,
    "selection_sets": media.selection_sets_image,
    "delete": media.delete_animation_image,
    "curve_tools": media.share_keys_image,
    "reset": media.asset_path("reset_animation_image"),
    "graph_editor": media.customGraph_image,
    "tempo_controls": media.nudge_right_image,
    "copy_paste": media.copy_animation_image,
    "worldspace": media.worldspace_copy_frame_image,
    "tangents": media.auto_tangent_image,
    "tween_slider": media.asset_path("yellow_dot_image"),
    "blend_slider": media.asset_path("green_dot_image"),
    "tangent_slider": media.auto_tangent_image,
    "bake": media.bake_animation_1_image,
    "tracer": media.tracer_image,
    "mirror": media.mirror_image,
    "match": media.match_image,
    "follow_cam": media.follow_cam_image,
    "opposite": media.opposite_select_image,
    "temp_pivot": media.temp_pivot_image,
    "link_objects": media.link_objects_image,
}


HOTKEY_SECTION_SPECS = OrderedDict(
    [
        (
            "windows",
            {
                "title": "Windows",
                "icon_path": HOTKEY_SECTION_ICONS["windows"],
                "tools": ["gimbal"],
                "commands": [
                    "toolbar_toggle",
                    "toolbar_add_shelf_button",
                    "toolbar_reload",
                    "toolbar_unload",
                    "check_for_updates",
                    "open_custom_graph",
                    "orbit_window",
                    "animation_offset_toggle",
                    "micro_move_toggle",
                    "custom_graph_toggle",
                    "hotkeys_window",
                    "about_window",
                    "donate_window",
                    "bug_report_window",
                ],
            },
        ),
        (
            "manipulators",
            {
                "title": "Manipulators",
                "icon_path": HOTKEY_SECTION_ICONS["manipulators"],
                "commands": ["smart_rotation", "smart_rotation_release", "smart_translation", "smart_translation_release", "depth_mover"],
            },
        ),
        (
            "selection",
            {
                "title": "Selection",
                "icon_path": HOTKEY_SECTION_ICONS["selection"],
                "tools": ["attribute_switcher", "selector"],
                "commands": [
                    "create_locator",
                    "isolate_master",
                    "attribute_switcher",
                    "selector",
                    "select_rig_controls",
                    "select_rig_controls_animated",
                    "select_hierarchy",
                    "locator_select_temp",
                    "locator_remove_temp",
                ],
            },
        ),
        (
            "selection_sets",
            {
                "title": "Selection Sets",
                "icon_path": HOTKEY_SECTION_ICONS["selection_sets"],
                "tools": ["selection_sets"],
                "commands": ["selection_sets_toggle"],
            },
        ),
        (
            "curve_tools",
            {
                "title": "Key Tools",
                "icon_path": HOTKEY_SECTION_ICONS["curve_tools"],
                "tools": ["share_keys", "reblock", "extra_tools", "flip", "snap", "overlap"],
            },
        ),
        (
            "reset",
            {
                "title": "Reset",
                "icon_path": HOTKEY_SECTION_ICONS["reset"],
                "tools": ["reset_objects_mods"],
            },
        ),
        (
            "graph_editor",
            {
                "title": "Graph Editor",
                "icon_path": HOTKEY_SECTION_ICONS["graph_editor"],
                "tools": [
                    "graph_isolate_curves",
                    "graph_toggle_mute",
                    "graph_toggle_lock",
                ],
            },
        ),
        (
            "delete",
            {
                "title": "Delete",
                "icon_path": HOTKEY_SECTION_ICONS["delete"],
                "tools": ["delete_all_animation", "static"],
            },
        ),
        (
            "copy_paste",
            {
                "title": "Copy Paste",
                "icon_path": HOTKEY_SECTION_ICONS["copy_paste"],
                "commands": [
                    "copy_pose",
                    "paste_pose",
                    "copy_animation",
                    "paste_animation",
                    "paste_insert_animation",
                    "paste_animation_to",
                ],
            },
        ),
        (
            "bake",
            {
                "title": "Bake",
                "icon_path": HOTKEY_SECTION_ICONS["bake"],
                "tools": ["bake_animation_1"],
            },
        ),
        (
            "tempo_controls",
            {
                "title": "Nudge",
                "icon_path": HOTKEY_SECTION_ICONS["tempo_controls"],
                "tools": ["move_left", "move_right"],
                "commands": ["insert_inbetween", "remove_inbetween", "nudge_left", "nudge_right"],
            },
        ),
        (
            "match",
            {
                "title": "Match",
                "icon_path": HOTKEY_SECTION_ICONS["match"],
                "tools": ["match", "align_selected_objects"],
                "commands": ["align_selected_objects"],
                "command_prefixes": ["align_selected_objects_", "match_"],
            },
        ),
        (
            "tangents",
            {
                "title": "Tangents",
                "icon_path": HOTKEY_SECTION_ICONS["tangents"],
                "tools": [
                    "tangent_auto",
                    "tangent_spline",
                    "tangent_clamped",
                    "tangent_linear",
                    "tangent_flat",
                    "tangent_step",
                    "tangent_plateau",
                    "tangent_cycle_matcher",
                    "tangent_bouncy",
                ],
            },
        ),
        (
            "tracer",
            {
                "title": "Tracer",
                "icon_path": HOTKEY_SECTION_ICONS["tracer"],
                "tools": ["tracer_refresh", "tracer_show_hide", "tracer_offset_node", "tracer_grey", "tracer_red", "tracer_blue", "tracer_remove"],
                "commands": ["create_tracer"],
            },
        ),
        (
            "mirror",
            {
                "title": "Mirror",
                "icon_path": HOTKEY_SECTION_ICONS["mirror"],
                "tools": ["mirror"],
            },
        ),
        (
            "opposite",
            {
                "title": "Opposite",
                "icon_path": HOTKEY_SECTION_ICONS["opposite"],
                "tools": ["selectOpposite", "paste_opposite_animation_direct"],
            },
        ),
        (
            "follow_cam",
            {
                "title": "Follow Cam",
                "icon_path": HOTKEY_SECTION_ICONS["follow_cam"],
                "tools": ["fcam_trans_only", "fcam_rot_only", "fcam_remove"],
                "commands": ["create_follow_cam"],
            },
        ),
        (
            "worldspace",
            {
                "title": "World Space",
                "icon_path": HOTKEY_SECTION_ICONS["worldspace"],
                "tools": ["copy_worldspace_single_frame"],
            },
        ),
        (
            "temp_pivot",
            {
                "title": "Temp Controls",
                "icon_path": HOTKEY_SECTION_ICONS["temp_pivot"],
                "tools": ["tp_last_used"],
                "commands": ["create_temp_pivot", "create_temp_pivot_last"],
            },
        ),
        (
            "link_objects",
            {
                "title": "Link Objects",
                "icon_path": HOTKEY_SECTION_ICONS["link_objects"],
                "tools": ["link_paste"],
                "commands": ["copy_link", "paste_link"],
            },
        ),
    ]
)


HOTKEY_COMMAND_METADATA = {
    "open_custom_graph": ("Custom Graph", media.customGraph_image),
    "toolbar_toggle": ("Toggle Toolbar", media.tool_icon),
    "toolbar_add_shelf_button": ("Add Toggle Button To Shelf", media.asset_path("tool_icon")),
    "toolbar_reload": ("Reload", media.reload_image),
    "toolbar_unload": ("Unload", media.close_image),
    "check_for_updates": ("Check for Updates", media.check_updates_image),
    "orbit_window": ("Orbit Window", media.orbit_ui_image),
    "selection_sets_toggle": ("Selection Sets", media.selection_sets_image),
    "animation_offset_toggle": ("Animation Offset", media.animation_offset_image),
    "micro_move_toggle": ("Micro Move", media.ruler_image),
    "custom_graph_toggle": ("Graph Toolbar Toggle", media.customGraph_image),
    "hotkeys_window": ("Hotkeys", media.hotkeys_image),
    "about_window": ("About", media.about_image),
    "donate_window": ("Donate", media.stripe_image),
    "bug_report_window": ("Bug Report", media.report_a_bug_image),
    "smart_rotation": ("Smart Rotation", media.auto_tangent_image),
    "smart_rotation_release": ("Smart Rotation Release", media.auto_tangent_image),
    "smart_translation": ("Smart Translation", media.create_locator_image),
    "smart_translation_release": ("Smart Translation Release", media.create_locator_image),
    "depth_mover": ("Depth Mover", media.depth_mover_image),
    "create_locator": ("Create Locator", media.create_locator_image),
    "isolate_master": ("Isolate", media.isolate_image),
    "select_rig_controls": ("Select Rig Controls", media.select_rig_controls_image),
    "select_rig_controls_animated": ("Select Animated Rig Controls", media.select_rig_controls_animated_image),
    "select_hierarchy": ("Select Hierarchy", media.select_hierarchy_image),
    "align_selected_objects": ("Align Selected Objects", media.align_menu_image),
    "create_tracer": ("Create Tracer", media.tracer_image),
    "refresh_tracer": ("Refresh Tracer", media.refresh_image),
    "delete_all_animation": ("Delete All Animation", media.delete_animation_image),
    "insert_inbetween": ("Insert Inbetween", media.insert_inbetween_image),
    "remove_inbetween": ("Remove Inbetween", media.remove_inbetween_image),
    "nudge_left": ("Nudge Left", media.nudge_left_image),
    "nudge_right": ("Nudge Right", media.nudge_right_image),
    "reset_values": ("Reset Values", media.asset_path("reset_animation_image")),
    "reset_translations": ("Reset Translations", media.asset_path("reset_animation_image")),
    "reset_rotations": ("Reset Rotations", media.asset_path("reset_animation_image")),
    "reset_scales": ("Reset Scales", media.asset_path("reset_animation_image")),
    "reset_trs": ("Reset Translation Rotation Scale", media.asset_path("reset_animation_image")),
    "select_opposite": ("Select Opposite", media.opposite_select_image),
    "add_opposite": ("Add Opposite", media.opposite_add_image),
    "copy_opposite": ("Copy Opposite", media.opposite_copy_image),
    "mirror": ("Mirror", media.mirror_image),
    "copy_pose": ("Copy Pose", media.copy_pose_image),
    "paste_pose": ("Paste Pose", media.paste_pose_image),
    "copy_animation": ("Copy Animation", media.copy_animation_image),
    "paste_animation": ("Paste Animation", media.paste_animation_image),
    "paste_insert_animation": ("Paste Insert Animation", media.paste_insert_animation_image),
    "paste_opposite_animation": ("Paste Opposite Animation", media.paste_opposite_animation_image),
    "paste_animation_to": ("Paste Animation To", media.paste_animation_image),
    "copy_link": ("Copy Link Position", media.link_objects_copy_image),
    "paste_link": ("Paste Link Position", media.link_objects_paste_image),
    "copy_worldspace_single_frame": ("Copy World Space Current Frame", media.worldspace_copy_frame_image),
    "paste_worldspace_single_frame": ("Paste World Space Current Frame", media.worldspace_paste_frame_image),
    "copy_range_worldspace_animation": ("Copy World Space Selected Range", media.worldspace_copy_animation_image),
    "worldspace_paste_animation": ("Paste World Space Animation", media.worldspace_paste_animation_image),
    "worldspace_copy_animation": ("Copy World Space Animation", media.worldspace_copy_animation_image),
    "create_temp_pivot": ("Create Temp Pivot", media.temp_pivot_image),
    "create_temp_pivot_last": ("Create Temp Pivot Last", media.temp_pivot_use_last_image),
    "create_follow_cam": ("Create Follow Cam", media.follow_cam_image),
    "set_auto_tangent": ("Auto Tangent", media.auto_tangent_image),
    "set_spline_tangent": ("Spline Tangent", media.spline_tangent_image),
    "set_clamped_tangent": ("Clamped Tangent", media.clamped_tangent_image),
    "set_linear_tangent": ("Linear Tangent", media.linear_tangent_image),
    "set_flat_tangent": ("Flat Tangent", media.flat_tangent_image),
    "set_step_tangent": ("Step Tangent", media.step_tangent_image),
    "set_plateau_tangent": ("Plateau Tangent", media.plateau_tangent_image),
}


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
    try:
        count = cmds.assignCommand(query=True, numElements=True) or 0
    except Exception:
        return mapping

    for index in range(1, int(count) + 1):
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
        mapping[str(name).replace("TKMTriggerName_", "", 1)] = combo
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


def _pixmap_for_icon(icon_path, size=18):
    if not icon_path:
        return QtGui.QPixmap()
    return QtGui.QIcon(icon_path).pixmap(wutil.DPI(size), wutil.DPI(size))


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
        QtCore.Qt.Key_Space: ("Space", "Space"),
        QtCore.Qt.Key_Tab: ("Tab", "Tab"),
        QtCore.Qt.Key_Return: ("Enter", "Enter"),
        QtCore.Qt.Key_Enter: ("Enter", "Enter"),
        QtCore.Qt.Key_Escape: ("Escape", "Escape"),
        QtCore.Qt.Key_Left: ("Left", "Left"),
        QtCore.Qt.Key_Right: ("Right", "Right"),
        QtCore.Qt.Key_Up: ("Up", "Up"),
        QtCore.Qt.Key_Down: ("Down", "Down"),
        QtCore.Qt.Key_Home: ("Home", "Home"),
        QtCore.Qt.Key_End: ("End", "End"),
        QtCore.Qt.Key_PageUp: ("PageUp", "PageUp"),
        QtCore.Qt.Key_PageDown: ("PageDown", "PageDown"),
        QtCore.Qt.Key_Insert: ("Insert", "Insert"),
        QtCore.Qt.Key_Minus: ("-", "-"),
        QtCore.Qt.Key_Equal: ("=", "="),
        QtCore.Qt.Key_Slash: ("/", "/"),
        QtCore.Qt.Key_Backslash: ("\\", "\\"),
        QtCore.Qt.Key_BracketLeft: ("[", "["),
        QtCore.Qt.Key_BracketRight: ("]", "]"),
        QtCore.Qt.Key_Semicolon: (";", ";"),
        QtCore.Qt.Key_Apostrophe: ("'", "'"),
        QtCore.Qt.Key_Comma: (",", ","),
        QtCore.Qt.Key_Period: (".", "."),
        QtCore.Qt.Key_QuoteLeft: ("`", "`"),
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
        display_key, maya_key = special_map[key]
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
    command_name = tool_data.get("command")
    if not command_name:
        return None
    return {
        "command": command_name,
        "title": tool_data.get("status_title") or tool_data.get("label") or _humanize(command_name),
        "icon_path": tool_data.get("icon_path"),
        "badge_text": None if tool_data.get("icon_path") else tool_data.get("text"),
    }


def _variant_command_row(tool_data, variant, shortcut_label=None):
    command_name = variant.get("command")
    if not command_name:
        return None
    icon_path = variant.get("icon_path") or tool_data.get("icon_path")
    return {
        "command": command_name,
        "title": shortcut_label or variant.get("status_title") or variant.get("label") or variant.get("description") or _humanize(command_name),
        "icon_path": icon_path,
        "badge_text": None if icon_path else variant.get("text") or tool_data.get("text"),
    }


def _manual_command_row(command_name):
    title, icon_path = HOTKEY_COMMAND_METADATA.get(command_name, (_humanize(command_name), None))
    return {
        "command": command_name,
        "title": title,
        "icon_path": icon_path,
        "badge_text": None,
    }


def _append_section_row(section, seen, title_lookup, icon_lookup, trigger_commands, row):
    if not row:
        return
    command_name = row.get("command")
    if not command_name or command_name in seen or command_name not in trigger_commands:
        return
    section["commands"].append(row)
    seen.add(command_name)
    title_lookup[command_name] = row["title"]
    icon_lookup[command_name] = row.get("icon_path")


def _append_section_tool_rows(section, seen, title_lookup, icon_lookup, trigger_commands, tool_id):
    tool_data = toolbox.get_tool(tool_id)
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


def _build_slider_hotkey_section(prefix, title, modes, default_icon=None):
    section = {"id": prefix, "title": title, "icon_path": default_icon, "commands": []}
    for mode in modes:
        if not isinstance(mode, dict):
            continue
        mode_icon = mode.get("icon") if isinstance(mode.get("icon"), str) and os.path.splitext(str(mode.get("icon")))[1] else None
        for value in trigger.SLIDER_BUTTON_VALUES:
            value_title = mode["label"] if int(value) == 0 else "{} {}".format(mode["label"], _slider_value_label(value))
            section["commands"].append(
                {
                    "command": "slider_{}_{}_{}".format(prefix.split("_", 1)[0], mode["key"], _slider_value_suffix(value)),
                    "title": value_title,
                    "icon_path": mode_icon,
                    "badge_text": None if mode_icon else str(mode.get("icon") or ""),
                }
            )
    return section


def _build_command_catalog():
    trigger_commands = set(trigger.list_commands())
    title_lookup = {}
    icon_lookup = {}
    sections = []

    for section_id, section_data in HOTKEY_SECTION_SPECS.items():
        section = {
            "id": section_id,
            "title": section_data["title"],
            "icon_path": section_data["icon_path"],
            "commands": [],
        }
        seen = set()

        for tool_id in section_data.get("tools", []):
            _append_section_tool_rows(section, seen, title_lookup, icon_lookup, trigger_commands, tool_id)

        for command_name in section_data.get("commands", []):
            _append_section_row(section, seen, title_lookup, icon_lookup, trigger_commands, _manual_command_row(command_name))

        for prefix in section_data.get("command_prefixes", []):
            for command_name in sorted(command for command in trigger_commands if command.startswith(prefix)):
                _append_section_row(section, seen, title_lookup, icon_lookup, trigger_commands, _manual_command_row(command_name))

        if section["commands"]:
            sections.append(section)

    from TheKeyMachine.sliders import BLEND_MODES, TANGENT_MODES, TWEEN_MODES

    for section in (
        _build_slider_hotkey_section("blend_slider", "Blend Slider", BLEND_MODES, HOTKEY_SECTION_ICONS["blend_slider"]),
        _build_slider_hotkey_section("tween_slider", "Tween Slider", TWEEN_MODES, HOTKEY_SECTION_ICONS["tween_slider"]),
        _build_slider_hotkey_section("tangent_slider", "Tangent Slider", TANGENT_MODES, HOTKEY_SECTION_ICONS["tangent_slider"]),
    ):
        filtered = [row for row in section["commands"] if row["command"] in trigger_commands]
        if not filtered:
            continue
        section["commands"] = filtered
        sections.append(section)
        for row in filtered:
            title_lookup[row["command"]] = row["title"]
            icon_lookup[row["command"]] = row.get("icon_path")

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
        self._icon_path = command_data.get("icon_path")
        self._pressed_icon = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tool_button = QtWidgets.QPushButton(command_data["title"])
        self.tool_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.tool_button.setFlat(True)
        self.tool_button.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        self.tool_button.setMinimumHeight(wutil.DPI(24))
        if self._icon_path:
            cw.QFlatHoverableIcon.apply(self.tool_button, self._icon_path, highlight=False)
            self._pressed_icon = cw.QFlatHoverableIcon._color_icon(QtGui.QIcon(self._icon_path), self._accent_color, self.tool_button.iconSize())
        elif command_data.get("badge_text"):
            self.tool_button.setIcon(QtGui.QIcon(_text_badge_pixmap(command_data.get("badge_text"))))
        self.tool_button.clicked.connect(lambda *_: trigger.invoke(self.command_name()))
        self.tool_button.pressed.connect(self._on_tool_pressed)
        self.tool_button.released.connect(self._on_tool_released)
        layout.addWidget(self.tool_button, 1)

        self.status_cell = HotkeyStatusLabel()
        self.status_cell.setFixedWidth(wutil.DPI(28))
        layout.addWidget(self.status_cell)

        self.edit = HotkeyCaptureEdit()
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

    def set_status(self, icon_path=None, tooltip="", tooltip_data=None):
        self.status_cell.setPixmap(_pixmap_for_icon(icon_path, size=16) if icon_path else QtGui.QPixmap())
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
        if self._icon_path:
            self.tool_button.setIcon(QtGui.QIcon(self._icon_path))

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.FocusIn):
            self.requestSelect.emit(self.command_name())
        return super().eventFilter(watched, event)


class TriggerHotkeysDialog(cd.QFlatDialog):
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

        main = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setContentsMargins(wutil.DPI(12), wutil.DPI(12), wutil.DPI(12), wutil.DPI(12))
        main_layout.setSpacing(wutil.DPI(8))

        title_wrap = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_wrap)
        title_layout.setContentsMargins(0, wutil.DPI(8), 0, wutil.DPI(10))
        title_layout.setSpacing(wutil.DPI(16))

        icon_size = wutil.DPI(51)

        self.window_icon = QtWidgets.QLabel()
        self.window_icon.setFixedSize(icon_size, icon_size)
        self.window_icon.setAlignment(QtCore.Qt.AlignCenter)
        hotkeys_pixmap = QtGui.QPixmap(media.hotkeys_image)
        if not hotkeys_pixmap.isNull():
            self.window_icon.setPixmap(
                hotkeys_pixmap.scaled(
                    icon_size,
                    icon_size,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        title_layout.addWidget(self.window_icon, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.window_title = QtWidgets.QLabel("Hotkeys")
        self.window_title.setStyleSheet("color:#d8d8d8;font-size:%spx;font-weight:bold;" % wutil.DPI(22))
        title_layout.addWidget(self.window_title, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        title_layout.addStretch(1)
        main_layout.addWidget(title_wrap)

        content_layout = QtWidgets.QGridLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setHorizontalSpacing(wutil.DPI(12))
        content_layout.setVerticalSpacing(wutil.DPI(8))
        content_layout.setColumnStretch(0, 0)
        content_layout.setColumnStretch(1, 1)
        content_layout.setRowStretch(1, 1)
        main_layout.addLayout(content_layout, 1)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.section_list = QtWidgets.QListWidget()
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

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.command_stack = QtWidgets.QStackedWidget()
        self.command_stack.setStyleSheet("QStackedWidget{background:transparent;}")
        right_layout.addWidget(self.command_stack, 1)

        self.tools_title = QtWidgets.QLabel("Tools")
        self.tools_title.setStyleSheet("color:#bcbcbc;font-size:%spx;" % wutil.DPI(11))
        self.section_title = QtWidgets.QLabel("Hotkeys")
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
                cd.QFlatDialogButton("Clear", callback=self.clear_hotkeys, icon=media.trash_image),
                cd.QFlatDialogButton("Apply", callback=self.apply_hotkeys, icon=media.apply_image, highlight=True),
                cd.QFlatDialogButton("Close", callback=self.request_close, icon=media.close_image),
            ],
            closeButton=False,
            highlight="Apply",
        )

    def _populate_sections(self):
        self.section_list.clear()
        for section in self._sections:
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(section.get("icon_path") or ""), section["title"])
            item.setData(QtCore.Qt.UserRole, section["id"])
            item.setSizeHint(QtCore.QSize(0, wutil.DPI(62)))
            self.section_list.addItem(item)
        if self.section_list.count():
            self.section_list.setCurrentRow(0)

    def _create_command_list(self, section_id):
        command_list = QtWidgets.QListWidget()
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
        command_list.currentItemChanged.connect(lambda current, previous, sid=section_id: self._on_command_item_changed(sid, current, previous))
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
            row = HotkeyCommandRow(command, self._title_lookup, self._icon_lookup, row_index=row_index)
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
        self._begin_section_build(section_id, section["commands"], batched=section_id.endswith("_slider"))

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
        self._draft_mapping = {name: _normalize_combo(combo) for name, combo in data.items() if _normalize_combo(combo)}
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


def create_TheKeyMachine_hotkeys(*args):
    return show_hotkeys_window(*args)


def set_smart_key():
    selected_objects = wutil.get_selected_objects()
    if not selected_objects:
        return
    current_time = cmds.currentTime(query=True)
    for obj in selected_objects:
        cmds.setKeyframe(obj, insert=True, time=current_time)


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


def insert_inbetween(*args):
    mel.eval("timeSliderEditKeys addInbetween")
    cmds.currentTime(cmds.currentTime(q=True) + 1)


def remove_inbetween(*args):
    mel.eval("timeSliderEditKeys removeInbetween")
    cmds.currentTime(cmds.currentTime(q=True) - 1)


def move_keyframes_left():
    import TheKeyMachine.mods.keyToolsMod as keyTools

    keyTools.move_keyframes_in_range(-1)


def move_keyframes_right():
    import TheKeyMachine.mods.keyToolsMod as keyTools

    keyTools.move_keyframes_in_range(1)
