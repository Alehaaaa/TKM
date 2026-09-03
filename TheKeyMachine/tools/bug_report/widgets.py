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

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets

from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets.util import DPI, get_maya_qt


class QFlatBugReportDialog(customDialogs.QFlatDialog):
    """
    Modern bug report dialog that reuses QFlatDialog styling.
    """

    MAX_TEXT_CHARS = 1200
    MAX_SCRIPT_ERROR_CHARS = 12000

    _BUG_ACCENT_COLOR = "#CA6161"
    _SUGGESTION_ACCENT_COLOR = "#D9A441"

    def __init__(
        self,
        parent=None,
        submit_callback=None,
        prepare_callback=None,
        worker_class=None,
        open_issue_callback=None,
        dialog_title=None,
        prefill_name="",
        prefill_explanation="",
        prefill_script_error="",
    ):
        from TheKeyMachine.core import i18n

        self._submit_callback = submit_callback
        self._prepare_callback = prepare_callback
        self._worker_class = worker_class
        self._open_issue_callback = open_issue_callback
        self._submit_worker = None
        self._submitted_successfully = False
        self._submitted_report_type = None
        self._last_issue_number = None
        self._send_button = None
        super().__init__(parent=parent)
        self.setWindowTitle(dialog_title or i18n.tr("bug_report_title", "Report a Bug or Suggestion"))
        # More horizontal / less tall default footprint.
        self.setMinimumSize(DPI(600), DPI(450))

        self._info_color = "#9bbbca"
        self._error_color = "#CA6161"
        self._status_placeholder = " "

        content_widget = QtWidgets.QWidget(self)
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(12), DPI(12), DPI(12), 0)
        content_layout.setSpacing(DPI(8))

        self.addWindowHeader(
            parentLayout=content_layout,
            icon=icons.bug,
            textColor="#CA6161",
        )

        subtitle = QtWidgets.QLabel(
            i18n.tr(
                "bug_report_subtitle",
                "Send a private bug report or suggestion. System details help diagnose bugs; personal home paths are removed before upload.",
            ),
            content_widget,
        )
        subtitle.setAlignment(QtCore.Qt.AlignLeft)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #cccccc; font-size: %spx;" % DPI(11))
        content_layout.addWidget(subtitle)

        self.type_group = QtWidgets.QButtonGroup(self)
        self.type_group.setExclusive(True)
        self.type_bug_button = QtWidgets.QPushButton(
            i18n.tr("bug_report_type_bug", "Bug"), content_widget
        )
        self.type_suggestion_button = QtWidgets.QPushButton(
            i18n.tr("bug_report_type_suggestion", "Suggestion"), content_widget
        )
        self.type_bug_button.setStyleSheet(self._type_button_style(self._BUG_ACCENT_COLOR))
        self.type_suggestion_button.setStyleSheet(self._type_button_style(self._SUGGESTION_ACCENT_COLOR))
        for button in (self.type_bug_button, self.type_suggestion_button):
            button.setCheckable(True)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            self.type_group.addButton(button)
        self.type_bug_button.setChecked(True)
        self.type_bug_button.toggled.connect(self._on_type_toggled)
        self.type_suggestion_button.toggled.connect(self._on_type_toggled)

        type_row = QtWidgets.QWidget(content_widget)
        type_row_layout = QtWidgets.QHBoxLayout(type_row)
        type_row_layout.setContentsMargins(0, 0, 0, 0)
        type_row_layout.setSpacing(DPI(6))
        type_row_layout.addWidget(self.type_bug_button)
        type_row_layout.addWidget(self.type_suggestion_button)
        type_row_layout.addStretch(1)
        content_layout.addWidget(type_row)

        self.status_label = QtWidgets.QLabel(self._status_placeholder, content_widget)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.status_label.setMinimumHeight(self._status_row_height())
        self.status_label.setStyleSheet("color: %s;" % self._info_color)
        self.status_label.setVisible(False)

        self.name_input = QtWidgets.QLineEdit(content_widget)
        self.name_input.setPlaceholderText(i18n.tr("bug_report_name_placeholder", "Name or alias (optional)"))
        self.name_input.setMaxLength(50)
        if prefill_name:
            self.name_input.setText(prefill_name)

        self._explanation_placeholder_bug = i18n.tr(
            "bug_report_explanation_placeholder",
            "* Describe what happened, what you expected, and the steps to reproduce it.",
        )
        self._explanation_placeholder_suggestion = i18n.tr(
            "bug_report_explanation_placeholder_suggestion",
            "* Describe the idea and what problem it would solve.",
        )
        self._script_error_placeholder_bug = i18n.tr(
            "bug_report_script_error_placeholder",
            "Paste the last Script Editor lines here. Include the traceback or exact error if you have it.",
        )
        self._script_error_placeholder_suggestion = i18n.tr(
            "bug_report_script_error_placeholder_suggestion",
            "Optional: any related error or context.",
        )
        self._send_button_label_bug = i18n.tr("bug_report_send_button", "Send bug")
        self._send_button_label_suggestion = i18n.tr(
            "bug_report_send_suggestion_button", "Send suggestion"
        )
        self._open_ticket_button_label = i18n.tr("bug_report_open_ticket_button", "Open ticket")

        self.explanation_textbox = QtWidgets.QTextEdit(content_widget)
        self.explanation_textbox.setPlaceholderText(self._explanation_placeholder_bug)
        self.explanation_textbox.setAcceptRichText(False)
        self.explanation_textbox.setMinimumHeight(DPI(110))
        self.explanation_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.explanation_textbox.textChanged.connect(lambda: self._enforce_text_limit(self.explanation_textbox))
        if prefill_explanation:
            self.explanation_textbox.setPlainText(prefill_explanation)

        self.script_error_textbox = QtWidgets.QTextEdit(content_widget)
        self.script_error_textbox.setPlaceholderText(self._script_error_placeholder_bug)
        self.script_error_textbox.setAcceptRichText(False)
        self.script_error_textbox.setMinimumHeight(DPI(80))
        self.script_error_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.script_error_textbox.textChanged.connect(
            lambda: self._enforce_text_limit(self.script_error_textbox, limit=self.MAX_SCRIPT_ERROR_CHARS)
        )
        if prefill_script_error:
            self.script_error_textbox.setPlainText(prefill_script_error)

        self.name_input.setStyleSheet(self._input_style())
        self.name_input.textChanged.connect(self._clear_status_message)

        for widget in (self.explanation_textbox, self.script_error_textbox):
            widget.setStyleSheet(self._textedit_style())
            widget.textChanged.connect(self._clear_status_message)

        left_fields = QtWidgets.QWidget(content_widget)
        left_fields_layout = QtWidgets.QVBoxLayout(left_fields)
        left_fields_layout.setContentsMargins(0, 0, 0, 0)
        left_fields_layout.setSpacing(DPI(8))
        left_fields_layout.addWidget(self.name_input)
        left_fields_layout.addWidget(self.explanation_textbox, 1)

        self.details_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, content_widget)
        self.details_splitter.setChildrenCollapsible(False)
        self.details_splitter.setOpaqueResize(True)
        self.details_splitter.setHandleWidth(DPI(6))
        self.details_splitter.addWidget(left_fields)
        self.details_splitter.addWidget(self.script_error_textbox)
        self.details_splitter.setStretchFactor(0, 2)
        self.details_splitter.setStretchFactor(1, 1)
        content_layout.addWidget(self.details_splitter, 1)
        content_layout.addWidget(self.status_label)

        self.root_layout.addWidget(content_widget, 1)

        send_cfg = customDialogs.QFlatDialogButton(
            "Send bug", highlight=True, icon=icons.apply, i18n_key="bug_report_send_button"
        )
        send_cfg["callback"] = self._on_send_clicked
        self.setBottomBar([send_cfg], closeButton=True, highlight="Send bug")
        self._send_button = self._find_button("Send bug")

        # Keep a horizontal rectangle feel even with vertical fields.
        self.resize(DPI(680), DPI(500))
        QtCore.QTimer.singleShot(0, self._init_splitter_sizes)

    def _input_style(self):
        return (
            "QLineEdit {background-color: #2d2d2d;border: 1px solid #393939;border-radius: %spx;color: #cccccc;padding: %spx;font-size: %spx;}"
        ) % (DPI(4), DPI(6), DPI(11))

    def _textedit_style(self):
        return (
            "QTextEdit {background-color: #2d2d2d;border: 1px solid #393939;border-radius: %spx;color: #cccccc;padding: %spx;font-size: %spx;}"
        ) % (DPI(4), DPI(6), DPI(11))

    def _type_button_style(self, accent_color):
        return (
            "QPushButton {background-color: #2d2d2d;border: 1px solid #393939;border-radius: %spx;"
            "color: #999999;padding: %spx %spx;font-size: %spx;}"
            "QPushButton:checked {background-color: #3a3a3a;border: 1px solid %s;color: #ffffff;}"
            "QPushButton:hover {color: #ffffff;}"
        ) % (DPI(4), DPI(4), DPI(12), DPI(11), accent_color)

    def _report_type_value(self):
        return "suggestion" if self.type_suggestion_button.isChecked() else "bug"

    def _on_type_toggled(self, checked):
        if not checked:
            # Only react to the button that just became the checked one --
            # the group's toggled signal fires twice per switch (off, then on).
            return
        self._apply_type_dependent_labels()

    def _apply_type_dependent_labels(self):
        # Once a report has been sent, the send button has turned into an
        # "Open ticket" button for that submission -- switching type at that
        # point (via apply_prefill, when the dialog is reused for a new
        # report) is handled by the success-state reset, not here.
        if self._submitted_successfully:
            return
        is_suggestion = self._report_type_value() == "suggestion"
        self.explanation_textbox.setPlaceholderText(
            self._explanation_placeholder_suggestion if is_suggestion else self._explanation_placeholder_bug
        )
        self.script_error_textbox.setPlaceholderText(
            self._script_error_placeholder_suggestion if is_suggestion else self._script_error_placeholder_bug
        )
        if self._send_button:
            self._send_button.setText(
                self._send_button_label_suggestion if is_suggestion else self._send_button_label_bug
            )
        self._clear_status_message()

    def _find_button(self, name):
        if not self.bottomBar:
            return None
        for btn in self.bottomBar.findChildren(QtWidgets.QPushButton):
            # Match by the untranslated English name stashed in
            # _defineButtons() -- btn.text() is translated and no longer
            # comparable to a literal English name like "Send bug".
            stored_name = btn.property("tkm_dialog_button_name")
            candidate = str(stored_name) if stored_name else btn.text()
            if candidate.strip().lower() == name.lower():
                return btn
        return None

    def apply_prefill(self, dialog_title=None, name="", explanation="", script_error="", report_type="bug"):
        if self._submit_worker and self._submit_worker.isRunning():
            return
        if dialog_title:
            self.setWindowTitle(dialog_title)
        self.name_input.setText(name or "")
        self.explanation_textbox.setPlainText(explanation or "")
        self.script_error_textbox.setPlainText(script_error or "")
        self._submitted_successfully = False
        self._submitted_report_type = None
        self._last_issue_number = None
        if str(report_type or "").strip().lower() == "suggestion":
            self.type_suggestion_button.setChecked(True)
        else:
            self.type_bug_button.setChecked(True)
        # setChecked() above is a no-op (fires no toggled signal) when the
        # dialog is reused for another report of the *same* type -- refresh
        # the send button's label explicitly so it drops out of "Open ticket".
        self._apply_type_dependent_labels()
        self._set_form_enabled(True)
        self._set_send_enabled(True)
        self._clear_status_message()

    def _status_row_height(self):
        metrics = self.status_label.fontMetrics() if hasattr(self, "status_label") else self.fontMetrics()
        return max(DPI(10), metrics.lineSpacing() + DPI(1))

    def _init_splitter_sizes(self):
        if not hasattr(self, "details_splitter"):
            return
        total = max(DPI(420), self.details_splitter.size().width())
        left = max(DPI(260), int(total * 0.62))
        right = max(DPI(180), total - left)
        self.details_splitter.setSizes([left, right])

    def _set_send_enabled(self, enabled):
        if self._send_button:
            self._send_button.setEnabled(bool(enabled))

    def _set_form_enabled(self, enabled):
        for widget in (
            self.type_bug_button,
            self.type_suggestion_button,
            self.name_input,
            self.explanation_textbox,
            self.script_error_textbox,
        ):
            widget.setEnabled(bool(enabled))

    def _required_values(self):
        return (
            self.name_input.text().strip(),
            self.explanation_textbox.toPlainText().strip(),
        )

    def _optional_values(self):
        return {
            "script_error": self.script_error_textbox.toPlainText().strip(),
            "report_type": self._report_type_value(),
        }

    def _validate(self):
        from TheKeyMachine.core import i18n

        name, explanation = self._required_values()
        if not explanation:
            self._set_status(
                i18n.tr("bug_report_status_missing_fields", "Please fill in the required fields."),
                error=True,
            )
            return None
        return {
            "name": name,
            "explanation": explanation,
            **self._optional_values(),
        }

    def _set_status(self, message, error=False):
        color = self._error_color if error else self._info_color
        self.status_label.setStyleSheet("color: %s;" % color)
        self.status_label.setText(message or "")
        self.status_label.setVisible(bool(message))

    def _clear_status_message(self):
        if self._submitted_successfully:
            return
        if self._send_button and not self._send_button.isEnabled():
            return
        self.status_label.setText("")
        self.status_label.setVisible(False)

    def _enforce_text_limit(self, widget, limit=None):
        limit = int(limit or self.MAX_TEXT_CHARS)
        text = widget.toPlainText()
        if len(text) <= limit:
            return
        cursor = widget.textCursor()
        pos = cursor.position()
        widget.blockSignals(True)
        widget.setPlainText(text[:limit])
        cursor.setPosition(min(pos, limit))
        widget.setTextCursor(cursor)
        widget.blockSignals(False)

    def _open_last_issue(self):
        if not self._last_issue_number or not self._open_issue_callback:
            return
        try:
            self._open_issue_callback(self._last_issue_number)
        except Exception as exc:
            print("[TheKeyMachine] Failed to open bug report ticket:", exc)

    def _on_send_clicked(self):
        from TheKeyMachine.core import i18n

        if self._submitted_successfully:
            # The button has turned into "Open ticket" for this submission.
            self._open_last_issue()
            return

        payload = self._validate()
        if not payload:
            return

        unavailable_message = i18n.tr(
            "bug_report_status_unavailable", "Report submission is unavailable right now."
        )

        if not self._submit_callback:
            self._set_status(unavailable_message, error=True)
            return

        if self._submit_worker and self._submit_worker.isRunning():
            return

        if self._prepare_callback:
            try:
                payload = self._prepare_callback(**payload)
            except Exception as exc:
                print("[TheKeyMachine] Bug report preparation failed:", exc)
                self._set_status(
                    i18n.tr("bug_report_status_prepare_failed", "Failed to prepare the report."),
                    error=True,
                )
                return

        self._submitted_report_type = payload.get("report_type", self._report_type_value())
        is_suggestion = self._submitted_report_type == "suggestion"
        self._set_status(
            i18n.tr(
                "bug_report_status_sending_suggestion" if is_suggestion else "bug_report_status_sending",
                "Sending suggestion..." if is_suggestion else "Sending bug report...",
            ),
            error=False,
        )
        self._set_form_enabled(False)
        self._set_send_enabled(False)

        if self._worker_class is None:
            self._set_status(unavailable_message, error=True)
            self._set_form_enabled(True)
            self._set_send_enabled(True)
            return

        self._submit_worker = self._worker_class(self._submit_callback, payload, parent=self)
        self._submit_worker.result_ready.connect(self._on_submit_finished)
        self._submit_worker.finished.connect(self._submit_worker.deleteLater)
        self._submit_worker.start()

    def _on_submit_finished(self, success, error):
        from TheKeyMachine.core import i18n

        if success:
            self._submitted_successfully = True
            self._last_issue_number = error.get("issue_number") if isinstance(error, dict) else None
            if isinstance(error, dict) and error.get("duplicate", False):
                self._set_status(
                    i18n.tr(
                        "bug_report_status_duplicate",
                        "This matches an existing report, so its occurrence count was updated. Thank you!",
                    ),
                    error=False,
                )
            else:
                is_suggestion = self._submitted_report_type == "suggestion"
                self._set_status(
                    i18n.tr(
                        "bug_report_status_success_suggestion" if is_suggestion else "bug_report_status_success",
                        "Suggestion sent privately. Thank you!"
                        if is_suggestion
                        else "Bug report sent privately. Thank you!",
                    ),
                    error=False,
                )
            if self._send_button and self._last_issue_number and self._open_issue_callback:
                self._send_button.setText(self._open_ticket_button_label)
                self._set_send_enabled(True)
            else:
                self._set_send_enabled(False)
        else:
            if error:
                print("[TheKeyMachine] Bug report submission failed:", error)
            if isinstance(error, dict) and error.get("fallback_saved", False):
                self._set_status(
                    i18n.tr(
                        "bug_report_status_saved_fallback",
                        "Could not send the report. A local copy was saved to your Desktop.",
                    ),
                    error=True,
                )
            else:
                self._set_status(
                    i18n.tr("bug_report_status_failed", "Failed to send the report. Try again later."),
                    error=True,
                )
            self._set_form_enabled(True)
            self._set_send_enabled(True)
        self._submit_worker = None

    def closeEvent(self, event):
        if self._submit_worker and self._submit_worker.isRunning():
            from TheKeyMachine.core import i18n

            self._set_status(
                i18n.tr(
                    "bug_report_status_sending_wait_suggestion"
                    if self._submitted_report_type == "suggestion"
                    else "bug_report_status_sending_wait",
                    "Sending suggestion. Please wait..."
                    if self._submitted_report_type == "suggestion"
                    else "Sending bug report. Please wait...",
                ),
                error=False,
            )
            event.ignore()
            return
        customDialogs.QFlatDialog.closeEvent(self, event)

    def show_centered(self):
        # Avoid adjustSize() here: it tends to make this dialog overly tall based on content hints.
        self.resize(DPI(680), DPI(500))
        parent = self.parentWidget() or get_maya_qt()
        if isinstance(parent, QtWidgets.QWidget) and hasattr(parent, "frameGeometry"):
            geo = parent.frameGeometry()
            x = geo.x() + (geo.width() - self.width()) / 2
            y = geo.y() + (geo.height() - self.height()) / 2
        else:
            geo = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            x = geo.x() + (geo.width() - self.width()) / 2
            y = geo.y() + (geo.height() - self.height()) / 2

        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()
