from TheKeyMachine.Qt import QtCore, QtWidgets  # type: ignore

import TheKeyMachine.tools.orbit.api as orbitApi
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.widgets import customWidgets as cw, util as wutil


ORBIT_BUTTON_SIZE = wutil.DPI(28)
ORBIT_ICON_SIZE = wutil.DPI(22)
ORBIT_FLOW_SPACING = wutil.DPI(2)


class OrbitFlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=0):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self._row_size(self._visible_items())

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._visible_items():
            size = size.expandedTo(item.minimumSize())
        return self._with_margins(size)

    def _visible_items(self):
        return [item for item in self._items if not self._is_hidden(item)]

    def _is_hidden(self, item):
        widget = item.widget()
        return bool(widget and widget.isHidden())

    def _with_margins(self, size):
        margins = self.contentsMargins()
        return size + QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _row_size(self, items):
        width = 0
        height = 0
        for index, item in enumerate(items):
            item_size = item.sizeHint()
            width += item_size.width()
            if index:
                width += self._spacing
            height = max(height, item_size.height())
        return self._with_margins(QtCore.QSize(width, height))

    def _build_rows(self, width):
        rows = []
        row = []
        row_width = 0
        row_height = 0

        for item in self._visible_items():
            item_size = item.sizeHint()
            next_width = item_size.width() if not row else row_width + self._spacing + item_size.width()
            if row and next_width > width:
                rows.append((row, row_width, row_height))
                row = []
                row_width = 0
                row_height = 0

            row.append(item)
            row_width = item_size.width() if row_width == 0 else row_width + self._spacing + item_size.width()
            row_height = max(row_height, item_size.height())

        if row:
            rows.append((row, row_width, row_height))
        return rows

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        width = max(0, rect.width() - margins.left() - margins.right())
        rows = self._build_rows(width)

        for row, row_width, row_height in rows:
            if not test_only:
                current_x = x + max(0, (width - row_width) // 2)
                for item in row:
                    item_size = item.sizeHint()
                    current_y = y + max(0, (row_height - item_size.height()) // 2)
                    item.setGeometry(QtCore.QRect(QtCore.QPoint(current_x, current_y), item_size))
                    current_x += item_size.width() + self._spacing
            y += row_height + self._spacing

        if rows:
            y -= self._spacing
        return y - rect.y() + margins.bottom()


class OrbitToolSection(cw.QFlatSectionWidget):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            spacing=ORBIT_FLOW_SPACING,
            hiddeable=True,
            settings_namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE,
        )
        self._use_centered_flow_layout()

    def _use_centered_flow_layout(self):
        QtWidgets.QWidget().setLayout(self.layout())
        layout = OrbitFlowLayout(
            self,
            margin=0,
            spacing=ORBIT_FLOW_SPACING,
        )
        self.setLayout(layout)
        self.setContentsMargins(0, 0, 0, 0)

        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.layout().heightForWidth(width)

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        layout = self.layout()
        if layout:
            layout.setGeometry(self.rect())


class OrbitWindowMixin(FloatingToolWindowMixin):
    def _get_menu_items(self):
        import TheKeyMachine.core.toolbox as toolbox

        return [
            toolbox.get_tool("isolate_master"),
            toolbox.get_tool("align_objects"),
            toolbox.get_tool("create_tracer"),
            toolbox.get_tool("default_object_values"),
            toolbox.get_tool("delete_all_animation"),
            toolbox.get_tool("select_opposite"),
            toolbox.get_tool("opposite_copy"),
            toolbox.get_tool("mirror"),
            toolbox.get_tool("copy_animation"),
            toolbox.get_tool("paste_animation"),
            toolbox.get_tool("paste_insert_animation"),
            toolbox.get_tool("copy_pose"),
            toolbox.get_tool("paste_pose"),
            toolbox.get_tool("select_hierarchy"),
            toolbox.get_tool("link_copy"),
            toolbox.get_tool("temp_pivot"),
            toolbox.get_tool("ws_copy_frame", label="Copy World Space Current Frame"),
            toolbox.get_tool("ws_paste_frame", label="Paste World Space Current Frame"),
        ]

    def _setup_orbit_ui(self):
        self._orbit_flow_can_resize_window = False
        self._orbit_flow_resizing_window = False
        self.tools_section = OrbitToolSection(self)
        self.header_left_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.set_header_left_widget(self.tools_section, stretch=1)
        self._seed_orbit_visibility_settings()

        default_actions = set(orbitApi.DEFAULT_ORBIT_ACTIONS)
        for tool_data in self._get_menu_items():
            self._create_orbit_tool_button(
                tool_data=tool_data,
                default=tool_data["id"] in default_actions,
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_orbit_flow(resize_window=self._orbit_flow_can_resize_window)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._finish_initial_orbit_flow_layout)

    def _finish_initial_orbit_flow_layout(self):
        self._update_orbit_flow(resize_window=False, force_layout=True)
        self._orbit_flow_can_resize_window = True
        self._fit_orbit_window_to_flow_height()

    def update_orbit_layout_for_current_geometry(self):
        section = getattr(self, "tools_section", None)
        if not section:
            return

        margins = self.mainLayout.contentsMargins()
        available_width = self.width() - margins.left() - margins.right()
        for widget in (
            self._header_left_spacing,
            self.header_separator,
            self._header_right_spacing,
            self.header_right_container,
        ):
            if widget.isVisible():
                available_width -= widget.width() or widget.sizeHint().width()

        available_width = max(1, available_width)
        available_height = max(1, self.height() - margins.top() - margins.bottom())
        section.resize(available_width, available_height)
        layout = section.layout()
        if layout:
            layout.invalidate()
            layout.setGeometry(QtCore.QRect(0, 0, available_width, available_height))
        section.updateGeometry()
        section.repaint()

    def _update_orbit_flow(self, resize_window=False, force_layout=False):
        if not wutil.is_valid_widget(self):
            return
        if self._orbit_flow_resizing_window:
            return

        section = getattr(self, "tools_section", None)
        if not section:
            return

        old_section_height = section.height()

        layout = section.layout()
        if layout:
            layout.invalidate()
        section.updateGeometry()
        self.header_left_container.updateGeometry()
        self.layout().activate()
        if force_layout and layout:
            layout.setGeometry(section.rect())
        section.repaint()

        width = max(1, section.width())
        new_section_height = section.heightForWidth(width)
        if new_section_height < 0:
            return
        height_delta = new_section_height - old_section_height
        if resize_window and height_delta:
            self._orbit_flow_resizing_window = True
            try:
                section.setMinimumHeight(new_section_height)
                self._fit_orbit_window_to_flow_height(new_section_height)
            finally:
                self._orbit_flow_resizing_window = False

    def _update_height(self):
        self._update_orbit_flow(resize_window=self._orbit_flow_can_resize_window)

    def _fit_orbit_window_to_flow_height(self, section_height=None):
        section = getattr(self, "tools_section", None)
        if not section:
            return

        if section_height is None:
            section_height = section.heightForWidth(max(1, section.width()))
        if section_height < 0:
            return

        margins = self.mainLayout.contentsMargins()
        chrome_height = margins.top() + margins.bottom()
        close_height = self.header_right_container.sizeHint().height()
        target_height = chrome_height + max(section_height, close_height)

        if target_height > 0 and self.height() != target_height:
            self.setGeometry(self.x(), self.y(), self.width(), target_height)
            self.clamp_to_current_screen()

    def _seed_orbit_visibility_settings(self):
        current_actions = set(orbitApi.load_orbit_configuration().values())
        for tool_data in self._get_menu_items():
            action_identifier = tool_data["id"]
            setting_key = f"pin_{action_identifier}"
            current_value = orbitApi.settings.get_setting(setting_key, None, namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE)
            if current_value is None:
                orbitApi.settings.set_setting(
                    setting_key,
                    action_identifier in current_actions,
                    namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE,
                )

    def _create_orbit_tool_button(self, tool_data, default):
        label = tool_data.get("label") or tool_data.get("id")
        action_identifier = tool_data["id"]
        tooltip_text = tool_data.get("tooltip_template") or label
        description = tool_data.get("description") or tooltip_text

        btn = cw.create_tool_button_from_data(
            tool_data,
            tooltip_template=tooltip_text,
            description=description,
            status_title=tool_data.get("status_title", label),
            status_description=tool_data.get("status_description", description),
        )
        btn.setFixedSize(ORBIT_BUTTON_SIZE, ORBIT_BUTTON_SIZE)
        btn.setIconSize(QtCore.QSize(ORBIT_ICON_SIZE, ORBIT_ICON_SIZE))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: self.tools_section.open_menu(b.mapToGlobal(pos)))

        self.tools_section.addWidget(
            btn,
            label=label,
            key=action_identifier,
            default=default,
            description=description,
            tooltip_template=tooltip_text,
        )
        return btn
