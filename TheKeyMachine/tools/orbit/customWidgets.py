try:
    from PySide2 import QtCore, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtWidgets

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.tools.orbit.api as orbitApi
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.widgets import customWidgets as cw, util as wutil


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
        while self.header_left_layout.count():
            item = self.header_left_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.tools_section = cw.QFlatSectionWidget(
            spacing=wutil.DPI(2),
            hiddeable=True,
            settings_namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE,
        )
        self.tools_section.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        section_layout = self.tools_section.layout()
        if section_layout:
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
        self.tools_section.setContentsMargins(0, 0, 0, 0)
        self.set_header_left_widget(self.tools_section, stretch=1)

        self._seed_orbit_visibility_settings()

        default_actions = set(orbitApi.DEFAULT_ORBIT_CONFIGURATION.values())
        for icon_path, label, action_identifier, tooltip_text in self._get_menu_items():
            self._create_orbit_tool_button(
                icon_path=icon_path,
                label=label,
                action_identifier=action_identifier,
                tooltip_text=tooltip_text,
                default_visible=action_identifier in default_actions,
            )

    def _seed_orbit_visibility_settings(self):
        current_actions = set(orbitApi.load_orbit_configuration().values())
        for _icon_path, _label, action_identifier, _tooltip_text in self._get_menu_items():
            setting_key = f"pin_{action_identifier}"
            current_value = orbitApi.settings.get_setting(setting_key, None, namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE)
            if current_value is None:
                orbitApi.settings.set_setting(
                    setting_key,
                    action_identifier in current_actions,
                    namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE,
                )

    def _create_orbit_tool_button(self, icon_path, label, action_identifier, tooltip_text, default_visible):
        btn = cw.QFlatToolButton(
            icon=icon_path or None,
            tooltip_template=tooltip_text,
            description=tooltip_text,
        )
        btn.setFixedSize(wutil.DPI(26), wutil.DPI(26))
        btn.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        btn.clicked.connect(lambda *_args, action=action_identifier: orbitApi.execute_action(action))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: self.tools_section.open_menu(b.mapToGlobal(pos)))

        self.tools_section.addWidget(
            btn,
            label=label,
            key=action_identifier,
            default_visible=default_visible,
            description=tooltip_text,
            tooltip_template=tooltip_text,
        )
        return btn
