from __future__ import division
import os
import ssl
import json
import shutil
import zipfile
import sys
import importlib
import maya.cmds as cmds
from TheKeyMachine.tools import common as toolCommon

if sys.version_info[0] > 2:
    import urllib.request as urllib_request
    import urllib.error as urllib_error
    from http.client import responses
else:
    import urllib2 as urllib_request
    import urllib2 as urllib_error
    import httplib

    responses = httplib.responses

from TheKeyMachine.core.Qt import QtCore, QtGui

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
DOWNLOAD_PROGRESS_UNITS = 1000
DOWNLOAD_PROGRESS_UPDATE_MS = 80
DOWNLOAD_ETA_MIN_BYTES = 262144

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


def _download_status(downloaded, total_size, elapsed_ms):
    label = "Downloading Update"
    if (
        total_size <= 0
        or downloaded <= 0
        or elapsed_ms <= 0
        or downloaded < min(total_size, DOWNLOAD_ETA_MIN_BYTES)
    ):
        return label

    remaining = max(0, total_size - downloaded)
    if remaining <= 0:
        return label

    bytes_per_second = downloaded / max(0.001, elapsed_ms / 1000.0)
    if bytes_per_second <= 0:
        return label
    eta = toolCommon.format_eta(remaining / bytes_per_second)
    return "{}, about {} left".format(label, eta) if eta else label


def _reopen_after_install():
    try:
        importlib.invalidate_caches()
    except Exception:
        pass

    for module_name in list(sys.modules.keys()):
        if module_name == "TheKeyMachine" or module_name.startswith("TheKeyMachine."):
            try:
                del sys.modules[module_name]
            except KeyError:
                pass

    import TheKeyMachine.core.toolbar as toolbar

    return toolbar.show(cleanup_existing=False)


def _response_header(response, name, default=None):
    getheader = getattr(response, "getheader", None)
    if callable(getheader):
        return getheader(name, default)

    info = getattr(response, "info", None)
    headers = info() if callable(info) else None
    for getter_name in ("getheader", "get"):
        get = getattr(headers, getter_name, None)
        if callable(get):
            return get(name, default)
    return default


def _response_status(response):
    getcode = getattr(response, "getcode", None)
    status = getattr(response, "status", None)
    status = status if status is not None else getattr(response, "code", None)
    status = status if status is not None else (getcode() if callable(getcode) else 200)
    return int(status or 200)


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
    response = urllib_request.urlopen(
        downloadUrl, context=unverified_ssl_context, timeout=60
    )

    if response is None:
        cmds.warning("Error trying to install.")
        return

    try:
        total_size = _response_header(response, "Content-Length")
        total_size = int(total_size) if total_size else 0
        block_size = 65536

        downloaded = 0
        displayed_units = 0
        last_update_ms = -DOWNLOAD_PROGRESS_UPDATE_MS
        progress_timer = QtCore.QElapsedTimer()
        progress_timer.start()
        progress_max = DOWNLOAD_PROGRESS_UNITS if total_size > 0 else 0
        with toolCommon.tool_operation(
            tool_id="download_update",
            label="Downloading Update",
            progress_max=progress_max,
            progress=True,
            interruptable=False,
            undo=False,
            suspend_refresh=False,
        ) as operation:
            with open(saveFile, "wb") as output:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    output.write(buffer)

                    now = progress_timer.elapsed()
                    if total_size > 0:
                        target_units = int(
                            (downloaded / float(total_size)) * DOWNLOAD_PROGRESS_UNITS
                        )
                        target_units = min(
                            DOWNLOAD_PROGRESS_UNITS, max(displayed_units, target_units)
                        )
                        if target_units > displayed_units and (
                            now - last_update_ms >= DOWNLOAD_PROGRESS_UPDATE_MS
                            or target_units >= DOWNLOAD_PROGRESS_UNITS
                        ):
                            operation.step(
                                target_units - displayed_units,
                                exact_status=_download_status(downloaded, total_size, now),
                            )
                            displayed_units = target_units
                            last_update_ms = now
                    elif now - last_update_ms >= DOWNLOAD_PROGRESS_UPDATE_MS:
                        operation.step(exact_status="Downloading Update")
                        last_update_ms = now

            if total_size > 0 and displayed_units < DOWNLOAD_PROGRESS_UNITS:
                operation.step(DOWNLOAD_PROGRESS_UNITS - displayed_units)
    finally:
        try:
            response.close()
        except Exception:
            pass
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
    response = None
    try:
        req = urllib_request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        response = urllib_request.urlopen(
            req, context=unverified_ssl_context, timeout=10
        )
        if _response_status(response) == 200:
            data = json.loads(response.read().decode("utf-8"))
            sha = data.get("sha", sha)
    except Exception:
        pass
    finally:
        try:
            if response is not None:
                response.close()
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

    try:
        import TheKeyMachine.core.runtimeManager as runtime

        runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
    except Exception:
        pass

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
    response = None
    try:
        response = urllib_request.urlopen(
            url, context=unverified_ssl_context, timeout=30
        )
        status = _response_status(response)
        if status == 200:
            text = response.read().decode("utf-8")
            if not text:
                return False, NO_DATA_ERROR
            return True, text
        error_message = responses.get(status, "Unknown Error")
        return False, NO_SERVER_ERROR % (status, error_message)
    except urllib_error.URLError as e:
        reason = getattr(e, "reason", e)
        return False, "Network error: %s" % reason
    except TimeoutError:
        return False, "Connection timed out."
    except Exception as e:
        return False, "Unexpected error: %s" % e
    finally:
        try:
            if response is not None:
                response.close()
        except Exception:
            pass


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
        "<title>Update {} available\n(using {})</title>\n".format(
            latest_version, installed_version
        )
        + "<text>A new version of TheKeyMachine is ready to download and install.</text>\n"
        + changelogMod.changelog_template(
            changelog, latest_version, installed_version=installed_version
        )
        + "<separator/>"
        + '<spacing size="8"/>\n'
        + "<text>Install replaces tool files and keeps your user data.</text>\n"
        + "<text>Skip hides this prompt until you check again.</text>\n"
    )


class UpdateCheckWorker(QtCore.QThread):
    result_ready = QtCore.Signal(bool, object)

    def __init__(self, installed_version, force=False, delay=0, parent=None):
        QtCore.QThread.__init__(self, parent)
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
updater_result_dispatcher = None


class UpdateResultDispatcher(QtCore.QObject):
    result_ready = QtCore.Signal(bool, object)

    def emit_result(self, success, result):
        self.result_ready.emit(success, result)


def shutdown_update_worker(wait_ms=1000):
    global updater_worker, updater_result_dispatcher
    worker = updater_worker
    updater_worker = None
    updater_result_dispatcher = None
    if worker is None:
        return
    try:
        if worker.isRunning():
            worker.quit()
            worker.wait(int(wait_ms))
    except Exception:
        pass
    try:
        worker.deleteLater()
    except Exception:
        pass


def check_for_updates(anchor_widget=None, warning=True, force=False):
    global updater_worker, updater_result_dispatcher
    from TheKeyMachine.mods import generalMod as general

    if not general.config.get("INTERNET_CONNECTION", True):
        return None
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
        global updater_result_dispatcher
        if not success:
            if warning:
                wutil.make_inViewMessage(
                    latest_version
                )  # latest_version contains error msg here
            updater_result_dispatcher = None
            return

        if latest_version is None:
            if warning:
                wutil.make_inViewMessage(
                    "<hl>" + installed_version + "</hl>\nYou are up-to-date."
                )
            updater_result_dispatcher = None
            return

        try:
            changelog = ""
            if isinstance(latest_version, dict):
                changelog = latest_version.get("changelog") or ""
                latest_version = latest_version.get("version")

            # Update the icon
            if anchor_widget and hasattr(anchor_widget, "setIcon"):
                anchor_widget.setIcon(QtGui.QIcon(icons.tkm_main_update))

            # If we are skipping updates and this isn't a forced check, don't do anything else
            if not force and settings.get_setting("skip_updates", False):
                return

            latest_version = latest_version.strip()
            template = _update_template(latest_version, installed_version, changelog)
            if anchor_widget:
                result = QFlatTooltipConfirm.question(
                    anchor_widget,
                    title="Update available",
                    tooltip=template,
                    icon=icons.tkm_main_update,
                    buttons=_update_buttons(QFlatTooltipConfirm),
                    highlight="Install",
                )
            else:
                result = QFlatConfirmDialog.question(
                    None,
                    "Update available",
                    title="",
                    message="",
                    tooltip=template,
                    icon=icons.tkm_main_update,
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
                        reopen_error = None
                        try:
                            _reopen_after_install()
                        except Exception as error:
                            reopen_error = error
                            cmds.warning(
                                "TheKeyMachine was updated but could not reopen: {}".format(error)
                            )

                        message = "You have successfully updated the tool!"
                        if reopen_error is not None:
                            message += (
                                "<br><br>\nThe files were updated, but TheKeyMachine could not reopen automatically. "
                                "Please restart Maya."
                            )
                        else:
                            message += "<br><br>\nPlease restart Maya if you experience any issues."
                        QFlatConfirmDialog.information(
                            None,
                            "Updated",
                            title="Installed TheKeyMachine {}".format(latest_version),
                            message=message,
                            icon=icons.success,
                            closeButton=True,
                        )

                    QtCore.QTimer.singleShot(100, _post_update)

                elif result.get("name") == "Skip":
                    settings.set_setting("skip_updates", True)
        finally:
            updater_result_dispatcher = None

    delay = 0 if warning or force else 1000
    updater_worker = UpdateCheckWorker(installed_version, force=force, delay=delay)
    updater_result_dispatcher = UpdateResultDispatcher()
    updater_result_dispatcher.result_ready.connect(handle_result)
    updater_worker.result_ready.connect(
        updater_result_dispatcher.emit_result, QtCore.Qt.QueuedConnection
    )
    updater_worker.finished.connect(cleanup_worker)
    updater_worker.start()
