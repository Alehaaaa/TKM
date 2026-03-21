from __future__ import division
import os
import ssl
import json
import shutil
import zipfile
import sys
import maya.cmds as cmds
import maya.mel as mel

if sys.version_info[0] > 2:
    import urllib.request as urllib_request
    import urllib.error as urllib_error
    from http.client import responses
else:
    import urllib2 as urllib_request
    import urllib2 as urllib_error
    import httplib

    responses = httplib.responses

try:
    from importlib import reload
except ImportError:
    pass

try:
    from PySide6.QtCore import QTimer, QThread, Signal
except ImportError:
    from PySide2.QtCore import QTimer, QThread, Signal

from TheKeyMachine.mods.generalMod import get_thekeymachine_version

from TheKeyMachine.widgets.customDialogs import QFlatConfirmDialog, QFlatTooltipConfirm

from TheKeyMachine.mods import mediaMod as media
import TheKeyMachine.widgets.util as util
import TheKeyMachine.mods.settingsMod as settings

try:
    from PySide6 import QtGui
except ImportError:
    from PySide2 import QtGui


# Constants
REPO = "https://raw.githubusercontent.com/Alehaaaa/TKM/main/"
NO_DATA_ERROR = "<hl>No Data</hl>\nCould not sync with the server."
NO_SERVER_ERROR = "<hl>%s %s</hl>\nCould not sync with the server."

# SSL Context
unverified_ssl_context = ssl.create_default_context()
unverified_ssl_context.check_hostname = False
unverified_ssl_context.verify_mode = ssl.CERT_NONE


def formatPath(path):
    path = str(path).replace("/", os.sep)
    path = path.replace("\\", os.sep)
    return path


def compare_versions(version1, version2):
    import re

    def normalize(v):
        return [int(x) for x in re.sub(r"[^0-9.]", "", str(v)).split(".") if x]

    v1 = normalize(version1)
    v2 = normalize(version2)

    # Pad to equal length
    max_len = max(len(v1), len(v2))
    v1.extend([0] * (max_len - len(v1)))
    v2.extend([0] * (max_len - len(v2)))

    for i in range(max_len):
        if v1[i] > v2[i]:
            return 1
        elif v1[i] < v2[i]:
            return -1
    return 0


def download(downloadUrl, saveFile):
    response = urllib_request.urlopen(downloadUrl, context=unverified_ssl_context, timeout=60)

    if response is None:
        cmds.warning("Error trying to install.")
        return

    total_size = response.getheader("Content-Length")
    total_size = int(total_size) if total_size else 0
    block_size = 8192

    try:
        gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
        if total_size > 0 and gMainProgressBar:
            cmds.progressBar(
                gMainProgressBar,
                edit=True,
                beginProgress=True,
                isInterruptable=False,
                status="Downloading Update...",
                maxValue=total_size,
            )
    except Exception:
        gMainProgressBar = None

    downloaded = 0
    try:
        with open(saveFile, "wb") as output:
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                output.write(buffer)
                if gMainProgressBar and total_size > 0:
                    cmds.progressBar(gMainProgressBar, edit=True, progress=downloaded)
    finally:
        if gMainProgressBar and total_size > 0:
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
    return True


def install(command=None, file_path=None):
    # Derive the actual installation path of TKM
    toolsFolder = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    scriptPath = os.path.dirname(toolsFolder)

    tmpZipFile = os.path.join(scriptPath, "tmp.zip")

    if os.path.isfile(tmpZipFile):
        try:
            os.remove(tmpZipFile)
        except OSError:
            pass

    if file_path:
        shutil.copy(file_path, tmpZipFile)
    else:
        sha = "main"
        if "raw.githubusercontent.com" in REPO:
            parts = str(REPO).split("raw.githubusercontent.com/")[-1].strip("/").split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                branch = parts[2] if len(parts) > 2 else "main"
                try:
                    api_url = "https://api.github.com/repos/%s/%s/commits/%s" % (owner, repo, branch)
                    req = urllib_request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib_request.urlopen(req, context=unverified_ssl_context, timeout=10) as response:
                        if response.status == 200:
                            data = json.loads(response.read().decode("utf-8"))
                            sha = data.get("sha", "main")
                except Exception:
                    pass

        FileUrl = "https://github.com/Alehaaaa/TKM/archive/%s.zip" % sha
        download(FileUrl, tmpZipFile)

    if not os.path.isfile(tmpZipFile):
        return cmds.error("Error trying to install.")

    zfobj = zipfile.ZipFile(tmpZipFile)
    fileList = zfobj.namelist()

    if not fileList:
        return cmds.error("Error trying to install.")

    # Remove old tools files cautiously - only files inside TheKeyMachine
    if os.path.isdir(toolsFolder) and os.path.basename(toolsFolder) == "TheKeyMachine":
        for item in os.listdir(toolsFolder):
            item_path = os.path.join(toolsFolder, item)
            if item == "data":  # maybe skip data or not? user_data is outside
                continue
            if os.path.isfile(item_path):
                try:
                    os.remove(item_path)
                except OSError:
                    pass
            elif os.path.isdir(item_path):
                try:
                    shutil.rmtree(item_path)
                except OSError:
                    pass

    for name in fileList:
        # GitHub archives look like: TKM-main/TheKeyMachine/__init__.py
        parts = name.replace("\\", "/").split("/")

        try:
            aleha_idx = parts.index("TheKeyMachine")
            rel_parts = parts[aleha_idx + 1 :]
        except ValueError:
            continue

        if not rel_parts:
            # This is the directory itself
            continue

        filename = os.path.join(toolsFolder, *rel_parts)
        d = os.path.dirname(filename)

        if not os.path.exists(d):
            os.makedirs(d)

        if name.endswith("/") or name.endswith(os.sep):
            continue

        uncompressed = zfobj.read(name)
        with open(filename, "wb") as output:
            output.write(uncompressed)

    zfobj.close()
    if os.path.isfile(tmpZipFile):
        os.remove(tmpZipFile)

    return True


def _fetch_repo_file(filename):
    sha = "main"
    if "raw.githubusercontent.com" in REPO:
        parts = str(REPO).split("raw.githubusercontent.com/")[-1].strip("/").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            branch = parts[2] if len(parts) > 2 else "main"
            api_url = "https://api.github.com/repos/%s/%s/commits/%s" % (owner, repo, branch)
            try:
                req = urllib_request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib_request.urlopen(req, context=unverified_ssl_context, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        if "sha" in data:
                            sha = data["sha"]
            except Exception:
                pass

    url = REPO.replace("/main/", "/%s/TheKeyMachine/" % sha) + filename
    success, result = _download_text(url)

    if not success and sha != "main":
        success, result = _download_text(REPO + "TheKeyMachine/" + filename)

    return success, result


def _download_text(url):
    try:
        with urllib_request.urlopen(url, context=unverified_ssl_context, timeout=30) as response:
            if response.status == 200:
                text = response.read().decode("utf-8")
                if not text:
                    return False, NO_DATA_ERROR
                return True, text
            else:
                error_message = responses.get(response.status, "Unknown Error")
                return False, NO_SERVER_ERROR % (response.status, error_message)
    except urllib_error.URLError as e:
        reason = getattr(e, "reason", e)
        return False, "Network error: %s" % reason
    except TimeoutError:
        return False, "Connection timed out."
    except Exception as e:
        return False, "Unexpected error: %s" % e


def get_latest_version():
    success, result = _fetch_repo_file("version")
    if success:
        return True, result.strip()
    return False, result


class UpdateCheckWorker(QThread):
    finished = Signal(bool, object)

    def __init__(self, installed_version, force=False, delay=0, parent=None):
        QThread.__init__(self, parent)
        self.installed_version = installed_version
        self.force = force
        self.delay = delay

    def run(self):
        if self.delay > 0:
            self.msleep(self.delay)

        success, latest_version = get_latest_version()
        if not success:
            self.finished.emit(False, latest_version)
            return

        comp = compare_versions(latest_version, self.installed_version)
        if comp <= 0 and not self.force:
            self.finished.emit(True, None)
            return
        elif comp <= 0 and self.force:
            # We still want to let them know they are up to date instead of prompting a false update.
            self.finished.emit(True, None)
            return

        self.finished.emit(True, latest_version)


updater_worker = None


def check_for_updates(anchor_widget=None, warning=True, force=False):
    global updater_worker
    if updater_worker is not None and updater_worker.isRunning():
        return

    installed_version = get_thekeymachine_version()

    def handle_result(success, latest_version):
        global updater_worker
        updater_worker = None

        if not success:
            if warning:
                util.make_inViewMessage(latest_version)  # latest_version contains error msg here
            return

        if latest_version is None:
            if warning:
                util.make_inViewMessage("<hl>" + installed_version + "</hl>\nYou are up-to-date.")
            return

        # Update the icon
        if anchor_widget and hasattr(anchor_widget, "setIcon"):
            anchor_widget.setIcon(QtGui.QIcon(media.settings_update_image))

        # If we are skipping updates and this isn't a forced check, don't do anything else
        if not force and settings.get_setting("skip_updates", False):
            return

        template = (
            "<title>Version {} available\n(using {})</title>\n".format(latest_version, installed_version)
            + "<text>A new version of TheKeyMachine is available to download and install.</text>\n"
        )

        if anchor_widget:
            result = QFlatTooltipConfirm.question(
                anchor_widget,
                title="Update available",
                template=template,
                icon=media.getImage("update.svg"),
                buttons=[
                    QFlatTooltipConfirm.CustomButton("Install", positive=True, icon=media.getImage("install.png")),
                    QFlatTooltipConfirm.CustomButton("Skip", positive=True, icon=media.getImage("skip.png")),
                    QFlatTooltipConfirm.No,
                ],
                highlight="Install",
            )
        else:
            result = QFlatConfirmDialog.question(
                None,
                "Update available",
                title=f"Version {latest_version.strip()} available",
                message="A new version of TheKeyMachine is available to download and install.",
                icon=media.getImage("update.svg"),
                buttons=[
                    QFlatConfirmDialog.CustomButton("Install", positive=True, icon=media.getImage("install.png")),
                    QFlatConfirmDialog.CustomButton("Skip", positive=True, icon=media.getImage("skip.png")),
                    QFlatConfirmDialog.No,
                ],
                highlight="Install",
            )

        if result and result.get("positive"):
            if result.get("name") == "Install":
                if not install():
                    return

                # Reset skip setting on successful manual install
                settings.set_setting("skip_updates", False)

                def _post_update():
                    import TheKeyMachine.core.toolbar as ui

                    reload(ui)

                    QFlatConfirmDialog.information(
                        None,
                        "Updated",
                        title=f"Installed TheKeyMachine {latest_version.strip()}",
                        message="You have successfully updated the tool!<br><br>\nPlease restart Maya if you experience any issues.",
                        icon=media.getImage("success.svg"),
                        closeButton=True,
                    )

                QTimer.singleShot(100, _post_update)

            elif result.get("name") == "Skip":
                settings.set_setting("skip_updates", True)

    delay = 0 if warning or force else 1000
    updater_worker = UpdateCheckWorker(installed_version, force=force, delay=delay)
    updater_worker.finished.connect(handle_result)
    updater_worker.start()
