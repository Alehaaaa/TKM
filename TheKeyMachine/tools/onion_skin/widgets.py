"""Floating Onion Skin manager using TKM's standard tool window shell."""

from __future__ import absolute_import

from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore

from TheKeyMachine.core import i18n
from TheKeyMachine.data import icons
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.tools.onion_skin import api, controller
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets import customWidgets as cw
from TheKeyMachine.ui.widgets import util as wutil


WINDOW_NAME = "onion_skin_window"
ROW_HEIGHT = wutil.DPI(26)
HEADER_HEIGHT = wutil.DPI(22)
BASE_COLOR_EVEN = "#2b2b2b"
BASE_COLOR_ODD = "#2e2e2e"
HOVER_COLOR = "#343434"


def _t(text):
    return i18n.tr_text(text)


def _goto_frame(frame):
    try:
        from maya import cmds  # type: ignore

        cmds.currentTime(frame)
    except Exception:
        pass


def _select_in_scene(object_name):
    try:
        from maya import cmds  # type: ignore

        if cmds.objExists(object_name):
            cmds.select(object_name, replace=True)
    except Exception:
        pass


class _ListSectionHeader(QtWidgets.QFrame):
    """Thin, low-chrome divider label -- 'Objects' / 'Held Poses' -- with an
    optional small action button docked at its right edge (e.g. Hold Current Pose)."""

    def __init__(self, title, action_button=None, parent=None):
        super(_ListSectionHeader, self).__init__(parent)
        self.setFixedHeight(HEADER_HEIGHT)
        self.setStyleSheet("QFrame{background:transparent;border:0;border-bottom:1px solid #3a3a3a;}")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(4), wutil.DPI(4))
        layout.setSpacing(wutil.DPI(4))
        label = QtWidgets.QLabel(title, self)
        label.setStyleSheet("background:transparent;color:#9a9a9a;font-weight:600;")
        layout.addWidget(label)
        layout.addStretch(1)
        if action_button is not None:
            layout.addWidget(action_button)


class _EmptyHint(QtWidgets.QLabel):
    def __init__(self, text, parent=None):
        super(_EmptyHint, self).__init__(text, parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet("color:#7b7b7b;background:transparent;padding:14px 10px;")


class ObjectRow(QtWidgets.QFrame):
    """One managed object: click the row to select it in the scene, or remove it."""

    removeRequested = QtCore.Signal(str)

    def __init__(self, object_name, alternate=False, parent=None):
        super(ObjectRow, self).__init__(parent)
        self.object_name = object_name
        self.setFixedHeight(ROW_HEIGHT)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(_t("Click to select {} in the scene.").format(object_name))
        self._base_color = BASE_COLOR_ODD if alternate else BASE_COLOR_EVEN
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self._apply_style(hovered=False)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(8), 0, wutil.DPI(4), 0)
        layout.setSpacing(wutil.DPI(4))

        short_name = object_name.rsplit("|", 1)[-1]
        label = QtWidgets.QLabel(short_name, self)
        label.setStyleSheet("background:transparent;color:#d6d6d6;")
        label.setToolTip(object_name)
        layout.addWidget(label, 1)

        self.remove_button = cw.create_tool_button_from_data(
            {
                "label": _t("Remove Object"),
                "icon": icons.get("trash"),
                "description": _t("Remove this object from the onion skin view."),
            },
            callback=None,
        )
        self.remove_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.remove_button.clicked.connect(lambda *_args: self.removeRequested.emit(self.object_name))
        layout.addWidget(self.remove_button)

    def _apply_style(self, hovered):
        background = HOVER_COLOR if hovered else self._base_color
        self.setStyleSheet("ObjectRow{background:%s;border:0;}" % background)

    def event(self, evt):
        if evt.type() == QtCore.QEvent.HoverEnter:
            self._apply_style(hovered=True)
        elif evt.type() == QtCore.QEvent.HoverLeave:
            self._apply_style(hovered=False)
        return super(ObjectRow, self).event(evt)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            _select_in_scene(self.object_name)
        super(ObjectRow, self).mousePressEvent(event)


class HeldPoseRow(QtWidgets.QFrame):
    """One held (absolute) frame: click the frame chip to jump the playhead there."""

    changed = QtCore.Signal(int, int)
    removeRequested = QtCore.Signal(int)

    def __init__(self, frame, opacity, alternate=False, parent=None):
        super(HeldPoseRow, self).__init__(parent)
        self.frame = int(frame)
        self.setFixedHeight(ROW_HEIGHT)
        self.setStyleSheet(
            "HeldPoseRow{background:%s;border:0;} QLabel{background:transparent;} QSlider{background:transparent;}"
            % (BASE_COLOR_ODD if alternate else BASE_COLOR_EVEN)
        )
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(4), 0)
        layout.setSpacing(wutil.DPI(6))

        self.frame_button = QtWidgets.QPushButton(str(self.frame), self)
        self.frame_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.frame_button.setToolTip(_t("Jump the playhead to frame {}.").format(self.frame))
        self.frame_button.setFixedSize(wutil.DPI(38), wutil.DPI(19))
        self.frame_button.setStyleSheet(
            "QPushButton{background:#3c3c3c;border:1px solid #525252;border-radius:3px;color:#d6d6d6;}"
            "QPushButton:hover{background:#484848;border-color:#668DAF;color:#ffffff;}"
        )
        self.frame_button.clicked.connect(lambda *_args: _goto_frame(self.frame))
        layout.addWidget(self.frame_button)

        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(opacity))
        self.opacity_slider.setToolTip(_t("Set how strongly this pose appears"))
        layout.addWidget(self.opacity_slider, 1)

        self.opacity_label = QtWidgets.QLabel("{}%".format(int(opacity)))
        self.opacity_label.setFixedWidth(wutil.DPI(32))
        self.opacity_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.opacity_label.setStyleSheet("color:#a8a8a8;")
        layout.addWidget(self.opacity_label)

        self.remove_button = cw.create_tool_button_from_data(
            {"label": _t("Remove Held Pose"), "icon": icons.get("trash")}, callback=None
        )
        self.remove_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.remove_button.clicked.connect(lambda *_args: self.removeRequested.emit(self.frame))
        layout.addWidget(self.remove_button)

        self.opacity_slider.valueChanged.connect(self._update_opacity_label)
        self.opacity_slider.sliderReleased.connect(self._emit_changed)

    def _update_opacity_label(self, value):
        self.opacity_label.setText("{}%".format(value))

    def _emit_changed(self, *_args):
        self.changed.emit(self.frame, self.opacity_slider.value())


class OnionSkinWindow(FloatingToolWindowMixin, customDialogs.QFlatPinnableToolBarPopupDialog):
    """Manage onion objects and held poses in the same compact shell as Animation Layers.

    Both lists share one continuous scroll area, divided by thin section
    headers, rather than two separately-chromed boxes -- the same
    single-list feel Animation Layers' own window uses. Per-offset
    nearby-frame settings live in the tool's right-click menu instead (see
    api.populate_nearby_frames_menu): that's a fixed handful of on/off
    settings, not something worth a list row.
    """

    def __init__(self, parent=None, popup=False):
        self.title = "Onion Skin"
        self.icon = icons.get("onion_skin")
        super(OnionSkinWindow, self).__init__(
            parent=parent,
            popup=popup,
            bottom_bar_kwargs={"margins": 0, "spacing": 2},
        )
        self.setObjectName(WINDOW_NAME)
        self.title_label.setText(_t(self.title))
        self.setMinimumSize(wutil.DPI(330), wutil.DPI(220))
        self.mainLayout.setContentsMargins(0, 0, 0, wutil.DPI(4))
        self._refreshing = False
        self._build_ui()
        self._init_floating_window_behavior()
        self.resize(wutil.DPI(390), wutil.DPI(420))
        self._restore_saved_geometry()
        self.apply_stay_on_top_setting()
        self.update_transparency_state(False)
        self.refresh()

    def _preferred_floating_size(self):
        return self.size()

    def _build_ui(self):
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(wutil.DPI(6), 0, wutil.DPI(6), wutil.DPI(6))
        toolbar.setSpacing(wutil.DPI(2))
        self.enable_button = self._tool_button(
            "onion_skin_enable",
            "Show Onion Skins",
            self._toggle_enabled,
            checkable=True,
            description="Compare the current pose with nearby and held poses in the focused viewport.",
        )
        self.add_button = self._tool_button(
            "add",
            "Add Selected Objects",
            self._add_selection,
            description="Include the selected character meshes or props in the pose comparison.",
        )
        self.clear_button = self._tool_button(
            "trash",
            "Remove All Objects",
            self._clear_objects,
            description="Clear the object list when you are ready to inspect a different character or prop.",
        )
        toolbar.addWidget(self.enable_button)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch(1)
        self.refresh_button = self._tool_button(
            "refresh",
            "Refresh Onion Images",
            controller.refresh_current_frame,
            description="Recapture the current pose without discarding the other visited frames.",
        )
        toolbar.addWidget(self.refresh_button)
        self.mainLayout.addLayout(toolbar)

        page = QtWidgets.QWidget(self)
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:#242424;}")
        content = QtWidgets.QWidget(scroll)
        content.setStyleSheet("background:#242424;")
        self.list_layout = QtWidgets.QVBoxLayout(content)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.mainLayout.addWidget(page, 1)

        self.hold_button = self._tool_button(
            "add",
            "Hold Current Pose",
            controller.add_current_absolute_frame,
            description="Keep this pose visible while you compare other parts of the shot.",
        )
        self.hold_button.setFixedSize(wutil.DPI(18), wutil.DPI(18))

    def _tool_button(self, icon_name, label, callback, checkable=False, description=None):
        button = cw.create_tool_button_from_data(
            {
                "label": _t(label),
                "icon": icons.get(icon_name),
                "checkable": checkable,
                "callback": callback,
                "description": _t(description) if description else None,
            }
        )
        button.setFixedSize(wutil.DPI(24), wutil.DPI(24))
        return button

    def _clear_layout(self, layout):
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self):
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self.enable_button.blockSignals(True)
            self.enable_button.setChecked(controller.is_enabled())
            self.enable_button.blockSignals(False)
            self._rebuild_list()
        finally:
            self._refreshing = False

    def _insert(self, widget):
        self.list_layout.insertWidget(self.list_layout.count() - 1, widget)

    def _rebuild_list(self):
        self._clear_layout(self.list_layout)

        self._insert(_ListSectionHeader(_t("Objects"), parent=self))
        names = controller.object_names()
        if names:
            for index, name in enumerate(names):
                row = ObjectRow(name, alternate=bool(index % 2), parent=self)
                row.removeRequested.connect(lambda value: controller.remove_objects([value]))
                self._insert(row)
        else:
            self._insert(_EmptyHint(
                _t("Select the character meshes or props you want to compare, then click Add."),
                parent=self,
            ))

        self._insert(_ListSectionHeader(_t("Held Poses"), action_button=self.hold_button, parent=self))
        absolute_frames = controller.get_setting("absolute_frames") or []
        absolute_opacities = controller.get_setting("absolute_opacities") or {}
        if absolute_frames:
            for index, frame in enumerate(sorted(absolute_frames)):
                row = HeldPoseRow(
                    frame,
                    absolute_opacities.get(str(frame), 50),
                    alternate=bool(index % 2),
                    parent=self,
                )
                row.changed.connect(self._held_pose_changed)
                row.removeRequested.connect(self._remove_absolute_frame)
                self._insert(row)
        else:
            self._insert(_EmptyHint(
                _t('Click "+" above to hold this pose here for comparison.'),
                parent=self,
            ))

    def _toggle_enabled(self, checked=False):
        controller.set_enabled(bool(checked))

    def _add_selection(self, *_args):
        controller.add_selected_objects()

    def _clear_objects(self, *_args):
        controller.clear_objects()

    def _held_pose_changed(self, frame, opacity):
        if self._refreshing:
            return
        controller.set_absolute_frame_opacity(frame, opacity)

    def _remove_absolute_frame(self, frame):
        controller.remove_absolute_frame(frame)

    def _auto_transparency_setting_enabled(self):
        # Onion Skin has no fade-when-not-hovered setting of its own -- this
        # window never fades; the hook only exists because
        # FloatingToolWindowMixin requires every floating window to answer it.
        return False

    def _stays_on_top_setting_enabled(self):
        return api.is_stay_on_top()

    def _geometry_settings_key(self):
        return "onion_skin_geometry_v4"

    def _geometry_settings_namespace(self):
        return api.SETTINGS_NAMESPACE

    def closeEvent(self, event):
        api._emit_window_state(False)
        super(OnionSkinWindow, self).closeEvent(event)

    def hideEvent(self, event):
        api._emit_window_state(False)
        super(OnionSkinWindow, self).hideEvent(event)
