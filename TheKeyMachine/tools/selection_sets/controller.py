import json
import os
import re

from maya import cmds

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

import TheKeyMachine.core.runtime_manager as runtime
from TheKeyMachine.core import selection_targets
from TheKeyMachine.tools.selection_sets import api as selectionSetsApi
from TheKeyMachine.widgets import util as wutil


class SelectionSetsController:
    color_names = dict(selectionSetsApi.selection_set_color_names)

    def __init__(self, owner=None):
        self.owner = owner

    def export_sets(self, file_path=None, *args):
        if not file_path:
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(None, "Export Sets", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        set_data = {"set_groups": []}

        for set_group in self.get_set_groups():
            set_group_data = {"name": set_group.replace("_setgroup", ""), "sets": []}
            sub_sel_sets = cmds.sets(set_group, q=True) or []
            for sub_sel_set in sub_sel_sets:
                if cmds.objExists(sub_sel_set):
                    split_name = sub_sel_set.split("_")
                    color_suffix = split_name[-1]
                    set_name = "_".join(split_name[:-1])
                    set_group_data["sets"].append(
                        {"name": set_name, "color_suffix": color_suffix, "objects": cmds.sets(sub_sel_set, q=True)}
                    )
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

        sel_set_name = "TheKeyMachine_SelectionSet"
        if not cmds.objExists(sel_set_name):
            cmds.sets(name=sel_set_name, empty=True)

        for set_group_data in set_data.get("set_groups", []):
            set_group_name = set_group_data["name"]
            set_group_name_with_suffix = f"{set_group_name}_setgroup"

            if not cmds.objExists(set_group_name_with_suffix):
                cmds.sets(name=set_group_name_with_suffix, empty=True)
                cmds.sets(set_group_name_with_suffix, add=sel_set_name)

            for set_info in set_group_data.get("sets", []):
                set_name = set_info["name"]
                color_suffix = set_info["color_suffix"]
                set_name_with_suffix = f"{set_name}_{color_suffix}"

                if not cmds.objExists(set_name_with_suffix):
                    new_set = cmds.sets(name=set_name_with_suffix, empty=True)
                    cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)
                    cmds.sets(new_set, add=set_group_name_with_suffix)

                for obj in set_info.get("objects", []):
                    if cmds.objExists(obj):
                        cmds.sets(obj, add=set_name_with_suffix)

        QtCore.QTimer.singleShot(500, self.create_buttons_for_sel_sets)

    def rename_setgroup(self, old_setgroup_name, new_setgroup_name, *args):
        new_setgroup_name = new_setgroup_name.strip()

        if not new_setgroup_name:
            return cmds.warning("Please enter a valid set group name")

        new_name = f"{new_setgroup_name}_setgroup"
        if old_setgroup_name == new_name:
            return

        try:
            cmds.rename(old_setgroup_name, new_name)
        except Exception as e:
            return cmds.warning(f"Error renaming set group: {e}")

        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def rename_set(self, old_set_name, new_set_name, set_group=None, *args):
        if not new_set_name.strip():
            return cmds.warning("Please enter a valid set name")

        current_color_suffix = old_set_name.rsplit("_", 1)[-1]
        new_set_name_with_color = f"{new_set_name}_{current_color_suffix}"

        if cmds.objExists(new_set_name_with_color):
            return cmds.warning(f"A set named '{new_set_name_with_color}' already exists. Please choose a different name")

        cmds.evalDeferred(lambda: cmds.rename(old_set_name, new_set_name_with_color))
        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def set_set_color(self, set_name, color_suffix, *args):
        set_node = cmds.ls(set_name)
        if not set_node:
            cmds.warning(f"Set '{set_name}' does not exist")
            return

        color_suffix = color_suffix.strip("_")
        current_color_suffix = set_name.rsplit("_", 1)[-1]
        new_set_name = set_name.replace(current_color_suffix, color_suffix)

        if cmds.objExists(new_set_name):
            cmds.warning(f"A set named '{new_set_name}' already exists. Please choose a different color")
            return

        cmds.rename(set_node, new_set_name)

        if cmds.window("changeSetColorWindow", exists=True):
            cmds.deleteUI("changeSetColorWindow")

        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def update_set_group_menu(self, combo_widget):
        combo_widget.clear()
        for set_group in self.get_set_groups():
            combo_widget.addItem(set_group.replace("_setgroup", ""), set_group)

    def get_set_groups(self):
        if cmds.objExists("TheKeyMachine_SelectionSet"):
            all_sets = cmds.sets("TheKeyMachine_SelectionSet", q=True) or []
            return [s for s in all_sets if s.endswith("_setgroup")]
        return []

    def get_selection_sets(self):
        sel_set_name = "TheKeyMachine_SelectionSet"
        if not cmds.objExists(sel_set_name):
            return []
        selection_sets = []
        for node in cmds.sets(sel_set_name, q=True) or []:
            if not cmds.objExists(node):
                continue
            if str(node).endswith("_setgroup"):
                continue
            selection_sets.append(node)
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
            selection = selection_targets.get_selected_objects()
        return self._find_matching_selection_set(selection)

    def show_matching_selection_set_message(self, set_name):
        if set_name:
            display_name = self.get_selection_set_display_name(set_name)
            wutil.make_inViewMessage(f"Selection already matches set: {display_name or set_name}")

    def _ensure_selection_sets_root(self):
        sel_set_name = "TheKeyMachine_SelectionSet"
        if not cmds.objExists(sel_set_name):
            cmds.sets(name=sel_set_name, empty=True)
        return sel_set_name

    def create_new_set_and_update_buttons(self, color_suffix, set_name_field, *args):
        selection = selection_targets.get_selected_objects()
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

        if selection_targets.get_selected_objects():
            cmds.sets(selection_targets.get_selected_objects(), add=new_set)

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
        selection = selection_targets.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to add")
        if not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")
        cmds.sets(selection, add=set_name)

    def remove_selection_from_set(self, set_name, *args):
        selection = selection_targets.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to remove")
        if not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")
        cmds.sets(selection, remove=set_name)

    def update_selection_to_set(self, set_name, *args):
        selection = selection_targets.get_selected_objects()
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
            if cmds.objExists("TheKeyMachine_SelectionSet"):
                try:
                    cmds.sets(subset, remove="TheKeyMachine_SelectionSet")
                except Exception:
                    pass
            cmds.delete(subset)
            removed_any = True

        if removed_any:
            cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def clear_selection_sets(self, *args):
        removed_any = False
        sel_set_name = "TheKeyMachine_SelectionSet"

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
            if cmds.objExists("TheKeyMachine_SelectionSet"):
                try:
                    cmds.sets(set_name, remove="TheKeyMachine_SelectionSet")
                except Exception:
                    pass
            cmds.delete(set_name)

        cmds.evalDeferred(self.create_buttons_for_sel_sets)

    def toggle_selection_sets_workspace(self, *args):
        selectionSetsApi.toggle_selection_sets_window(controller=self)
