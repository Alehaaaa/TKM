import json
import os
import re

from maya import cmds

from TheKeyMachine.Qt import QtCore, QtWidgets

import TheKeyMachine.core.runtimeManager as runtime
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools.selection_sets import api as selectionSetsApi
from TheKeyMachine.widgets import util as wutil


SELECTION_SETS_ROOT = "TheKeyMachine_SelectionSet"
SET_GROUP_SUFFIX = "_setgroup"
ANIMBOT_SELECTION_SETS_ROOT = "animBot_Select_Sets"
ANIMBOT_COLOR_INDEX_TO_TKM_INDEX = {
    0: 1,
    1: 8,
    2: 14,
    3: 2,
    4: 3,
    5: 3,
    6: 4,
    7: 5,
    8: 6,
    9: 7,
    11: 9,
    12: 10,
    13: 11,
    14: 12,
    15: 13,
    17: 15,
    18: 19,
    19: 20,
    20: 21,
    21: 16,
    22: 17,
    23: 18,
    24: 22,
    25: 23,
    26: 24,
    27: 25,
    28: 26,
    29: 27,
}
TKM_SELECTION_COLOR_BY_INDEX = {color.index: color for color in selectionSetsApi.SELECTION_SET_COLORS}


def _selection_color_suffix_from_tkm_index(tkm_index):
    color = TKM_SELECTION_COLOR_BY_INDEX.get(tkm_index)
    return color.suffix if color else selectionSetsApi.SELECTION_SET_DEFAULT_COLOR.suffix


class SelectionSetsController:
    color_names = dict(selectionSetsApi.selection_set_color_names)

    def __init__(self, owner=None):
        self.owner = owner

    def export_sets(self, file_path=None, *args):
        if not file_path:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(None, "Export Sets", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        set_data = {"sets": [], "set_groups": []}

        for subset in self._get_direct_selection_sets():
            set_data["sets"].append(self._serialize_selection_set(subset))

        for set_group in self.get_set_groups():
            set_group_data = {"name": set_group.replace(SET_GROUP_SUFFIX, ""), "sets": []}
            sub_sel_sets = cmds.sets(set_group, q=True) or []
            for sub_sel_set in sub_sel_sets:
                if cmds.objExists(sub_sel_set):
                    set_group_data["sets"].append(self._serialize_selection_set(sub_sel_set))
            if set_group_data["sets"]:
                set_data["set_groups"].append(set_group_data)

        export_dir = os.path.dirname(file_path)
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)

        with open(file_path, "w") as file:
            json.dump(set_data, file, indent=4)

    def import_sets(self, file_path=None, *args):
        if not file_path:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Import Sets", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        if not os.path.isfile(file_path):
            wutil.make_inViewMessage("Selection sets file not found")
            return

        with open(file_path, "r") as file:
            set_data = json.load(file)

        sel_set_name = self._ensure_selection_sets_root()

        for set_info in set_data.get("sets", []):
            self._import_selection_set(set_info, sel_set_name)

        for set_group_data in set_data.get("set_groups", []):
            set_group_name = set_group_data["name"]
            set_group_name_with_suffix = f"{set_group_name}{SET_GROUP_SUFFIX}"

            if not cmds.objExists(set_group_name_with_suffix):
                cmds.sets(name=set_group_name_with_suffix, empty=True)
                cmds.sets(set_group_name_with_suffix, add=sel_set_name)

            for set_info in set_group_data.get("sets", []):
                self._import_selection_set(set_info, set_group_name_with_suffix)

        QtCore.QTimer.singleShot(500, self.create_buttons_for_sel_sets)

    def rename_setgroup(self, old_setgroup_name, new_setgroup_name, *args):
        new_setgroup_name = new_setgroup_name.strip()

        if not new_setgroup_name:
            return wutil.make_inViewMessage("Please enter a valid set group name")

        new_name = f"{new_setgroup_name}{SET_GROUP_SUFFIX}"
        if old_setgroup_name == new_name:
            return

        try:
            cmds.rename(old_setgroup_name, new_name)
        except Exception as e:
            return wutil.make_inViewMessage(f"Error renaming set group: {e}")

        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def rename_set(self, old_set_name, new_set_name, set_group=None, *args):
        if not new_set_name.strip():
            return wutil.make_inViewMessage("Please enter a valid set name")

        current_color_suffix = old_set_name.rsplit("_", 1)[-1]
        new_set_name_with_color = f"{new_set_name}_{current_color_suffix}"

        if cmds.objExists(new_set_name_with_color):
            return wutil.make_inViewMessage(f"A set named '{new_set_name_with_color}' already exists. Please choose a different name")

        cmds.evalDeferred(lambda: cmds.rename(old_set_name, new_set_name_with_color))
        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def set_set_color(self, set_name, color_suffix, *args):
        set_node = cmds.ls(set_name)
        if not set_node:
            return wutil.make_inViewMessage(f"Set '{set_name}' does not exist")

        color_suffix = color_suffix.strip("_")
        set_base_name, _, _current_color_suffix = set_name.rpartition("_")
        if not set_base_name:
            return wutil.make_inViewMessage(f"Set '{set_name}' does not have a color suffix")
        new_set_name = f"{set_base_name}_{color_suffix}"

        if cmds.objExists(new_set_name):
            return wutil.make_inViewMessage(f"A set named '{new_set_name}' already exists. Please choose a different color")

        cmds.rename(set_node[0], new_set_name)

        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def update_set_group_menu(self, combo_widget):
        combo_widget.clear()
        for set_group in self.get_set_groups():
            combo_widget.addItem(set_group.replace(SET_GROUP_SUFFIX, ""), set_group)

    def get_set_groups(self):
        if cmds.objExists(SELECTION_SETS_ROOT):
            all_sets = cmds.sets(SELECTION_SETS_ROOT, q=True) or []
            return [s for s in all_sets if s.endswith(SET_GROUP_SUFFIX)]
        return []   

    def _get_direct_selection_sets(self):
        if not cmds.objExists(SELECTION_SETS_ROOT):
            return []
        all_sets = cmds.sets(SELECTION_SETS_ROOT, q=True) or []
        return [s for s in all_sets if cmds.objExists(s) and not str(s).endswith(SET_GROUP_SUFFIX)]

    def get_selection_sets(self):
        if not cmds.objExists(SELECTION_SETS_ROOT):
            return []
        selection_sets = []
        seen = set()

        def _append(node):
            if not cmds.objExists(node):
                return
            if str(node).endswith(SET_GROUP_SUFFIX):
                return
            if node in seen:
                return
            seen.add(node)
            selection_sets.append(node)

        for node in cmds.sets(SELECTION_SETS_ROOT, q=True) or []:
            if str(node).endswith(SET_GROUP_SUFFIX):
                for subset in cmds.sets(node, q=True) or []:
                    _append(subset)
                continue
            _append(node)
        return selection_sets

    def _normalize_scene_members(self, items):
        if not items:
            return set()
        normalized = cmds.ls(items, long=True) or []
        return set(normalized or items)

    def _find_matching_selection_set(self, selection):
        target_members = self._normalize_scene_members(selection)
        if not target_members:
            return None

        for subset in self.get_selection_sets():
            if not cmds.objExists(subset):
                continue
            subset_members = self._normalize_scene_members(cmds.sets(subset, q=True) or [])
            if subset_members == target_members:
                return subset
        return None

    def get_selection_set_display_name(self, set_name):
        if not set_name:
            return ""
        split_name = str(set_name).split("_")
        if len(split_name) >= 2:
            return "_".join(split_name[:-1])
        return str(set_name)

    def find_matching_selection_set(self, selection=None):
        if selection is None:
            selection = selectionMod.get_selected_objects()
        return self._find_matching_selection_set(selection)

    def show_matching_selection_set_message(self, set_name):
        if set_name:
            display_name = self.get_selection_set_display_name(set_name)
            wutil.make_inViewMessage(f"Selection already matches set: {display_name or set_name}")

    def _sanitize_set_name(self, name):
        parts = [part for part in re.split(r"[^A-Za-z0-9]+", str(name or "")) if part]
        sanitized = "_".join(parts)
        sanitized = re.sub(r"^[^A-Za-z_]+", "", sanitized)
        return sanitized or "Selection_Set"

    def _ensure_selection_sets_root(self):
        sel_set_name = SELECTION_SETS_ROOT
        if not cmds.objExists(sel_set_name):
            cmds.sets(name=sel_set_name, empty=True)
        return sel_set_name

    def _serialize_selection_set(self, set_name):
        base_name, _, color_suffix = set_name.rpartition("_")
        return {
            "name": base_name or set_name,
            "color_suffix": color_suffix,
            "objects": cmds.sets(set_name, q=True) or [],
        }

    def _import_selection_set(self, set_info, parent_set):
        set_name = set_info.get("name")
        color_suffix = str(set_info.get("color_suffix", "")).strip("_")
        if not set_name or not color_suffix:
            return None

        set_name_with_suffix = f"{set_name}_{color_suffix}"
        if not cmds.objExists(set_name_with_suffix):
            new_set = cmds.sets(name=set_name_with_suffix, empty=True)
            cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)
            cmds.sets(new_set, add=parent_set)
        else:
            new_set = set_name_with_suffix
            if not cmds.attributeQuery("hidden", node=new_set, exists=True):
                cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)
            try:
                cmds.sets(new_set, add=parent_set)
            except Exception:
                pass

        for obj in set_info.get("objects", []):
            if cmds.objExists(obj):
                cmds.sets(obj, add=new_set)
        return new_set

    def create_selection_set_from_data(self, name, color_suffix, objects, refresh=True):
        valid_objects = cmds.ls(objects or [], long=True) or []
        if not valid_objects:
            return None

        existing_match = self._find_matching_selection_set(valid_objects)
        if existing_match:
            return existing_match

        base_name = self._sanitize_set_name(name)
        color_suffix = color_suffix if str(color_suffix).startswith("_") else f"_{color_suffix}"
        sel_set_name = self._ensure_selection_sets_root()

        candidate = f"{base_name}{color_suffix}"
        index = 1
        while cmds.objExists(candidate):
            candidate = f"{base_name}_{index}{color_suffix}"
            index += 1

        new_set = cmds.sets(name=candidate, empty=True)
        cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)
        cmds.sets(valid_objects, add=new_set)
        cmds.sets(new_set, add=sel_set_name)

        if refresh:
            self.create_buttons_for_sel_sets()
        return new_set

    def _animbot_root(self):
        matches = cmds.ls(ANIMBOT_SELECTION_SETS_ROOT, long=True) or []
        if not matches:
            matches = cmds.ls(f"*|{ANIMBOT_SELECTION_SETS_ROOT}", long=True) or []
        for node in matches:
            if str(node).endswith(f"|{ANIMBOT_SELECTION_SETS_ROOT}"):
                return node
        return matches[0] if matches else None

    def _animbot_color_suffix(self, color_group):
        if not cmds.attributeQuery("colorIndex", node=color_group, exists=True):
            return None
        try:
            animbot_index = int(cmds.getAttr(f"{color_group}.colorIndex"))
        except Exception:
            return None
        tkm_index = ANIMBOT_COLOR_INDEX_TO_TKM_INDEX.get(animbot_index)
        return _selection_color_suffix_from_tkm_index(tkm_index) if tkm_index else None

    def _animbot_selection_sets(self):
        root = self._animbot_root()
        if not root:
            return []

        entries = []
        color_groups = cmds.listRelatives(root, children=True, type="transform", fullPath=True) or []
        for color_group in color_groups:
            color_suffix = self._animbot_color_suffix(color_group)
            if not color_suffix:
                continue
            set_nodes = cmds.listRelatives(color_group, children=True, type="transform", fullPath=True) or []
            for set_node in set_nodes:
                if not cmds.attributeQuery("contents", node=set_node, exists=True):
                    continue
                contents = cmds.getAttr(f"{set_node}.contents") or ""
                objects = [item for item in str(contents).split(" ") if item]
                valid_objects = cmds.ls(objects, long=True) or []
                if not valid_objects:
                    continue
                entries.append(
                    {
                        "name": str(set_node).rsplit("|", 1)[-1],
                        "color_suffix": color_suffix,
                        "objects": valid_objects,
                    }
                )
        return entries

    def pending_animbot_selection_sets(self):
        pending = []
        for entry in self._animbot_selection_sets():
            if self._find_matching_selection_set(entry["objects"]):
                continue
            pending.append(entry)
        return pending

    def convert_animbot_selection_sets(self, entries=None):
        entries = entries if entries is not None else self.pending_animbot_selection_sets()
        created = []
        for entry in entries:
            new_set = self.create_selection_set_from_data(
                entry.get("name"),
                entry.get("color_suffix"),
                entry.get("objects"),
                refresh=False,
            )
            if new_set:
                created.append(new_set)
        if created:
            self.create_buttons_for_sel_sets()
        return created

    def _delete_empty_set_groups(self):
        for set_group in list(self.get_set_groups()):
            if not cmds.objExists(set_group):
                continue
            try:
                members = cmds.sets(set_group, q=True) or []
            except Exception:
                members = []
            if members:
                continue
            try:
                cmds.delete(set_group)
            except Exception:
                pass

    def create_new_set_and_update_buttons(self, color_suffix, set_name_field, *args):
        selection = selectionMod.get_selected_objects()
        if not selection:
            wutil.make_inViewMessage("Select something first")
            return False

        matching_set = self._find_matching_selection_set(selection)
        if matching_set:
            self.show_matching_selection_set_message(matching_set)
            return False

        new_set_name = set_name_field.text().replace(" ", "_")
        sel_set_name = self._ensure_selection_sets_root()

        if not re.match("^[a-zA-Z_][a-zA-Z0-9_]*$", new_set_name):
            cmds.warning("Invalid set name. Name can't start with a number or contain invalid characters")
            return False

        new_set_name += f"{color_suffix}"
        if cmds.objExists(new_set_name):
            cmds.warning(f"{new_set_name} already exists")
            return False

        new_set = cmds.sets(name=new_set_name, empty=True)
        cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)

        if selectionMod.get_selected_objects():
            cmds.sets(selectionMod.get_selected_objects(), add=new_set)

        cmds.sets(new_set, add=sel_set_name)
        self.create_buttons_for_sel_sets()
        set_name_field.clear()
        return True

    def handle_set_selection(self, set_name, shift_pressed, ctrl_pressed):
        mods = runtime.get_modifier_mask()
        shift_pressed = bool(mods & 1)
        ctrl_pressed = bool(mods & 4)

        if cmds.objExists(set_name):
            if shift_pressed:
                cmds.select(set_name, add=True)
            elif ctrl_pressed:
                cmds.select(set_name, d=True)
            else:
                cmds.select(set_name)

    def add_selection_to_set(self, set_name, *args):
        selection = selectionMod.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to add")
        if not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")
        cmds.sets(selection, add=set_name)

    def remove_selection_from_set(self, set_name, *args):
        selection = selectionMod.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to remove")
        if not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")
        cmds.sets(selection, remove=set_name)

    def update_selection_to_set(self, set_name, *args):
        selection = selectionMod.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to update")
        if not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")

        current_members = cmds.sets(set_name, q=True) or []
        if current_members:
            cmds.sets(current_members, remove=set_name)
        cmds.sets(selection, add=set_name)

    def delete_sets_by_color_suffix(self, color_suffix, *args):
        target_suffix = color_suffix if str(color_suffix).startswith("_") else f"_{color_suffix}"
        removed_any = False

        for subset in list(self.get_selection_sets()):
            if not cmds.objExists(subset) or not subset.endswith(target_suffix):
                continue
            if cmds.objExists(SELECTION_SETS_ROOT):
                try:
                    cmds.sets(subset, remove=SELECTION_SETS_ROOT)
                except Exception:
                    pass
            cmds.delete(subset)
            removed_any = True

        if removed_any:
            self._delete_empty_set_groups()
            cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def clear_selection_sets(self, *args):
        removed_any = False
        sel_set_name = SELECTION_SETS_ROOT

        for subset in list(self.get_selection_sets()):
            if not cmds.objExists(subset):
                continue
            try:
                if cmds.objExists(sel_set_name):
                    cmds.sets(subset, remove=sel_set_name)
            except Exception:
                pass
            try:
                cmds.delete(subset)
                removed_any = True
            except Exception:
                pass

        self._delete_empty_set_groups()

        if cmds.objExists(sel_set_name):
            try:
                members = cmds.sets(sel_set_name, q=True) or []
            except Exception:
                members = []
            if not members:
                try:
                    cmds.delete(sel_set_name)
                except Exception:
                    pass

        if removed_any:
            selectionSetsApi.refresh_selection_sets_window()
            wutil.make_inViewMessage("All selection sets cleared")

    def create_buttons_for_sel_sets(self, *args):
        selectionSetsApi.refresh_selection_sets_window()

    def remove_set_and_update_buttons(self, set_name, set_group=None, *args):
        if cmds.objExists(set_name):
            if cmds.objExists(SELECTION_SETS_ROOT):
                try:
                    cmds.sets(set_name, remove=SELECTION_SETS_ROOT)
                except Exception:
                    pass
            cmds.delete(set_name)

        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def toggle_selection_sets_workspace(self, *args):
        selectionSetsApi.toggle_selection_sets_window(controller=self)
