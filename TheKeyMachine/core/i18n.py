"""Central translation service for the TKM toolbar.

Design mirrors ``toolbox.load_tooltips``: every tool package that wants
translated labels/tooltips owns one small ``lang.json`` file next to its
``tooltip.json`` (added only where translations exist -- packages without one
simply fall back to their English source strings, so nothing else has to
change). Chrome strings that aren't tied to a single tool id (menu section
headers, alignment labels, etc.) live in one shared ``data/lang/core.json``.

This module is the *only* place language state, the available-language
registry, and string lookup are implemented -- ``toolbox.get_tool`` and the
handful of hardcoded chrome labels in ``toolMenus.py`` call into it, but none
of them duplicate its logic.

Loading is cheap and lazy: the language registry and the shared core strings
are tiny JSON files read once and cached; a package's ``lang.json`` is only
ever read the first time one of its tools is resolved, exactly like
``load_tooltips`` already does for tooltips. Nothing is parsed for a language
the user never selects beyond the couple of KB already loaded for the
registry itself.
"""

import json
import os

from TheKeyMachine.core.Qt import QtCore

SOURCE_LANGUAGE = "en"

LANGUAGE_SETTING = "language"
TRANSLATE_TOOL_NAMES_SETTING = "translate_tool_names"

_DATA_LANG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lang")
_LANGUAGES_FILE = os.path.join(_DATA_LANG_DIR, "languages.json")
_CORE_STRINGS_FILE = os.path.join(_DATA_LANG_DIR, "core.json")

_languages_cache = None
_core_strings_cache = None
_package_lang_cache = {}


class _LanguageBus(QtCore.QObject):
    """Signals so live UI can react when the active language/settings change.

    Most menus in this toolbar are already rebuilt fresh every time they're
    opened (see ``toolMenus._add_registered_menu`` / shelfMod's rebuild
    pattern), so they simply pick up the new language on their next open.
    The few menus cached across opens (the toolbar's right-click pinning
    menu, the dock menu) listen on this bus to invalidate themselves.
    """

    languageChanged = QtCore.Signal()


bus = _LanguageBus()


def _load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return dict(default) if default is not None else {}


def available_languages():
    """Return ``{code: {"name": ..., "native": ...}}`` for every installed language."""
    global _languages_cache
    if _languages_cache is None:
        _languages_cache = _load_json(
            _LANGUAGES_FILE, default={SOURCE_LANGUAGE: {"name": "English", "native": "English"}}
        )
        _languages_cache.setdefault(SOURCE_LANGUAGE, {"name": "English", "native": "English"})
    return _languages_cache


def language_display_name(code):
    entry = available_languages().get(code) or {}
    return entry.get("native") or entry.get("name") or code


def get_language():
    from TheKeyMachine.mods import settingsMod as settings

    lang = settings.get_setting(LANGUAGE_SETTING, SOURCE_LANGUAGE)
    return lang if lang in available_languages() else SOURCE_LANGUAGE


def set_language(code):
    from TheKeyMachine.mods import settingsMod as settings

    if code not in available_languages():
        code = SOURCE_LANGUAGE
    if code == get_language():
        return
    settings.set_setting(LANGUAGE_SETTING, code)
    bus.languageChanged.emit()


def get_translate_tool_names():
    from TheKeyMachine.mods import settingsMod as settings

    return bool(settings.get_setting(TRANSLATE_TOOL_NAMES_SETTING, False))


def set_translate_tool_names(enabled):
    from TheKeyMachine.mods import settingsMod as settings

    enabled = bool(enabled)
    if enabled == get_translate_tool_names():
        return
    settings.set_setting(TRANSLATE_TOOL_NAMES_SETTING, enabled)
    bus.languageChanged.emit()


def _core_strings():
    global _core_strings_cache
    if _core_strings_cache is None:
        _core_strings_cache = _load_json(_CORE_STRINGS_FILE, default={"ui": {}, "messages": {}})
        _core_strings_cache.setdefault("ui", {})
        _core_strings_cache.setdefault("messages", {})
    return _core_strings_cache


def tr(key, default=""):
    """Translate a chrome string that isn't owned by a single tool id.

    Menu section headers, alignment labels, and similar cross-cutting UI
    text look themselves up here by a short id, backed by
    ``data/lang/core.json``. Falls back to ``default`` (the English source)
    whenever the active language is English or the key/language has no
    translation yet -- switching to a not-yet-translated string never raises.
    """
    lang = get_language()
    if lang == SOURCE_LANGUAGE:
        return default
    translated = _core_strings()["ui"].get(key, {}).get(lang)
    return translated or default


def tr_text(message):
    """Translate a literal display string (in-view messages, status text) by exact match.

    Lets call sites like ``wutil.make_inViewMessage("Select at least one
    object")`` keep passing plain English text -- the source string doubles
    as its own translation key, so nothing at the call site needs to change
    when a translation becomes available (or stays untranslated).
    """
    if not message:
        return message
    lang = get_language()
    if lang == SOURCE_LANGUAGE:
        return message
    translated = _core_strings()["messages"].get(message, {}).get(lang)
    return translated or message


def load_package_lang(package_file):
    """Load (and cache) a tool package's ``lang.json``, mirroring ``load_tooltips``.

    Returns ``{}`` when the package has no translations yet -- callers don't
    need to special-case that; every lookup against an empty dict simply
    falls back to the package's English source strings.
    """
    if not package_file:
        return {}
    lang_path = os.path.join(os.path.dirname(package_file), "lang.json")
    if lang_path in _package_lang_cache:
        return _package_lang_cache[lang_path]
    data = _load_json(lang_path, default={})
    _package_lang_cache[lang_path] = data
    return data


def _translate_tooltip(original, translated_strings):
    """Rebuild a tooltip list, swapping only its plain-string entries.

    Tooltip lists can mix plain text with platform variants, movies, and
    separators (see ``toolbox.load_tooltips``); none of that media is
    language-specific, so a translation only ever supplies replacement text
    for the string entries, in the same order they appear in the source.
    """
    if not isinstance(original, list) or not translated_strings:
        return original
    remaining = list(translated_strings)
    result = []
    for item in original:
        if isinstance(item, str) and remaining:
            result.append(remaining.pop(0))
        else:
            result.append(item)
    return result


def _lookup_translation(key, package_file):
    """Shared entry point behind both ``localize_tool`` and ``localize_label_tooltip``.

    Returns the ``{"label": ..., "tooltip": [...]}`` entry for *key* in
    *package_file*'s ``lang.json`` under the active language, or ``None`` when
    nothing is recorded there yet for that key/language.

    ``lang.json`` carries an ``"en"`` entry alongside every translation, so
    this looks itself up the same way regardless of which language is
    active -- English is not special-cased. That keeps every consumer
    (tool labels/tooltips, slider modes, section labels) reading from one
    single source of truth per key, and means a plain re-lookup is always
    enough to refresh a widget after a language switch, in either
    direction, without any caller needing to keep the original English text
    around separately.
    """
    translations = load_package_lang(package_file)
    return (translations.get(key) or {}).get(get_language())


def localize_tool(tool_id, tool):
    """Apply the active language to one package tool definition, in place.

    Called from ``toolbox.get_tool`` *before* any caller-supplied overrides
    are applied, so an explicit override always wins over translation --
    this only ever touches the package's own declared ``label``/``tooltip``.
    Tooltips (the "helper" text) translate whenever a non-English language
    is active; the tool's name/label additionally requires the "Translate
    Tool Names" preference to be on.
    """
    entry = _lookup_translation(tool_id, tool.get("_package_file"))
    if not entry:
        return tool

    if get_translate_tool_names():
        label = entry.get("label")
        if label:
            tool["label"] = label
            if tool.get("menu_label"):
                tool["menu_label"] = label
        menu_label = entry.get("menu_label")
        if menu_label and tool.get("menu_label"):
            tool["menu_label"] = menu_label

    translated_tooltip = entry.get("tooltip")
    if translated_tooltip:
        tool["tooltip"] = _translate_tooltip(tool.get("tooltip"), translated_tooltip)

    return tool


def localize_label_tooltip(key, package_file, label, tooltip):
    """Translate a bare label/tooltip pair keyed the same way as ``localize_tool``.

    Some presentation objects (slider modes -- see ``mods/sliders.py`` and
    ``toolWidgets.build_slider_section``) carry their own label/tooltip
    instead of living in the ``toolbox.get_tool`` registry, but still want a
    per-package ``lang.json`` entry under the same key. Returns
    ``(label, tooltip)``, translated if available, otherwise the inputs
    unchanged.
    """
    entry = _lookup_translation(key, package_file)
    if not entry:
        return label, tooltip

    new_label = label
    if get_translate_tool_names():
        new_label = entry.get("label") or label

    new_tooltip = tooltip
    translated_tooltip = entry.get("tooltip")
    if translated_tooltip:
        new_tooltip = _translate_tooltip(tooltip, translated_tooltip)

    return new_label, new_tooltip


def localize_slider_modes(modes, package_file):
    """Return a copy of *modes* with each ``SliderMode``'s label/tooltip/description translated.

    A slider widget keeps its *entire* mode list around internally (for its
    own mode-switch menu -- see ``widgets/sliderWidget.py``), not just the
    one mode it's currently showing, so translating only the active mode
    when the widget is built isn't enough: the switcher menu would still
    list every other mode in English. This translates the whole list in one
    pass, using the same per-package ``lang.json`` and "Translate Tool
    Names" gate as everything else. Entries that aren't a ``SliderMode``
    (the ``"separator"`` marker) pass through unchanged.
    """
    from dataclasses import replace

    localized = []
    for mode in modes:
        if not hasattr(mode, "key"):
            localized.append(mode)
            continue
        label, tooltip = localize_label_tooltip(mode.key, package_file, mode.label, mode.tooltip)
        if label == mode.label and tooltip is mode.tooltip:
            localized.append(mode)
            continue
        description = mode.description
        if isinstance(tooltip, list) and tooltip and isinstance(tooltip[0], str):
            description = tooltip[0]
        localized.append(replace(mode, label=label, tooltip=tooltip, description=description))
    return localized


def localize_section_label(section_id, package_file, label):
    """Translate a toolbox SECTION's display label (used by the toolbar's
    right-click pinning menu and section headers), the same way tool labels
    are translated -- gated by "Translate Tool Names" since a section name
    like "Nudge" is as much an identity as any one tool's name.
    """
    if not get_translate_tool_names():
        return label
    entry = _lookup_translation(section_id, package_file)
    if not entry:
        return label
    return entry.get("label") or label
