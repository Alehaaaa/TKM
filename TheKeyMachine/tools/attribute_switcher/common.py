from TheKeyMachine.data import icons
from TheKeyMachine.tools import colors as toolColors


ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE = "attribute_switcher_window"
ATTRIBUTE_SWITCHER_GEOMETRY_KEY = "attribute_switcher_geometry"
ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY = "attribute_switcher_stays_on_top"


UI_COLOR = toolColors.UI_COLORS
ACCENT_DARK_COLOR = toolColors.get_selection_set_color("_12")
ACCENT_MAIN_COLOR = toolColors.get_selection_set_color("_11")
ACCENT_LIGHT_COLOR = toolColors.get_selection_set_color("_10")

COLOR_BG_MAIN = UI_COLOR.dark_gray.hex
COLOR_BG_POPUP = UI_COLOR.gray.hex
COLOR_BG_TRACK = UI_COLOR.darker_gray.hex
COLOR_ACCENT_DARK = ACCENT_DARK_COLOR.base.hex
COLOR_ACCENT_MAIN = ACCENT_MAIN_COLOR.base.hex
COLOR_ACCENT_LIGHT = ACCENT_LIGHT_COLOR.base.hex
COLOR_ACCENT_HOVER = ACCENT_MAIN_COLOR.hover.hex
COLOR_ACCENT_WHITE = ACCENT_LIGHT_COLOR.hover.hex
COLOR_TEXT_MAIN = UI_COLOR.darker_gray.hex
COLOR_TEXT_SECONDARY = UI_COLOR.dark_white.hex
COLOR_BLEND_MULTI = ACCENT_DARK_COLOR.hover.hex

ATTRIBUTE_SWITCHER_GLOBE_IMAGE = icons.globe
