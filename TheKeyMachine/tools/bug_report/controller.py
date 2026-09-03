"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io



"""

import hashlib
import json
import os
import platform
import re
import ssl
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from functools import partial

from maya import cmds

import TheKeyMachine.core.application as general

from TheKeyMachine.core.Qt import QtCore, QtWidgets

from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.bug_report import widgets as bug_report_widgets


_BUG_EXCEPTION_HANDLER_INSTALLED = False
_BUG_EXCEPTION_DIALOG_PENDING = False
_BUG_EXCEPTION_LAST_SIGNATURE = None
_BUG_EXCEPTION_LAST_TIME = 0.0
_BUG_REPORT_DIALOG = None
_REPORTED_EXCEPTION_IDS = {}
_PREVIOUS_EXCEPTHOOK = None
_PREVIOUS_THREADING_EXCEPTHOOK = None
_TKM_EXCEPTHOOK_MARKER = "_tkm_bug_exception_hook"
_TKM_PREVIOUS_HOOK_ATTR = "_tkm_previous_hook"
_BUG_REPORT_ENDPOINT = "https://tkm-bug-relay.alehaaaa.workers.dev/report"
_BUG_REPORT_STATUS_ENDPOINT = "https://tkm-bug-relay.alehaaaa.workers.dev/status"
_BUG_REPORT_INSTALLATION_OPTION = "tkm_bug_report_installation_id"

# Maya's bundled Python often has no (or a stale) system CA bundle, so a
# plain urlopen() fails with CERTIFICATE_VERIFY_FAILED on some machines --
# same issue and same fix TheKeyMachine.tools.update.controller already
# uses for its own network calls.
_UNVERIFIED_SSL_CONTEXT = ssl.create_default_context()
_UNVERIFIED_SSL_CONTEXT.check_hostname = False
_UNVERIFIED_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Reports this machine has actually sent, so the Help menu can list them and
# let the artist check on one later (has the maintainer closed it yet?).
# Kept client-side only -- the relay has no concept of "who sent this".
_SENT_REPORTS_OPTION = "tkm_bug_report_sent_history"
_SENT_REPORTS_MAX_ENTRIES = 30
_SENT_REPORT_SUMMARY_CHARS = 70
_PRUNE_WORKERS = []  # keeps QThreads alive while a background prune check runs

# Local, cheap dedupe for auto-detected exceptions: mirrors the relay's own
# fingerprint normalization so a recurring bug is recognized on-device,
# without any network round trip, before we ever show a dialog or contact
# the relay. This keeps repeat crashes from spamming the artist with the
# same dialog and keeps the relay/GitHub API off the hot path for duplicates.
_LOCAL_DEDUPE_OPTION = "tkm_bug_report_local_cache"
_LOCAL_DEDUPE_COOLDOWN_SECONDS = 6 * 60 * 60
_LOCAL_DEDUPE_MAX_ENTRIES = 200
_PENDING_LOCAL_COUNTS = {}

# Mirrors the relay's own REPORT_TYPES/normalizeReportType() so an invalid or
# missing type never reaches the relay -- defense in depth, since the dialog
# itself only ever offers these two choices.
_REPORT_TYPES = ("bug", "suggestion")
_DEFAULT_REPORT_TYPE = "bug"


def _normalize_report_type(value):
    normalized = str(value or "").strip().lower()
    return normalized if normalized in _REPORT_TYPES else _DEFAULT_REPORT_TYPE


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


def _get_bug_report_dialog(include_hidden=False):
    global _BUG_REPORT_DIALOG

    if _is_valid_dialog(_BUG_REPORT_DIALOG):
        try:
            if include_hidden or _BUG_REPORT_DIALOG.isVisible():
                return _BUG_REPORT_DIALOG
        except Exception:
            pass
        if not include_hidden:
            return None
        _clear_bug_report_dialog()

    for widget in QtWidgets.QApplication.topLevelWidgets():
        if (
            isinstance(widget, bug_report_widgets.QFlatBugReportDialog)
            and _is_valid_dialog(widget)
            and (include_hidden or widget.isVisible())
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


def _collect_debug_context():
    info = {
        "tkm_version": general.get_thekeymachine_version(),
        "python_version": sys.version,
        "python_implementation": _safe_call(platform.python_implementation),
        "python_compiler": _safe_call(platform.python_compiler),
        "python_build": _safe_call(platform.python_build),
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


class BugReportSubmitWorker(QtCore.QThread):
    result_ready = QtCore.Signal(bool, object)

    def __init__(self, submit_callback, payload, parent=None):
        QtCore.QThread.__init__(self, parent)
        self._submit_callback = submit_callback
        self._payload = dict(payload or {})

    def run(self):
        try:
            result = self._submit_callback(**self._payload)
            if isinstance(result, dict):
                self.result_ready.emit(bool(result.get("success")), result)
            else:
                self.result_ready.emit(bool(result), None)
        except Exception as exc:
            self.result_ready.emit(False, exc)


def _format_bug_report_payload(payload):
    report_type = _normalize_report_type(payload.get("report_type"))
    is_suggestion = report_type == "suggestion"
    lines = [
        "# TheKeyMachine {}".format("Suggestion" if is_suggestion else "Bug Report"),
        "",
        "Generated: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "",
        "## Reporter",
        payload.get("name", "") or "Anonymous",
        "",
        "## Idea" if is_suggestion else "## What happened",
        payload.get("explanation", "") or "",
        "",
        "## Related context" if is_suggestion else "## Script error",
        "```text",
        payload.get("script_error", "") or "No script error supplied.",
        "```",
        "",
        "## System details",
    ]
    for key in sorted(payload.get("system", {})):
        lines.append("- **{}:** {}".format(key, payload["system"][key]))
    return "\n".join(lines)


def _redact_home_path(value):
    text = _sanitize_payload_value(value)
    home = os.path.expanduser("~")
    if home and home != "~":
        text = text.replace(home, "<home>")
        text = text.replace(home.replace("\\", "/"), "<home>")
        text = text.replace(home.replace("/", "\\"), "<home>")
    return text


def _installation_id():
    try:
        if cmds.optionVar(exists=_BUG_REPORT_INSTALLATION_OPTION):
            value = str(cmds.optionVar(query=_BUG_REPORT_INSTALLATION_OPTION) or "")
            if value:
                return value
        value = str(uuid.uuid4())
        cmds.optionVar(stringValue=(_BUG_REPORT_INSTALLATION_OPTION, value))
        return value
    except Exception:
        # Stable within this Maya process if optionVar storage is unavailable.
        global _BUG_REPORT_SESSION_INSTALLATION_ID
        try:
            return _BUG_REPORT_SESSION_INSTALLATION_ID
        except NameError:
            _BUG_REPORT_SESSION_INSTALLATION_ID = str(uuid.uuid4())
            return _BUG_REPORT_SESSION_INSTALLATION_ID


def _local_fingerprint_source(value):
    # Mirrors the relay worker's normalizeFingerprintSource() so the client
    # can recognize the same bug locally without asking the server.
    text = str(value or "unknown").lower()
    text = re.sub(r"(?:[a-z]:)?[\\/](?:[^\s:\n]+[\\/])+[^\s:\n]+", "<path>", text)
    text = re.sub(r"line \d+", "line <n>", text)
    text = re.sub(r"0x[0-9a-f]+", "<address>", text)
    text = re.sub(r"\b\d+\b", "<n>", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:8000]


def _local_fingerprint(value):
    return hashlib.sha256(_local_fingerprint_source(value).encode("utf-8")).hexdigest()


def _load_local_dedupe_cache():
    try:
        if cmds.optionVar(exists=_LOCAL_DEDUPE_OPTION):
            raw = cmds.optionVar(query=_LOCAL_DEDUPE_OPTION)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def _save_local_dedupe_cache(cache):
    try:
        if len(cache) > _LOCAL_DEDUPE_MAX_ENTRIES:
            ordered = sorted(
                cache.items(),
                key=lambda item: item[1].get("last_seen", 0) if isinstance(item[1], dict) else 0,
                reverse=True,
            )
            cache = dict(ordered[:_LOCAL_DEDUPE_MAX_ENTRIES])
        cmds.optionVar(stringValue=(_LOCAL_DEDUPE_OPTION, json.dumps(cache)))
    except Exception:
        pass


def _register_local_occurrence(fingerprint):
    """Record a local sighting of `fingerprint`.

    Returns ``(should_notify, occurrences_since_last_send)``. ``should_notify``
    is False while the fingerprint is inside its cooldown window, letting
    callers skip the dialog and the network call entirely for a bug that is
    already known and being tracked. Once the cooldown lapses (or this is the
    first sighting), the caller gets back how many times it happened locally
    since the last real submission, so that count can ride along on the next
    report instead of each occurrence costing its own round trip.
    """
    now = time.time()
    cache = _load_local_dedupe_cache()
    entry = cache.get(fingerprint) or {}
    occurrences = int(entry.get("since_last_sent", 0)) + 1
    last_sent = float(entry.get("last_sent", 0) or 0)
    should_notify = (now - last_sent) >= _LOCAL_DEDUPE_COOLDOWN_SECONDS

    entry["last_seen"] = now
    entry["since_last_sent"] = 0 if should_notify else occurrences
    if should_notify:
        entry["last_sent"] = now
    cache[fingerprint] = entry
    _save_local_dedupe_cache(cache)
    return should_notify, occurrences


def _consume_pending_local_count(fingerprint):
    return _PENDING_LOCAL_COUNTS.pop(fingerprint, 1)


def prepare_bug_report_payload(name, explanation, script_error, report_type="bug"):
    fingerprint = _local_fingerprint(script_error or explanation)
    payload = {
        "installation_id": _installation_id(),
        "name": _redact_home_path(name),
        "explanation": _redact_home_path(explanation),
        "script_error": _redact_home_path(script_error),
        "report_type": _normalize_report_type(report_type),
        "local_count": _consume_pending_local_count(fingerprint),
    }
    payload["system"] = {
        key: _redact_home_path(value)
        for key, value in _collect_debug_context().items()
    }
    return payload


def _write_bug_report_file(payload):
    try:
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(desktop_dir):
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_label = "Suggestion" if _normalize_report_type(payload.get("report_type")) == "suggestion" else "Bug Report"
        report_path = os.path.join(desktop_dir, "TKM_{}_{}.txt".format(report_label, timestamp))
        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(_format_bug_report_payload(payload))
    except Exception:
        return None

    return report_path


def write_bug_report_payload(**payload):
    return bool(_write_bug_report_file(payload))


def _load_sent_reports():
    try:
        if cmds.optionVar(exists=_SENT_REPORTS_OPTION):
            raw = cmds.optionVar(query=_SENT_REPORTS_OPTION)
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


def _save_sent_reports(entries):
    try:
        cmds.optionVar(
            stringValue=(_SENT_REPORTS_OPTION, json.dumps(entries[:_SENT_REPORTS_MAX_ENTRIES]))
        )
    except Exception:
        pass


def _report_summary(payload):
    text = (payload.get("explanation") or "").strip()
    first_line = text.split("\n", 1)[0].strip() if text else ""
    if not first_line:
        return "Bug report"
    if len(first_line) > _SENT_REPORT_SUMMARY_CHARS:
        return first_line[: _SENT_REPORT_SUMMARY_CHARS - 1].rstrip() + "…"
    return first_line


def _record_sent_report(payload, result):
    issue_number = result.get("issue_number") if isinstance(result, dict) else None
    if not issue_number:
        return
    fingerprint = _local_fingerprint(payload.get("script_error") or payload.get("explanation"))
    entry = {
        "issue_number": issue_number,
        "fingerprint": fingerprint,
        "summary": _report_summary(payload),
        "report_type": _normalize_report_type(payload.get("report_type")),
        "sent_at": time.time(),
        "duplicate": bool(result.get("duplicate")),
    }
    # Newest first, one entry per fingerprint (a resend just refreshes it).
    entries = [e for e in _load_sent_reports() if e.get("fingerprint") != fingerprint]
    entries.insert(0, entry)
    _save_sent_reports(entries)


def list_sent_bug_reports():
    """Newest-first list of reports this machine has actually sent."""
    return _load_sent_reports()


def _fetch_bug_report_status(fingerprint):
    """Ask the relay whether `fingerprint` still has a live issue. Raises on failure."""
    query = urllib.parse.urlencode({"fingerprint": fingerprint})
    request = urllib.request.Request(
        "{}?{}".format(_BUG_REPORT_STATUS_ENDPOINT, query),
        headers={
            "User-Agent": "TheKeyMachine/{}".format(general.get_thekeymachine_version()),
        },
        method="GET",
    )
    with urllib.request.urlopen(request, context=_UNVERIFIED_SSL_CONTEXT, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class _BugReportPruneWorker(QtCore.QThread):
    pruned_ready = QtCore.Signal(list)

    def __init__(self, entries, parent=None):
        QtCore.QThread.__init__(self, parent)
        self._entries = entries

    def run(self):
        removed_fingerprints = []
        for entry in self._entries:
            fingerprint = entry.get("fingerprint")
            if not fingerprint:
                continue
            try:
                result = _fetch_bug_report_status(fingerprint)
            except Exception:
                # Network hiccup or rate limit -- don't prune on uncertainty,
                # only on an explicit "not found" from the relay.
                continue
            if isinstance(result, dict) and result.get("found") is False:
                removed_fingerprints.append(fingerprint)
        self.pruned_ready.emit(removed_fingerprints)


def _prune_deleted_sent_reports():
    """Check sent reports against the relay in the background and drop any

    whose GitHub issue is gone (deleted, or the relay no longer tracks it).
    Fires and forgets: runs off the UI thread, and only affects what the
    Bug Report menu shows the *next* time it's opened, never the one
    currently on screen -- checking synchronously would make every menu
    open pause on a network round trip per sent report.
    """
    entries = _load_sent_reports()
    if not entries:
        return None

    worker = _BugReportPruneWorker(entries)
    _PRUNE_WORKERS.append(worker)

    def _on_pruned(removed_fingerprints):
        try:
            _PRUNE_WORKERS.remove(worker)
        except ValueError:
            pass
        if not removed_fingerprints:
            return
        removed = set(removed_fingerprints)
        current = _load_sent_reports()
        remaining = [e for e in current if e.get("fingerprint") not in removed]
        if len(remaining) != len(current):
            _save_sent_reports(remaining)

    worker.pruned_ready.connect(_on_pruned)
    worker.finished.connect(worker.deleteLater)
    worker.start()
    return worker


_BUG_REPORT_INBOX_REPO_URL = "https://github.com/Alehaaaa/TKM-bug-inbox"


def open_issue(issue_number):
    """Open a GitHub issue in this machine's default browser, given its number.

    The single place that knows the inbox repo's URL -- both the sent-reports
    menu (via ``open_sent_bug_report``) and the dialog's post-send "Open
    ticket" button (via ``bug_report_window``'s ``open_issue_callback``) route
    through here so the two never drift apart.
    """
    try:
        issue_number = int(issue_number)
    except (TypeError, ValueError):
        return
    if issue_number <= 0:
        return
    general.open_url("{}/issues/{}".format(_BUG_REPORT_INBOX_REPO_URL, issue_number))


def open_sent_bug_report(entry, *_args):
    """Open a previously sent report's GitHub issue in the browser.

    Accepts and ignores any extra positional args -- menu actions built via
    ``addAction(label, callback=...)`` may invoke this through a shared
    runner that appends its own arguments (e.g. the QAction ``checked``
    state) after the ones already bound by ``partial()``.
    """
    open_issue(entry.get("issue_number"))


def _format_sent_report_label(entry):
    from TheKeyMachine.core import i18n

    issue_number = entry.get("issue_number")
    summary = entry.get("summary") or "Bug report"
    try:
        when = datetime.fromtimestamp(float(entry.get("sent_at", 0))).strftime("%Y-%m-%d")
    except Exception:
        when = ""
    prefix = "#{}".format(issue_number) if issue_number else "?"
    # Bug is the common case and stays unlabeled to match the existing look;
    # suggestions get a short tag so the two don't blur together in the list.
    type_tag = (
        "[{}] ".format(i18n.tr("bug_report_type_suggestion", "Suggestion"))
        if entry.get("report_type") == "suggestion"
        else ""
    )
    return "{}{} · {}{}".format(type_tag, prefix, summary, "  ({})".format(when) if when else "")


def populate_bug_report_menu(menu):
    """Rebuild the whole Bug Report menu in place.

    Used both as a ``dynamic_menu`` builder (the TKM logo's Help submenu)
    and as a pinned/shelf tool's own popup (the flat "bug_report_window"
    tool's "menu" callable) -- one implementation, so the two surfaces can't
    drift apart. Always starts with "Report a Bug"; previously sent reports
    (if any) are listed flat underneath it, newest first, with no tooltip of
    their own -- clicking one just opens that report on GitHub.
    """
    from TheKeyMachine.tools import registry

    menu.clear()
    dialog_tool = registry.get_tool("bug_report_open_dialog")
    menu.addAction(
        dialog_tool.get("label", "Report a Bug"),
        callback=dialog_tool.get("callback"),
        icon=dialog_tool.get("icon"),
        command_id="bug_report_open_dialog",
    )

    entries = list_sent_bug_reports()
    if not entries:
        return menu

    menu.addSeparator()
    for entry in entries:
        menu.addAction(
            _format_sent_report_label(entry),
            callback=partial(open_sent_bug_report, entry),
            tooltip_enabled=False,
        )

    # Check in the background whether any of these were deleted on GitHub;
    # this menu instance still shows everything, but a stale entry won't
    # survive to the next time it's opened.
    _prune_deleted_sent_reports()
    return menu


def submit_bug_report(**payload):
    """Send a report through the credential-holding Cloudflare relay."""
    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            _BUG_REPORT_ENDPOINT,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TheKeyMachine/{}".format(general.get_thekeymachine_version()),
            },
            method="POST",
        )
        with urllib.request.urlopen(request, context=_UNVERIFIED_SSL_CONTEXT, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "Relay rejected the report")
        _record_sent_report(payload, result)
        return result
    except Exception as exc:
        backup_path = _write_bug_report_file(payload)
        return {
            "success": False,
            "fallback_saved": bool(backup_path),
            "backup_path": backup_path,
            "error": str(exc),
        }


def send_bug_report(name, explanation, script_error, report_type="bug"):
    payload = prepare_bug_report_payload(name, explanation, script_error, report_type=report_type)
    return bool(submit_bug_report(**payload).get("success"))


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


def _is_thekeymachine_frame(filename):
    normalized = os.path.normpath(filename or "")
    parts = [part for part in normalized.split(os.sep) if part]
    return "TheKeyMachine" in parts


def _traceback_has_thekeymachine_frame(tb):
    if tb is None:
        return False
    try:
        for frame in traceback.extract_tb(tb):
            if _is_thekeymachine_frame(frame.filename):
                return True
    except Exception:
        return False
    return False


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
    _REPORTED_EXCEPTION_IDS = {key: timestamp for key, timestamp in _REPORTED_EXCEPTION_IDS.items() if (now - timestamp) < expiry_seconds}


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

    if not general.config.get("BUG_REPORT", True):
        return

    if _is_exception_already_reported(exc):
        return

    if _get_bug_report_dialog():
        _mark_exception_reported(exc)
        return

    try:
        source_name = source_file or _extract_exception_source_file(exc=exc)
        report_traceback = traceback_text
        if not report_traceback:
            if exc is not None:
                report_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            else:
                report_traceback = "".join(traceback.format_stack())
    except Exception:
        return

    # Cheap, local, network-free gate: if this exact bug already notified the
    # user recently, just tally the occurrence and stop -- no dialog, no
    # relay call, no GitHub API cost.
    fingerprint = _local_fingerprint(report_traceback)
    should_notify, local_occurrences = _register_local_occurrence(fingerprint)
    if not should_notify:
        _mark_exception_reported(exc)
        return
    _PENDING_LOCAL_COUNTS[fingerprint] = local_occurrences

    try:
        recurrence_note = (
            "\n\nSeen locally {} time(s) since this was last reported.".format(local_occurrences)
            if local_occurrences > 1
            else ""
        )
        report_explanation = "{}\n\nDetected source: {}{}".format(
            _default_detected_bug_explanation(context=context),
            source_name,
            recurrence_note,
        )
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
        from TheKeyMachine.core import i18n

        try:
            bug_report_window(
                dialog_title=i18n.tr("bug_report_title_detected", "Sorry, you found a bug!"),
                prefill_name="",
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


def _restore_previous_hook(owner, hook_name):
    restored = False
    while True:
        current_hook = getattr(owner, hook_name, None)
        if current_hook is None or not getattr(current_hook, _TKM_EXCEPTHOOK_MARKER, False):
            return restored

        previous_hook = getattr(current_hook, _TKM_PREVIOUS_HOOK_ATTR, None)
        if previous_hook is None:
            return restored
        try:
            setattr(owner, hook_name, previous_hook)
            restored = True
        except Exception:
            return restored


def uninstall_bug_exception_handler():
    global _BUG_EXCEPTION_HANDLER_INSTALLED, _PREVIOUS_EXCEPTHOOK, _PREVIOUS_THREADING_EXCEPTHOOK

    _restore_previous_hook(sys, "excepthook")
    if hasattr(threading, "excepthook"):
        _restore_previous_hook(threading, "excepthook")

    _PREVIOUS_EXCEPTHOOK = None
    _PREVIOUS_THREADING_EXCEPTHOOK = None
    _BUG_EXCEPTION_HANDLER_INSTALLED = False


def install_bug_exception_handler():
    global _BUG_EXCEPTION_HANDLER_INSTALLED, _PREVIOUS_EXCEPTHOOK, _PREVIOUS_THREADING_EXCEPTHOOK

    uninstall_bug_exception_handler()
    if not general.config.get("BUG_REPORT", True):
        return False
    previous_excepthook = sys.excepthook
    _PREVIOUS_EXCEPTHOOK = previous_excepthook

    def _tkm_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            if previous_excepthook:
                previous_excepthook(exc_type, exc_value, exc_tb)
            return
        if _traceback_has_thekeymachine_frame(exc_tb):
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

    setattr(_tkm_excepthook, _TKM_EXCEPTHOOK_MARKER, True)
    setattr(_tkm_excepthook, _TKM_PREVIOUS_HOOK_ATTR, previous_excepthook)
    sys.excepthook = _tkm_excepthook

    if hasattr(threading, "excepthook"):
        previous_threading_hook = threading.excepthook
        _PREVIOUS_THREADING_EXCEPTHOOK = previous_threading_hook

        def _tkm_threading_excepthook(args):
            if issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
                if previous_threading_hook:
                    previous_threading_hook(args)
                return
            if _traceback_has_thekeymachine_frame(args.exc_traceback):
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

        setattr(_tkm_threading_excepthook, _TKM_EXCEPTHOOK_MARKER, True)
        setattr(_tkm_threading_excepthook, _TKM_PREVIOUS_HOOK_ATTR, previous_threading_hook)
        threading.excepthook = _tkm_threading_excepthook

    _BUG_EXCEPTION_HANDLER_INSTALLED = True
    return True


def bug_report_window(*args, dialog_title=None, prefill_name="", prefill_explanation="", prefill_script_error=""):
    if not general.config.get("BUG_REPORT", True):
        return None
    if dialog_title is None:
        from TheKeyMachine.core import i18n

        dialog_title = i18n.tr("bug_report_title", "Report a Bug or Suggestion")
    existing_dialog = _get_bug_report_dialog(include_hidden=True)
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

    dlg = bug_report_widgets.QFlatBugReportDialog(
        submit_callback=submit_bug_report,
        prepare_callback=prepare_bug_report_payload,
        worker_class=BugReportSubmitWorker,
        open_issue_callback=open_issue,
        dialog_title=dialog_title,
        prefill_name=prefill_name,
        prefill_explanation=prefill_explanation,
        prefill_script_error=prefill_script_error,
    )
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
    _set_bug_report_dialog(dlg)
    dlg.destroyed.connect(_clear_bug_report_dialog)
    toolCommon.invalidate_cached_window_on_language_change(dlg, _clear_bug_report_dialog)
    dlg.show_centered()
    return dlg
