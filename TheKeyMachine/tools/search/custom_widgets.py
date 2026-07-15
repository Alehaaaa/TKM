"""Custom Qt widgets used by Search."""

from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets  # type: ignore
from TheKeyMachine.core import trigger
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


class SearchLineEdit(QtWidgets.QLineEdit):
    """Line edit that paints the selected tool's remaining text as a suffix."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._completion = ""
        self._completion_secondary = False
        self._result_icon_visible = False
        self._result_icon = QtWidgets.QLabel(self)
        self._result_icon.setAlignment(QtCore.Qt.AlignCenter)
        self._result_icon.setFixedSize(wutil.DPI(38), wutil.DPI(38))
        self._result_icon.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._result_icon.hide()

    def set_completion(self, completion, secondary=False):
        completion = completion or ""
        secondary = bool(secondary)
        if completion == self._completion and secondary == self._completion_secondary:
            return
        self._completion = completion
        self._completion_secondary = secondary
        self.update()

    def set_result_icon(self, icon_path=None, fallback_text=""):
        self._result_icon_visible = bool(icon_path or fallback_text)
        self._result_icon.clear()
        if icon_path:
            self._result_icon.setPixmap(
                QtGui.QIcon(icon_path).pixmap(wutil.DPI(30), wutil.DPI(30))
            )
            self._result_icon.setStyleSheet("background:transparent;")
        elif fallback_text:
            self._result_icon.setText(str(fallback_text)[:2].upper())
            self._result_icon.setStyleSheet(
                "background:transparent;color:#aeb8c0;font-size:%spx;" % wutil.DPI(9)
            )
        self._result_icon.setVisible(self._result_icon_visible)
        self.setTextMargins(0, 0, wutil.DPI(42) if self._result_icon_visible else 0, 0)
        self._position_result_icon()
        self.update()

    def _position_result_icon(self):
        margin = wutil.DPI(5)
        self._result_icon.move(
            self.width() - self._result_icon.width() - margin,
            max(0, int((self.height() - self._result_icon.height()) / 2)),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_result_icon()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._completion or self.cursorPosition() != len(self.text()):
            return

        cursor_rect = self.cursorRect()
        # Start immediately after the caret. Using its left edge can paint the
        # completion over the last entered characters on some Qt/Maya versions.
        # cursorRect is the most reliable reference across Maya/Qt versions.
        # Its right edge includes extra cursor advance, so apply the measured
        # optical correction instead of deriving placement from outer padding.
        completion_x = cursor_rect.right() - max(1, int(wutil.DPI(1))) - 3
        completion_right = (
            self._result_icon.x() - wutil.DPI(4)
            if self._result_icon_visible
            else self.contentsRect().right() - wutil.DPI(8)
        )
        available = completion_right - completion_x
        if available <= 0:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        # Text antialiasing visually darkens #444444 over the input background;
        # this compensated value matches the floating shell perceptually.
        painter.setPen(QtGui.QColor("#606060"))
        if self._completion_secondary:
            completion_font = QtGui.QFont(self.font())
            completion_font.setPointSizeF(max(7.0, completion_font.pointSizeF() * 0.72))
            painter.setFont(completion_font)
        suffix = painter.fontMetrics().elidedText(self._completion, QtCore.Qt.ElideRight, available)
        rect = QtCore.QRect(
            completion_x,
            cursor_rect.top() - 1,
            available,
            cursor_rect.height(),
        )
        painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, suffix)
        painter.end()


class SearchResultItemWidget(QtWidgets.QWidget):
    """Compact, fixed-layout result row with selection that never shifts its icon."""

    clicked = QtCore.Signal()
    invoked = QtCore.Signal()

    def __init__(self, row, row_index=0, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setObjectName("SearchResultItemWidget")
        self.setProperty("rowSelected", False)
        self.setProperty("rowBase", "#2b2b2b" if row_index % 2 == 0 else "#2e2e2e")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#SearchResultItemWidget{background:%s;}"
            "#SearchResultItemWidget[rowSelected='true']{background:#5f88a8;}"
            % ("#2b2b2b" if row_index % 2 == 0 else "#2e2e2e")
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(wutil.DPI(2), 0, wutil.DPI(6), 0)
        layout.setSpacing(wutil.DPI(3))

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_path = row.get("icon")
        if icon_path:
            self.icon_label.setPixmap(QtGui.QIcon(icon_path).pixmap(wutil.DPI(18), wutil.DPI(18)))
        else:
            title = str(row.get("title") or row.get("command") or "")
            fallback = str(row.get("badge_text") or title[:2]).upper()
            self.icon_label.setText(fallback)
            self.icon_label.setStyleSheet("background:transparent;color:#aeb8c0;font-size:%spx;" % wutil.DPI(8))
        layout.addWidget(self.icon_label)

        self.check_box = None
        if row.get("checkable"):
            self.check_box = QtWidgets.QCheckBox(self)
            self.check_box.setObjectName("SearchResultCheckBox")
            self.check_box.setProperty("tkm_window_anchor", False)
            self.check_box.setFixedSize(wutil.DPI(15), wutil.DPI(22))
            self.check_box.setFocusPolicy(QtCore.Qt.NoFocus)
            self.check_box.setStyleSheet(
                "#SearchResultCheckBox{background:transparent;spacing:0px;}"
                "#SearchResultCheckBox::indicator{width:%spx;height:%spx;border:1px solid #626262;border-radius:%spx;background:#262626;}"
                "#SearchResultCheckBox::indicator:hover{border-color:#7d7d7d;background:#303030;}"
                "#SearchResultCheckBox::indicator:checked{image:url(%s);border-color:#7d7d7d;background:#363636;}"
                % (wutil.DPI(11), wutil.DPI(11), wutil.DPI(3), icons.apply)
            )
            callback = row.get("callback") or trigger.get_command(row.get("command"))
            toolCommon.connect_tool_control(
                self.check_box,
                (lambda *_args, cb=callback: cb()) if callable(callback) else None,
                checkable=True,
                getter=row.get("get_checked"),
                setter=row.get("set_checked"),
                changed_signal=row.get("changed_signal"),
                bind_fn=row.get("bind_checked_fn"),
                state_key=row.get("state_key"),
            )
            layout.addWidget(self.check_box)

        self.title_label = QtWidgets.QLabel(str(row.get("title") or row.get("command") or ""), self)
        self.title_label.setStyleSheet("background:transparent;color:#d0d0d0;font-size:%spx;" % wutil.DPI(10))
        layout.addWidget(self.title_label, 1)

        for watched in (self.icon_label, self.title_label):
            watched.installEventFilter(self)

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("rowSelected", self._selected)
        self.title_label.setStyleSheet(
            "background:transparent;color:%s;font-size:%spx;"
            % ("#ffffff" if selected else "#d0d0d0", wutil.DPI(10))
        )
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.invoked.emit()
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self.invoked.emit()
            return True
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.clicked.emit()
        return super().eventFilter(watched, event)
