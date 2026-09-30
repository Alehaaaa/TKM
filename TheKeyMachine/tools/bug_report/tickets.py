"""Ticket inbox reads and a native Qt manager; credentials stay on this machine."""
import html
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from functools import partial

from maya import cmds
from TheKeyMachine.core import debug
from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets
from TheKeyMachine.core.lifecycle import on_shutdown, ShutdownPhase
from TheKeyMachine.core.workers import BackgroundThread
from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets.util import DPI, get_maya_qt

_CACHE = "tkm_ticket_inbox"
_dialog = None
_worker = None
_error = ""


def _open_request(request):
    """Retry missing macOS/Maya certificate trust with an unverified context.

    Only certificate verification failures qualify: HTTP failures, timeouts,
    and other TLS failures must not replay a write request.
    """
    try:
        return urllib.request.urlopen(request, timeout=15)
    except (urllib.error.URLError, ssl.SSLCertVerificationError) as exc:
        reason = getattr(exc, "reason", exc)
        if sys.platform != "darwin" or not isinstance(reason, ssl.SSLCertVerificationError):
            raise
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(request, timeout=15, context=context)


def is_enabled():
    return debug.env_flag("TKM_TICKETS_DEBUG")


def _cached():
    try:
        value = json.loads(cmds.optionVar(query=_CACHE)) if cmds.optionVar(exists=_CACHE) else []
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def entries():
    """The manager always shows the repository inbox, regardless of author."""
    return _cached()


_STATUS_ACTIONS = {
    "Reported": ("open", "reopened", "status:reported"),
    "In progress": ("open", "reopened", "status:worked-on"),
    "Completed": ("closed", "completed", "status:completed"),
    "Cancelled": ("closed", "not_planned", "status:cancelled"),
}


def _normalize_issue(issue):
    return {"issue_number": issue["number"], "summary": issue.get("title", ""),
            "body": issue.get("body") or "", "status": issue.get("state", "open"),
            "state_reason": issue.get("state_reason"),
            "created_at": issue.get("created_at", ""),
            "updated_at": issue.get("updated_at", ""),
            "labels": [label["name"] for label in issue.get("labels", [])]}


def _status_name(entry):
    labels = entry.get("labels", [])
    for name, (state, reason, label) in _STATUS_ACTIONS.items():
        if entry.get("status") == state and label in labels:
            return name
    if entry.get("status") == "closed":
        return "Cancelled" if entry.get("state_reason") == "not_planned" else "Completed"
    return "Reported"


def update_issue(token, issue_number, status, cancelled=lambda: False):
    """Read current labels before replacing only the workflow status labels."""
    if not token:
        raise RuntimeError("Set TKM_TICKETS_TOKEN in TheKeyMachine/.env to edit tickets.")
    if status not in _STATUS_ACTIONS or isinstance(issue_number, bool) or int(issue_number) <= 0:
        raise ValueError("Invalid ticket or status.")
    url = "https://api.github.com/repos/Alehaaaa/TKM-bug-inbox/issues/{}".format(int(issue_number))
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "TheKeyMachine", "Content-Type": "application/json"}
    try:
        if cancelled():
            return None
        with _open_request(urllib.request.Request(url, headers=headers)) as response:
            current = json.load(response)
        if "pull_request" in current:
            raise ValueError("Pull requests cannot be edited in the ticket manager.")
        state, reason, label = _STATUS_ACTIONS[status]
        workflow_labels = {value[2] for value in _STATUS_ACTIONS.values()}
        labels = [item["name"] for item in current.get("labels", []) if item["name"] not in workflow_labels]
        labels.append(label)
        payload = {"state": state, "state_reason": reason, "labels": labels}
        if cancelled():
            return None
        request = urllib.request.Request(url, headers=headers, data=json.dumps(payload).encode("utf-8"), method="PATCH")
        with _open_request(request) as response:
            return _normalize_issue(json.load(response))
    except urllib.error.HTTPError as exc:
        messages = {401: "The ticket token was rejected.",
                    403: "GitHub denied this change. Check Issues read/write access and rate limits.",
                    404: "The ticket was not found or the token cannot access it.",
                    422: "GitHub rejected the ticket status change. Refetch and try again."}
        raise RuntimeError(messages.get(exc.code, "GitHub returned HTTP {}.".format(exc.code))) from None


def fetch_issues(token, cancelled=lambda: False):
    """Read every page, excluding pull requests. Never persist a partial fetch."""
    if not token:
        raise RuntimeError("Set TKM_TICKETS_TOKEN in TheKeyMachine/.env to read the private inbox.")
    result = []
    page = 1
    while not cancelled():
        request = urllib.request.Request(
            "https://api.github.com/repos/Alehaaaa/TKM-bug-inbox/issues?state=all&sort=created&direction=desc&per_page=100&page={}".format(page),
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "TheKeyMachine"},
        )
        try:
            with _open_request(request) as response:
                batch = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            messages = {401: "The ticket token was rejected.", 403: "GitHub denied access or its rate limit was reached.", 404: "The token needs Issues read access to Alehaaaa/TKM-bug-inbox."}
            raise RuntimeError(messages.get(exc.code, "GitHub returned HTTP {}.".format(exc.code))) from None
        if not isinstance(batch, list):
            raise RuntimeError("GitHub returned an unexpected inbox response.")
        for issue in batch:
            if "pull_request" in issue:
                continue
            result.append(_normalize_issue(issue))
        if len(batch) < 100:
            return result
        page += 1
    return None


class InboxWorker(BackgroundThread):
    result_signals = ("loaded", "failed")
    loaded = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(self, token):
        super().__init__()
        self.token = token

    def run(self):
        try:
            result = fetch_issues(self.token, lambda: self._cancelled or self.isInterruptionRequested())
            if result is not None and not self._cancelled:
                self.loaded.emit(result)
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(str(exc))
        finally:
            self.token = None


class UpdateWorker(BackgroundThread):
    result_signals = ("updated", "failed")
    updated = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, token, issue_number, status):
        super().__init__()
        self.token = token
        self.issue_number = issue_number
        self.status = status

    def run(self):
        try:
            result = update_issue(self.token, self.issue_number, self.status,
                                  lambda: self._cancelled or self.isInterruptionRequested())
            if result is not None and not self._cancelled:
                self.updated.emit(result)
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(str(exc))
        finally:
            self.token = None


def change_status(issue_number, status):
    global _worker, _error
    if not is_enabled() or _worker is not None:
        return
    token = os.environ.get("TKM_TICKETS_TOKEN") or debug._dotenv_value("TKM_TICKETS_TOKEN")
    _error = ""
    _worker = UpdateWorker(token, issue_number, status)
    _worker.updated.connect(_updated)
    _worker.failed.connect(_failed)
    _worker.finished.connect(_finished)
    _worker.start()
    _update_dialog()


def _updated(entry):
    items = _cached()
    items = [entry if item.get("issue_number") == entry["issue_number"] else item for item in items]
    if not any(item.get("issue_number") == entry["issue_number"] for item in items):
        items.insert(0, entry)
    cmds.optionVar(stringValue=(_CACHE, json.dumps(items)))
    from . import controller
    local = controller.list_sent_bug_reports()
    for item in local:
        if item.get("issue_number") == entry["issue_number"]:
            item.update({key: entry[key] for key in ("status", "state_reason", "labels")})
    controller._save_sent_reports(local)
    _update_dialog()


def refresh(*_args):
    global _worker, _error
    if not is_enabled() or _worker is not None:
        return
    token = os.environ.get("TKM_TICKETS_TOKEN") or debug._dotenv_value("TKM_TICKETS_TOKEN")
    _error = ""
    _worker = InboxWorker(token)
    _worker.loaded.connect(_loaded)
    _worker.failed.connect(_failed)
    _worker.finished.connect(_finished)
    _worker.start()
    _update_dialog()


def _loaded(items):
    previous = {entry["issue_number"]: entry for entry in _cached()}
    cmds.optionVar(stringValue=(_CACHE, json.dumps(items)))
    _update_dialog()
    from TheKeyMachine.ui.widgets import toolbar
    instance = toolbar.get_toolbar()
    anchor = getattr(instance, "tkm_btn", None)
    for item in items:
        if not is_enabled():
            break
        if item["issue_number"] in previous or item.get("status") != "open":
            continue
        customDialogs.QFlatAutoHideMessage.show_message(
            "<title>New ticket #{}</title><text>{}</text>".format(item["issue_number"], html.escape(item["summary"])),
            duration=10000, anchor_widget=anchor, action_text="Open ticket",
            action_callback=partial(open_manager, item["issue_number"]),
        )


def _failed(message):
    global _error
    _error = message
    _update_dialog()
    if _dialog is None:
        cmds.warning("Ticket manager: " + message)


def _finished():
    global _worker
    _worker = None
    _update_dialog()


def _update_dialog():
    if _dialog is not None:
        _dialog.reload()


_STATUS_COLORS = {"Reported": "#9bbbca", "In progress": "#e0b66f",
                  "Completed": "#8ac5a1", "Cancelled": "#bc9bad"}


def _report_sections(body):
    """Hide relay bookkeeping outside code fences and separate system metadata."""
    sections = [[], []]
    section = 0
    fence = None
    for line in (body or "").splitlines():
        stripped = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
        elif fence is None:
            if re.match(r"^<!--\s*(?:tkm-|fingerprint:).*-->$", stripped):
                continue
            if re.match(r"^#{1,6}\s+System details\s*$", stripped, re.I):
                section = 1
                continue
        sections[section].append(line)
    return tuple("\n".join(part).strip() for part in sections)


class TicketBodyBrowser(QtWidgets.QTextBrowser):
    """Render GitHub Markdown without loading remote images or embedded HTML."""
    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.document().setDocumentMargin(DPI(18))
        self.document().setDefaultStyleSheet(
            "h1, h2, h3 { color: #dce5e9; } "
            "pre { color: #d3dce1; } "
            "a { color: #9bbbca; }")

    def loadResource(self, resource_type, url):
        # A report is untrusted Markdown: never fetch local or remote resources.
        return QtCore.QByteArray()

    def _open_link(self, url):
        if url.scheme().lower() in ("https", "http"):
            QtGui.QDesktopServices.openUrl(url)

    def set_report(self, markdown):
        self.document().setMarkdown(markdown, QtGui.QTextDocument.MarkdownNoHTML)
        document = self.document()
        code_ranges = []
        code_start = None
        code_end = None
        block = document.begin()
        while block.isValid():
            block_format = block.blockFormat()
            is_code = block_format.hasProperty(QtGui.QTextFormat.BlockCodeFence)
            cursor = QtGui.QTextCursor(block)
            if is_code:
                if code_start is None:
                    code_start = block.position()
                code_end = block.position() + block.length() - 1
                cursor.select(QtGui.QTextCursor.BlockUnderCursor)
                code_format = QtGui.QTextCharFormat()
                code_font = QtGui.QFont("Menlo" if sys.platform == "darwin" else "Consolas")
                code_font.setStyleHint(QtGui.QFont.Monospace)
                code_font.setFixedPitch(True)
                code_format.setFont(code_font)
                code_format.setForeground(QtGui.QColor("#d7e5ed"))
                cursor.mergeCharFormat(code_format)
            else:
                if code_start is not None:
                    code_ranges.append((code_start, code_end))
                    code_start = None
                if block_format.headingLevel():
                    # Keep each report section distinct without restyling controls.
                    block_format.setTopMargin(DPI(24) if block.position() else DPI(4))
                    block_format.setBottomMargin(DPI(10))
                    cursor.setBlockFormat(block_format)
            block = block.next()
        if code_start is not None:
            code_ranges.append((code_start, code_end))
        # Wrap whole fences, rather than drawing a border around every line.
        # Work backwards so inserting frames cannot invalidate earlier positions.
        for start, end in reversed(code_ranges):
            cursor = QtGui.QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(end, QtGui.QTextCursor.KeepAnchor)
            frame_format = QtGui.QTextFrameFormat()
            frame_format.setBorder(1)
            frame_format.setBorderStyle(QtGui.QTextFrameFormat.BorderStyle_Solid)
            frame_format.setBorderBrush(QtGui.QBrush(QtGui.QColor("#56616a")))
            frame_format.setBackground(QtGui.QBrush(QtGui.QColor("#23282d")))
            frame_format.setPadding(DPI(12))
            frame_format.setTopMargin(0)
            frame_format.setBottomMargin(DPI(12))
            frame = cursor.insertFrame(frame_format)
            # Qt inserts an empty paragraph before a frame. Collapse that
            # spacer so a section heading stays attached to its code block.
            preceding = document.findBlock(frame.firstPosition() - 1)
            if preceding.isValid() and not preceding.text().strip():
                spacer_cursor = QtGui.QTextCursor(preceding)
                spacer_format = preceding.blockFormat()
                spacer_format.setTopMargin(0)
                spacer_format.setBottomMargin(0)
                spacer_format.setLineHeight(1, QtGui.QTextBlockFormat.FixedHeight)
                spacer_cursor.setBlockFormat(spacer_format)
                spacer_text = QtGui.QTextCharFormat()
                spacer_text.setFontPointSize(1)
                spacer_cursor.setBlockCharFormat(spacer_text)
                preceding = preceding.previous()
            if preceding.isValid() and preceding.blockFormat().headingLevel():
                heading_cursor = QtGui.QTextCursor(preceding)
                heading_format = preceding.blockFormat()
                heading_format.setBottomMargin(DPI(4))
                heading_cursor.setBlockFormat(heading_format)
        self.verticalScrollBar().setValue(0)


class TicketManager(customDialogs.QFlatDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("TicketManager")
        self.setWindowTitle("Ticket Manager")
        self.resize(DPI(1080), DPI(720))
        self.setMinimumSize(DPI(650), DPI(400))
        content = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(DPI(12), DPI(12), DPI(12), DPI(12))
        layout.setSpacing(DPI(10))
        self.addWindowHeader(parentLayout=layout, icon=icons.get_in_touch)
        self.overview = QtWidgets.QLabel("Repository inbox · All reporters")
        self.overview.setStyleSheet("color: #a7b5bf;")
        layout.addWidget(self.overview)
        row = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by ticket number, title, or report text…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(DPI(34))
        self.filter = QtWidgets.QComboBox()
        self.filter.addItems(["All tickets", "Open", "Closed"])
        row.addWidget(self.search, 1)
        row.addWidget(self.filter)
        self.refetch = QtWidgets.QPushButton("Refetch Issues")
        self.refetch.setVisible(is_enabled())
        self.refetch.clicked.connect(refresh)
        row.addWidget(self.refetch)
        layout.addLayout(row)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.ticket_lists = {}
        self.list_sections = {}
        self._active_list = None
        left_panel = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        for kind, title in (("bug", "Bugs"), ("suggestion", "Suggestions")):
            section = QtWidgets.QWidget()
            section_layout = QtWidgets.QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.addWidget(QtWidgets.QLabel(title))
            ticket_list = QtWidgets.QTreeWidget()
            ticket_list.setHeaderLabels(["Ticket", "Status"])
            ticket_list.setRootIsDecorated(False)
            ticket_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            ticket_list.setAlternatingRowColors(True)
            ticket_list.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            ticket_list.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            section_layout.addWidget(ticket_list)
            self.ticket_lists[kind] = ticket_list
            self.list_sections[kind] = section
            left_panel.addWidget(section)
            left_panel.setCollapsible(left_panel.count() - 1, False)
        detail_panel = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(DPI(8), 0, 0, 0)
        self.ticket_title = QtWidgets.QLabel("Select a ticket")
        self.ticket_title.setTextFormat(QtCore.Qt.PlainText)
        self.ticket_title.setWordWrap(True)
        self.ticket_title.setStyleSheet("color: #e1e8ed;")
        detail_layout.addWidget(self.ticket_title)
        self.ticket_meta = QtWidgets.QLabel()
        self.ticket_meta.setWordWrap(True)
        detail_layout.addWidget(self.ticket_meta)
        self.detail_tabs = QtWidgets.QTabWidget()
        self.details = TicketBodyBrowser()
        self.system_details = TicketBodyBrowser()
        self.detail_tabs.addTab(self.details, "Report")
        self.detail_tabs.addTab(self.system_details, "System details")
        detail_layout.addWidget(self.detail_tabs, 1)
        splitter.addWidget(left_panel)
        splitter.addWidget(detail_panel)
        splitter.setSizes([DPI(390), DPI(650)])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        layout.addWidget(splitter, 1)
        self.edit_row = QtWidgets.QWidget()
        edit_layout = QtWidgets.QHBoxLayout(self.edit_row)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.addWidget(QtWidgets.QLabel("Set status"))
        self.status_choice = QtWidgets.QComboBox()
        self.status_choice.addItems(list(_STATUS_ACTIONS))
        self.status_choice.setToolTip("Reported and In progress reopen a ticket. Completed and Cancelled close it.")
        edit_layout.addWidget(self.status_choice)
        self.apply_status = QtWidgets.QPushButton("Apply status")
        self.apply_status.clicked.connect(self.save_status)
        self.status_choice.currentIndexChanged.connect(self.update_actions)
        edit_layout.addWidget(self.apply_status)
        edit_layout.addStretch()
        detail_layout.addWidget(self.edit_row)
        self.action_hint = QtWidgets.QLabel()
        self.action_hint.setWordWrap(True)
        self.action_hint.setStyleSheet("color: #9eabb5;")
        detail_layout.addWidget(self.action_hint)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.root_layout.addWidget(content, 1)
        button = customDialogs.QFlatDialogButton("Open on GitHub", callback=self.open_selected)
        self.setBottomBar([button], closeButton=True)
        self.search.textChanged.connect(self.reload)
        self.filter.currentIndexChanged.connect(self.reload)
        for ticket_list in self.ticket_lists.values():
            ticket_list.currentItemChanged.connect(partial(self._select_from_list, ticket_list))
        self.reload()

    def _select_from_list(self, ticket_list, item, *_args):
        if item is None:
            return
        self._active_list = ticket_list
        for other in self.ticket_lists.values():
            if other is not ticket_list:
                other.blockSignals(True)
                other.setCurrentItem(None)
                other.clearSelection()
                other.blockSignals(False)
        self.show_selected()

    def selected(self):
        item = self._active_list.currentItem() if self._active_list is not None else None
        return item.data(0, QtCore.Qt.UserRole) if item else None

    def reload(self, *_args):
        selected = self.selected()
        number = selected.get("issue_number") if selected else None
        for ticket_list in self.ticket_lists.values():
            ticket_list.blockSignals(True)
            ticket_list.clear()
        self._active_list = None
        restore = None
        all_entries = entries()
        open_count = sum(entry.get("status") == "open" for entry in all_entries)
        self.overview.setText("Repository inbox · {} open · {} closed · All reporters".format(open_count, len(all_entries) - open_count))
        query = self.search.text().strip().lower()
        state = (None, "open", "closed")[self.filter.currentIndex()]
        for entry in all_entries:
            if state and entry.get("status") != state:
                continue
            if query and query not in "{} {} {}".format(entry.get("issue_number"), entry.get("summary", ""), entry.get("body", "")).lower():
                continue
            item = QtWidgets.QTreeWidgetItem(["#{}  {}".format(entry.get("issue_number"), entry.get("summary", "")), _status_name(entry)])
            item.setForeground(1, QtGui.QBrush(QtGui.QColor(_STATUS_COLORS[_status_name(entry)])))
            item.setToolTip(0, entry.get("summary", ""))
            item.setData(0, QtCore.Qt.UserRole, entry)
            labels = {label.lower() for label in entry.get("labels", [])}
            suggestion = bool(labels & {"suggestion", "enhancement"}) or entry.get("report_type") == "suggestion"
            ticket_list = self.ticket_lists["suggestion" if suggestion else "bug"]
            ticket_list.addTopLevelItem(item)
            if entry.get("issue_number") == number:
                restore = (ticket_list, item)
        for kind, ticket_list in self.ticket_lists.items():
            self.list_sections[kind].setVisible(ticket_list.topLevelItemCount() > 0)
            ticket_list.blockSignals(False)
            if restore is None and ticket_list.topLevelItemCount():
                restore = (ticket_list, ticket_list.topLevelItem(0))
        if restore is not None:
            restore[0].setCurrentItem(restore[1])
        self.show_selected()
        self.refetch.setVisible(is_enabled())
        self.refetch.setEnabled(_worker is None)
        self.update_actions()
        message = _error or (("Updating ticket…" if isinstance(_worker, UpdateWorker) else "Checking the inbox…") if _worker else "")
        self.status.setText(message)
        self.status.setVisible(bool(message))

    def select_ticket(self, number):
        self.search.clear()
        self.filter.setCurrentIndex(0)
        for ticket_list in self.ticket_lists.values():
            for index in range(ticket_list.topLevelItemCount()):
                item = ticket_list.topLevelItem(index)
                if item.data(0, QtCore.Qt.UserRole).get("issue_number") == number:
                    ticket_list.setCurrentItem(item)
                    ticket_list.scrollToItem(item)
                    return

    def show_selected(self, *_args):
        entry = self.selected()
        self.status_choice.setCurrentText(_status_name(entry) if entry else "Reported")
        self.update_actions()
        if not entry:
            self.ticket_title.setText("No tickets to show")
            self.ticket_meta.clear()
            self.details.setPlainText("Try another search or filter. New tickets will appear here after the inbox is checked.")
            self.system_details.clear()
            self.detail_tabs.setTabEnabled(1, False)
            self.detail_tabs.setCurrentIndex(0)
            return
        self.ticket_title.setText("#{} · {}".format(entry["issue_number"], entry.get("summary", "")))
        status = _status_name(entry)
        labels = [label.replace("area:", "Area: ").replace("source:", "Source: ")
                  for label in entry.get("labels", []) if not label.startswith("status:")]
        created = QtCore.QDateTime.fromString(entry.get("created_at", ""), QtCore.Qt.ISODate)
        if created.isValid():
            labels.append("Created " + created.toLocalTime().toString("d MMM yyyy, HH:mm"))
        self.ticket_meta.setText('<b style="color: {}">{}</b> <span style="color: #9eabb5"> · {}</span>'.format(
            _STATUS_COLORS[status], html.escape(status), html.escape(" · ".join(labels))))
        report, system = _report_sections(entry.get("body"))
        self.details.set_report(report or "No report description. Open this ticket on GitHub for the conversation.")
        self.system_details.set_report(system)
        self.detail_tabs.setTabEnabled(1, bool(system))
        if not system:
            self.detail_tabs.setCurrentIndex(0)

    def update_actions(self, *_args):
        entry = self.selected()
        choice = self.status_choice.currentText()
        self.action_hint.setText({
            "Reported": "Reopen this ticket and return it to the inbox.",
            "In progress": "Keep this ticket open and mark it as being worked on.",
            "Completed": "Close this ticket as completed.",
            "Cancelled": "Close this ticket as not planned.",
        }.get(choice, "") if entry else "Select a ticket to change its status.")
        enabled = is_enabled()
        self.edit_row.setVisible(enabled)
        self.status_choice.setEnabled(enabled and bool(entry) and _worker is None)
        self.apply_status.setEnabled(enabled and bool(entry) and _worker is None
                                     and self.status_choice.currentText() != _status_name(entry))

    def save_status(self):
        entry = self.selected()
        if entry:
            change_status(entry["issue_number"], self.status_choice.currentText())

    def open_selected(self):
        from . import controller
        entry = self.selected()
        if entry:
            controller.open_issue(entry["issue_number"])


def open_manager(issue_number=None, *_args):
    global _dialog
    if not is_enabled():
        if _dialog is not None:
            _dialog.hide()
        return None
    if _dialog is None:
        _dialog = TicketManager()
        _dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
    _dialog.reload()
    if issue_number is not None:
        _dialog.select_ticket(issue_number)
    if not _dialog.isVisible():
        parent = _dialog.parentWidget() or get_maya_qt()
        geometry = parent.frameGeometry() if parent else QtGui.QGuiApplication.primaryScreen().availableGeometry()
        _dialog.move(geometry.center() - _dialog.rect().center())
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    refresh()
    return _dialog


@on_shutdown(phase=ShutdownPhase.TOOLS)
def shutdown():
    global _dialog
    if _dialog is not None:
        _dialog.close()
        _dialog.deleteLater()
        _dialog = None
