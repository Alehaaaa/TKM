# -*- coding: utf-8 -*-
"""
TheKeyMachine - Drag & Drop Installer for Autodesk Maya

This file is part of TheKeyMachine, open source software licensed under
the GNU General Public License v3.0 (GPL-3.0).

Developed by: Rodrigo Torres / rodritorres.com
"""

from __future__ import print_function

import os
import sys
import shutil
import traceback
import importlib

import maya.cmds as cmds
import maya.OpenMayaUI as omui


try:
    from shiboken2 import wrapInstance
    from PySide2 import QtWidgets, QtCore, QtGui
except Exception:
    from shiboken6 import wrapInstance
    from PySide6 import QtWidgets, QtCore, QtGui

__version__ = "0.1.33"
__stage__ = "beta"
__build__ = "336"
__codename__ = "Cortado"

WINDOW_NAME = "TheKeyMachineInstaller"


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr:
        return wrapInstance(int(ptr), QtWidgets.QWidget)
    return None


def app_instance():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def dpi(value):
    # Qt uses device-independent logical pixels when high-DPI scaling is active.
    # Multiplying by devicePixelRatio makes the installer oversized on Retina/4K displays.
    return int(value)


def installer_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def source_dir():
    return os.path.join(installer_dir(), "TheKeyMachine")


def license_file_path():
    return os.path.join(installer_dir(), "license_gpl-3.0.txt")


def full_license_text():
    path = license_file_path()
    try:
        with open(path, "r", encoding="utf-8") as license_file:
            return license_file.read()
    except Exception:
        return "GNU GPL-3.0 license file could not be loaded from:\n{0}".format(path)


def scripts_dir():
    return os.path.normpath(os.path.join(cmds.internalVar(userAppDir=True), "scripts"))


def destination_dir():
    return os.path.join(scripts_dir(), "TheKeyMachine")


def version_string():
    return "v{0} {1} (Build {2}) - {3}".format(
        __version__,
        __stage__,
        __build__,
        __codename__,
    )


def show_error(parent, title, message, details=None):
    if details:
        message = "{0}\n\nDetails:\n{1}".format(message, details)

    QtWidgets.QMessageBox.critical(parent, title, message)


def show_info(parent, title, message):
    QtWidgets.QMessageBox.information(parent, title, message)


def confirm(parent, title, message):
    result = QtWidgets.QMessageBox.question(
        parent,
        title,
        message,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.No,
    )
    return result == QtWidgets.QMessageBox.Yes


def replace_install(src, dst):
    """Stage a complete copy, then swap it into place with rollback support."""
    if not os.path.exists(src):
        raise RuntimeError(
            "Source folder not found:\n{0}\n\n"
            "The installer must be next to the 'TheKeyMachine' folder.".format(src)
        )

    if not os.path.isdir(src):
        raise RuntimeError("Source path is not a folder:\n{0}".format(src))

    parent = os.path.dirname(dst)
    if not os.path.exists(parent):
        os.makedirs(parent)

    staging = dst + ".installing"
    backup = dst + ".backup"
    for temporary_path in (staging, backup):
        if os.path.isdir(temporary_path):
            shutil.rmtree(temporary_path)
        elif os.path.exists(temporary_path):
            os.remove(temporary_path)

    had_previous_install = os.path.exists(dst)
    previous_install_moved = False
    try:
        shutil.copytree(src, staging)
        if had_previous_install:
            if not os.path.isdir(dst):
                raise RuntimeError("Destination exists but is not a folder: {0}".format(dst))
            os.rename(dst, backup)
            previous_install_moved = True
        os.rename(staging, dst)
    except Exception:
        if previous_install_moved and os.path.isdir(backup) and not os.path.exists(dst):
            os.rename(backup, dst)
        if os.path.isdir(staging):
            shutil.rmtree(staging)
        raise

    # The new install is active. Backup cleanup must not invalidate a successful swap.
    if os.path.isdir(backup):
        try:
            shutil.rmtree(backup)
        except Exception:
            traceback.print_exc()


def unload_tkm_modules():
    for module_name in list(sys.modules.keys()):
        if module_name == "TheKeyMachine" or module_name.startswith("TheKeyMachine."):
            del sys.modules[module_name]


def ensure_scripts_on_path():
    path = scripts_dir()
    if path not in sys.path:
        sys.path.insert(0, path)


def load_thekeymachine():
    ensure_scripts_on_path()
    unload_tkm_modules()

    import TheKeyMachine

    TheKeyMachine = importlib.reload(TheKeyMachine)
    TheKeyMachine.welcome()


def reload_installer_module():
    module = sys.modules.get(__name__)
    if module is None:
        return None
    importlib.invalidate_caches()
    return importlib.reload(module)


def install_thekeymachine(parent):
    src = source_dir()
    dst = destination_dir()

    parent.set_installing(True)
    parent.set_status("Installing...")
    QtWidgets.QApplication.processEvents()

    try:
        if os.path.exists(dst):
            ok = confirm(
                parent,
                "Already Installed",
                "TheKeyMachine is already installed.\n\n"
                "Current installation:\n{0}\n\n"
                "Do you want to overwrite it?".format(dst),
            )

            if not ok:
                parent.set_installing(False)
                parent._refresh_state()
                return

        parent.set_status("Copying and validating files...")
        QtWidgets.QApplication.processEvents()
        replace_install(src, dst)

        parent.set_status("Installation completed. Loading TheKeyMachine...")
        QtWidgets.QApplication.processEvents()

        try:
            load_thekeymachine()
        except Exception:
            traceback.print_exc()
            show_error(
                parent,
                "Load Error",
                "TheKeyMachine was installed, but Maya could not load it automatically.",
                traceback.format_exc(),
            )
            parent.set_installing(False)
            parent.set_status("Installed, but automatic load failed.")
            return

        parent.set_status("Installation completed successfully.")
        show_info(
            parent,
            "Installation Complete",
            "TheKeyMachine has been installed successfully.\n\n"
            "Installed to:\n{0}".format(dst),
        )

        QtCore.QTimer.singleShot(500, parent.close)

    except Exception:
        traceback.print_exc()
        show_error(
            parent,
            "Installation Error",
            "TheKeyMachine could not be installed.",
            traceback.format_exc(),
        )
        parent.set_installing(False)
        parent.set_status("Installation failed.")


class TheKeyMachineInstallerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TheKeyMachineInstallerDialog, self).__init__(parent)

        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("TheKeyMachine Installer")

        window_type = QtCore.Qt.Tool if sys.platform == "darwin" else QtCore.Qt.Window
        base_flags = self.windowFlags() & ~QtCore.Qt.WindowType_Mask
        self.setWindowFlags(base_flags | window_type | QtCore.Qt.WindowCloseButtonHint)

        self._build_ui()
        self._fit_to_screen()
        self._refresh_state()

    def _fit_to_screen(self):
        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos) or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(dpi(500), dpi(680))
            return

        available = screen.availableGeometry()
        edge_margin = dpi(24)
        max_width = max(1, available.width() - edge_margin * 2)
        max_height = max(1, available.height() - edge_margin * 2)
        width = min(dpi(500), max_width)
        height = min(dpi(680), max_height)
        self.setMinimumSize(min(dpi(390), width), min(dpi(460), height))
        self.resize(width, height)
        self.move(available.center() - self.rect().center())

    def _build_ui(self):
        window_layout = QtWidgets.QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        window_layout.addWidget(scroll_area)

        content = QtWidgets.QWidget(scroll_area)
        scroll_area.setWidget(content)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(dpi(20), dpi(16), dpi(20), dpi(18))
        layout.setSpacing(dpi(10))

        header = QtWidgets.QVBoxLayout()
        header.setAlignment(QtCore.Qt.AlignCenter)
        header.setSpacing(dpi(8))

        logo_path = os.path.join(
            installer_dir(),
            "TheKeyMachine",
            "data",
            "icons",
            "TheKeyMachine_logo_500.png",
        )

        logo_loaded = False
        if os.path.exists(logo_path):
            pixmap = QtGui.QPixmap(logo_path)
            if not pixmap.isNull():
                logo = QtWidgets.QLabel()
                logo.setAlignment(QtCore.Qt.AlignCenter)
                logo.setPixmap(
                    pixmap.scaled(
                        dpi(190),
                        dpi(190),
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                )
                header.addWidget(logo)
                logo_loaded = True

        if not logo_loaded:
            title = QtWidgets.QLabel("TheKeyMachine")
            title.setAlignment(QtCore.Qt.AlignCenter)
            title.setStyleSheet("font-size: 22px; font-weight: bold;")
            header.addWidget(title)

        subtitle = QtWidgets.QLabel("Animation toolset for Maya animators")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setStyleSheet("font-style: italic; color: #999;")
        header.addWidget(subtitle)

        self.status_label = QtWidgets.QLabel(version_string())
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 10px;")
        header.addWidget(self.status_label)

        layout.addLayout(header)

        paths_box = QtWidgets.QGroupBox("Install paths")
        paths_layout = QtWidgets.QFormLayout(paths_box)
        paths_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        paths_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        paths_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        paths_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.source_path_label = QtWidgets.QLabel(source_dir())
        self.source_path_label.setWordWrap(True)
        self.source_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.destination_path_label = QtWidgets.QLabel(destination_dir())
        self.destination_path_label.setWordWrap(True)
        self.destination_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        paths_layout.addRow("Source:", self.source_path_label)
        paths_layout.addRow("Destination:", self.destination_path_label)

        layout.addWidget(paths_box)

        info = QtWidgets.QLabel(
            "This installer copies the local TheKeyMachine folder into your Maya "
            "scripts directory, reloads the package, and creates the shelf icon."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.license_text = QtWidgets.QTextEdit()
        self.license_text.setReadOnly(True)
        self.license_text.setAcceptRichText(False)
        self.license_text.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.license_text.setMinimumHeight(dpi(125))
        self.license_text.setPlainText(full_license_text())
        self.license_text.setStyleSheet(
            "QTextEdit {"
            "background-color: #2b2b2b;"
            "border: 1px solid #444;"
            "border-radius: 5px;"
            "padding: 8px;"
            "}"
        )
        layout.addWidget(self.license_text)

        self.accept_checkbox = QtWidgets.QCheckBox("I have read and accept the GNU GPL-3.0 license")
        self.accept_checkbox.setStyleSheet(
            "QCheckBox { color: #c8cec9; spacing: 7px; padding: 3px 0; }"
            "QCheckBox:hover { color: #ffffff; }"
        )
        layout.addWidget(self.accept_checkbox)

        self.install_button = QtWidgets.QPushButton("Install TheKeyMachine")
        self.install_button.setFixedHeight(dpi(44))
        self.install_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.install_button.setStyleSheet(
            """
            QPushButton {
                background-color: #456f4b;
                color: #eeeeee;
                border: 1px solid #587d5d;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:enabled:hover {
                background-color: #527f59;
                border-color: #6b916f;
            }
            QPushButton:enabled:pressed {
                background-color: #395f40;
                border-color: #4d7052;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
                border-color: #383838;
            }
            QPushButton:disabled:hover {
                background-color: #2a2a2a;
            }
            QPushButton:disabled:pressed {
                background-color: #2a2a2a;
            }
            """
        )
        layout.addWidget(self.install_button)

        self.open_scripts_button = QtWidgets.QPushButton("Open Maya scripts folder")
        self.open_scripts_button.setFixedHeight(dpi(32))
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setFixedHeight(dpi(32))

        secondary_actions = QtWidgets.QHBoxLayout()
        secondary_actions.setContentsMargins(0, 0, 0, 0)
        secondary_actions.setSpacing(dpi(8))
        secondary_actions.addWidget(self.open_scripts_button, 2)
        secondary_actions.addWidget(self.cancel_button, 1)
        layout.addLayout(secondary_actions)

        self.accept_checkbox.toggled.connect(self._refresh_state)
        self.install_button.clicked.connect(self._install)
        self.open_scripts_button.clicked.connect(self._open_scripts_folder)
        self.cancel_button.clicked.connect(self.reject)

    def _refresh_state(self):
        src_exists = os.path.isdir(source_dir())
        accepted = self.accept_checkbox.isChecked()

        self.install_button.setEnabled(src_exists and accepted)

        if not src_exists:
            self.status_label.setText("Source folder missing: TheKeyMachine")
            self.status_label.setStyleSheet("color: #d66; font-size: 10px;")
        else:
            self.status_label.setText(version_string())
            self.status_label.setStyleSheet("color: #888; font-size: 10px;")

    def set_status(self, text):
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #888; font-size: 10px;")

    def set_installing(self, installing):
        installing = bool(installing)
        self.accept_checkbox.setEnabled(not installing)
        self.open_scripts_button.setEnabled(not installing)
        self.cancel_button.setEnabled(not installing)
        if installing:
            self.install_button.setEnabled(False)
        else:
            self._refresh_state()

    def _install(self):
        install_thekeymachine(self)

    def _open_scripts_folder(self):
        path = scripts_dir()

        try:
            if not os.path.exists(path):
                os.makedirs(path)

            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile(path)
            )
        except Exception:
            traceback.print_exc()
            show_error(
                self,
                "Open Folder Error",
                "Could not open Maya scripts folder.",
                traceback.format_exc(),
            )


def close_existing_window():
    try:
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.objectName() == WINDOW_NAME:
                widget.close()
                widget.deleteLater()
    except Exception:
        pass

    try:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME, window=True)
    except Exception:
        pass


def TheKeyMachine_installer():
    if sys.version_info.major < 3:
        cmds.confirmDialog(
            title="Python Version Error",
            message="TheKeyMachine requires Python 3.",
            button=["OK"],
        )
        return None

    app_instance()
    close_existing_window()

    window = TheKeyMachineInstallerDialog(maya_main_window())
    window.show()
    window.raise_()
    window.activateWindow()

    return window


def onMayaDroppedPythonFile(*args, **kwargs):
    """
    Maya calls this when the file is dragged into the viewport.

    Maya 2022/2023/2024 commonly passes one argument.
    Some versions/tools may pass none or extra args.
    Keep *args/**kwargs so drag and drop never fails because of signature mismatch.
    """
    try:
        reload_installer_module()
    except Exception:
        traceback.print_exc()
    return TheKeyMachine_installer()


if __name__ == "__main__":
    TheKeyMachine_installer()
