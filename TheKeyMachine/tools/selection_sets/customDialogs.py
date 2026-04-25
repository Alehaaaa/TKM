import re

import maya.cmds as cmds

try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi
from TheKeyMachine.core import selection_targets
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import customDialogs, customWidgets as cw, util as wutil
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.tools.selection_sets.customWidgets import SelectionSetButton


class SelectionSetCreationDialog(customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, controller, parent=None, on_created=None, on_rejected=None):
        super().__init__(popup=False, parent=parent)
        self.controller = controller
        self.on_created = on_created
        self.on_rejected = on_rejected
        self._opened = False
        self._completed = False
        self._selected_color = selectionSetsApi.SELECTION_SET_DEFAULT_COLOR
        self._color_buttons = {}
        self.setObjectName("selection_set_creation_dialog")
        self.setWindowTitle("Create Selection Set")
        self.setMinimumWidth(wutil.DPI(320))
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.grip.hide()
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setSpacing(0)
        while self.top_bar_layout.count():
            item = self.top_bar_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        self._build_controls()
        self._apply_default_name_from_selection()

    def _build_controls(self):
        self.top_row = QtWidgets.QWidget()
        self.top_row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        top_row_layout = QtWidgets.QHBoxLayout(self.top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(wutil.DPI(6))

        self.entry_button = QtWidgets.QFrame()
        self.entry_button.setObjectName("selection_set_creation_entry")
        self.entry_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.entry_button.setFixedHeight(wutil.DPI(37))
        self.entry_button.setStyleSheet(
            """
            QFrame#selection_set_creation_entry {
                background-color: %s;
                border-radius: 7px;
            }
            """
            % self._selected_color.base.hex
        )
        entry_layout = QtWidgets.QHBoxLayout(self.entry_button)
        entry_layout.setContentsMargins(wutil.DPI(10), 0, wutil.DPI(10), 0)
        entry_layout.setSpacing(0)

        self.name_field = cw.PersistentPlaceholderLineEdit()
        self.name_field.setPlaceholderText("Selection Set")
        self.name_field.setAlignment(QtCore.Qt.AlignCenter)
        self.name_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.name_field.setFixedHeight(wutil.DPI(30))
        self.name_field.setStyleSheet(
            """
            QLineEdit {
                background-color: transparent;
                border: none;
                color: #000000;
                padding: 0px 6px;
            }
            QLineEdit::placeholder {
                color: transparent;
            }
            """
        )
        self.name_field.returnPressed.connect(self._create_set_from_selected_color)
        entry_layout.addWidget(self.name_field, 1)
        top_row_layout.addWidget(self.entry_button, 1)

        self.confirm_button = self._create_action_button("OK", self._create_set_from_selected_color, highlight=True, icon=media.apply_image)
        top_row_layout.addWidget(self.confirm_button, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.close_dialog_button = QtWidgets.QToolButton()
        self.close_dialog_button.setAutoRaise(True)
        self.close_dialog_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_dialog_button.setIcon(QtGui.QIcon(media.close_image))
        self.close_dialog_button.setIconSize(QtCore.QSize(wutil.DPI(18), wutil.DPI(18)))
        self.close_dialog_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.close_dialog_button.setStyleSheet(
            """
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QToolButton:pressed {
                background-color: rgba(0, 0, 0, 0.45);
            }
            """
        )
        self.close_dialog_button.clicked.connect(self.close)
        top_row_layout.addWidget(self.close_dialog_button, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.mainLayout.addWidget(self.top_row)

        self.color_row = QtWidgets.QWidget()
        self.color_row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.color_layout = QtWidgets.QHBoxLayout(self.color_row)
        self.color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_layout.setSpacing(wutil.DPI(1))

        for color in selectionSetsApi.SELECTION_SET_COLORS:
            self.color_layout.addWidget(self._create_color_button(color))

        self.color_layout.addStretch(1)
        self.mainLayout.addWidget(self.color_row)
        self.mainLayout.setSpacing(wutil.DPI(5))

    def _create_action_button(self, text, callback, highlight=False, icon=None, fixed_width=None):
        button = cw.QFlatButton(text=text, icon_path=icon, highlight=highlight)
        button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        if fixed_width is not None:
            button.setFixedWidth(fixed_width)
        button.clicked.connect(callback)
        return button

    def showEvent(self, event):
        super().showEvent(event)
        self._opened = True
        self._compress_to_contents()
        self.place_near_cursor()
        QtCore.QTimer.singleShot(0, self._focus_name_field)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.hide()

    def _compress_to_contents(self):
        self.adjustSize()
        target_size = self.sizeHint().expandedTo(QtCore.QSize(self.minimumWidth(), 0))
        self.setFixedSize(target_size)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange and self._opened and not self.isActiveWindow():
            self.close()
            return
        super().changeEvent(event)

    def closeEvent(self, event):
        if not self._completed and callable(self.on_rejected):
            self.on_rejected()
        super().closeEvent(event)

    def _focus_name_field(self):
        if not wutil.is_valid_widget(self) or not self.isVisible():
            return
        self.raise_()
        self.activateWindow()
        self.name_field.setFocus(QtCore.Qt.ActiveWindowFocusReason)
        self.name_field.selectAll()

    def _sanitize_selection_name(self, name):
        short_name = name.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
        parts = [part for part in re.split(r"[^A-Za-z0-9]+", short_name) if part]
        sanitized = "_".join(parts)
        sanitized = re.sub(r"^[^A-Za-z_]+", "", sanitized)
        return sanitized

    def _build_default_name_from_selection(self):
        selection = selection_targets.get_selected_objects()
        if not selection:
            return ""

        sanitized_names = [self._sanitize_selection_name(item) for item in selection]
        sanitized_names = [name for name in sanitized_names if name]
        if not sanitized_names:
            return ""
        if len(sanitized_names) == 1:
            return sanitized_names[0]

        token_lists = [name.split("_") for name in sanitized_names]
        common_tokens = []
        for token in token_lists[0]:
            if all(token in tokens for tokens in token_lists[1:]) and token not in common_tokens:
                common_tokens.append(token)

        if common_tokens:
            return "_".join(common_tokens)

        prefix = sanitized_names[0]
        for name in sanitized_names[1:]:
            max_len = min(len(prefix), len(name))
            match_len = 0
            while match_len < max_len and prefix[match_len].lower() == name[match_len].lower():
                match_len += 1
            prefix = prefix[:match_len]
            if not prefix:
                break
        return re.sub(r"[^A-Za-z0-9]+$", "", prefix).strip("_")

    def _apply_default_name_from_selection(self):
        default_name = self._build_default_name_from_selection()
        if default_name:
            self.name_field.setText(default_name)

    def _create_set_from_selected_color(self):
        self._create_set(self._selected_color.suffix)

    def _create_set(self, suffix):
        if self.controller:
            set_name = self.name_field.text().strip()
            if not set_name:
                self.name_field.setFocus(QtCore.Qt.ActiveWindowFocusReason)
                return
            created = self.controller.create_new_set_and_update_buttons(suffix, self.name_field, None)
            if created:
                self._completed = True
                self.close()
                if callable(self.on_created):
                    self.on_created()

    def _create_color_button(self, color):
        label = getattr(color, "label", "") or (self.controller.color_names.get(color.suffix, "") if hasattr(self.controller, "color_names") else "")
        tooltip = f"Create {label} Set"
        button_size = max(1, int(round(wutil.DPI(30) * 0.7)))
        icon_size = max(1, int(round(wutil.DPI(28) * 0.7)))
        btn = cw.create_tool_button_from_data(
            {
                "key": f"selection_set_color{color.suffix}",
                "label": tooltip,
                "icon_path": media.selection_set_color_images.get(color.suffix),
                "tooltip_template": tooltip,
            },
            callback=None,
        )
        btn.setFixedSize(button_size, button_size)
        btn.setIconSize(QtCore.QSize(icon_size, icon_size))
        btn.setCheckable(True)
        btn.clicked.connect(lambda *_, c=color: self._create_set_from_color_click(c))
        self._color_buttons[color.suffix] = btn
        btn.setStyleSheet(btn.styleSheet() + " QToolButton:checked { background-color: #4a4a4a; color: #ffffff; }")
        if color.suffix == self._selected_color.suffix:
            btn.setChecked(True)
        return btn

    def _set_selected_color(self, color):
        self._selected_color = color
        for key, button in self._color_buttons.items():
            block = button.blockSignals(True)
            button.setChecked(key == color.suffix)
            button.blockSignals(block)

    def _create_set_from_color_click(self, color):
        self._set_selected_color(color)
        self._create_set(color.suffix)


class SelectionSetMembersDialog(customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, set_name, parent=None):
        super().__init__(popup=False, parent=parent)
        self.setObjectName("selection_set_members_dialog")
        self.setWindowTitle("Set Items")
        self.setMinimumWidth(wutil.DPI(220))
        self.setMinimumHeight(wutil.DPI(260))
        self.set_name = set_name

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._sync_selection)
        self.mainLayout.addWidget(self.list_widget, 1)

        reload_btn = cw.QFlatButton(text="Reload", icon_path=media.reload_image, highlight=True)
        reload_btn.clicked.connect(self.reload_members)
        self.mainLayout.addWidget(reload_btn)

        self.reload_members()

    def reload_members(self):
        members = cmds.sets(self.set_name, q=True) or []
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item in sorted(members):
            self.list_widget.addItem(item)
        self.list_widget.selectAll()
        self.list_widget.blockSignals(False)
        self._sync_selection()

    def _sync_selection(self):
        selected = [item.text() for item in self.list_widget.selectedItems()]
        cmds.select(selected, replace=True) if selected else cmds.select(clear=True)


class SelectionSetsWindow(FloatingToolWindowMixin, customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(popup=False, parent=parent)
        self.controller = controller or selectionSetsApi._resolve_toolbar_controller(controller)
        self._creation_dialog = None
        self._set_buttons = {}
        self._selection_match_timer = QtCore.QTimer(self)
        self._selection_match_timer.setSingleShot(True)
        self._selection_match_timer.timeout.connect(self._update_button_match_states)
        self.setObjectName("selection_sets_window")
        self.setWindowTitle("Selection Sets")
        self.setMinimumHeight(wutil.DPI(76))
        self.mainLayout.setContentsMargins(0, wutil.DPI(4), 0, wutil.DPI(4))
        self._section_menu_targets = []
        self._build_ui()
        self._init_floating_window_behavior()
        self._connect_selection_callback()
        self.adjustSize()
        self._restored_geometry = self._restore_saved_geometry()
        self.apply_stay_on_top_setting()
        self.update_transparency_state(False)
        self.refresh()

    def _build_ui(self):
        self.clear_header_right_widgets()
        self.close_button.setToolTip("Close Select Sets")
        while self.header_left_layout.count():
            item = self.header_left_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        if hasattr(self, "_set_header_divider_visible"):
            self._set_header_divider_visible(False)
        if hasattr(self, "header_right_layout") and self.header_right_layout:
            self.header_right_layout.setContentsMargins(0, 0, wutil.DPI(6), 0)

        self.header_section = cw.QFlatSectionWidget(
            spacing=wutil.DPI(2),
            hiddeable=True,
            settings_namespace=selectionSetsApi.SELECTION_SETS_SETTINGS_NAMESPACE,
        )
        self.header_section.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        section_layout = self.header_section.layout()
        if section_layout:
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
        self.header_section.setContentsMargins(0, 0, 0, 0)
        self.add_header_right_widget(self.header_section, before_close=True)

        self.add_button = self._create_header_button(
            media.selection_sets_add_image,
            "Create Selection Set",
            self._open_set_creation_window,
            key="selection_sets_add_btn",
            default_visible=True,
            description="Create a new selection set from the current selection.",
        )
        self.refresh_button = self._create_header_button(
            media.selection_sets_reload_image,
            "Reload Selection Sets",
            self.refresh,
            key="selection_sets_refresh_btn",
            default_visible=False,
            description="Reload the selection set list from the current scene data.",
        )
        self.export_button = self._create_header_button(
            media.selection_sets_export_image,
            "Export Selection Sets",
            self._export_sets,
            key="selection_sets_export_btn",
            default_visible=False,
            description="Export selection sets to a file for reuse in another scene.",
        )
        self.import_button = self._create_header_button(
            media.selection_sets_import_image,
            "Import Selection Sets",
            self._import_sets,
            key="selection_sets_import_btn",
            default_visible=False,
            description="Import selection sets from a previously exported file.",
        )
        self._install_header_context_menu()
        for btn in (self.add_button, self.refresh_button, self.export_button, self.import_button):
            self._register_section_menu_target(btn)

        self.header_sets_host = QtWidgets.QWidget(self.header_left_container)
        self.header_sets_host.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.header_sets_layout = QtWidgets.QVBoxLayout(self.header_sets_host)
        self.header_sets_layout.setContentsMargins(wutil.DPI(4), wutil.DPI(2), 0, wutil.DPI(2))
        self.header_sets_layout.setSpacing(0)

        self.flow_container = cw.QFlowContainer()
        self.flow_container.setMinimumHeight(0)
        self.flow_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.flow_layout = cw.QFillFlowLayout(
            self.flow_container,
            margin=0,
            Hspacing=wutil.DPI(1),
            Vspacing=wutil.DPI(1),
            alignment=QtCore.Qt.AlignLeft,
        )
        self.flow_container.setLayout(self.flow_layout)
        self.header_sets_layout.addWidget(self.flow_container, 0, QtCore.Qt.AlignTop)
        self.header_sets_layout.addStretch(1)
        self.set_header_left_widget(self.header_sets_host, stretch=1)

    def _create_header_button(self, icon, tooltip, callback, key, default_visible, description=None):
        btn = cw.create_tool_button_from_data(
            {
                "key": key,
                "label": tooltip,
                "icon_path": icon,
                "tooltip_template": tooltip,
                "description": description,
            },
            callback=None,
        )
        btn.setFixedSize(wutil.DPI(26), wutil.DPI(26))
        btn.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        btn.clicked.connect(callback)
        if hasattr(self, "header_section") and self.header_section:
            self.header_section.addWidget(
                btn,
                label=tooltip,
                key=key,
                default_visible=default_visible,
                description=description or tooltip,
                tooltip_template=tooltip,
            )
        return btn

    def _install_header_context_menu(self):
        for target in getattr(self, "_section_menu_targets", []):
            if target:
                target.removeEventFilter(self)
        self._section_menu_targets = []
        self._register_section_menu_target(self.header_section)
        self._register_section_menu_target(self.header_right_container)
        self._register_section_menu_target(self.close_button)

    def _register_section_menu_target(self, widget):
        if not widget:
            return
        widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(lambda pos, w=widget: self._open_section_menu(pos, w))
        widget.installEventFilter(self)
        self._section_menu_targets.append(widget)

    def _open_section_menu(self, pos=None, widget=None):
        menu_fn = getattr(self.header_section, "open_menu", None)
        if callable(menu_fn):
            global_pos = widget.mapToGlobal(pos) if widget is not None and pos is not None else QtGui.QCursor.pos()
            menu_fn(global_pos)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.ContextMenu and obj in getattr(self, "_section_menu_targets", []):
            self._open_section_menu(event.pos(), obj)
            return True
        return super().eventFilter(obj, event)

    def _open_set_creation_window(self):
        controller = self.controller or selectionSetsApi._resolve_toolbar_controller()
        if controller:
            selectionSetsApi.open_selection_set_creation_dialog(controller=controller, parent=self)

    def _open_menu(self):
        selectionSetsApi.build_selection_sets_context_menu(parent=self, controller=self.controller).exec_(QtGui.QCursor.pos())

    def _export_sets(self):
        controller = self.controller or selectionSetsApi._resolve_toolbar_controller()
        if controller and self._has_exportable_sets(controller):
            controller.export_sets()

    def _import_sets(self):
        controller = self.controller or selectionSetsApi._resolve_toolbar_controller()
        if controller:
            controller.import_sets()

    def _has_exportable_sets(self, controller=None):
        controller = controller or self.controller or selectionSetsApi._resolve_toolbar_controller()
        if controller is None:
            return False
        for subset in controller.get_selection_sets():
            if cmds.objExists(subset):
                return True
        wutil.make_inViewMessage("No sets to export")
        return False

    def _auto_transparency_setting_enabled(self):
        return selectionSetsApi._selection_sets_auto_transparency_enabled()

    def _stays_on_top_setting_enabled(self):
        return selectionSetsApi._selection_sets_stays_on_top()

    def _geometry_settings_key(self):
        return "selection_sets_geometry"

    def _geometry_settings_namespace(self):
        return selectionSetsApi.SELECTION_SETS_SETTINGS_NAMESPACE

    def closeEvent(self, event):
        self._disconnect_selection_callback()
        selectionSetsApi._emit_selection_sets_window_state(False)
        super().closeEvent(event)

    def refresh(self):
        self._clear_scroll()
        controller = self.controller or selectionSetsApi._resolve_toolbar_controller()
        if controller is None:
            self._add_empty_state("Toolbar not available.")
            return

        visible_sets = []
        for subset in controller.get_selection_sets():
            if not cmds.objExists(subset):
                continue
            if cmds.attributeQuery("hidden", node=subset, exists=True) and cmds.getAttr(f"{subset}.hidden"):
                continue
            visible_sets.append(subset)

        if not visible_sets:
            self._add_empty_state("Create your first selection set from the toolbar button.")
            return

        visible_sets.sort(key=self._selection_set_sort_key)
        for subset in visible_sets:
            button = self._create_set_button(controller, subset)
            if button:
                self.flow_layout.addWidget(button)
        self._update_button_match_states()

    def _clear_scroll(self):
        self._set_buttons = {}
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _add_empty_state(self, _message):
        return

    def _selection_set_sort_key(self, subset):
        split_name = subset.split("_")
        color_suffix = split_name[-1] if len(split_name) >= 2 else ""
        set_name = "_".join(split_name[:-1]) if len(split_name) >= 2 else subset
        color = selectionSetsApi.get_selection_set_color(f"_{color_suffix}", fallback=None)
        order = color.order if color else 999
        return order, set_name.lower(), subset.lower()

    def _create_set_button(self, controller, subset):
        split_name = subset.split("_")
        if len(split_name) < 2:
            return None
        color_suffix = split_name[-1]
        set_name = "_".join(split_name[:-1])

        button = SelectionSetButton(set_name)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button.setFixedHeight(wutil.DPI(38))
        button.set_rename_target(controller, subset, set_name)
        button.clicked.connect(lambda *_, s=subset: controller.handle_set_selection(s, False, False))
        button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda *_: self._show_set_menu(controller, subset))

        color = selectionSetsApi.get_selection_set_color(f"_{color_suffix}")
        button.setProperty("tkm_base_color", color.base.hex)
        button.setProperty("tkm_hover_color", color.hover.hex)
        button.setProperty("tkm_text_color", color.text.hex)
        self._apply_set_button_style(button, match_state="none")
        self._set_buttons[subset] = button
        return button

    def _apply_set_button_style(self, button, match_state="none"):
        color = button.property("tkm_base_color") or "#333333"
        hover = button.property("tkm_hover_color") or "#454545"
        text_color = button.property("tkm_text_color") or "#1a1a1a"
        button.setStyleSheet(
            """
            QPushButton {
                color: %s;
                background-color: %s;
                border-radius: %dpx;
                border: none;
                padding: 0px %dpx;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: %s;
            }
            """
            % (text_color, color, wutil.DPI(7), wutil.DPI(12), hover)
        )
        if hasattr(button, "set_match_state"):
            button.set_match_state(match_state)

    def _connect_selection_callback(self):
        runtime_manager = getattr(self, "_runtime_manager", None)
        if runtime_manager:
            toolCommon.clear_tracked_connection(self, "_selection_changed_relay")
        try:
            import TheKeyMachine.core.runtime_manager as runtime

            self._runtime_manager = runtime.get_runtime_manager()
            toolCommon.replace_tracked_connection(
                self,
                "_selection_changed_relay",
                self._runtime_manager.selection_changed,
                self._schedule_selection_match_refresh,
                parent=self,
            )
        except Exception:
            self._runtime_manager = None

    def _disconnect_selection_callback(self):
        runtime_manager = getattr(self, "_runtime_manager", None)
        if not runtime_manager:
            return
        toolCommon.clear_tracked_connection(self, "_selection_changed_relay")
        self._runtime_manager = None

    def _schedule_selection_match_refresh(self):
        if not self._selection_match_timer.isActive():
            self._selection_match_timer.start(0)

    def showEvent(self, event):
        self._connect_selection_callback()
        self._schedule_selection_match_refresh()
        super().showEvent(event)

    def _normalize_scene_objects(self, items):
        if not items:
            return set()
        normalized = cmds.ls(items, long=True) or []
        return set(normalized or items)

    def _update_button_match_states(self):
        current_selection = self._normalize_scene_objects(selection_targets.get_selected_objects(long=True))
        for subset, button in list(self._set_buttons.items()):
            if not wutil.is_valid_widget(button):
                self._set_buttons.pop(subset, None)
                continue
            if not cmds.objExists(subset):
                self._apply_set_button_style(button, match_state="none")
                continue
            set_members = self._normalize_scene_objects(cmds.sets(subset, q=True) or [])
            if current_selection == set_members:
                match_state = "exact"
            elif current_selection and set_members and current_selection.intersection(set_members):
                match_state = "partial"
            else:
                match_state = "none"
            self._apply_set_button_style(button, match_state=match_state)

    def _show_set_menu(self, controller, subset):
        menu = QtWidgets.QMenu()
        menu.addAction(QtGui.QIcon(media.add_image), "Add Selection").triggered.connect(lambda: controller.add_selection_to_set(subset))
        menu.addAction(QtGui.QIcon(media.subtract_image), "Remove Selection").triggered.connect(lambda: controller.remove_selection_from_set(subset))
        menu.addAction(QtGui.QIcon(media.reload_image), "Update Selection").triggered.connect(lambda: controller.update_selection_to_set(subset))
        menu.addSeparator()

        color_menu = QtWidgets.QMenu("Change Color")
        color_menu.setIcon(QtGui.QIcon(media.color_image))
        menu.addMenu(color_menu)
        for suffix, label in controller.color_names.items():
            color_menu.addAction(QtGui.QIcon(media.selection_set_color_images.get(suffix, "")), label).triggered.connect(
                lambda *_, s=subset, suf=suffix: controller.set_set_color(s, suf)
            )

        menu.addAction(QtGui.QIcon(media.rename_image), "Rename").triggered.connect(
            lambda: (
                self._set_buttons.get(subset).start_inline_rename()
                if self._set_buttons.get(subset)
                else controller.change_set_name_window(subset, subset.rsplit("_", 1)[0])
            )
        )
        menu.addAction(QtGui.QIcon(media.trash_image), "Delete").triggered.connect(lambda: controller.remove_set_and_update_buttons(subset))
        current_color_suffix = f"_{subset.rsplit('_', 1)[-1]}"
        current_color_label = controller.color_names.get(current_color_suffix, current_color_suffix.strip("_"))
        menu.addAction(
            QtGui.QIcon(media.selection_set_color_trash_images.get(current_color_suffix, media.trash_image)),
            f"Delete All {current_color_label}",
        ).triggered.connect(lambda: controller.delete_sets_by_color_suffix(current_color_suffix))
        menu.exec_(QtGui.QCursor.pos())


def make_selection_set_creation_dialog(controller, parent=None, on_created=None, on_rejected=None):
    return SelectionSetCreationDialog(controller=controller, parent=parent, on_created=on_created, on_rejected=on_rejected)


def make_selection_set_members_dialog(set_name):
    parent = wutil.get_maya_qt(qt=QtWidgets.QWidget)
    dlg = SelectionSetMembersDialog(set_name=set_name, parent=parent)
    dlg.show()
    return dlg
