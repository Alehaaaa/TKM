from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.copy_paste import api


TOOLTIPS = load_tooltips(__file__)


class CopyPasteToolObject(ToolObject):
    ORDER = 450
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"

    TOOLS = {
        "copy_pose": {
            "type": "tool", "label": "Copy Pose", "icon": "copy_pose",
            "callback": api.copy_pose, "tooltip": TOOLTIPS["copy_pose"],
            "menu": {
                "label": "Copy Pose", "icon": "copy_pose",
                "items": [
                    "paste_pose", "paste_mirror_pose", "separator",
                    {"command": "paste_pose_to", "label": "Paste Pose To..."},
                    "separator",
                    {"command": "import_pose_file", "label": "Import Pose"},
                    {"command": "export_pose_file", "label": "Export Pose"},
                ],
            },
        },
        "paste_pose": {
            "type": "tool", "label": "Paste Pose", "icon": "paste_pose",
            "callback": api.paste_pose, "tooltip": TOOLTIPS["paste_pose"],
        },
        "paste_mirror_pose": {
            "type": "tool", "label": "Paste Mirror Pose", "icon": "paste_opposite_animation",
            "callback": api.paste_mirror_pose, "tooltip": TOOLTIPS["paste_mirror_pose"],
        },
        "paste_pose_to": {
            "type": "tool", "label": "Paste Pose To", "icon": "paste_pose",
            "callback": api.paste_pose_to, "tooltip": TOOLTIPS["paste_pose_to"],
        },
        "export_pose_file": {
            "type": "tool", "label": "Export Pose", "icon": "export",
            "callback": api.export_pose_file, "tooltip": TOOLTIPS["export_pose"],
        },
        "import_pose_file": {
            "type": "tool", "label": "Import Pose", "icon": "import",
            "callback": api.import_pose_file, "tooltip": TOOLTIPS["import_pose"],
        },
        "copy_animation": {
            "type": "tool", "label": "Copy Animation", "icon": "copy_animation",
            "callback": api.copy_animation, "tooltip": TOOLTIPS["copy_animation"],
            "menu": {
                "label": "Copy Animation", "icon": "copy_animation",
                "items": [
                    {"command": "paste_insert_animation", "label": "Paste Insert"},
                    {"command": "paste_animation", "label": "Paste Replace"},
                    {"command": "paste_opposite_animation", "label": "Paste Mirror Animation"},
                    "separator",
                    {"command": "paste_animation_to", "label": "Paste Animation To..."},
                    "separator",
                    {"command": "import_animation_file", "label": "Import Animation"},
                    {"command": "export_animation_file", "label": "Export Animation"},
                ],
            },
        },
        "paste_animation": {
            "type": "tool", "label": "Paste Replace Animation", "icon": "paste_animation",
            "callback": api.paste_animation, "tooltip": TOOLTIPS["paste_animation"],
        },
        "paste_insert_animation": {
            "type": "tool", "label": "Paste Insert Animation", "icon": "paste_insert_animation",
            "callback": api.paste_insert_animation, "tooltip": TOOLTIPS["paste_insert_animation"],
        },
        "paste_opposite_animation": {
            "type": "tool", "label": "Paste Mirror Animation", "icon": "paste_opposite_animation",
            "callback": api.paste_opposite_animation, "tooltip": TOOLTIPS["paste_opposite_animation"],
        },
        "paste_animation_to": {
            "type": "tool", "label": "Paste Animation To", "icon": "paste_animation",
            "callback": api.paste_animation_to, "tooltip": TOOLTIPS["paste_animation_to"],
        },
        "export_animation_file": {
            "type": "tool", "label": "Export Animation", "icon": "export",
            "callback": api.export_animation_file, "tooltip": TOOLTIPS["export_animation"],
        },
        "import_animation_file": {
            "type": "tool", "label": "Import Animation", "icon": "import",
            "callback": api.import_animation_file, "tooltip": TOOLTIPS["import_animation"],
        },
    }

    SECTION = {
        "id": "pose_animation_section",
        "label": "Pose & Animation",
        "color": COLORS.toolbar.green.hex,
        "items": [
            {
                "id": "copy_pose",
                "shortcuts": [
                    {"id": "paste_pose", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_pose_to", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_pose"},
            {"id": "paste_mirror_pose"},
            {"id": "paste_pose_to"},
            {"id": "export_pose_file"},
            {"id": "import_pose_file"},
            "separator",
            {
                "id": "copy_animation",
                "shortcuts": [
                    {"id": "paste_animation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "paste_insert_animation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_opposite_animation", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_animation"},
            {"id": "paste_insert_animation"},
            {"id": "paste_opposite_animation"},
            {"id": "paste_animation_to"},
            {"id": "export_animation_file"},
            {"id": "import_animation_file"},
        ],
    }
