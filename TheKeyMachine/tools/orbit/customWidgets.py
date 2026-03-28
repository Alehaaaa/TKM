from functools import partial

try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.tools.orbit.api as orbitApi
from TheKeyMachine.widgets import customWidgets as cw, util as wutil
from TheKeyMachine.tools.common import FloatingToolWindowMixin

class OrbitWindowMixin(FloatingToolWindowMixin):
    def _get_menu_items(self):
        import TheKeyMachine.mods.helperMod as helper

        return [
            (media.isolate_image, "Isolate", "isolate_master", getattr(helper, "isolate_tooltip_text", "Isolate")),
            (media.align_menu_image, "Align", "align_selected_objects", getattr(helper, "align_tooltip_text", "Align")),
            (media.tracer_image, "Tracer", "mod_tracer", getattr(helper, "tracer_tooltip_text", "Tracer")),
            (media.reset_animation_image, "Reset Values", "reset_objects_mods", getattr(helper, "reset_values_tooltip_text", "Reset Values")),
            (media.delete_animation_image, "Delete Animation", "deleteAnimation", getattr(helper, "delete_animation_tooltip_text", "Delete Animation")),
            (media.opposite_select_image, "Select Opposite", "selectOpposite", getattr(helper, "opposite_select_tooltip_text", "Select Opposite")),
            (media.opposite_copy_image, "Copy Opposite", "copyOpposite", getattr(helper, "opposite_copy_tooltip_text", "Copy Opposite")),
            (media.mirror_image, "Mirror", "mirror", getattr(helper, "mirror_tooltip_text", "Mirror")),
            (media.copy_animation_image, "Copy Animation", "copy_animation", getattr(helper, "copy_animation_tooltip_text", "Copy Animation")),
            (media.paste_animation_image, "Paste Animation", "paste_animation", getattr(helper, "paste_animation_tooltip_text", "Paste Animation")),
            (
                media.paste_insert_animation_image,
                "Paste Insert Animation",
                "paste_insert_animation",
                getattr(helper, "paste_insert_animation_tooltip_text", "Paste Insert Animation"),
            ),
            (media.copy_pose_image, "Copy Pose", "copy_pose", getattr(helper, "copy_pose_tooltip_text", "Copy Pose")),
            (media.paste_pose_image, "Paste Pose", "paste_pose", getattr(helper, "copy_pose_tooltip_text", "Paste Pose")),
            (
                media.select_hierarchy_image,
                "Select Hierarchy",
                "selectHierarchy",
                getattr(helper, "select_hierarchy_tooltip_text", "Select Hierarchy"),
            ),
            (media.link_objects_image, "Copy/Paste Link", "mod_link_objects", getattr(helper, "link_objects_tooltip_text", "Link objects")),
            (media.temp_pivot_image, "Temp Pivot", "temp_pivot", getattr(helper, "temp_pivot_tooltip_text", "Temp Pivot")),
            (
                media.worldspace_copy_frame_image,
                "Copy World Space Current Frame",
                "copy_worldspace_single_frame",
                getattr(helper, "copy_worldspace_tooltip_text", "Copy World Space"),
            ),
            (
                media.worldspace_paste_frame_image,
                "Paste World Space Current Frame",
                "paste_worldspace_single_frame",
                getattr(helper, "paste_worldspace_tooltip_text", "Paste World Space"),
            ),
        ]

    def _setup_orbit_ui(self):
        self.clear_header_right_widgets()

        self.orbit_buttons = []
        self.button_widgets = {}

        self.button_flow_container = cw.QFlowContainer()
        self.button_flow_layout = cw.QFlowLayout(
            self.button_flow_container,
            margin=0,
            Hspacing=wutil.DPI(6),
            Vspacing=wutil.DPI(6),
            alignment=QtCore.Qt.AlignLeft,
        )
        self.button_flow_container.setLayout(self.button_flow_layout)
        self.button_flow_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.set_header_left_widget(self.button_flow_container, stretch=1)

        orbitApi.orbit_configuration = orbitApi.load_orbit_configuration()

        button_keys = sorted(
            [k for k in orbitApi.orbit_configuration.keys() if k.startswith("button")],
            key=lambda x: int(x.replace("button", "")) if x.replace("button", "").isdigit() else 99,
        )

        for button_id in button_keys:
            self._create_orbit_button(button_id, orbitApi.orbit_configuration.get(button_id, ""))

        self.add_button = cw.QFlatToolButton(
            icon=media.add_image,
            tooltip_template="Add Orbit Tool",
            description="Add another action button to the floating Orbit tool palette.",
        )
        self.add_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.add_button.clicked.connect(self._setup_add_button_menu)
        self.add_button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.add_button.customContextMenuRequested.connect(lambda *_: self._setup_add_button_menu())
        self.add_header_right_widget(self.add_button, before_close=True)

    def _remove_from_flow_layout(self, widget):
        if not hasattr(self, "button_flow_layout"):
            return
        for index in range(self.button_flow_layout.count()):
            item = self.button_flow_layout.itemAt(index)
            if item and item.widget() is widget:
                removed = self.button_flow_layout.takeAt(index)
                if removed:
                    child = removed.widget()
                    if child:
                        child.setParent(None)
                break

    def _get_action_display_info(self, action_identifier):
        icon_path = orbitApi.orbit_action_icons.get(orbitApi.orbit_actions.get(action_identifier, ""), media.isolate_image)
        label = "Tool"
        tooltip_text = label

        for icon_path_item, label_item, action_name, tooltip in self._get_menu_items():
            if action_name == action_identifier:
                icon_path = icon_path_item
                label = label_item
                tooltip_text = tooltip or label_item
                break

        return icon_path, label, tooltip_text

    def _create_orbit_button(self, button_id, action_identifier):
        icon_path, _label, tooltip_text = self._get_action_display_info(action_identifier)

        btn = cw.QFlatToolButton(icon=icon_path or None, tooltip_template=tooltip_text)
        btn.setFixedSize(wutil.DPI(26), wutil.DPI(26))
        btn.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        btn.clicked.connect(partial(orbitApi.execute_action, action_identifier))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(partial(self._setup_orbit_button_menu, btn, button_id))

        self.button_flow_layout.addWidget(btn)
        self.orbit_buttons.append(btn)
        self.button_widgets[button_id] = btn
        return btn

    def _update_button(self, btn, action_identifier, button_id):
        icon_path, label, tooltip_text = self._get_action_display_info(action_identifier)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setToolTipData(text=label, tooltip_template=tooltip_text, description=tooltip_text)
        try:
            btn.clicked.disconnect()
        except Exception:
            pass
        btn.clicked.connect(partial(orbitApi.execute_action, action_identifier))
        if action_identifier in orbitApi.orbit_actions:
            orbitApi.orbit_configuration[button_id] = action_identifier
            orbitApi.save_orbit_button_config()

    def _setup_orbit_button_menu(self, btn, button_id, *_):
        menu = cw.OpenMenuWidget()
        action_group = QtGui.QActionGroup(menu)
        action_group.setExclusive(True)

        current_action = orbitApi.orbit_configuration.get(button_id, "")
        used_actions = {value for key, value in orbitApi.orbit_configuration.items() if key != button_id and key.startswith("button")}

        for icon_path, label, action_ident, tooltip_text in self._get_menu_items():
            action = menu.addAction(QtGui.QIcon(icon_path), label, tooltip_template=tooltip_text)
            action.setCheckable(True)
            action_group.addAction(action)

            if action_ident == current_action:
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.setChecked(False)
                if action_ident in used_actions:
                    action.setEnabled(False)
                else:
                    action.triggered.connect(partial(self._update_button, btn, action_ident, button_id))

        menu.addSeparator()
        remove_action = menu.addAction(QtGui.QIcon(media.close_image), "Remove this Button")
        remove_action.triggered.connect(lambda: (self._remove_button(button_id), menu.close()))
        menu.exec_(QtGui.QCursor.pos())

    def _setup_add_button_menu(self, *_):
        menu = cw.OpenMenuWidget()
        add_menu_actions = {}

        for icon_path, label, action_ident, tooltip_text in self._get_menu_items():
            action = menu.addAction(QtGui.QIcon(icon_path), label, tooltip_template=tooltip_text)
            action.setCheckable(True)
            add_menu_actions[action_ident] = action
            action.setChecked(self._is_action_assigned(action_ident))
            action.toggled.connect(partial(self._handle_add_action_toggle, action, action_ident))

        menu.addSeparator()
        menu.addAction(QtGui.QIcon(media.default_dot_image), "Pin Defaults").triggered.connect(
            lambda: self._pin_default_tools(add_menu_actions)
        )
        menu.addAction(QtGui.QIcon(media.default_dot_image), "Pin All").triggered.connect(lambda: self._pin_all_tools(add_menu_actions))
        menu.aboutToShow.connect(lambda: self._sync_add_menu_actions(add_menu_actions))
        menu.exec_(QtGui.QCursor.pos())

    def _handle_add_action_toggle(self, action, action_identifier, checked):
        is_assigned = self._is_action_assigned(action_identifier)
        if checked:
            if not is_assigned:
                self._add_new_tool(action_identifier)
            else:
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
        else:
            if is_assigned:
                self._remove_action_assignment(action_identifier)
            action.blockSignals(True)
            action.setChecked(self._is_action_assigned(action_identifier))
            action.blockSignals(False)

    def _is_action_assigned(self, action_identifier):
        return any(value == action_identifier for key, value in orbitApi.orbit_configuration.items() if key.startswith("button"))

    def _remove_action_assignment(self, action_identifier):
        for key, value in list(orbitApi.orbit_configuration.items()):
            if key.startswith("button") and value == action_identifier:
                self._remove_button(key)
                break

    def _add_new_tool(self, action_identifier):
        numeric_keys = [
            int(k.replace("button", "")) for k in orbitApi.orbit_configuration.keys() if k.startswith("button") and k.replace("button", "").isdigit()
        ]
        button_id = f"button{max(numeric_keys + [0]) + 1}"
        orbitApi.orbit_configuration[button_id] = action_identifier
        orbitApi.save_orbit_button_config()
        self._create_orbit_button(button_id, action_identifier)

    def _sync_add_menu_actions(self, add_menu_actions):
        for action_identifier, action in add_menu_actions.items():
            if action is None:
                continue
            action.blockSignals(True)
            action.setChecked(self._is_action_assigned(action_identifier))
            action.blockSignals(False)
        if add_menu_actions:
            first_action = next(iter(add_menu_actions.values()))
            menu = first_action.parent() if first_action else None
            if menu:
                menu.update()
                menu.repaint()

    def _reset_orbit_buttons(self, new_config):
        for button_id in list(self.button_widgets.keys()):
            self._remove_button(button_id)

        orbitApi.orbit_configuration.clear()
        orbitApi.orbit_configuration.update(orbitApi.sanitize_orbit_configuration(new_config))
        orbitApi.save_orbit_button_config()

        for button_id in sorted(orbitApi.orbit_configuration.keys(), key=orbitApi._orbit_button_sort_key):
            self._create_orbit_button(button_id, orbitApi.orbit_configuration[button_id])

    def _pin_default_tools(self, add_menu_actions=None):
        self._reset_orbit_buttons(dict(orbitApi.DEFAULT_ORBIT_CONFIGURATION))
        if add_menu_actions:
            self._sync_add_menu_actions(add_menu_actions)

    def _pin_all_tools(self, add_menu_actions=None):
        all_config = {f"button{index}": action_ident for index, (_, _, action_ident, _) in enumerate(self._get_menu_items(), start=1)}
        self._reset_orbit_buttons(all_config)
        if add_menu_actions:
            self._sync_add_menu_actions(add_menu_actions)

    def _remove_button(self, button_id):
        btn = self.button_widgets.pop(button_id, None)
        if button_id in orbitApi.orbit_configuration:
            del orbitApi.orbit_configuration[button_id]
            orbitApi.save_orbit_button_config()

        if btn:
            self._remove_from_flow_layout(btn)
            if btn in self.orbit_buttons:
                self.orbit_buttons.remove(btn)
            btn.deleteLater()
