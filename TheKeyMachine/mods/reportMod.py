"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io



"""

import os
import platform
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request

import maya.cmds as cmds

import TheKeyMachine.mods.generalMod as general

try:
    from PySide2 import QtCore, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtWidgets

from TheKeyMachine.widgets import customDialogs


_BUG_EXCEPTION_HANDLER_INSTALLED = False
_BUG_EXCEPTION_DIALOG_PENDING = False
_BUG_EXCEPTION_LAST_SIGNATURE = None
_BUG_EXCEPTION_LAST_TIME = 0.0
_BUG_REPORT_DIALOG = None
_REPORTED_EXCEPTION_IDS = {}


def _is_valid_dialog(dialog):
    if dialog is None:
        return False
    try:
        dialog.objectName()
        return True
    except RuntimeError:
        return False
    except Exception:
        return False


def _set_bug_report_dialog(dialog):
    global _BUG_REPORT_DIALOG
    _BUG_REPORT_DIALOG = dialog


def _clear_bug_report_dialog(*_):
    global _BUG_REPORT_DIALOG
    _BUG_REPORT_DIALOG = None


def _get_open_bug_report_dialog():
    global _BUG_REPORT_DIALOG

    if _is_valid_dialog(_BUG_REPORT_DIALOG):
        try:
            if _BUG_REPORT_DIALOG.isVisible():
                return _BUG_REPORT_DIALOG
        except Exception:
            pass
        _clear_bug_report_dialog()

    for widget in QtWidgets.QApplication.topLevelWidgets():
        if (
            isinstance(widget, customDialogs.QFlatBugReportDialog)
            and _is_valid_dialog(widget)
            and widget.isVisible()
        ):
            _set_bug_report_dialog(widget)
            return widget
    return None


def _safe_about(**kwargs):
    try:
        return cmds.about(**kwargs)
    except Exception:
        return None


def _safe_call(callback):
    try:
        return callback()
    except Exception:
        return None


def _sanitize_payload_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _detect_qt_binding():
    module_name = QtCore.__module__ or ""
    if module_name.startswith("PySide6"):
        return "PySide6"
    if module_name.startswith("PySide2"):
        return "PySide2"
    return module_name or "Unknown"


def _collect_debug_context():
    info = {
        "tkm_version": general.get_thekeymachine_version(),
        "python_version": sys.version,
        "python_implementation": _safe_call(platform.python_implementation),
        "python_compiler": _safe_call(platform.python_compiler),
        "python_build": _safe_call(platform.python_build),
        "qt_binding": _detect_qt_binding(),
        "qt_version": _safe_call(QtCore.qVersion),
        "maya_version": _safe_about(version=True),
        "maya_api_version": _safe_about(apiVersion=True),
        "maya_product": _safe_about(product=True),
        "maya_installed_version": _safe_about(installedVersion=True),
        "maya_operating_system": _safe_about(operatingSystem=True),
        "maya_operating_system_version": _safe_about(operatingSystemVersion=True),
        "maya_ui_language": _safe_about(uiLanguage=True),
        "maya_batch_mode": _safe_about(batch=True),
        "maya_64bit": _safe_about(is64=True),
        "maya_cut_identifier": _safe_about(cutIdentifier=True),
        "maya_current_unit_time": _safe_call(lambda: cmds.currentUnit(query=True, time=True)),
        "maya_current_unit_linear": _safe_call(lambda: cmds.currentUnit(query=True, linear=True)),
        "maya_current_unit_angle": _safe_call(lambda: cmds.currentUnit(query=True, angle=True)),
        "platform_system": _safe_call(platform.system),
        "platform_release": _safe_call(platform.release),
        "platform_version": _safe_call(platform.version),
        "platform_platform": _safe_call(lambda: platform.platform(aliased=True, terse=False)),
        "platform_machine": _safe_call(platform.machine),
        "platform_architecture": _safe_call(lambda: platform.architecture()[0]),
    }
    return {key: _sanitize_payload_value(value) for key, value in info.items()}


def send_bug_report(name, explanation, script_error):
    url = ""
    if not url:
        return False

    payload = {
        "name": name,
        "explanation": explanation,
        "script_error": script_error,
    }
    payload.update(_collect_debug_context())
    request_data = urllib.parse.urlencode(payload).encode("utf-8")

    try:
        with urllib.request.urlopen(url, request_data) as response:
            response_data = response.read().decode("utf-8")
    except Exception:
        return False

    return "success" in response_data


def _extract_exception_source_file(exc=None, tb=None):
    extracted = []
    if tb is not None:
        extracted = traceback.extract_tb(tb)
    elif exc is not None and getattr(exc, "__traceback__", None) is not None:
        extracted = traceback.extract_tb(exc.__traceback__)

    if not extracted:
        return "unknown.py"

    for frame in reversed(extracted):
        filename = frame.filename or ""
        if "TheKeyMachine" in filename:
            return _format_exception_source_file(filename)
    return _format_exception_source_file(extracted[-1].filename or "unknown.py")


def _format_exception_source_file(filename):
    normalized = os.path.normpath(filename or "")
    marker = "{}{}".format("TheKeyMachine", os.sep)
    if marker in normalized:
        return normalized.split(marker, 1)[1]
    return os.path.basename(normalized) or "unknown.py"


def _format_detected_bug_name(source_file):
    return "Error Detection on file {}".format(source_file or "unknown.py")


def _default_detected_bug_explanation(context=None):
    if context:
        return "Auto-detected exception in {}.\n\nPlease describe what you were doing when this happened.".format(context)
    return "Auto-detected exception.\n\nPlease describe what you were doing when this happened."


def _detected_exception_signature(exc=None, source_file=None):
    exc_type = type(exc).__name__ if exc is not None else "UnknownError"
    exc_message = str(exc) if exc is not None else ""
    return "{}|{}|{}".format(source_file or "unknown.py", exc_type, exc_message)


def _prune_reported_exception_ids(now=None):
    global _REPORTED_EXCEPTION_IDS
    if now is None:
        now = time.time()
    expiry_seconds = 10.0
    _REPORTED_EXCEPTION_IDS = {
        key: timestamp
        for key, timestamp in _REPORTED_EXCEPTION_IDS.items()
        if (now - timestamp) < expiry_seconds
    }


def _is_exception_already_reported(exc=None):
    if exc is None:
        return False
    try:
        if getattr(exc, "_tkm_reported", False):
            return True
    except Exception:
        pass

    exc_id = id(exc)
    now = time.time()
    _prune_reported_exception_ids(now=now)
    return exc_id in _REPORTED_EXCEPTION_IDS


def _mark_exception_reported(exc=None):
    if exc is None:
        return
    try:
        setattr(exc, "_tkm_reported", True)
    except Exception:
        pass
    now = time.time()
    _prune_reported_exception_ids(now=now)
    _REPORTED_EXCEPTION_IDS[id(exc)] = now


def report_detected_exception(exc=None, context=None, source_file=None, traceback_text=None):
    global _BUG_EXCEPTION_DIALOG_PENDING, _BUG_EXCEPTION_LAST_SIGNATURE, _BUG_EXCEPTION_LAST_TIME

    if _is_exception_already_reported(exc):
        return

    if _get_open_bug_report_dialog():
        _mark_exception_reported(exc)
        return

    try:
        source_name = source_file or _extract_exception_source_file(exc=exc)
        report_name = _format_detected_bug_name(source_name)
        report_traceback = traceback_text
        if not report_traceback:
            if exc is not None:
                report_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            else:
                report_traceback = "".join(traceback.format_stack())
        report_explanation = _default_detected_bug_explanation(context=context)
    except Exception:
        return

    signature = _detected_exception_signature(exc=exc, source_file=source_name)
    now = time.time()
    if signature == _BUG_EXCEPTION_LAST_SIGNATURE and (now - _BUG_EXCEPTION_LAST_TIME) < 2.0:
        _mark_exception_reported(exc)
        return
    _BUG_EXCEPTION_LAST_SIGNATURE = signature
    _BUG_EXCEPTION_LAST_TIME = now

    if _BUG_EXCEPTION_DIALOG_PENDING:
        _mark_exception_reported(exc)
        return
    _mark_exception_reported(exc)
    _BUG_EXCEPTION_DIALOG_PENDING = True

    def _show_dialog():
        global _BUG_EXCEPTION_DIALOG_PENDING
        try:
            bug_report_window(
                dialog_title="Sorry, you found a bug!",
                prefill_name=report_name,
                prefill_explanation=report_explanation,
                prefill_script_error=report_traceback,
            )
        finally:
            _BUG_EXCEPTION_DIALOG_PENDING = False

    try:
        QtCore.QTimer.singleShot(0, _show_dialog)
    except Exception:
        _BUG_EXCEPTION_DIALOG_PENDING = False


def _emit_exception_to_script_editor(traceback_text):
    if not traceback_text:
        return
    try:
        sys.stderr.write(traceback_text)
        if not traceback_text.endswith("\n"):
            sys.stderr.write("\n")
        sys.stderr.flush()
    except Exception:
        pass


def safe_execute(callback, *args, context=None, source_file=None, default=None, **kwargs):
    try:
        return callback(*args, **kwargs)
    except Exception as exc:
        traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        _emit_exception_to_script_editor(traceback_text)
        report_detected_exception(exc=exc, context=context, source_file=source_file, traceback_text=traceback_text)
        return default


def wrap_callback(callback, context=None, source_file=None, default=None):
    def _wrapped(*args, **kwargs):
        return safe_execute(callback, *args, context=context, source_file=source_file, default=default, **kwargs)

    return _wrapped


def install_bug_exception_handler():
    global _BUG_EXCEPTION_HANDLER_INSTALLED
    if _BUG_EXCEPTION_HANDLER_INSTALLED:
        return

    previous_excepthook = sys.excepthook

    def _tkm_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            if previous_excepthook:
                previous_excepthook(exc_type, exc_value, exc_tb)
            return
        try:
            report_detected_exception(
                exc=exc_value,
                source_file=_extract_exception_source_file(tb=exc_tb),
                traceback_text="".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            )
        except Exception:
            pass
        if previous_excepthook:
            previous_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _tkm_excepthook

    if hasattr(threading, "excepthook"):
        previous_threading_hook = threading.excepthook

        def _tkm_threading_excepthook(args):
            if issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
                if previous_threading_hook:
                    previous_threading_hook(args)
                return
            try:
                report_detected_exception(
                    exc=args.exc_value,
                    source_file=_extract_exception_source_file(tb=args.exc_traceback),
                    traceback_text="".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
                )
            except Exception:
                pass
            if previous_threading_hook:
                previous_threading_hook(args)

        threading.excepthook = _tkm_threading_excepthook

    _BUG_EXCEPTION_HANDLER_INSTALLED = True


def bug_report_window(*args, dialog_title="Sorry, you found a bug!", prefill_name="", prefill_explanation="", prefill_script_error=""):
    existing_dialog = _get_open_bug_report_dialog()
    if existing_dialog:
        if hasattr(existing_dialog, "apply_prefill"):
            existing_dialog.apply_prefill(
                dialog_title=dialog_title,
                name=prefill_name,
                explanation=prefill_explanation,
                script_error=prefill_script_error,
            )
        try:
            existing_dialog.show()
            existing_dialog.raise_()
            existing_dialog.activateWindow()
        except Exception:
            pass
        return existing_dialog

    dlg = customDialogs.QFlatBugReportDialog(
        submit_callback=send_bug_report,
        dialog_title=dialog_title,
        prefill_name=prefill_name,
        prefill_explanation=prefill_explanation,
        prefill_script_error=prefill_script_error,
    )
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    _set_bug_report_dialog(dlg)
    if hasattr(dlg, "finished"):
        dlg.finished.connect(_clear_bug_report_dialog)
    dlg.destroyed.connect(_clear_bug_report_dialog)
    dlg.show_centered()
    return dlg
