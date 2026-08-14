"""Canonical toolbar display modes shared by every toolbar surface."""

from TheKeyMachine.core.Qt import QtCore


ALIGN_LEFT = "Left"
ALIGN_CENTER = "Center"
ALIGN_RIGHT = "Right"
SINGLE_LINE = "Single Line"

DEFAULT_ALIGNMENT = ALIGN_CENTER
ALIGNMENT_NAMES = (ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT, SINGLE_LINE)

MAIN_ALIGNMENT_SETTING = "toolbar_icon_alignment"
GRAPH_ALIGNMENT_SETTING = "graph_toolbar_alignment"
SINGLE_LINE_SCROLL_SETTING = "single_line_scroll_position"

_ALIGNMENT_VALUES = {
    ALIGN_LEFT: QtCore.Qt.AlignLeft,
    ALIGN_CENTER: QtCore.Qt.AlignHCenter,
    ALIGN_RIGHT: QtCore.Qt.AlignRight,
}

_TRANSLATION_SPECS = {
    ALIGN_LEFT: (
        "align_left_label",
        "Align Left",
        "align_left_desc",
        "Align toolbar icons to the left.",
    ),
    ALIGN_CENTER: (
        "align_center_label",
        "Align Center",
        "align_center_desc",
        "Align toolbar icons to the center.",
    ),
    ALIGN_RIGHT: (
        "align_right_label",
        "Align Right",
        "align_right_desc",
        "Align toolbar icons to the right.",
    ),
    SINGLE_LINE: (
        "align_single_line_label",
        "Single Line",
        "align_single_line_desc",
        "Keep every toolbar section on one horizontally scrollable line.",
    ),
}


def normalize(alignment_name):
    """Return a supported mode, falling back to the application default."""
    return alignment_name if alignment_name in ALIGNMENT_NAMES else DEFAULT_ALIGNMENT


def is_single_line(alignment_name):
    return normalize(alignment_name) == SINGLE_LINE


def alignment_value(alignment_name):
    """Return the Qt alignment used by the flow layout for *alignment_name*."""
    return _ALIGNMENT_VALUES.get(normalize(alignment_name), QtCore.Qt.AlignHCenter)


def apply_to(toolbar_widget, alignment_name):
    """Apply one display mode consistently to a live toolbar widget."""
    alignment_name = normalize(alignment_name)
    layout = toolbar_widget.layout() if toolbar_widget is not None else None
    if layout is None:
        return alignment_name

    single_line = is_single_line(alignment_name)
    if hasattr(toolbar_widget, "set_single_line"):
        toolbar_widget.set_single_line(single_line)
    elif hasattr(layout, "setSingleLine"):
        layout.setSingleLine(single_line)

    layout.setAlignment(alignment_value(alignment_name))
    layout.invalidate()
    toolbar_widget.updateGeometry()
    toolbar_widget.update()
    return alignment_name


def translated_options():
    """Return ``(value, label, description)`` rows in canonical menu order."""
    from TheKeyMachine.core import i18n

    options = []
    for value in ALIGNMENT_NAMES:
        label_key, label, description_key, description = _TRANSLATION_SPECS[value]
        label = i18n.localize_string(label_key, __file__, label)
        description = i18n.localize_string(description_key, __file__, description)
        options.append((value, label, description))
    return options


def translated_option(alignment_name):
    alignment_name = normalize(alignment_name)
    return next(option for option in translated_options() if option[0] == alignment_name)
