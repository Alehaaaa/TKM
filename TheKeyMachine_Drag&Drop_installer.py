
'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine an open source software for Autodesk Maya, licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html            
                                                                                                                                              
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
                                                                                                                                             


'''



import sys
import os
import platform
import shutil
import logging
from functools import partial

import maya.cmds as cmds
import maya.mel as mel
import maya.utils as utils
import maya.OpenMayaUI as omui

try:
    from shiboken2 import wrapInstance
    from PySide2 import QtWidgets
    from PySide2.QtWidgets import QApplication, QDesktopWidget
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    from PySide2.QtCore import QTimer
except ImportError:
    from shiboken6 import wrapInstance
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from PySide6.QtCore import *
    from PySide6.QtGui import *
    from PySide6.QtWidgets import *




TKM_VERSION = "Beta 0.1.4 / Build 306"


def get_screen_resolution():
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    try:
        # PySide2
        from PySide2.QtGui import QDesktopWidget
        desktop = QDesktopWidget()
        screen_rect = desktop.screenGeometry()
    except ImportError:
        # PySide6
        screen = app.primaryScreen()
        screen_rect = screen.geometry()

    screen_width = screen_rect.width()
    screen_height = screen_rect.height()
    
    return screen_width, screen_height


def update_maya_env():
    version_maya = cmds.about(version=True)
    user_dir = cmds.internalVar(userAppDir=True)
    maya_dir = os.path.join(user_dir, version_maya)
    
    env_file_path = os.path.join(maya_dir, "Maya.env")
    
    user_app_folder = cmds.internalVar(userAppDir=True)
    tkm_img_folder = os.path.join(user_app_folder, "scripts/TheKeyMachine/data/img")
    
    new_line = f"\n# THIS LINE IS HERE FOR UNINSTALLING PURPOSES, PLEASE DO NOT TOUCH. START OF THEKEYMACHINE CODE\nXBMLANGPATH = {tkm_img_folder};%XBMLANGPATH%\n# END OF THEKEYMACHINE CODE\n"
    
    if platform.system() != 'Windows':
        new_line = f"\n# THIS LINE IS HERE FOR UNINSTALLING PURPOSES, PLEASE DO NOT TOUCH. START OF THEKEYMACHINE CODE\nXBMLANGPATH = {tkm_img_folder}:$XBMLANGPATH\n# END OF THEKEYMACHINE CODE\n"

    if not os.path.exists(env_file_path):
        with open(env_file_path, 'w') as file:
            file.write(new_line)
    else:
        with open(env_file_path, 'a') as file:
            file.write(new_line)




def onMayaDroppedPythonFile(*args):
    QApplication.processEvents()
    utils.executeDeferred(TheKeyMachine_installer)

def install(button, checkbox, tkm_version, window):
    screen_width, screen_height = get_screen_resolution()
    screen_width = screen_width

    if not checkbox.isChecked():
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle("License Agreement")
        msg_box.setText("You must accept the license agreement.")
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        ok_button = msg_box.addButton('OK', QtWidgets.QMessageBox.AcceptRole)
        ok_button.setMinimumHeight(30)
        ok_button.setMinimumWidth(80)
        msg_box.exec()
        return

    current_dir = os.path.dirname(__file__)
    source_dir = os.path.join(current_dir, 'TheKeyMachine')

    user_dir = cmds.internalVar(userAppDir=True)
    destination_dir = os.path.join(user_dir, "scripts", "TheKeyMachine")

    if not os.path.exists(os.path.join(user_dir, "scripts")):
        os.makedirs(os.path.join(user_dir, "scripts"))

    if os.path.exists(destination_dir):
        uninstalled_folder_path = os.path.join(destination_dir, "uninstalled")
        if os.path.exists(uninstalled_folder_path):
            shutil.rmtree(destination_dir)
            print("Old TheKeyMachine folder removed.")
        else:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setWindowTitle("Installation Warning")
            msg_box.setText("TheKeyMachine folder already exists in the scripts directory. Please remove it before proceeding with the installation.")
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            ok_button = msg_box.addButton('OK', QtWidgets.QMessageBox.AcceptRole)
            ok_button.setMinimumHeight(30)
            ok_button.setMinimumWidth(80)
            msg_box.exec()
            return

    try:
        shutil.copytree(source_dir, destination_dir)
    except Exception as e:
        QtWidgets.QMessageBox.critical(
            button, "Installation Error", f"An error occurred while copying files: {str(e)}")
        return

    update_maya_env()

    tkm_version.setText("<p style='color: #b9e861;'>Installation completed</p>")
    tkm_version.setGeometry(222, 190, 250, 20) 

    if screen_width == 3840:
        tkm_version.setGeometry(320, 190, 250, 20) 

    QTimer.singleShot(1600, window.close)
    QTimer.singleShot(1700, load_ui)


def load_ui():

    import importlib
    import TheKeyMachine.core.toolbar
    TheKeyMachine.core.toolbar.tb.create_shelf_icon()
    importlib.reload(TheKeyMachine.core.toolbar)
    TheKeyMachine.core.toolbar.tb.startUI()

def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

def TheKeyMachine_installer():
    screen_width, screen_height = get_screen_resolution()
    screen_width = screen_width

    os_platform = platform.system()
    python_version = f"{sys.version_info.major}{sys.version_info.minor}"
    supported_os = ['Windows', 'Linux', 'Darwin']
    supported_python_versions = ['37', '39', '310', '311']

    if os_platform in supported_os and python_version in supported_python_versions:

        global TKM_VERSION

        try:
            cmds.deleteUI("TheKeyMachineInstaller", window=True)
        except:
            pass

        parent = maya_main_window()
        window = QtWidgets.QMainWindow(parent)
        window.setObjectName("TheKeyMachineInstaller")
        window.setWindowTitle("TheKeyMachine Installer")

        window.setFixedSize(550, 600)

        parent_geometry = parent.geometry()
        if screen_width == 3840:
            center_x = parent_geometry.center().x() - 1000 * 0.5
            center_y = parent_geometry.center().y() - 1000 * 0.5
        else:
            center_x = parent_geometry.center().x() - 550 * 0.5
            center_y = parent_geometry.center().y() - 700 * 0.5

        window.move(center_x, center_y)

        image_path = os.path.join(os.path.dirname(__file__), 'TheKeyMachine', 'data', 'img', 'TheKeyMachine_logo_250.png')
        image_label = QLabel(window)
        pixmap = QPixmap(image_path)
        image_label.setPixmap(pixmap)
        image_label.setGeometry(150, 1, 250, 200)

        label_below_image = QLabel("Animation toolset for Maya Animators", window)
        label_below_image.setGeometry(175, 152, 250, 20)

        tkm_version = QLabel(TKM_VERSION, window)
        tkm_version.setGeometry(220, 190, 250, 20)

        text_label = QLabel(window)
        text_label.setGeometry(40, 230, 480, 100)
        text_label.setText("This script will install TheKeyMachine on your computer. "
                           "Please note that this is a beta version, so there may be errors and even Maya crashes. "
                           "By installing this software, you agree to abide by the terms and conditions of the license agreement "
                           "and the Privacy Policy. Please read both agreements carefully before proceeding.")

        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignLeft)

        license_text = QTextEdit(window)
        license_text.setGeometry(35, 320, 480, 150)

        license_text_code = '''
        By using this software, you agree to be bound by the following terms and conditions based on the GNU General Public License (GPL) version 3.0:<br><br>

        <b>1. Freedom to Use:</b><br>
        You are free to use, copy, modify, and distribute the software for any purpose, as long as you comply with the terms of the GPL.<br><br>

        <b>2. Copyleft:</b><br>
        If you modify the software and distribute your modified version, you must make the source code available to the recipients and license it under the same GPL 3.0 terms. This ensures that the freedoms you received are preserved for others.<br><br>

        <b>3. No Warranty:</b><br>
        The software is provided "as-is" without any warranty. The authors are not liable for any damages or issues that arise from using the software.<br><br>

        <b>4. Redistribution:</b><br>
        You may distribute copies of the software, including modifications, under the terms of the GPL 3.0. However, you must make sure that the recipients are aware of the GPL license and have access to the source code.<br><br>

        <b>5. Tivoization:</b><br>
        If you distribute the software with hardware, you must not impose restrictions that prevent users from modifying the software and running their modified versions on that hardware.<br><br>

        <b>6. Patents:</b><br>
        If you distribute the software, you grant users a license to use any patents you hold that are necessary for them to use the software. You cannot initiate patent lawsuits related to the software.<br><br>

        <b>7. Compatibility with Other Licenses:</b><br>
        The GPL 3.0 may not be compatible with other licenses. If you combine GPL-licensed software with software under a different license, the combined work must comply with the GPL.<br><br>

        <b>8. Jurisdiction:</b><br>
        In case of legal disputes, the GPL allows users to bring issues to courts under the jurisdiction of their local legal system. For further information, consult the full GPL 3.0 license.<br><br>

        By using or distributing this software, you acknowledge that you have read, understood, and agree to be bound by the terms and conditions of the GPL 3.0 license.
        '''


        license_text.setHtml(license_text_code)
        license_text.setReadOnly(True)
        license_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        license_checkbox = QCheckBox("I accept the terms and conditions of the license agreement and the Privacy Policy", window)
        license_checkbox.setGeometry(35, 500, 480, 30)

        button = QtWidgets.QPushButton("Install TheKeyMachine", window)
        button.setStyleSheet('''
            QPushButton {
                color: #ccc;
                background-color: #5d5d5d;
                border-radius: 5px;
                font: 12px;
            }
            QPushButton:hover:!pressed {
                color: #ccc;
                background-color: #7a7a7a;
                border-radius: 5px;
                font: 12px;
            }
        ''')
        button.setGeometry(35, 540, 480, 40)
        button.clicked.connect(lambda: install(button, license_checkbox, tkm_version, window))

        if screen_width == 3840:
            window.setFixedSize(800, 900)
            image_label.setGeometry(270, 1, 250, 200)
            label_below_image.setGeometry(265, 155, 350, 20)
            tkm_version.setGeometry(320, 190, 350, 20)
            text_label.setGeometry(40, 230, 730, 150)
            license_text.setGeometry(35, 350, 730, 350)
            license_checkbox.setGeometry(35, 700, 750, 80)
            button.setGeometry(35, 800, 730, 60)

            button.setStyleSheet('''
                QPushButton {
                    color: #ccc;
                    background-color: #5d5d5d;
                    border-radius: 5px;
                    font: 18px;
                }
                QPushButton:hover:!pressed {
                    color: #ccc;
                    background-color: #7a7a7a;
                    border-radius: 5px;
                    font: 18px;
                }
            ''')


        window.show()
    else:
        cmds.confirmDialog(title='Error',
                           message='Oh no! Unfortunately, you are using an incompatible version of Maya or operating system. TheKeyMachine is only available for Maya 2022, 2023, 2024 on Linux, Windows and MacOS.',
                           button=['Ok'],
                           defaultButton='Ok')

TheKeyMachine_installer()
