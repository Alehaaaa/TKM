"""Canonical color object graph shared across TheKeyMachine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    hex: str


class SelectionColor:
    def __init__(self, suffix, label, family, shade, order, base, hover, text):
        self.suffix = suffix
        self.label = label
        self.family = family
        self.shade = shade
        self.order = order
        self.hex = base
        self.hover = Color(hover)
        self.text = Color(text)
        self.main = None
        self.light = None
        self.dark = None

    @property
    def index(self):
        return self.order

@dataclass
class SelectionFamily:
    light: SelectionColor
    main: SelectionColor
    dark: SelectionColor

    def __post_init__(self):
        self.light.main = self.main
        self.light.light = self.light
        self.light.dark = self.dark
        self.main.main = self.main
        self.main.light = self.light
        self.main.dark = self.dark
        self.dark.main = self.main
        self.dark.light = self.light
        self.dark.dark = self.dark


class ColorGroup:
    def __init__(self, **colors):
        self.__dict__.update(colors)


class SelectionColors:
    _DEFAULT = object()

    def __init__(self, red, orange, yellow, green, blue, teal, purple, pink, gray):
        self.red = red.main
        self.orange = orange.main
        self.yellow = yellow.main
        self.green = green.main
        self.blue = blue.main
        self.teal = teal.main
        self.purple = purple.main
        self.pink = pink.main
        self.gray = gray.main

        self.all = (
            gray.light, gray.main, gray.dark,
            red.light, red.main, red.dark,
            orange.light, orange.main, orange.dark,
            yellow.light, yellow.main, yellow.dark,
            green.light, green.main, green.dark,
            blue.light, blue.main, blue.dark,
            teal.light, teal.main, teal.dark,
            purple.light, purple.main, purple.dark,
            pink.light, pink.main, pink.dark,
        )
        self.by_suffix = {
            "_01": red.light, "_02": red.main, "_03": red.dark,
            "_04": orange.light, "_05": orange.main, "_06": orange.dark,
            "_07": yellow.light, "_08": yellow.main, "_09": yellow.dark,
            "_10": green.light, "_11": green.main, "_12": green.dark,
            "_13": blue.light, "_14": blue.main, "_15": blue.dark,
            "_16": teal.light, "_17": teal.main, "_18": teal.dark,
            "_19": purple.light, "_20": purple.main, "_21": purple.dark,
            "_22": pink.light, "_23": pink.main, "_24": pink.dark,
            "_25": gray.light, "_26": gray.main, "_27": gray.dark,
        }
        self.families = {
            "red": red.main,
            "orange": orange.main,
            "yellow": yellow.main,
            "green": green.main,
            "blue": blue.main,
            "teal": teal.main,
            "purple": purple.main,
            "pink": pink.main,
            "gray": gray.main,
        }
        self.default = self.red

    def get(self, suffix, fallback=_DEFAULT):
        if fallback is self._DEFAULT:
            fallback = self.default
        return self.by_suffix.get(suffix, fallback)


@dataclass(frozen=True)
class ColorRegistry:
    ui: ColorGroup
    toolbar: ColorGroup
    selection: SelectionColors


COLORS = ColorRegistry(
    ui=ColorGroup(
        gray=Color("#5A5A5A"),
        dark_gray=Color("#3C3C3C"),
        darker_gray=Color("#333333"),
        darkest_gray=Color("#444444"),
        light_gray=Color("#A0A0A0"),
        white=Color("#e9edf2"),
        dark_white=Color("#cfd6df"),
        cyan=Color("#58e1ff"),
        orange=Color("#dd7466"),
        yellow=Color("#d4d361"),
        green=Color("#4fb697"),
        blue=Color("#58e1ff"),
        red=Color("#AD4D4E"),
        purple=Color("#8C6D9F"),
    ),
    toolbar=ColorGroup(
        gray=Color("#787878"),
        green=Color("#72DBB8"),
        yellow=Color("#DBDB72"),
        orange=Color("#DB8072"),
        red=Color("#DB7274"),
        purple=Color("#B172DB"),
        violet=Color("#9072DB"),
        cyan=Color("#72DBDB"),
        blue_teal=Color("#72C1DB"),
        light_gray=Color("#E0E0E0"),
    ),
    selection=SelectionColors(
        red=SelectionFamily(
            light=SelectionColor("_01", "Red Light", "red", "light", 4, "#DDA6A1", "#E4B4AF", "#1a1a1a"),
            main=SelectionColor("_02", "Red", "red", "base", 5, "#C96B68", "#D57E7A", "#1a1a1a"),
            dark=SelectionColor("_03", "Red Dark", "red", "dark", 6, "#7E3D3C", "#8E4A49", "#DDA6A1"),
        ),
        orange=SelectionFamily(
            light=SelectionColor("_04", "Orange Light", "orange", "light", 7, "#DDB78F", "#E3C39F", "#1a1a1a"),
            main=SelectionColor("_05", "Orange", "orange", "base", 8, "#C98E57", "#D59C6B", "#1a1a1a"),
            dark=SelectionColor("_06", "Orange Dark", "orange", "dark", 9, "#7E5738", "#8F6644", "#DDB78F"),
        ),
        yellow=SelectionFamily(
            light=SelectionColor("_07", "Yellow Light", "yellow", "light", 10, "#DED595", "#E4DCAA", "#1a1a1a"),
            main=SelectionColor("_08", "Yellow", "yellow", "base", 11, "#CFC06B", "#D8CA7E", "#1a1a1a"),
            dark=SelectionColor("_09", "Yellow Dark", "yellow", "dark", 12, "#80723E", "#90824A", "#DED595"),
        ),
        green=SelectionFamily(
            light=SelectionColor("_10", "Green Light", "green", "light", 13, "#A3C4B7", "#B0CDC1", "#1a1a1a"),
            main=SelectionColor("_11", "Green", "green", "base", 14, "#689D85", "#78AA94", "#1a1a1a"),
            dark=SelectionColor("_12", "Green Dark", "green", "dark", 15, "#3B5F50", "#486C5D", "#A3C4B7"),
        ),
        blue=SelectionFamily(
            light=SelectionColor("_13", "Blue Light", "blue", "light", 16, "#9DBBD2", "#AAC6DB", "#1a1a1a"),
            main=SelectionColor("_14", "Blue", "blue", "base", 17, "#668DAF", "#7799B8", "#1a1a1a"),
            dark=SelectionColor("_15", "Blue Dark", "blue", "dark", 18, "#3A536D", "#476179", "#9DBBD2"),
        ),
        teal=SelectionFamily(
            light=SelectionColor("_16", "Teal Light", "teal", "light", 19, "#9BC2BC", "#ABCDC8", "#1a1a1a"),
            main=SelectionColor("_17", "Teal", "teal", "base", 20, "#5F9E94", "#70AAA1", "#1a1a1a"),
            dark=SelectionColor("_18", "Teal Dark", "teal", "dark", 21, "#35635D", "#43706A", "#9BC2BC"),
        ),
        purple=SelectionFamily(
            light=SelectionColor("_19", "Purple Light", "purple", "light", 22, "#BAA4C8", "#C4B3D0", "#1a1a1a"),
            main=SelectionColor("_20", "Purple", "purple", "base", 23, "#8C6D9F", "#9A7DAB", "#1a1a1a"),
            dark=SelectionColor("_21", "Purple Dark", "purple", "dark", 24, "#533F61", "#644D73", "#BAA4C8"),
        ),
        pink=SelectionFamily(
            light=SelectionColor("_22", "Pink Light", "pink", "light", 25, "#D5A6B7", "#DCB6C4", "#1a1a1a"),
            main=SelectionColor("_23", "Pink", "pink", "base", 26, "#B8718D", "#C3839B", "#1a1a1a"),
            dark=SelectionColor("_24", "Pink Dark", "pink", "dark", 27, "#6F4155", "#7D4E61", "#D5A6B7"),
        ),
        gray=SelectionFamily(
            light=SelectionColor("_25", "Gray Light", "gray", "light", 1, "#A0A0A0", "#AEAEAE", "#1a1a1a"),
            main=SelectionColor("_26", "Gray", "gray", "base", 2, "#5A5A5A", "#696969", "#e9edf2"),
            dark=SelectionColor("_27", "Gray Dark", "gray", "dark", 3, "#333333", "#404040", "#cfd6df"),
        ),
    ),
)
