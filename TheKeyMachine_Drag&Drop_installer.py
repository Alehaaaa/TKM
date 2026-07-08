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

__version__ = "0.1.21"
__stage__ = "beta"
__build__ = "327"
__codename__ = "Flat White"

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
    try:
        ratio = app_instance().devicePixelRatio()
    except Exception:
        ratio = 1.0
    return int(value * ratio)


def installer_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def source_dir():
    return os.path.join(installer_dir(), "TheKeyMachine")


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


def remove_old_install(path):
    if not os.path.exists(path):
        return

    if not os.path.isdir(path):
        raise RuntimeError("Destination exists but is not a folder: {0}".format(path))

    shutil.rmtree(path)


def copy_install(src, dst):
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

    shutil.copytree(src, dst)


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


def install_thekeymachine(parent, install_button, status_label):
    src = source_dir()
    dst = destination_dir()

    install_button.setEnabled(False)
    status_label.setText("Installing...")
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
                status_label.setText(version_string())
                install_button.setEnabled(True)
                return

            status_label.setText("Removing old installation...")
            QtWidgets.QApplication.processEvents()
            remove_old_install(dst)

        status_label.setText("Copying files...")
        QtWidgets.QApplication.processEvents()
        copy_install(src, dst)

        status_label.setText("Installation completed. Loading TheKeyMachine...")
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
            status_label.setText("Installed, but automatic load failed.")
            install_button.setEnabled(True)
            return

        status_label.setText("Installation completed successfully.")
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
        status_label.setText("Installation failed.")
        install_button.setEnabled(True)


class TheKeyMachineInstallerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TheKeyMachineInstallerDialog, self).__init__(parent)

        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("TheKeyMachine Installer")
        self.setMinimumWidth(dpi(520))
        self.setMinimumHeight(dpi(640))

        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.Window
            | QtCore.Qt.WindowCloseButtonHint
        )

        self._build_ui()
        self._refresh_state()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(dpi(28), dpi(24), dpi(28), dpi(24))
        layout.setSpacing(dpi(14))

        header = QtWidgets.QVBoxLayout()
        header.setAlignment(QtCore.Qt.AlignCenter)
        header.setSpacing(dpi(8))

        logo_path = os.path.join(
            source_dir(),
            "data",
            "img",
            "TheKeyMachine_logo_250.png",
        )

        if os.path.exists(logo_path):
            logo = QtWidgets.QLabel()
            logo.setAlignment(QtCore.Qt.AlignCenter)

            pixmap = QtGui.QPixmap(logo_path)
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        dpi(210),
                        dpi(210),
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                )

            header.addWidget(logo)

        title = QtWidgets.QLabel("TheKeyMachine")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
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
        self.license_text.setMinimumHeight(dpi(145))
        self.license_text.setHtml(
            """
            <b>GPL-3.0 license summary</b><br><br>
            1. You may use, modify, and distribute this software.<br><br>
            2. Modified versions must remain open source under the same license.<br><br>
            3. The software is provided as-is, without warranty.<br><br>
            4. By installing, you accept these terms.
            """
        )
        self.license_text.setStyleSheet(
            "QTextEdit {"
            "background-color: #2b2b2b;"
            "border: 1px solid #444;"
            "border-radius: 5px;"
            "padding: 8px;"
            "}"
        )
        layout.addWidget(self.license_text)

        self.accept_checkbox = QtWidgets.QCheckBox("I accept the terms and conditions")
        layout.addWidget(self.accept_checkbox)

        self.install_button = QtWidgets.QPushButton("Install TheKeyMachine")
        self.install_button.setFixedHeight(dpi(44))
        self.install_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.install_button.setStyleSheet(
            """
            QPushButton {
                background-color: #444;
                color: #eee;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            """
        )
        layout.addWidget(self.install_button)

        self.open_scripts_button = QtWidgets.QPushButton("Open Maya scripts folder")
        self.open_scripts_button.setFixedHeight(dpi(32))
        layout.addWidget(self.open_scripts_button)

        self.accept_checkbox.toggled.connect(self._refresh_state)
        self.install_button.clicked.connect(self._install)
        self.open_scripts_button.clicked.connect(self._open_scripts_folder)

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

    def _install(self):
        install_thekeymachine(
            self,
            self.install_button,
            self.status_label,
        )

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
    return TheKeyMachine_installer()


if __name__ == "__main__":
    TheKeyMachine_installer()
