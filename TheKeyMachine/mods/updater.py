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
    from imp import reload
except ImportError:
    pass

from TheKeyMachine.Qt import QtCore, QtGui

QTimer = QtCore.QTimer
QThread = QtCore.QThread
Signal = QtCore.Signal

from TheKeyMachine.mods.generalMod import get_thekeymachine_version

from TheKeyMachine.widgets.customDialogs import QFlatConfirmDialog, QFlatTooltipConfirm

from TheKeyMachine.data import icons
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.mods.changelogMod as changelogMod


# Constants
REPO = "https://raw.githubusercontent.com/Alehaaaa/TKM/main/"
NO_DATA_ERROR = "<hl>No Data</hl>\nCould not sync with the server."
NO_SERVER_ERROR = "<hl>%s %s</hl>\nCould not sync with the server."
_REPO_ARCHIVE_REF = None

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


def _repo_parts():
    if "raw.githubusercontent.com" not in REPO:
        return None
    parts = str(REPO).split("raw.githubusercontent.com/")[-1].strip("/").split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    branch = parts[2] if len(parts) > 2 else "main"
    return owner, repo, branch


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


def _repo_archive_ref():
    global _REPO_ARCHIVE_REF
    if _REPO_ARCHIVE_REF:
        return _REPO_ARCHIVE_REF

    sha = "main"
    repo_parts = _repo_parts()
    if not repo_parts:
        _REPO_ARCHIVE_REF = sha
        return _REPO_ARCHIVE_REF

    owner, repo, branch = repo_parts
    api_url = "https://api.github.com/repos/%s/%s/commits/%s" % (owner, repo, branch)
    try:
        req = urllib_request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib_request.urlopen(req, context=unverified_ssl_context, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                sha = data.get("sha", sha)
    except Exception:
        pass
    _REPO_ARCHIVE_REF = sha
    return _REPO_ARCHIVE_REF


def _repo_archive_url(ref):
    repo_parts = _repo_parts()
    if not repo_parts:
        return "https://github.com/Alehaaaa/TKM/archive/%s.zip" % ref
    owner, repo, _branch = repo_parts
    return "https://github.com/%s/%s/archive/%s.zip" % (owner, repo, ref)


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
        download(_repo_archive_url(_repo_archive_ref()), tmpZipFile)

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
    sha = _repo_archive_ref()

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


def get_changelog():
    success, result = _fetch_repo_file("changelog")
    if success:
        return True, result

    changelog = changelogMod.read_local_changelog()
    return (True, changelog) if changelog else (False, "")


def _update_buttons(dialog_cls):
    return [
        dialog_cls.CustomButton("Install", positive=True, icon=icons.install),
        dialog_cls.CustomButton("Skip", positive=True, icon=icons.skip),
        dialog_cls.No,
    ]


def _update_template(latest_version, installed_version, changelog):
    return (
        "<title>Version {} available\n(using {})</title>\n".format(latest_version, installed_version)
        + "<text>A new version of TheKeyMachine is ready to download and install.</text>\n"
        + changelogMod.changelog_template(changelog, latest_version)
        + "<separator/>"
        + "<text>Install will replace the current tool files while keeping your user data and preferences.</text>\n"
        + "<text>Choose Skip to hide this update prompt until you check manually again.</text>\n"
    )


def _update_message():
    return (
        "A new version of TheKeyMachine is ready to download and install.<br><br>"
        "Install will replace the current tool files while keeping your user data and preferences."
    )


class UpdateCheckWorker(QThread):
    result_ready = Signal(bool, object)

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
            self.result_ready.emit(False, latest_version)
            return

        comp = compare_versions(latest_version, self.installed_version)
        if comp <= 0:
            # We still want to let them know they are up to date instead of prompting a false update.
            self.result_ready.emit(True, None)
            return

        changelog_success, changelog = get_changelog()
        self.result_ready.emit(
            True,
            {
                "version": latest_version,
                "changelog": changelog if changelog_success else "",
            },
        )


updater_worker = None


def check_for_updates(anchor_widget=None, warning=True, force=False):
    global updater_worker
    if updater_worker is not None and updater_worker.isRunning():
        return

    installed_version = get_thekeymachine_version()

    def cleanup_worker():
        global updater_worker
        worker = updater_worker
        updater_worker = None
        if worker is not None:
            try:
                worker.deleteLater()
            except Exception:
                pass

    def handle_result(success, latest_version):
        if not success:
            if warning:
                wutil.make_inViewMessage(latest_version)  # latest_version contains error msg here
            return

        if latest_version is None:
            if warning:
                wutil.make_inViewMessage("<hl>" + installed_version + "</hl>\nYou are up-to-date.")
            return

        changelog = ""
        if isinstance(latest_version, dict):
            changelog = latest_version.get("changelog") or ""
            latest_version = latest_version.get("version")

        # Update the icon
        if anchor_widget and hasattr(anchor_widget, "setIcon"):
            anchor_widget.setIcon(QtGui.QIcon(icons.settings_update))

        # If we are skipping updates and this isn't a forced check, don't do anything else
        if not force and settings.get_setting("skip_updates", False):
            return

        latest_version = latest_version.strip()
        template = _update_template(latest_version, installed_version, changelog)

        if anchor_widget:
            result = QFlatTooltipConfirm.question(
                anchor_widget,
                title="Update available",
                tooltip_template=template,
                icon=icons.settings_update,
                buttons=_update_buttons(QFlatTooltipConfirm),
                highlight="Install",
            )
        else:
            result = QFlatConfirmDialog.question(
                None,
                "Update available",
                title=f"Version {latest_version} available",
                message=_update_message(),
                icon=icons.settings_update,
                buttons=_update_buttons(QFlatConfirmDialog),
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
                        title=f"Installed TheKeyMachine {latest_version}",
                        message="You have successfully updated the tool!<br><br>\nPlease restart Maya if you experience any issues.",
                        icon=icons.success,
                        closeButton=True,
                    )

                QTimer.singleShot(100, _post_update)

            elif result.get("name") == "Skip":
                settings.set_setting("skip_updates", True)

    delay = 0 if warning or force else 1000
    updater_worker = UpdateCheckWorker(installed_version, force=force, delay=delay)
    updater_worker.result_ready.connect(handle_result)
    updater_worker.finished.connect(cleanup_worker)
    updater_worker.start()
