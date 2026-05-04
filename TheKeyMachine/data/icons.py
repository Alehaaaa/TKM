"""
Runtime icon lookup.

The attribute name is the asset name:

    icons.bug               -> data/icons/bug.svg
    icons.sliders_overshoot -> data/icons/sliders_overshoot.svg

Missing icons return ``None``.
"""

from __future__ import annotations

import os

try:
    from PySide6 import QtCore, QtGui  # type: ignore
except ImportError:
    from PySide2 import QtCore, QtGui  # type: ignore

import TheKeyMachine.tools.colors as toolColors
from TheKeyMachine.mods.generalMod import config


INSTALL_PATH = config["INSTALL_PATH"]
IMAGE_ROOT = os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "icons")
SELECTION_SETS_ROOT = os.path.join(IMAGE_ROOT, "selection_sets")
ICON_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg")


class QHoverableIcon:
    HIGHLIGHT_HEX = "#282828"

    @staticmethod
    def apply(btn, icon, highlight=False, brighten_amount=80):
        if not icon:
            return

        base_icon = QtGui.QIcon(icon)
        icon_size = btn.iconSize()

        if highlight:
            btn._icon_normal = QHoverableIcon.color_icon(base_icon, QHoverableIcon.HIGHLIGHT_HEX, icon_size)
        else:
            btn._icon_normal = base_icon

        btn._icon_hover = QHoverableIcon.hover_icon(btn._icon_normal, icon_size, brighten_amount)
        btn.setIcon(btn._icon_normal)

    @staticmethod
    def color_icon(icon: QtGui.QIcon, color: QtGui.QColor, size: QtCore.QSize) -> QtGui.QIcon:
        if isinstance(color, (str, bytes)):
            color = QtGui.QColor(color)

        pix = icon.pixmap(size)
        img = pix.toImage()
        for x in range(img.width()):
            for y in range(img.height()):
                c = img.pixelColor(x, y)
                if c.alpha() > 0:
                    img.setPixelColor(x, y, QtGui.QColor(color.red(), color.green(), color.blue(), c.alpha()))

        return QtGui.QIcon(QtGui.QPixmap.fromImage(img))

    @staticmethod
    def hover_icon(icon: QtGui.QIcon, size: QtCore.QSize, brighten: int) -> QtGui.QIcon:
        pix = icon.pixmap(size)
        img = pix.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)

        bright_img = img.copy()
        for x in range(bright_img.width()):
            for y in range(bright_img.height()):
                c = bright_img.pixelColor(x, y)
                if c.alpha() > 0:
                    bright_img.setPixelColor(
                        x,
                        y,
                        QtGui.QColor(
                            min(c.red() + 40, 255),
                            min(c.green() + 40, 255),
                            min(c.blue() + 40, 255),
                            c.alpha(),
                        ),
                    )
        bright_pix = QtGui.QPixmap.fromImage(bright_img)

        out_pix = QtGui.QPixmap(size)
        out_pix.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(out_pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        glow_img = img.copy()
        for x in range(glow_img.width()):
            for y in range(glow_img.height()):
                c = glow_img.pixelColor(x, y)
                if c.alpha() > 0:
                    glow_img.setPixelColor(x, y, QtGui.QColor(255, 255, 255, 5))

        glow_pix = QtGui.QPixmap.fromImage(glow_img)
        for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
            painter.drawPixmap(dx, dy, glow_pix)

        painter.drawPixmap(0, 0, bright_pix)
        painter.end()

        return QtGui.QIcon(out_pix)


def path(filename: str | None, default=None):
    if not filename:
        return default
    return os.path.join(IMAGE_ROOT, filename)


def selection_set_path(filename: str | None, default=None):
    if not filename:
        return default
    return os.path.join(SELECTION_SETS_ROOT, filename)


def get(name: str | None, default=None):
    if not name:
        return default

    if os.path.splitext(name)[1]:
        candidate = path(name)
        return candidate if os.path.exists(candidate) else default

    for ext in ICON_EXTENSIONS:
        candidate = path("{}{}".format(name, ext))
        if os.path.exists(candidate):
            return candidate
    return default


def require(name: str) -> str:
    resolved = get(name)
    if resolved is None:
        raise AttributeError("Unknown icon: {}".format(name))
    return resolved


def exists(name: str) -> bool:
    return get(name) is not None


_selection_set_icon_shade_names = {
    "light": "Light",
    "base": "",
    "dark": "Dark",
}


def _selection_set_icon_filename(color):
    shade = _selection_set_icon_shade_names.get(color.shade, "")
    return "_{}{}_set.svg".format(color.family, shade)


selection_set_color_icon_names = {color.suffix: _selection_set_icon_filename(color) for color in toolColors.SELECTION_SET_COLORS}
selection_set_color_icons = {suffix: selection_set_path(filename) for suffix, filename in selection_set_color_icon_names.items()}
selection_set_color_trash_icons = {
    suffix: selection_set_path(filename.replace(".svg", "_trash.svg")) for suffix, filename in selection_set_color_icon_names.items()
}


def __getattr__(name):
    return get(name)
