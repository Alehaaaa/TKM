import os
import ssl
import json
import shutil
import tempfile
import zipfile
import sys
import importlib
from maya import cmds
from TheKeyMachine.tools import common as toolCommon

import urllib.error as urllib_error
import urllib.request as urllib_request
from http.client import responses

from TheKeyMachine.core.Qt import QtCore, QtGui

from TheKeyMachine.core.application import get_thekeymachine_version

from TheKeyMachine.ui.widgets.customDialogs import QFlatConfirmDialog, QFlatTooltipConfirm

from TheKeyMachine.data import icons
import TheKeyMachine.ui.widgets.util as wutil
from TheKeyMachine.core import settings, trigger
from TheKeyMachine.tools.update import changelog as changelog_service


# Constants
REPO = "https://raw.githubusercontent.com/Alehaaaa/TKM/main/"
NO_DATA_ERROR = "<hl>No Data</hl>\nCould not sync with the server."
NO_SERVER_ERROR = "<hl>%s %s</hl>\nCould not sync with the server."
_REPO_ARCHIVE_REF = None
DOWNLOAD_PROGRESS_UNITS = 1000
DOWNLOAD_PROGRESS_UPDATE_MS = 80
DOWNLOAD_ETA_MIN_BYTES = 262144
DOWNLOAD_ETA_MIN_MS = 1000

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


def _format_download_size(byte_count):
    try:
        size = float(max(0, int(byte_count or 0)))
    except Exception:
        return ""

    units = ("B", "KB", "MB", "GB")
    unit_index = 0
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return "{} {}".format(int(size), units[unit_index])
    return "{:.1f} {}".format(size, units[unit_index])


def _download_status(downloaded, total_size, elapsed_ms):
    label = "Downloading Update"
    if downloaded <= 0:
        return label

    downloaded_label = _format_download_size(downloaded)
    if total_size <= 0:
        return "{}... {} downloaded".format(label, downloaded_label)

    percent = int(min(100, max(0, round((downloaded / float(total_size)) * 100))))
    total_label = _format_download_size(total_size)
    status = "{}... {}% ({} / {})".format(
        label, percent, downloaded_label, total_label
    )

    if elapsed_ms < DOWNLOAD_ETA_MIN_MS or downloaded < min(
        total_size, DOWNLOAD_ETA_MIN_BYTES
    ):
        return status

    bytes_per_second = downloaded / max(0.001, elapsed_ms / 1000.0)
    if bytes_per_second <= 0:
        return status
    remaining = max(0, total_size - downloaded)
    if remaining <= 0:
        return "{}... complete".format(label)
    eta = toolCommon.format_eta(remaining / bytes_per_second)
    return "{}, about {} left".format(status, eta) if eta else status


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

    from TheKeyMachine.ui.widgets import toolbar

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


def _download_file(download_url, save_file, operation):
    """Transfer one update archive off the Maya thread.

    UI feedback is owned by the caller's ToolOperation; ``step`` safely
    marshals progress updates back to Maya's main thread.
    """
    response = urllib_request.urlopen(
        download_url, context=unverified_ssl_context, timeout=60
    )

    if response is None:
        return False

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
        operation.set_total(progress_max, reset=True)
        with open(save_file, "wb") as output:
            while not operation.cancelled:
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

        if operation.cancelled:
            try:
                os.remove(save_file)
            except OSError:
                pass
            return False
        if total_size > 0 and displayed_units < DOWNLOAD_PROGRESS_UNITS:
            operation.step(DOWNLOAD_PROGRESS_UNITS - displayed_units)
    finally:
        try:
            response.close()
        except Exception:
            pass
    return True


def download(downloadUrl, saveFile, tool_operation=None):
    """Download an update through the standard responsive operation path."""
    operation = toolCommon.require_tool_operation(tool_operation)
    operation.set_total(DOWNLOAD_PROGRESS_UNITS).set_status("Downloading Update")
    return operation.run_worker(
        _download_file,
        downloadUrl,
        saveFile,
        operation,
    )


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


def install(command=None, file_path=None, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
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
        operation.set_status("Preparing Update")
        operation.run_worker(shutil.copyfile, file_path, tmpZipFile)
    else:
        operation.set_status("Resolving Update")
        archive_ref = operation.run_worker(_repo_archive_ref)
        if not download(
            _repo_archive_url(archive_ref),
            tmpZipFile,
            tool_operation=operation,
        ):
            return False

    if not os.path.isfile(tmpZipFile):
        return cmds.error("Error trying to install.")

    operation.set_status("Validating Update")
    staging_root, staged_package = operation.run_worker(
        _stage_update_archive,
        tmpZipFile,
        scriptPath,
        operation,
    )
    if not staged_package:
        shutil.rmtree(staging_root, ignore_errors=True)
        if os.path.isfile(tmpZipFile):
            os.remove(tmpZipFile)
        if operation.cancelled:
            return False
        return wutil.make_inViewMessage("Update archive is empty or invalid")

    try:
        from TheKeyMachine.core import runtime

        runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
    except Exception:
        pass

    operation.set_status("Installing Update")
    try:
        operation.run_worker(
            _commit_staged_update,
            toolsFolder,
            staged_package,
        )
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        if os.path.isfile(tmpZipFile):
            os.remove(tmpZipFile)
    return True


def _archive_package_path(name):
    """Return a safe path relative to the archive's TheKeyMachine folder."""
    parts = [part for part in name.replace("\\", "/").split("/") if part]
    try:
        package_index = parts.index("TheKeyMachine")
    except ValueError:
        return None
    relative = parts[package_index + 1 :]
    if not relative or any(part in (".", "..") for part in relative):
        return None
    return relative


def _stage_update_archive(archive_path, script_path, operation):
    """Validate and extract an update without touching the live installation."""
    staging_root = tempfile.mkdtemp(prefix=".tkm-update-", dir=script_path)
    staged_package = os.path.join(staging_root, "TheKeyMachine")
    os.makedirs(staged_package)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = [
                (info, _archive_package_path(info.filename))
                for info in archive.infolist()
            ]
            entries = [(info, relative) for info, relative in entries if relative]
            if not entries:
                return staging_root, None
            operation.set_total(len(entries), reset=True).set_status("Extracting Update")
            for info, relative in entries:
                if operation.cancelled:
                    return staging_root, None
                destination = os.path.abspath(os.path.join(staged_package, *relative))
                package_root = os.path.abspath(staged_package) + os.sep
                if not destination.startswith(package_root):
                    return staging_root, None
                if info.is_dir():
                    os.makedirs(destination, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    with archive.open(info) as source, open(destination, "wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                operation.step()
        required = ("__init__.py", "version")
        if not all(os.path.isfile(os.path.join(staged_package, item)) for item in required):
            return staging_root, None
        return staging_root, staged_package
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _copy_missing_tree(source_root, destination_root):
    """Preserve local-only data files without replacing files from the update."""
    if not os.path.isdir(source_root):
        return
    for root, directories, files in os.walk(source_root):
        relative_root = os.path.relpath(root, source_root)
        target_root = (
            destination_root
            if relative_root == "."
            else os.path.join(destination_root, relative_root)
        )
        os.makedirs(target_root, exist_ok=True)
        for directory in directories:
            os.makedirs(os.path.join(target_root, directory), exist_ok=True)
        for filename in files:
            destination = os.path.join(target_root, filename)
            if not os.path.exists(destination):
                shutil.copy2(os.path.join(root, filename), destination)


def _commit_staged_update(tools_folder, staged_package):
    """Replace the validated package as one recoverable filesystem transaction."""
    if os.path.basename(tools_folder) != "TheKeyMachine":
        raise RuntimeError("Refusing to replace an unexpected installation path")
    _copy_missing_tree(
        os.path.join(tools_folder, "data"),
        os.path.join(staged_package, "data"),
    )
    backup_folder = tools_folder + ".update-backup"
    if os.path.exists(backup_folder):
        shutil.rmtree(backup_folder)
    os.replace(tools_folder, backup_folder)
    try:
        os.replace(staged_package, tools_folder)
    except Exception:
        os.replace(backup_folder, tools_folder)
        raise
    shutil.rmtree(backup_folder, ignore_errors=True)


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

    local_changelog = changelog_service.read_local_changelog()
    return (True, local_changelog) if local_changelog else (False, "")


def _update_buttons(dialog_cls):
    return [
        dialog_cls.CustomButton("Install", positive=True, icon=icons.install),
        dialog_cls.CustomButton("Skip", positive=True, icon=icons.skip),
        dialog_cls.No,
    ]


def _update_template(latest_version, installed_version, raw_changelog):
    return (
        "<title>Update {} available\n(using {})</title>\n".format(
            latest_version, installed_version
        )
        + "<text>A new version of TheKeyMachine is ready to download and install.</text>\n"
        + changelog_service.changelog_template(
            raw_changelog, latest_version, installed_version=installed_version
        )
        + "<separator/>"
        + '<spacing size="8"/>\n'
        + "<text>Install replaces tool files and keeps your user data.</text>\n"
        + "<text>Skip hides this prompt until you check again.</text>\n"
    )


def _check_update_payload(installed_version, operation):
    """Fetch update metadata on an I/O worker and report two bounded phases."""
    operation.set_total(2, reset=True)
    operation.set_status("Checking for Updates")
    success, latest_version = get_latest_version()
    operation.step()
    if not success:
        return False, latest_version
    if compare_versions(latest_version, installed_version) <= 0:
        operation.step()
        return True, None

    operation.set_status("Loading Changelog")
    changelog_success, changelog = get_changelog()
    operation.step()
    return True, {
        "version": latest_version,
        "changelog": changelog if changelog_success else "",
    }


def _show_installed_result(latest_version):
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
            "<br><br>\nThe files were updated, but TheKeyMachine could not "
            "reopen automatically. Please restart Maya."
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


def install_update(latest_version, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    if not install(tool_operation=operation):
        return
    settings.set_setting("skip_updates", False)
    QtCore.QTimer.singleShot(100, lambda: _show_installed_result(latest_version))


def check_for_updates(anchor_widget=None, warning=True, force=False, tool_operation=None):
    from TheKeyMachine.core import application as general

    if not general.config.get("INTERNET_CONNECTION", True):
        return None

    installed_version = get_thekeymachine_version()
    operation = toolCommon.require_tool_operation(tool_operation)
    operation.set_total(2).set_status("Checking for Updates")
    success, latest_version = operation.run_worker(
        _check_update_payload,
        installed_version,
        operation,
    )

    if not success:
        if warning:
            wutil.make_inViewMessage(latest_version)
        return False
    if latest_version is None:
        if warning:
            wutil.make_inViewMessage(
                "<hl>" + installed_version + "</hl>\nYou are up-to-date."
            )
        return True

    changelog = latest_version.get("changelog") or ""
    latest_version = latest_version["version"].strip()
    if anchor_widget and hasattr(anchor_widget, "setIcon"):
        anchor_widget.setIcon(QtGui.QIcon(icons.tkm_main_update))
    if not force and settings.get_setting("skip_updates", False):
        return True

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
            # Let the command's check operation close before the download
            # starts its own operation.
            QtCore.QTimer.singleShot(
                0,
                lambda: trigger.execute_command("install_update", latest_version),
            )
        elif result.get("name") == "Skip":
            settings.set_setting("skip_updates", True)
    return True
