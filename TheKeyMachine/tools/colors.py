from dataclasses import dataclass


@dataclass(frozen=True)
class ColorValue:
    name: str
    hex: str


@dataclass(frozen=True)
class SelectionSetColor:
    suffix: str
    label: str
    base: ColorValue
    hover: ColorValue
    text: ColorValue
    family: str
    shade: str
    order: int


@dataclass(frozen=True)
class UiPalette:
    gray: ColorValue
    dark_gray: ColorValue
    darker_gray: ColorValue
    light_gray: ColorValue
    white: ColorValue
    dark_white: ColorValue
    cyan: ColorValue
    orange: ColorValue
    yellow: ColorValue
    green: ColorValue
    blue: ColorValue
    red: ColorValue
    purple: ColorValue

    @property
    def darkGray(self):
        return self.dark_gray

    @property
    def darkerGray(self):
        return self.darker_gray

    @property
    def lightGray(self):
        return self.light_gray

    @property
    def darkWhite(self):
        return self.dark_white


UI_COLORS = UiPalette(
    gray=ColorValue("gray", "#444444"),
    dark_gray=ColorValue("darkGray", "#3C3C3C"),
    darker_gray=ColorValue("darkerGray", "#333333"),
    light_gray=ColorValue("lightGray", "#747474"),
    white=ColorValue("white", "#e9edf2"),
    dark_white=ColorValue("darkWhite", "#cfd6df"),
    cyan=ColorValue("cyan", "#58e1ff"),
    orange=ColorValue("orange", "#C9844B"),
    yellow=ColorValue("yellow", "#d4d361"),
    green=ColorValue("green", "#4fb68d"),
    blue=ColorValue("blue", "#58e1ff"),
    red=ColorValue("red", "#AD4D4E"),
    purple=ColorValue("purple", "#8190B8"),
)


SELECTION_SET_COLORS = (
    SelectionSetColor("_01", "Red Light", ColorValue("red_light", "#DDA6A1"), ColorValue("red_light_hover", "#E4B4AF"), ColorValue("red_light_text", "#1a1a1a"), "red", "light", 1),
    SelectionSetColor("_02", "Red", ColorValue("red", "#C96B68"), ColorValue("red_hover", "#D57E7A"), ColorValue("red_text", "#1a1a1a"), "red", "base", 2),
    SelectionSetColor("_03", "Red Dark", ColorValue("red_dark", "#7E3D3C"), ColorValue("red_dark_hover", "#8E4A49"), ColorValue("red_dark_text", "#DDA6A1"), "red", "dark", 3),
    SelectionSetColor("_04", "Orange Light", ColorValue("orange_light", "#DDB78F"), ColorValue("orange_light_hover", "#E3C39F"), ColorValue("orange_light_text", "#1a1a1a"), "orange", "light", 4),
    SelectionSetColor("_05", "Orange", ColorValue("orange", "#C98E57"), ColorValue("orange_hover", "#D59C6B"), ColorValue("orange_text", "#1a1a1a"), "orange", "base", 5),
    SelectionSetColor("_06", "Orange Dark", ColorValue("orange_dark", "#7E5738"), ColorValue("orange_dark_hover", "#8F6644"), ColorValue("orange_dark_text", "#DDB78F"), "orange", "dark", 6),
    SelectionSetColor("_07", "Yellow Light", ColorValue("yellow_light", "#DED595"), ColorValue("yellow_light_hover", "#E4DCAA"), ColorValue("yellow_light_text", "#1a1a1a"), "yellow", "light", 7),
    SelectionSetColor("_08", "Yellow", ColorValue("yellow", "#CFC06B"), ColorValue("yellow_hover", "#D8CA7E"), ColorValue("yellow_text", "#1a1a1a"), "yellow", "base", 8),
    SelectionSetColor("_09", "Yellow Dark", ColorValue("yellow_dark", "#80723E"), ColorValue("yellow_dark_hover", "#90824A"), ColorValue("yellow_dark_text", "#DED595"), "yellow", "dark", 9),
    SelectionSetColor("_10", "Green Light", ColorValue("green_light", "#A8C4A3"), ColorValue("green_light_hover", "#B3CCAF"), ColorValue("green_light_text", "#1a1a1a"), "green", "light", 10),
    SelectionSetColor("_11", "Green", ColorValue("green", "#6E9D68"), ColorValue("green_hover", "#7EAA79"), ColorValue("green_text", "#1a1a1a"), "green", "base", 11),
    SelectionSetColor("_12", "Green Dark", ColorValue("green_dark", "#3E5F3B"), ColorValue("green_dark_hover", "#4A6C46"), ColorValue("green_dark_text", "#A8C4A3"), "green", "dark", 12),
    SelectionSetColor("_13", "Blue Light", ColorValue("blue_light", "#9DBBD2"), ColorValue("blue_light_hover", "#AAC6DB"), ColorValue("blue_light_text", "#1a1a1a"), "blue", "light", 13),
    SelectionSetColor("_14", "Blue", ColorValue("blue", "#668DAF"), ColorValue("blue_hover", "#7799B8"), ColorValue("blue_text", "#1a1a1a"), "blue", "base", 14),
    SelectionSetColor("_15", "Blue Dark", ColorValue("blue_dark", "#3A536D"), ColorValue("blue_dark_hover", "#476179"), ColorValue("blue_dark_text", "#9DBBD2"), "blue", "dark", 15),
    SelectionSetColor("_16", "Teal Light", ColorValue("teal_light", "#9BC2BC"), ColorValue("teal_light_hover", "#ABCDC8"), ColorValue("teal_light_text", "#1a1a1a"), "teal", "light", 16),
    SelectionSetColor("_17", "Teal", ColorValue("teal", "#5F9E94"), ColorValue("teal_hover", "#70AAA1"), ColorValue("teal_text", "#1a1a1a"), "teal", "base", 17),
    SelectionSetColor("_18", "Teal Dark", ColorValue("teal_dark", "#35635D"), ColorValue("teal_dark_hover", "#43706A"), ColorValue("teal_dark_text", "#9BC2BC"), "teal", "dark", 18),
    SelectionSetColor("_19", "Purple Light", ColorValue("purple_light", "#BAA4C8"), ColorValue("purple_light_hover", "#C4B3D0"), ColorValue("purple_light_text", "#1a1a1a"), "purple", "light", 19),
    SelectionSetColor("_20", "Purple", ColorValue("purple", "#8C6D9F"), ColorValue("purple_hover", "#9A7DAB"), ColorValue("purple_text", "#1a1a1a"), "purple", "base", 20),
    SelectionSetColor("_21", "Purple Dark", ColorValue("purple_dark", "#533F61"), ColorValue("purple_dark_hover", "#644D73"), ColorValue("purple_dark_text", "#BAA4C8"), "purple", "dark", 21),
    SelectionSetColor("_22", "Pink Light", ColorValue("pink_light", "#D5A6B7"), ColorValue("pink_light_hover", "#DCB6C4"), ColorValue("pink_light_text", "#1a1a1a"), "pink", "light", 22),
    SelectionSetColor("_23", "Pink", ColorValue("pink", "#B8718D"), ColorValue("pink_hover", "#C3839B"), ColorValue("pink_text", "#1a1a1a"), "pink", "base", 23),
    SelectionSetColor("_24", "Pink Dark", ColorValue("pink_dark", "#6F4155"), ColorValue("pink_dark_hover", "#7D4E61"), ColorValue("pink_dark_text", "#D5A6B7"), "pink", "dark", 24),
)

SELECTION_SET_COLOR_BY_SUFFIX = {color.suffix: color for color in SELECTION_SET_COLORS}
SELECTION_SET_DEFAULT_COLOR = SELECTION_SET_COLOR_BY_SUFFIX["_02"]


def get_selection_set_color(suffix, fallback=None):
    return SELECTION_SET_COLOR_BY_SUFFIX.get(suffix, fallback or SELECTION_SET_DEFAULT_COLOR)
