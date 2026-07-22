"""Developer-only actions exposed by the TKM Debug menu.

Set ``TKM_TOOL_DEBUG=true`` in ``TheKeyMachine/.env`` (or in the process
environment) to show the menu. The committed fallback is always off.
"""

import os
import shutil
import xml.etree.ElementTree as ElementTree

from TheKeyMachine.data.colors import COLORS


TOOL_DEBUG = False
_ENV_NAME = "TKM_TOOL_DEBUG"
_TRUE_VALUES = frozenset(("1", "true", "yes", "on"))
_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
_FONT_PATH = os.path.join(os.path.dirname(__file__), "debug", "Stockholm_Mono.ttf")
_FONT_FAMILY = None
_SLIDER_BUTTON_CANVAS_SIZE = 50.0
_SLIDER_BUTTON_BORDER_WIDTH = 4.0
_SLIDER_BUTTON_STANDARD_SIZE = 12.3958
_SLIDER_BUTTON_SIZES = {
    "small": 4.375,
    "big": _SLIDER_BUTTON_STANDARD_SIZE,
    "frame": _SLIDER_BUTTON_STANDARD_SIZE,
}
_TRASH_ICON_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "data", "icons", "trash.svg")
)


def _dotenv_value():
    dotenv_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, ".env")
    )
    try:
        with open(dotenv_path, "r", encoding="utf-8") as stream:
            for raw_line in stream:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == _ENV_NAME:
                    return value.strip().strip('"\'')
    except OSError:
        pass
    return None


def is_enabled():
    """Read the process environment, then .env, then the off fallback."""
    value = os.environ.get(_ENV_NAME)
    if value is None:
        value = _dotenv_value()
    if value is None:
        return TOOL_DEBUG
    return str(value).strip().lower() in _TRUE_VALUES


def print_debug_summary(*_args):
    """Print a small runtime summary to Maya's Script Editor."""
    from maya import cmds

    from TheKeyMachine.core import toolbar

    instance = toolbar.get_toolbar()
    summary = {
        "maya_version": cmds.about(version=True),
        "toolbar_loaded": instance is not None,
        "toolbar_visible": bool(instance and instance.isVisible()),
        "tool_debug": is_enabled(),
    }
    print("TheKeyMachine debug: {}".format(summary))
    return summary


def _flatten_svg_paths(output_path):
    """Move Qt's grouped outline/fill paths directly under the SVG root."""
    ElementTree.register_namespace("", _SVG_NAMESPACE)
    tree = ElementTree.parse(output_path)
    root = tree.getroot()
    flattened = []

    def collect(element, inherited=None):
        attributes = dict(inherited or {})
        attributes.update(element.attrib)
        for child in element:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "path":
                path_attributes = dict(attributes)
                path_attributes.update(child.attrib)
                flattened.append(ElementTree.Element(child.tag, path_attributes))
            elif tag == "g":
                collect(child, attributes)

    for child in list(root):
        if child.tag.rsplit("}", 1)[-1] == "g":
            collect(child)
            root.remove(child)
    root.extend(flattened)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)


def _slider_icon_font(QtGui, pixel_size):
    """Load the configured local font, with a system-font fallback."""
    global _FONT_FAMILY

    if _FONT_FAMILY is None:
        font_id = QtGui.QFontDatabase.addApplicationFont(_FONT_PATH)
        families = (
            QtGui.QFontDatabase.applicationFontFamilies(font_id)
            if font_id >= 0
            else ()
        )
        _FONT_FAMILY = families[0] if families else ""

    font = QtGui.QFont(_FONT_FAMILY) if _FONT_FAMILY else QtGui.QFont()
    font.setPixelSize(pixel_size)
    return font


def _slider_text_path(QtGui, text, size):
    """Build and center a validated text path for one slider icon."""
    font = _slider_icon_font(QtGui, int(size * 0.68))
    path = QtGui.QPainterPath()
    path.addText(0, 0, font, str(text))
    bounds = path.boundingRect()
    if path.isEmpty() or bounds.isEmpty():
        return None

    maximum_width = size * 0.92
    if bounds.width() > maximum_width:
        font.setPixelSize(
            max(1, int(font.pixelSize() * maximum_width / bounds.width()))
        )
        path = QtGui.QPainterPath()
        path.addText(0, 0, font, str(text))
        bounds = path.boundingRect()
        if path.isEmpty() or bounds.isEmpty():
            return None

    path.translate(
        (size - bounds.width()) / 2.0 - bounds.left(),
        (size - bounds.height()) / 2.0 - bounds.top(),
    )
    return path


def _render_slider_text_icon(text, color, output_path, size=50):
    """Render one slider's text mark as a scalable SVG."""
    from TheKeyMachine.core.Qt import QtCore, QtGui, QtSvg

    path = _slider_text_path(QtGui, text, size)
    if path is None:
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    generator = QtSvg.QSvgGenerator()
    generator.setFileName(output_path)
    generator.setSize(QtCore.QSize(size, size))
    generator.setViewBox(QtCore.QRect(0, 0, size, size))
    generator.setTitle("TheKeyMachine slider icon")
    generator.setDescription("Vector slider text icon")

    painter = QtGui.QPainter(generator)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(
        QtGui.QPen(
            QtGui.QColor(COLORS.ui.dark_gray.hex),
            4.0,
            QtCore.Qt.SolidLine,
            QtCore.Qt.RoundCap,
            QtCore.Qt.RoundJoin,
        )
    )
    painter.drawPath(path)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    painter.drawPath(path)
    painter.end()
    _flatten_svg_paths(output_path)
    return os.path.isfile(output_path) and os.path.getsize(output_path) > 0


def _write_slider_button_icon(color, output_path, variant):
    """Write one flattened square icon matching the slider button proportions."""
    square_size = _SLIDER_BUTTON_SIZES.get(variant)
    if square_size is None:
        return False
    ElementTree.register_namespace("", _SVG_NAMESPACE)
    canvas_size = _SLIDER_BUTTON_CANVAS_SIZE
    square_origin = (canvas_size - square_size) / 2.0
    border_width = _SLIDER_BUTTON_BORDER_WIDTH
    border_origin = square_origin - (border_width / 2.0)
    border_size = square_size + border_width
    canvas_text = "{:g}".format(canvas_size)
    root = ElementTree.Element(
        "{{{}}}svg".format(_SVG_NAMESPACE),
        {
            "width": canvas_text,
            "height": canvas_text,
            "viewBox": "0 0 {0} {0}".format(canvas_text),
            "version": "1.1",
        },
    )
    ElementTree.SubElement(
        root,
        "{{{}}}rect".format(_SVG_NAMESPACE),
        {
            "x": "{:.4f}".format(border_origin),
            "y": "{:.4f}".format(border_origin),
            "width": "{:.4f}".format(border_size),
            "height": "{:.4f}".format(border_size),
            "fill": COLORS.ui.dark_gray.hex,
        },
    )
    ElementTree.SubElement(
        root,
        "{{{}}}rect".format(_SVG_NAMESPACE),
        {
            "x": "{:.4f}".format(square_origin),
            "y": "{:.4f}".format(square_origin),
            "width": "{:.4f}".format(square_size),
            "height": "{:.4f}".format(square_size),
            "fill": color,
        },
    )
    ElementTree.ElementTree(root).write(
        output_path,
        encoding="UTF-8",
        xml_declaration=True,
    )
    return os.path.isfile(output_path) and os.path.getsize(output_path) > 0


def _slider_button_icon_name(slider_type, variant):
    """Return the extensionless shared asset name for one slider type."""
    if not slider_type or variant not in _SLIDER_BUTTON_SIZES:
        return None
    return "slider_{}/square_{}".format(slider_type, variant)


def _clear_slider_button_icons(icons_dir, variants):
    """Remove old shared and per-mode button assets from one slider type."""
    shared_names = {"square_{}.svg".format(variant) for variant in variants}
    per_mode_suffixes = tuple(
        "_square_{}.svg".format(variant) for variant in variants
    )
    for filename in os.listdir(icons_dir):
        lower_name = filename.lower()
        if lower_name in shared_names or lower_name.endswith(per_mode_suffixes):
            os.remove(os.path.join(icons_dir, filename))


def _refresh_live_slider_icons():
    """Clear Qt image caches and refresh every live slider presentation."""
    from TheKeyMachine.core.Qt import QtGui, QtWidgets
    from TheKeyMachine.widgets.sliderWidget import QFlatSliderWidget

    QtGui.QPixmapCache.clear()
    application = QtWidgets.QApplication.instance()
    if application is None or not hasattr(application, "allWidgets"):
        return 0

    refreshed = 0
    for widget in application.allWidgets():
        if isinstance(widget, QFlatSliderWidget):
            widget.refreshModePresentation()
            refreshed += 1
    return refreshed


def _write_selection_set_icon(color, output_path, trash=False):
    """Write one selection-set SVG using a canonical selection color."""
    ElementTree.register_namespace("", _SVG_NAMESPACE)
    fill = color.hex.lower()
    if trash:
        tree = ElementTree.parse(_TRASH_ICON_PATH)
        root = tree.getroot()
        root.text = None
        for element in root.iter():
            element.tail = None
            tag = element.tag.rsplit("}", 1)[-1]
            if tag in {"path", "rect", "circle", "ellipse", "polygon", "polyline"}:
                element.attrib.pop("class", None)
                element.set("fill", fill)
        for child in list(root):
            if child.tag.rsplit("}", 1)[-1] == "defs":
                root.remove(child)
        tree.write(output_path, encoding="UTF-8", xml_declaration=True)
        return os.path.isfile(output_path) and os.path.getsize(output_path) > 0

    size = 50
    root = ElementTree.Element(
        "{{{}}}svg".format(_SVG_NAMESPACE),
        {
            "width": str(size),
            "height": str(size),
            "viewBox": "0 0 {0} {0}".format(size),
            "version": "1.1",
        },
    )
    ElementTree.SubElement(
        root,
        "{{{}}}rect".format(_SVG_NAMESPACE),
        {
            "x": "0",
            "y": "0",
            "width": str(size),
            "height": str(size),
            "ry": "11.43",
            "fill": fill,
        },
    )
    ElementTree.ElementTree(root).write(output_path, encoding="UTF-8", xml_declaration=True)
    return os.path.isfile(output_path) and os.path.getsize(output_path) > 0


def _refresh_visible_icons():
    """Clear Qt's image cache and repaint existing widgets."""
    from TheKeyMachine.core.Qt import QtGui, QtWidgets

    QtGui.QPixmapCache.clear()
    application = QtWidgets.QApplication.instance()
    if application is None or not hasattr(application, "allWidgets"):
        return 0
    widgets = application.allWidgets()
    for widget in widgets:
        widget.update()
    return len(widgets)


def export_selection_set_icons(*_args):
    """Replace all selection-set color and trash icons from the color registry."""
    from maya import cmds

    from TheKeyMachine.data import icons

    output_dir = icons.SELECTION_SETS_ROOT
    try:
        if os.path.isdir(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
    except OSError as error:
        cmds.warning("Selection-set icons could not be exported: {}".format(error))
        return []

    exported = []
    failed = []
    for color in COLORS.selection.all:
        filename = icons.selection_set_icon_filename(color)
        paths = (
            (os.path.join(output_dir, filename), False),
            (os.path.join(output_dir, filename.replace(".svg", "_trash.svg")), True),
        )
        for output_path, trash in paths:
            try:
                success = _write_selection_set_icon(color, output_path, trash=trash)
            except OSError:
                success = False
            (exported if success else failed).append(output_path)

    refreshed = _refresh_visible_icons()
    message = "Exported {} selection-set icons and refreshed {} widgets".format(len(exported), refreshed)
    if failed:
        cmds.warning("{}; {} failed: {}".format(message, len(failed), ", ".join(failed)))
    else:
        print("TheKeyMachine debug: {}.".format(message))
    return exported


def export_slider_text_icons(*_args):
    """Replace each text-slider namespace with fresh SVG exports."""
    from maya import cmds

    from TheKeyMachine.core import toolbox
    from TheKeyMachine.data import icons

    exported = []
    failed = []
    for section in toolbox.get_section_definitions().values():
        if section.get("type") != "slider":
            continue

        slider_type = section.get("slider_type")
        if not slider_type:
            continue
        text_modes = [
            mode
            for mode in section.get("modes") or ()
            if getattr(mode, "text", "")
        ]
        if not text_modes:
            continue

        icons_dir = os.path.join(icons.IMAGE_ROOT, "slider_{}".format(slider_type))
        icon_color = section.get("icon_color") or section.get("color") or "#ffffff"
        try:
            os.makedirs(icons_dir, exist_ok=True)
        except OSError:
            failed.append(icons_dir)
            continue

        for mode in text_modes:
            output_path = os.path.join(icons_dir, "{}.svg".format(mode.key))
            if _render_slider_text_icon(mode.text, icon_color, output_path):
                exported.append(output_path)
            else:
                failed.append(output_path)

    refreshed = _refresh_live_slider_icons()
    message = "Exported {} slider text icon{} and refreshed {} slider{}".format(
        len(exported),
        "" if len(exported) == 1 else "s",
        refreshed,
        "" if refreshed == 1 else "s",
    )
    if failed:
        message += "; {} failed".format(len(failed))
        cmds.warning("{}: {}".format(message, ", ".join(failed)))
    else:
        print("TheKeyMachine debug: {}.".format(message))
    return exported


def export_slider_button_icons(*_args):
    """Export one shared square-button asset set per slider type."""
    from maya import cmds

    from TheKeyMachine.core import toolbox
    from TheKeyMachine.data import icons
    from TheKeyMachine.widgets.sliderWidget import SLIDER_FRAME_BUTTON_COLOR

    exported = []
    failed = []
    for section in toolbox.get_section_definitions().values():
        if section.get("type") != "slider":
            continue

        slider_type = section.get("slider_type")
        if not slider_type:
            continue
        modes = [mode for mode in section.get("modes") or () if hasattr(mode, "key")]
        if not modes:
            continue

        icons_dir = os.path.join(icons.IMAGE_ROOT, "slider_{}".format(slider_type))
        try:
            os.makedirs(icons_dir, exist_ok=True)
            _clear_slider_button_icons(
                icons_dir,
                tuple(_SLIDER_BUTTON_SIZES),
            )
        except OSError:
            failed.append(icons_dir)
            continue

        colored = section.get("color") or "#ffffff"
        variants = ["small", "big"]
        if any(getattr(mode, "frame_buttons", False) for mode in modes):
            variants.append("frame")

        for variant in variants:
            asset_name = _slider_button_icon_name(slider_type, variant)
            output_path = os.path.join(
                icons.IMAGE_ROOT,
                "{}.svg".format(asset_name),
            )
            color = SLIDER_FRAME_BUTTON_COLOR if variant == "frame" else colored
            try:
                success = _write_slider_button_icon(
                    color,
                    output_path,
                    variant,
                )
            except OSError:
                success = False
            (exported if success else failed).append(output_path)

    refreshed = _refresh_live_slider_icons()
    message = "Exported {} slider button icon{} and refreshed {} slider{}".format(
        len(exported),
        "" if len(exported) == 1 else "s",
        refreshed,
        "" if refreshed == 1 else "s",
    )
    if failed:
        message += "; {} failed".format(len(failed))
        cmds.warning("{}: {}".format(message, ", ".join(failed)))
    else:
        print("TheKeyMachine debug: {}.".format(message))
    return exported


# Dictionary order is the menu order. Add developer actions here; every callback
# must be callable and live in this module so reloading debug refreshes it.
DEBUG_ACTIONS = {
    "Print Debug Summary": print_debug_summary,
    "Export Slider Text Icons": export_slider_text_icons,
    "Export Slider Button Icons": export_slider_button_icons,
    "Export Selection Set Icons": export_selection_set_icons,
}


def populate_menu(menu):
    """Rebuild ``menu`` from the current action routing dictionary."""
    menu.clear()
    for label, callback in DEBUG_ACTIONS.items():
        if callable(callback):
            menu.addAction(label, callback=callback)
    if not menu.actions():
        action = menu.addAction("No debug actions")
        action.setEnabled(False)
    return menu
