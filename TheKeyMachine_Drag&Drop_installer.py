"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine an open source software for Autodesk Maya, licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html


Developed by: Rodrigo Torres / rodritorres.com



"""

import sys
import os
import shutil

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from shiboken2 import wrapInstance
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from shiboken6 import wrapInstance
    from PySide6 import QtWidgets, QtCore, QtGui

__version__ = "0.1.90"
__stage__ = "beta"
__build__ = "316"
__codename__ = "Cold Brew"


def get_dpi_scale():
    try:
        from PySide2.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app.devicePixelRatio()


def DPI(value):
    return int(value * get_dpi_scale())


def install(button, tkm_version_label, window):
    current_dir = os.path.dirname(__file__)
    source_dir = os.path.join(current_dir, "TheKeyMachine")
    user_dir = cmds.internalVar(userAppDir=True)
    destination_dir = os.path.normpath(os.path.join(user_dir, "scripts", "TheKeyMachine"))

    if not os.path.exists(source_dir):
        QtWidgets.QMessageBox.critical(window, "Installation Error", "Source 'TheKeyMachine' folder not found in the installer directory.")
        return

    # Ensure scripts directory exists
    os.makedirs(os.path.dirname(destination_dir), exist_ok=True)

    # Handle existing installation
    if os.path.exists(destination_dir):
        msg = "TheKeyMachine is already installed. Do you want to overwrite it?"
        res = QtWidgets.QMessageBox.question(window, "Already Installed", msg, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if res == QtWidgets.QMessageBox.Yes:
            try:
                shutil.rmtree(destination_dir)
            except Exception as e:
                QtWidgets.QMessageBox.critical(window, "Error", f"Could not remove old installation: {e}")
                return
        else:
            return

    try:
        shutil.copytree(source_dir, destination_dir)
    except Exception as e:
        QtWidgets.QMessageBox.critical(window, "Installation Error", f"Failed to copy files: {e}")
        return

    tkm_version_label.setText("<p style='color: #b9e861; font-weight: bold;'>Installation Completed Successfully!</p>")

    # Reload and create shelf icon
    QtCore.QTimer.singleShot(1500, window.close)
    QtCore.QTimer.singleShot(1600, load_ui)


def load_ui():
    try:
        try:
            from importlib import reload
        except ImportError:
            from imp import reload
        except ImportError:
            pass
        import sys

        # Clean up any partial imports
        modules_to_del = [m for m in sys.modules if m.startswith("TheKeyMachine")]
        for m in modules_to_del:
            del sys.modules[m]

        import TheKeyMachine.core.toolbar as toolbar

        reload(toolbar)

        toolbar.show()
        if tb := toolbar.get_toolbar():
            tb.create_shelf_icon()
    except Exception as e:
        print(f"Error loading TheKeyMachine after install: {e}")


def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr:
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    return None


def TheKeyMachine_installer():
    if sys.version_info.major != 3:
        return cmds.confirmDialog(title="Error", message="TheKeyMachine requires Python 3.", button=["Ok"])

    try:
        cmds.deleteUI("TheKeyMachineInstaller", window=True)
    except Exception:
        pass

    parent = maya_main_window()
    window = QtWidgets.QDialog(parent)
    window.setObjectName("TheKeyMachineInstaller")
    window.setWindowTitle("TheKeyMachine Installer")
    window.setFixedSize(DPI(500), DPI(650))

    main_layout = QtWidgets.QVBoxLayout(window)
    main_layout.setContentsMargins(DPI(30), DPI(20), DPI(30), DPI(30))
    main_layout.setSpacing(DPI(15))

    # Header / Logo
    header_layout = QtWidgets.QVBoxLayout()
    header_layout.setAlignment(QtCore.Qt.AlignCenter)

    logo_path = os.path.join(os.path.dirname(__file__), "TheKeyMachine", "data", "img", "TheKeyMachine_logo_250.png")
    if os.path.exists(logo_path):
        logo_label = QtWidgets.QLabel()
        pix = QtGui.QPixmap(logo_path)
        logo_label.setPixmap(pix.scaled(DPI(220), DPI(220), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        header_layout.addWidget(logo_label)

    subtitle_label = QtWidgets.QLabel("Animation toolset for Maya Animators")
    subtitle_label.setStyleSheet("font-style: italic; color: #aaa;")
    subtitle_label.setAlignment(QtCore.Qt.AlignCenter)
    header_layout.addWidget(subtitle_label)

    version_str = f"v{__version__} {__stage__} (Build {__build__}) - {__codename__}"
    tkm_version_label = QtWidgets.QLabel(version_str)
    tkm_version_label.setStyleSheet("color: #888; font-size: 10px;")
    tkm_version_label.setAlignment(QtCore.Qt.AlignCenter)
    header_layout.addWidget(tkm_version_label)

    main_layout.addLayout(header_layout)

    # Info Text
    info_label = QtWidgets.QLabel(
        "This script will install TheKeyMachine. Please note that this is a beta version. By installing, you agree to the terms below."
    )
    info_label.setWordWrap(True)
    info_label.setStyleSheet("line-height: 140%;")
    main_layout.addWidget(info_label)

    # License Box
    license_text = QtWidgets.QTextEdit()
    license_text.setReadOnly(True)
    license_text.setHtml("""
        <div style='color: #bbb;'>
        <b>1. Freedom to Use:</b> You are free to use, modify, and distribute the software under GPL 3.0 terms.<br><br>
        <b>2. Copyleft:</b> Modifications must remain open source under the same license.<br><br>
        <b>3. No Warranty:</b> Provided "as-is" without any warranty. Authors are not liable for damages.<br><br>
        <b>4. Jurisdiction:</b> Local legal system applies for disputes.
        </div>
    """)
    license_text.setStyleSheet("background-color: #2b2b2b; border: 1px solid #3d3d3d; border-radius: 4px; padding: 5px;")
    main_layout.addWidget(license_text)

    # Acceptance
    license_checkbox = QtWidgets.QCheckBox("I accept the terms and conditions")
    main_layout.addWidget(license_checkbox)

    # Install Button
    install_btn = QtWidgets.QPushButton("Install TheKeyMachine")
    install_btn.setFixedHeight(DPI(45))
    install_btn.setCursor(QtCore.Qt.PointingHandCursor)
    install_btn.setEnabled(False)
    install_btn.setStyleSheet("""
        QPushButton {
            background-color: #444;
            color: #eee;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: #555; }
        QPushButton:pressed { background-color: #333; }
        QPushButton:disabled { background-color: #2a2a2a; color: #666; }
    """)
    main_layout.addWidget(install_btn)

    # Connections
    license_checkbox.toggled.connect(install_btn.setEnabled)
    install_btn.clicked.connect(lambda: install(install_btn, tkm_version_label, window))

    window.show()
