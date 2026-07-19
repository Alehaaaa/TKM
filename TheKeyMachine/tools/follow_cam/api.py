from maya import cmds

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.selectionMod as selectionMod
import TheKeyMachine.widgets.util as wutil


followCam_original_camera = None
FOLLOW_CAM_GROUP = "tkm_followCam"
FOLLOW_CAM_ORIGINAL_CAMERA_ATTR = "tkmOriginalCamera"


def _active_model_panel():
    candidates = []
    for query in (
        lambda: cmds.getPanel(withFocus=True),
        lambda: cmds.playblast(activeEditor=True),
        lambda: cmds.getPanel(visiblePanels=True),
    ):
        try:
            result = query()
        except Exception:
            continue
        candidates.extend(result if isinstance(result, (list, tuple)) else [result])

    for panel in candidates:
        if not panel:
            continue
        try:
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                return panel
        except Exception:
            continue
    return None


def _camera_transform(camera):
    if not camera or not cmds.objExists(camera):
        return None
    try:
        if cmds.nodeType(camera) == "camera":
            parents = cmds.listRelatives(camera, parent=True, fullPath=True) or []
            return parents[0] if parents else None
    except Exception:
        return None
    return camera


def _is_follow_camera(camera):
    camera = _camera_transform(camera)
    if not camera or not cmds.objExists("followCam"):
        return False
    camera_paths = cmds.ls(camera, long=True) or []
    follow_paths = cmds.ls("followCam", long=True) or []
    return bool(set(camera_paths).intersection(follow_paths))


def _stored_follow_camera():
    plug = "{}.{}".format(FOLLOW_CAM_GROUP, FOLLOW_CAM_ORIGINAL_CAMERA_ATTR)
    if cmds.objExists(plug):
        try:
            camera = cmds.getAttr(plug)
            if camera and cmds.objExists(camera):
                return camera
        except Exception:
            pass
    return None


def _store_follow_camera(camera):
    if not camera or not cmds.objExists(FOLLOW_CAM_GROUP):
        return
    plug = "{}.{}".format(FOLLOW_CAM_GROUP, FOLLOW_CAM_ORIGINAL_CAMERA_ATTR)
    if not cmds.objExists(plug):
        cmds.addAttr(FOLLOW_CAM_GROUP, longName=FOLLOW_CAM_ORIGINAL_CAMERA_ATTR, dataType="string")
    cmds.setAttr(plug, camera, type="string")


def create_follow_cam(translation=True, rotation=True, *args):
    global followCam_original_camera

    selected_objects = selectionMod.get_selected_objects()

    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()

    if not selected_objects:
        return wutil.make_inViewMessage("Select at least one object")

    target_object = selected_objects[0]

    panel = _active_model_panel()
    if not panel:
        return wutil.make_inViewMessage("Focus a model viewport before creating Follow Cam")
    camera = _camera_transform(cmds.modelEditor(panel, query=True, camera=True))
    if not camera:
        return wutil.make_inViewMessage("The active viewport has no valid camera")
    stored_camera = _stored_follow_camera()
    viewing_follow_cam = _is_follow_camera(camera)
    if not viewing_follow_cam:
        followCam_original_camera = camera
    elif stored_camera:
        followCam_original_camera = stored_camera

    if cmds.objExists("tkm_followCam"):
        follow_cam = cmds.duplicate(camera, name="followCam_tmp")[0]
        follow_cam_group = cmds.group(follow_cam, name="tkm_followCam_tmp")
    else:
        follow_cam = cmds.duplicate(camera, name="followCam")[0]
        follow_cam_group = cmds.group(follow_cam, name="tkm_followCam")

    cmds.parent(follow_cam_group, "TheKeyMachine")
    cmds.parent(follow_cam_group, world=True)

    if translation and not rotation:
        cmds.pointConstraint(target_object, follow_cam_group, maintainOffset=True)
    else:
        skip_trans = []
        skip_rot = []

        if not translation:
            skip_trans = ["x", "y", "z"]
        if not rotation:
            skip_rot = ["x", "y", "z"]

        cmds.parentConstraint(target_object, follow_cam_group, maintainOffset=True, skipTranslate=skip_trans, skipRotate=skip_rot)

    cmds.parent(follow_cam_group, "TheKeyMachine")

    if cmds.objExists("tkm_followCam_tmp"):
        cmds.delete("tkm_followCam")
        cmds.rename("tkm_followCam_tmp", "tkm_followCam")
        cmds.rename("followCam_tmp", "followCam")
        follow_cam = "followCam"

    _store_follow_camera(followCam_original_camera or stored_camera or "persp")

    if not viewing_follow_cam:
        cmds.lookThru(panel, follow_cam)

    cmds.select(selected_objects)


def remove_follow_cam(*args):
    global followCam_original_camera
    if not cmds.objExists(FOLLOW_CAM_GROUP):
        return wutil.make_inViewMessage("No followCam in the scene")

    panel = _active_model_panel()
    restore_camera = _stored_follow_camera() or followCam_original_camera
    if not restore_camera or not cmds.objExists(restore_camera):
        restore_camera = "persp" if cmds.objExists("persp") else None

    cmds.delete(FOLLOW_CAM_GROUP)
    followCam_original_camera = None

    if panel and restore_camera:
        cmds.lookThru(panel, restore_camera)
