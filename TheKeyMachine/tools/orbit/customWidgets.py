try:
    from PySide2 import QtCore, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtWidgets

import TheKeyMachine.tools.orbit.api as orbitApi
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.widgets import customWidgets as cw, util as wutil


class OrbitWindowMixin(FloatingToolWindowMixin):
    def _get_menu_items(self):
        import TheKeyMachine.core.toolbox as toolbox

        return [
            toolbox.get_tool("isolate_master"),
            toolbox.get_tool("align_selected_objects"),
            toolbox.get_tool("mod_tracer"),
            toolbox.get_tool("reset_objects_mods"),
            toolbox.get_tool("delete_all_animation"),
            toolbox.get_tool("selectOpposite"),
            toolbox.get_tool("copyOpposite"),
            toolbox.get_tool("mirror"),
            toolbox.get_tool("copy_animation"),
            toolbox.get_tool("paste_animation"),
            toolbox.get_tool("paste_insert_animation"),
            toolbox.get_tool("copy_pose"),
            toolbox.get_tool("paste_pose"),
            toolbox.get_tool("selectHierarchy"),
            toolbox.get_tool("mod_link_objects"),
            toolbox.get_tool("temp_pivot"),
            toolbox.get_tool("copy_worldspace_single_frame", label="Copy World Space Current Frame"),
            toolbox.get_tool("paste_worldspace_single_frame", label="Paste World Space Current Frame"),
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
        for tool_data in self._get_menu_items():
            self._create_orbit_tool_button(
                tool_data=tool_data,
                default_visible=tool_data["key"] in default_actions,
            )

    def _seed_orbit_visibility_settings(self):
        current_actions = set(orbitApi.load_orbit_configuration().values())
        for tool_data in self._get_menu_items():
            action_identifier = tool_data["key"]
            setting_key = f"pin_{action_identifier}"
            current_value = orbitApi.settings.get_setting(setting_key, None, namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE)
            if current_value is None:
                orbitApi.settings.set_setting(
                    setting_key,
                    action_identifier in current_actions,
                    namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE,
                )

    def _create_orbit_tool_button(self, tool_data, default_visible):
        label = tool_data.get("label") or tool_data.get("key")
        action_identifier = tool_data["key"]
        tooltip_text = tool_data.get("tooltip_template") or label
        description = tool_data.get("description") or tooltip_text

        btn = cw.create_tool_button_from_data(
            tool_data,
            tooltip_template=tooltip_text,
            description=description,
            status_title=tool_data.get("status_title", label),
            status_description=tool_data.get("status_description", description),
        )
        btn.setFixedSize(wutil.DPI(28), wutil.DPI(28))
        btn.setIconSize(QtCore.QSize(wutil.DPI(22), wutil.DPI(22)))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: self.tools_section.open_menu(b.mapToGlobal(pos)))

        self.tools_section.addWidget(
            btn,
            label=label,
            key=action_identifier,
            default_visible=default_visible,
            description=description,
            tooltip_template=tooltip_text,
        )
        return btn
