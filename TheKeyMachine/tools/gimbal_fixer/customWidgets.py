from TheKeyMachine.Qt import QtCore, QtWidgets  # type: ignore
from TheKeyMachine.widgets import util as wutil


class GimbalOrderButton(QtWidgets.QFrame):
    clicked = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.order = ""
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedHeight(wutil.DPI(42))

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(wutil.DPI(8), wutil.DPI(4), wutil.DPI(8), wutil.DPI(4))
        layout.setHorizontalSpacing(wutil.DPI(8))
        layout.setVerticalSpacing(wutil.DPI(2))

        self.rank_label = QtWidgets.QLabel("", self)
        self.rank_label.setFixedWidth(wutil.DPI(42))
        self.order_label = QtWidgets.QLabel("", self)
        self.order_label.setStyleSheet("font-size: %spx; font-weight: bold; color: #eeeeee;" % wutil.DPI(15))
        self.score_label = QtWidgets.QLabel("", self)
        self.score_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.score_label.setFixedWidth(wutil.DPI(42))

        self.bar = QtWidgets.QProgressBar(self)
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(wutil.DPI(5))

        layout.addWidget(self.rank_label, 0, 0, 2, 1)
        layout.addWidget(self.order_label, 0, 1)
        layout.addWidget(self.score_label, 0, 2)
        layout.addWidget(self.bar, 1, 1, 1, 2)
        self.set_data("", "", 100)

    def set_data(self, rank, order, percentage, current=False):
        self.order = order
        self.rank_label.setText(rank)
        self.order_label.setText(order.upper() if order else "-")
        self.score_label.setText("%s%%" % percentage if order else "-")
        self.bar.setValue(max(0, min(100, 100 - int(percentage))))

        if rank == "Best":
            fill = "#91c79f"
        elif rank == "Good":
            fill = "#c0bd7c"
        elif rank == "OK":
            fill = "#c99b6d"
        else:
            fill = "#b86f6f"

        border = "#d8d8d8" if current else "#4b4b4b"
        self.setStyleSheet(
            """
            QFrame {{
                background: #3d3d3d;
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: #cfcfcf;
            }}
            QProgressBar {{
                background: #292929;
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {fill};
                border-radius: 2px;
            }}
            """.format(border=border, fill=fill)
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.order:
            self.clicked.emit(self.order)
        super().mousePressEvent(event)
