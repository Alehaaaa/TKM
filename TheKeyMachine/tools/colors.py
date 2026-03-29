from dataclasses import dataclass


@dataclass(frozen=True)
class ColorValue:
    name: str
    hex: str


@dataclass
class SelectionSetColor:
    suffix: str
    label: str
    family: str
    shade: str
    order: int
    base: ColorValue
    hover: ColorValue
    text: ColorValue
    family_ref: "ColorFamily | None" = None

    @property
    def index(self):
        return self.order


@dataclass
class ColorFamily:
    name: str
    light: SelectionSetColor
    base: SelectionSetColor
    dark: SelectionSetColor

    def __iter__(self):
        yield self.light
        yield self.base
        yield self.dark


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


@dataclass
class ColorRegistry:
    ui: UiPalette
    selection_sets: tuple[SelectionSetColor, ...]
    by_suffix: dict[str, SelectionSetColor]
    families: dict[str, ColorFamily]
    default_selection_set: SelectionSetColor

    def get(self, suffix, fallback=None):
        return self.by_suffix.get(suffix, fallback or self.default_selection_set)

    def get_variant(self, selection_color, shade, fallback=None):
        family_name = getattr(selection_color, "family", None)
        if not family_name:
            return fallback
        family = self.families.get(family_name)
        if not family:
            return fallback
        return getattr(family, shade, fallback)


def _color(name, hex_value):
    return ColorValue(name, hex_value)


def _make_ui_palette():
    return UiPalette(
        gray=_color("gray", "#5A5A5A"),
        dark_gray=_color("dark_gray", "#3C3C3C"),
        darker_gray=_color("darker_gray", "#333333"),
        light_gray=_color("light_gray", "#A0A0A0"),
        white=_color("white", "#e9edf2"),
        dark_white=_color("dark_white", "#cfd6df"),
        cyan=_color("cyan", "#58e1ff"),
        orange=_color("orange", "#C9844B"),
        yellow=_color("yellow", "#d4d361"),
        green=_color("green", "#4fb697"),
        blue=_color("blue", "#58e1ff"),
        red=_color("red", "#AD4D4E"),
        purple=_color("purple", "#8190B8"),
    )


SELECTION_SET_ROWS = (
    ("_25", "Gray Light", "gray", "light", 1, "#A0A0A0", "#AEAEAE", "#1a1a1a"),
    ("_26", "Gray", "gray", "base", 2, "#5A5A5A", "#696969", "#e9edf2"),
    ("_27", "Gray Dark", "gray", "dark", 3, "#333333", "#404040", "#cfd6df"),
    ("_01", "Red Light", "red", "light", 4, "#DDA6A1", "#E4B4AF", "#1a1a1a"),
    ("_02", "Red", "red", "base", 5, "#C96B68", "#D57E7A", "#1a1a1a"),
    ("_03", "Red Dark", "red", "dark", 6, "#7E3D3C", "#8E4A49", "#DDA6A1"),
    ("_04", "Orange Light", "orange", "light", 7, "#DDB78F", "#E3C39F", "#1a1a1a"),
    ("_05", "Orange", "orange", "base", 8, "#C98E57", "#D59C6B", "#1a1a1a"),
    ("_06", "Orange Dark", "orange", "dark", 9, "#7E5738", "#8F6644", "#DDB78F"),
    ("_07", "Yellow Light", "yellow", "light", 10, "#DED595", "#E4DCAA", "#1a1a1a"),
    ("_08", "Yellow", "yellow", "base", 11, "#CFC06B", "#D8CA7E", "#1a1a1a"),
    ("_09", "Yellow Dark", "yellow", "dark", 12, "#80723E", "#90824A", "#DED595"),
    ("_10", "Green Light", "green", "light", 13, "#A3C4B7", "#B0CDC1", "#1a1a1a"),
    ("_11", "Green", "green", "base", 14, "#689D85", "#78AA94", "#1a1a1a"),
    ("_12", "Green Dark", "green", "dark", 15, "#3B5F50", "#486C5D", "#A3C4B7"),
    ("_13", "Blue Light", "blue", "light", 16, "#9DBBD2", "#AAC6DB", "#1a1a1a"),
    ("_14", "Blue", "blue", "base", 17, "#668DAF", "#7799B8", "#1a1a1a"),
    ("_15", "Blue Dark", "blue", "dark", 18, "#3A536D", "#476179", "#9DBBD2"),
    ("_16", "Teal Light", "teal", "light", 19, "#9BC2BC", "#ABCDC8", "#1a1a1a"),
    ("_17", "Teal", "teal", "base", 20, "#5F9E94", "#70AAA1", "#1a1a1a"),
    ("_18", "Teal Dark", "teal", "dark", 21, "#35635D", "#43706A", "#9BC2BC"),
    ("_19", "Purple Light", "purple", "light", 22, "#BAA4C8", "#C4B3D0", "#1a1a1a"),
    ("_20", "Purple", "purple", "base", 23, "#8C6D9F", "#9A7DAB", "#1a1a1a"),
    ("_21", "Purple Dark", "purple", "dark", 24, "#533F61", "#644D73", "#BAA4C8"),
    ("_22", "Pink Light", "pink", "light", 25, "#D5A6B7", "#DCB6C4", "#1a1a1a"),
    ("_23", "Pink", "pink", "base", 26, "#B8718D", "#C3839B", "#1a1a1a"),
    ("_24", "Pink Dark", "pink", "dark", 27, "#6F4155", "#7D4E61", "#D5A6B7"),
)


def _make_selection_color(suffix, label, family, shade, order, base_hex, hover_hex, text_hex):
    key = family if shade == "base" else f"{family}_{shade}"
    return SelectionSetColor(
        suffix=suffix,
        label=label,
        family=family,
        shade=shade,
        order=order,
        base=_color(key, base_hex),
        hover=_color(f"{key}_hover", hover_hex),
        text=_color(f"{key}_text", text_hex),
    )


def _build_registry():
    ui = _make_ui_palette()
    selection_sets = tuple(_make_selection_color(*row) for row in SELECTION_SET_ROWS)
    by_suffix = {item.suffix: item for item in selection_sets}

    grouped = {}
    for item in selection_sets:
        grouped.setdefault(item.family, {})[item.shade] = item

    families = {}
    for family_name, shades in grouped.items():
        family = ColorFamily(
            name=family_name,
            light=shades["light"],
            base=shades["base"],
            dark=shades["dark"],
        )
        families[family_name] = family
        family.light.family_ref = family
        family.base.family_ref = family
        family.dark.family_ref = family

    return ColorRegistry(
        ui=ui,
        selection_sets=selection_sets,
        by_suffix=by_suffix,
        families=families,
        default_selection_set=by_suffix["_02"],
    )


COLORS = _build_registry()

UI_COLORS = COLORS.ui
SELECTION_SET_COLORS = COLORS.selection_sets
SELECTION_SET_COLOR_BY_SUFFIX = COLORS.by_suffix
SELECTION_SET_DEFAULT_COLOR = COLORS.default_selection_set
SELECTION_SET_COLORS_BY_FAMILY = COLORS.families


gray_light = SELECTION_SET_COLOR_BY_SUFFIX["_25"]
gray = SELECTION_SET_COLOR_BY_SUFFIX["_26"]
gray_dark = SELECTION_SET_COLOR_BY_SUFFIX["_27"]
red_light = SELECTION_SET_COLOR_BY_SUFFIX["_01"]
red = SELECTION_SET_COLOR_BY_SUFFIX["_02"]
red_dark = SELECTION_SET_COLOR_BY_SUFFIX["_03"]
orange_light = SELECTION_SET_COLOR_BY_SUFFIX["_04"]
orange = SELECTION_SET_COLOR_BY_SUFFIX["_05"]
orange_dark = SELECTION_SET_COLOR_BY_SUFFIX["_06"]
yellow_light = SELECTION_SET_COLOR_BY_SUFFIX["_07"]
yellow = SELECTION_SET_COLOR_BY_SUFFIX["_08"]
yellow_dark = SELECTION_SET_COLOR_BY_SUFFIX["_09"]
green_light = SELECTION_SET_COLOR_BY_SUFFIX["_10"]
green = SELECTION_SET_COLOR_BY_SUFFIX["_11"]
green_dark = SELECTION_SET_COLOR_BY_SUFFIX["_12"]
blue_light = SELECTION_SET_COLOR_BY_SUFFIX["_13"]
blue = SELECTION_SET_COLOR_BY_SUFFIX["_14"]
blue_dark = SELECTION_SET_COLOR_BY_SUFFIX["_15"]
teal_light = SELECTION_SET_COLOR_BY_SUFFIX["_16"]
teal = SELECTION_SET_COLOR_BY_SUFFIX["_17"]
teal_dark = SELECTION_SET_COLOR_BY_SUFFIX["_18"]
purple_light = SELECTION_SET_COLOR_BY_SUFFIX["_19"]
purple = SELECTION_SET_COLOR_BY_SUFFIX["_20"]
purple_dark = SELECTION_SET_COLOR_BY_SUFFIX["_21"]
pink_light = SELECTION_SET_COLOR_BY_SUFFIX["_22"]
pink = SELECTION_SET_COLOR_BY_SUFFIX["_23"]
pink_dark = SELECTION_SET_COLOR_BY_SUFFIX["_24"]


def get_selection_set_color(suffix, fallback=None):
    return COLORS.get(suffix, fallback=fallback)


def get_selection_set_variant(selection_color, shade, fallback=None):
    return COLORS.get_variant(selection_color, shade, fallback=fallback)


class _ColorNamespace:
    pass


color = _ColorNamespace()
for family_name, family in SELECTION_SET_COLORS_BY_FAMILY.items():
    setattr(color, family_name, family)
