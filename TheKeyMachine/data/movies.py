"""Movie path helpers and tooltip movie widgets."""

from __future__ import annotations

import os

from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets  # type: ignore

QWidget = QtWidgets.QWidget
QLabel = QtWidgets.QLabel
QFrame = QtWidgets.QFrame
QVBoxLayout = QtWidgets.QVBoxLayout
QPainterPath = QtGui.QPainterPath
QRegion = QtGui.QRegion
Qt = QtCore.Qt
QRectF = QtCore.QRectF

from TheKeyMachine.mods.generalMod import config
from TheKeyMachine.widgets import util as wutil


INSTALL_PATH = config["INSTALL_PATH"]
MOVIE_ROOT = os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "movies")


class TooltipMedia:
    def __init__(self, path):
        self.path = str(path)


class TooltipMovieLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._movie = None
        self._display_size = None
        self.setAlignment(Qt.AlignCenter)

    def set_tooltip_movie(self, movie, display_size=None):
        self._movie = movie
        self._display_size = display_size if display_size and display_size.isValid() else None
        if self._display_size is not None:
            self.setFixedSize(self._display_size)
        elif movie is not None:
            frame_rect = movie.frameRect()
            if frame_rect.isValid():
                self.setFixedSize(frame_rect.size())
        if movie is not None:
            movie.frameChanged.connect(self._update_frame)
            self._update_frame()

    def _update_frame(self, *_):
        if self._movie is None:
            return
        frame = self._movie.currentPixmap()
        if frame.isNull():
            return
        if self._display_size is not None and frame.size() != self._display_size:
            frame = frame.scaled(self._display_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(frame)


class TooltipMovieWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._movie = None
        self._display_size = None
        self._corner_radius = wutil.DPI(10)

        self._movie_label = TooltipMovieLabel(self)
        self._progress_track = QFrame(self._movie_label)
        self._progress_fill = QFrame(self._progress_track)

        self.setObjectName("tooltip_movie_widget")
        self.setStyleSheet(
            "#tooltip_movie_widget { background: transparent; border: none; border-radius: %dpx; }" % self._corner_radius
        )
        self._movie_label.setStyleSheet("background: transparent; border: none;")
        self._progress_track.setStyleSheet("background: transparent; border: none;")
        self._progress_fill.setStyleSheet("background-color: rgba(192, 192, 192, 0.5); border: none;")
        self._progress_track.setFixedHeight(wutil.DPI(2))
        self._progress_fill.setFixedHeight(wutil.DPI(2))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._movie_label)

    def set_tooltip_movie(self, movie, display_size=None):
        self._movie = movie
        self._display_size = display_size if display_size and display_size.isValid() else None
        self._movie_label.set_tooltip_movie(movie, display_size=display_size)
        if self._display_size is not None:
            self.setFixedWidth(self._display_size.width())
        else:
            self.setMinimumWidth(self._movie_label.width())
        if movie is not None:
            movie.frameChanged.connect(self._update_progress)
            self._update_progress()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_rounded_mask()
        self._layout_overlay()
        self._update_progress()

    def _apply_rounded_mask(self):
        rect = self.rect()
        if not rect.isValid():
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), self._corner_radius, self._corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
        self._movie_label.setMask(region.translated(-self._movie_label.x(), -self._movie_label.y()))

    def _layout_overlay(self):
        track_height = self._progress_track.height()
        self._progress_track.setGeometry(
            0,
            max(0, self._movie_label.height() - track_height),
            self._movie_label.width(),
            track_height,
        )
        self._progress_track.raise_()
        self._progress_fill.raise_()

    def _update_progress(self, *_):
        if self._movie is None:
            self._progress_fill.setFixedWidth(0)
            return

        track_width = max(0, self._progress_track.width())
        if track_width <= 0:
            self._progress_fill.setFixedWidth(0)
            return

        frame_count = self._movie.frameCount()
        current_frame = self._movie.currentFrameNumber()
        if frame_count and frame_count > 1 and current_frame >= 0:
            progress = float(current_frame) / float(frame_count - 1)
        else:
            progress = 0.0
        fill_width = max(0, min(track_width, int(round(track_width * progress))))
        self._progress_fill.setGeometry(0, 0, fill_width, self._progress_track.height())


def path(filename: str | None, default=None):
    if not filename:
        return default
    return os.path.join(MOVIE_ROOT, filename)


def get_path(name: str, default=None):
    filename = name if os.path.splitext(name)[1] else "{}.gif".format(name)
    resolved = path(filename)
    return resolved if os.path.exists(resolved) else default


def get(name: str, default=None):
    resolved = get_path(name)
    return TooltipMedia(resolved) if resolved else default


def __getattr__(name):
    return get(name)
