from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.Qt import QtGui, QtWidgets  # type: ignore

from TheKeyMachine.data import icons
from TheKeyMachine.mods import generalMod
from TheKeyMachine.mods import changelogMod
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets.util import DPI, is_valid_widget


class LogoAction(QtWidgets.QWidgetAction):
    def __init__(self, parent, clickable=True):
        QtWidgets.QWidgetAction.__init__(self, parent)
        self.setStatusTip("")
        self.setToolTip("")
        self.clickable = bool(clickable)
        self._widgets = []

    def createWidget(self, parent):
        container = QtWidgets.QWidget(parent)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, DPI(10), 0, DPI(10))
        layout.setSpacing(0)

        logo_pixmap = QtGui.QPixmap(icons.TheKeyMachine_logo_250)
        if not logo_pixmap.isNull():
            logo_label = QtWidgets.QLabel(container)
            logo_label.setPixmap(
                logo_pixmap.scaledToHeight(DPI(60), QtCore.Qt.SmoothTransformation)
            )
            logo_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(logo_label)

        if self.clickable:
            container.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            container.mouseReleaseEvent = self._on_clicked

        self._widgets.append(container)
        return container

    def deleteWidget(self, widget):
        if widget in self._widgets:
            self._widgets.remove(widget)
        QtWidgets.QWidgetAction.deleteWidget(self, widget)

    def isClickable(self):
        return self.clickable

    def _on_clicked(self, _event):
        generalMod.open_url("https://github.com/Alehaaaa/TKM")
        parent = self.parent()
        if parent and hasattr(parent, "hide"):
            parent.hide()


def _present_window(window):
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def show_reload_scene_prompt(anchor_widget=None):
    buttons = [
        {"name": "Save", "value": "save", "positive": True},
        {"name": "Save As", "value": "save_as", "positive": True, "highlight": True},
        {"name": "Skip", "value": "skip", "positive": False},
        {"name": "Cancel", "value": "cancel", "positive": False},
    ]
    title = "Save the scene before reloading?"
    message = (
        "Reloading replaces TheKeyMachine's Python modules, callbacks, and Maya UI while Maya is running.",
        "This can occasionally make Maya unstable or cause it to crash. Save the scene before continuing.",
    )
    if is_valid_widget(anchor_widget):
        tooltip = "<text>{}</text><spacing size='8'/><text>{}</text>".format(*message)
        clicked = customDialogs.QFlatTooltipConfirm.question(
            anchor_widget,
            title=title,
            tooltip=tooltip,
            icon=icons.reload,
            buttons=buttons,
            highlight="Save As",
        )
    else:
        clicked = customDialogs.QFlatConfirmDialog.question(
            None,
            "Reload TheKeyMachine",
            message,
            title=title,
            icon=icons.reload,
            buttons=buttons,
            highlight="Save As",
        )
    return (clicked or {}).get("value", "cancel")


_donate_dialog = None


def show_donate(parent=None):
    global _donate_dialog

    if _donate_dialog and is_valid_widget(_donate_dialog):
        return _present_window(_donate_dialog)

    link = "https://github.com/Alehaaaa/TKM"
    message = (
        "The development of TheKeyMachine takes a substantial amount of time and energy.",
        "If you use it professionally or regularly, consider supporting its continued development.",
        "",
        "Support TheKeyMachine <a href='{}' style='color:#86CDAD;'><br>{}</a>".format(link, link),
    )
    _donate_dialog = customDialogs.QFlatConfirmDialog(
        parent=parent,
        window="Donate",
        title="Donate to TheKeyMachine",
        message=message,
        closeButton=True,
        icon=icons.donate,
    )
    _donate_dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
    _donate_dialog.message_label.setTextFormat(QtCore.Qt.RichText)
    _donate_dialog.message_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
    _donate_dialog.message_label.setOpenExternalLinks(True)
    return _present_window(_donate_dialog)


class TKMAboutDialog(customDialogs.QFlatDialog):
    def __init__(self, parent=None):
        customDialogs.QFlatDialog.__init__(self, parent)
        self.setWindowTitle("About TheKeyMachine")

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(20), DPI(20), DPI(20), 0)
        content_layout.setSpacing(DPI(12))

        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignCenter)
        logo_pixmap = QtGui.QPixmap(icons.TheKeyMachine_logo_250)
        logo_label.setPixmap(logo_pixmap)
        content_layout.addWidget(logo_label)

        stage_version = generalMod.get_thekeymachine_stage_version()
        version = generalMod.get_thekeymachine_version()
        build_version = generalMod.get_thekeymachine_build_version()
        codename = generalMod.get_thekeymachine_codename()

        tool_name = QtWidgets.QLabel("Animation toolset for Maya Animators")
        tool_name.setAlignment(QtCore.Qt.AlignCenter)
        tool_name.setStyleSheet(
            "font-size: %spx; font-weight: bold; color: #ececec;" % DPI(16)
        )
        content_layout.addWidget(tool_name)

        version_button = QtWidgets.QPushButton(
            "v{} {}".format(version, stage_version)
        )
        version_button.setCursor(QtCore.Qt.PointingHandCursor)
        version_button.clicked.connect(self._open_version_history)
        version_button.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(76, 175, 80, 0.15);
                border: 1px solid #4CAF50;
                color: #81C784;
                border-radius: %spx;
                padding: %spx %spx;
                font-size: %spx;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #498042;
                color: white;
            }
            QPushButton:pressed {
                background-color: #3a5a3d;
                color: #98ae97;
            }
            """
            % (DPI(4), DPI(4), DPI(8), DPI(12))
        )
        content_layout.addWidget(version_button, alignment=QtCore.Qt.AlignCenter)

        build_label = QtWidgets.QLabel(
            "Build: {} | {}".format(build_version, codename)
        )
        build_label.setAlignment(QtCore.Qt.AlignCenter)
        build_label.setStyleSheet(
            "font-size: %spx; color: #888888;" % DPI(11)
        )
        content_layout.addWidget(build_label)

        info_text = """
            <div style='text-align: center; color: #888888; font-size: %spx;'>
                <p>This tool is licensed under the <a href='https://www.gnu.org/licenses/gpl-3.0.en.html' style='color: #67b9e0; text-decoration: none;'>GNU GPL 3.0</a>.</p>
                <div style='margin-top: 10px;'>
                    Developed by <a href='http://rodritorres.com' style='color: #67b9e0; text-decoration: none;'>Rodrigo Torres</a>
                </div>
                <div style='margin-top: 5px;'>
                    Modified by <a href='http://alehaaaa.github.io' style='color: #67b9e0; text-decoration: none;'>Alehaaaa</a>
                </div>
            </div>
        """ % DPI(11)

        info_label = QtWidgets.QLabel(info_text)
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_label.setTextFormat(QtCore.Qt.RichText)
        info_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        info_label.setOpenExternalLinks(True)
        info_label.setStyleSheet("background: transparent;")
        content_layout.addWidget(info_label)

        self.root_layout.addWidget(content_widget)
        self.setBottomBar(closeButton=True)
        self.adjustSize()

    def _open_version_history(self):
        self.close()
        QtCore.QTimer.singleShot(0, lambda: show_version_history_dialog(parent=None))


_about_dialog = None


def show_about(parent=None):
    global _about_dialog

    if _about_dialog and is_valid_widget(_about_dialog):
        return _present_window(_about_dialog)

    _about_dialog = TKMAboutDialog(parent=parent)
    _about_dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
    return _present_window(_about_dialog)


_version_history_dialog = None


def show_version_history_dialog(parent=None):
    global _version_history_dialog

    if _version_history_dialog and is_valid_widget(_version_history_dialog):
        return _present_window(_version_history_dialog)

    dlg = TKMVersionHistoryDialog(parent=parent)
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def _clear_ref(*_args):
        global _version_history_dialog
        _version_history_dialog = None

    dlg.destroyed.connect(_clear_ref)
    _version_history_dialog = dlg
    return _present_window(dlg)


class TKMVersionHistoryDialog(customDialogs.QFlatDialog):
    def __init__(self, parent=None):
        customDialogs.QFlatDialog.__init__(self, parent)
        self.setWindowTitle("TheKeyMachine Version History")
        self.setMinimumSize(DPI(620), DPI(520))

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(12), DPI(12), DPI(12), 0)
        content_layout.setSpacing(DPI(0))

        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        logo_pixmap = QtGui.QPixmap(icons.TheKeyMachine_logo_250)
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaledToWidth(DPI(170), QtCore.Qt.SmoothTransformation)
            )
        content_layout.addWidget(logo_label)
        content_layout.addSpacing(DPI(18))

        title_label = QtWidgets.QLabel("Version History")
        title_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        title_label.setStyleSheet("font-size: %spx; font-weight: bold; color: #cfcfcf;" % DPI(15))
        content_layout.addWidget(title_label)

        sections = changelogMod.get_local_changelog_sections()
        range_text = self._version_range_text(sections)
        range_label = QtWidgets.QLabel(range_text)
        range_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        range_label.setStyleSheet("font-size: %spx; font-weight: bold; color: #a8a8a8;" % DPI(10))
        content_layout.addWidget(range_label)
        content_layout.addSpacing(DPI(24))

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: #242424;
                border: none;
            }
            """
        )

        history_widget = QtWidgets.QWidget()
        history_widget.setStyleSheet("background-color: #242424;")
        history_layout = QtWidgets.QVBoxLayout(history_widget)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(0)

        if sections:
            for index, section in enumerate(sections):
                history_layout.addWidget(self._build_version_block(section, index))
        else:
            empty_label = QtWidgets.QLabel("No changelog available.")
            empty_label.setAlignment(QtCore.Qt.AlignCenter)
            empty_label.setStyleSheet("color: #bbbbbb; font-size: %spx; padding: %spx;" % (DPI(12), DPI(24)))
            history_layout.addWidget(empty_label)

        history_layout.addStretch(1)
        scroll_area.setWidget(history_widget)
        content_layout.addWidget(scroll_area, 1)

        self.root_layout.addWidget(content_widget)
        self.setBottomBar(closeButton=True)
        self.resize(DPI(650), DPI(580))

    def _version_range_text(self, sections):
        if not sections:
            return "(No changelog entries found)"
        newest = sections[0].get("version", "")
        oldest = sections[-1].get("version", "")
        return "(From %s up to %s)" % (oldest, newest)

    def _build_version_block(self, section, index):
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background-color: %s;
                border: none;
            }
            """
            % ("#292929" if index % 2 == 0 else "#262626")
        )

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(DPI(10), DPI(10), DPI(10), DPI(12))
        layout.setSpacing(DPI(7))

        version_label = QtWidgets.QLabel("Version %s" % section.get("version", ""))
        version_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        version_label.setStyleSheet("font-size: %spx; font-weight: bold; color: #f0f0f0;" % DPI(15))
        layout.addWidget(version_label)

        for group in changelogMod.group_changelog_entries(section.get("entries", [])):
            layout.addLayout(self._build_entry_group(group))

        return frame

    def _build_entry_group(self, group):
        group_layout = QtWidgets.QVBoxLayout()
        group_layout.setContentsMargins(DPI(2), 0, 0, 0)
        group_layout.setSpacing(DPI(3))

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(DPI(8))

        icon_label = QtWidgets.QLabel()
        kind = group.get("kind", "")
        pixmap = QtGui.QPixmap(changelogMod.change_kind_icon(kind))
        icon_size = DPI(17)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(icon_size, icon_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        icon_label.setFixedSize(icon_size, icon_size)
        header_layout.addWidget(icon_label, 0, QtCore.Qt.AlignVCenter)

        title = QtWidgets.QLabel("<b>%s</b>" % changelogMod.escape_text(changelogMod.change_kind_label(kind)))
        title.setTextFormat(QtCore.Qt.RichText)
        title.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        title.setStyleSheet("font-size: %spx; color: #d3d3d3;" % DPI(11))
        header_layout.addWidget(title, 0, QtCore.Qt.AlignVCenter)
        header_layout.addStretch(1)
        group_layout.addLayout(header_layout)

        for entry in group.get("entries", []):
            label = QtWidgets.QLabel(changelogMod.escape_text(entry.get("description", "")))
            label.setWordWrap(True)
            label.setTextFormat(QtCore.Qt.RichText)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            label.setStyleSheet("font-size: %spx; color: #d3d3d3;" % DPI(11))
            group_layout.addWidget(label)

        return group_layout
