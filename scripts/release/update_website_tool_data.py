#!/usr/bin/env python3
"""Export the Standard workspace toolbar and its assets to the website.

The application registry normally runs inside Maya and therefore imports Qt
and Maya-facing callbacks.  This exporter substitutes inert callback modules
while loading the declarative ToolObject metadata.  Labels, icons, tooltip
JSON, slider modes, workspace pins, and section order still come from the same
files used by the application.
"""

import argparse
import filecmp
import importlib
import json
import re
import shutil
import struct
import sys
import types
from pathlib import Path
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "TheKeyMachine" / "tools"
ICON_ROOT = REPO_ROOT / "TheKeyMachine" / "data" / "icons"
VERSION_FILE = REPO_ROOT / "TheKeyMachine" / "version"
TOOLS_JSON = "tools.json"
CURRENT_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()

# A script launched by path gets scripts/release on sys.path, not the checkout
# root that owns the TheKeyMachine package.
sys.path.insert(0, str(REPO_ROOT))


def _noop(*_args, **_kwargs):
    return None


class _QtPlaceholder:
    """Hashable/callable stand-in for Qt constants and signal factories."""

    def __getattr__(self, _name):
        return self

    def __call__(self, *_args, **_kwargs):
        return None


class _TooltipLink:
    def __init__(self, url, label=None, text=None):
        self.url = url
        self.label = label
        self.text = text


def _inert_module(name):
    module = types.ModuleType(name)
    module.__getattr__ = lambda _attribute: _noop
    return module


def install_export_stubs(package_names):
    """Install only the runtime dependencies declarative metadata does not need."""
    qt_module = types.ModuleType("TheKeyMachine.core.Qt")
    qt_module.QtCore = _QtPlaceholder()
    sys.modules[qt_module.__name__] = qt_module

    for name in (
        "TheKeyMachine.core.application",
        "TheKeyMachine.core.i18n",
        "TheKeyMachine.core.settings",
        "TheKeyMachine.core.trigger",
        "TheKeyMachine.ui.widgets.toolbar_menus",
    ):
        sys.modules[name] = _inert_module(name)

    tooltip_module = types.ModuleType("TheKeyMachine.ui.tooltips")
    tooltip_module.separator = object()
    tooltip_module.TooltipLink = _TooltipLink
    sys.modules[tooltip_module.__name__] = tooltip_module

    for package_name in package_names:
        for child in ("api", "controller", "widgets"):
            name = "{}.{}".format(package_name, child)
            sys.modules[name] = _inert_module(name)


def tool_package_names():
    names = []
    for init_path in sorted(PACKAGE_ROOT.glob("*/__init__.py")):
        source = init_path.read_text(encoding="utf-8")
        if not re.search(r"^class\s+\w+ToolObject\s*\(", source, flags=re.MULTILINE):
            continue
        names.append("TheKeyMachine.tools.{}".format(init_path.parent.name))
    return names


def load_registry_metadata():
    package_names = tool_package_names()
    install_export_stubs(package_names)

    from TheKeyMachine.tools import registry
    from TheKeyMachine.core import workspaces

    tools = {}
    sections = {}
    failures = []
    for package_name in package_names:
        try:
            package = importlib.import_module(package_name)
            tool_object = registry._tool_object_from_package(package)
            if tool_object is None:
                continue
            tool_object._package_file = package.__file__
            tools.update(tool_object.tools())
            sections.update(tool_object.sections())
        except Exception as exc:
            failures.append("{}: {}".format(package_name, exc))
    if failures:
        raise SystemExit("Unable to export tool packages:\n- " + "\n- ".join(failures))

    standard_pins = set(workspaces.WORKSPACE_DEFAULTS["standard"]["pins"]["main"])
    return registry.TOOLBAR_SECTION_IDS["main"], tools, sections, standard_pins


def tooltip_text(value):
    lines = []

    def collect(item):
        if isinstance(item, str):
            lines.append(item.strip())
        elif isinstance(item, (list, tuple)):
            for child in item:
                collect(child)

    collect(value)
    return " ".join(line for line in lines if line)


def tooltip_movies(value):
    from TheKeyMachine.data.movies import TooltipMedia

    paths = []

    def collect(item):
        if isinstance(item, TooltipMedia):
            paths.append(Path(item.path))
        elif isinstance(item, (list, tuple)):
            for child in item:
                collect(child)
        elif isinstance(item, dict):
            for child in item.values():
                collect(child)

    collect(value)
    return paths


def website_asset_path(source, kind):
    source = Path(source)
    if kind == "icons":
        relative = source.resolve().relative_to(ICON_ROOT.resolve())
        return "icons/{}".format(relative.as_posix())
    return "movies/{}".format(source.name)


def copy_asset(source, website_root, kind):
    source = Path(source)
    if not source.is_file():
        raise SystemExit("Missing {} asset: {}".format(kind.rstrip("s"), source))
    destination = website_root / website_asset_path(source, kind)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Most releases change code but not media. Avoid rewriting large GIFs (and
    # perturbing their mtimes) when the website checkout already has the same
    # bytes.
    if not destination.is_file() or not filecmp.cmp(str(source), str(destination), shallow=False):
        # Copy bytes only. Source assets may be executable in the application
        # checkout; those mode bits are irrelevant and undesirable on the
        # static website branch.
        shutil.copyfile(str(source), str(destination))
    return destination.relative_to(website_root).as_posix()


def versioned_asset(path):
    return "{}?v={}".format(path, quote(CURRENT_VERSION, safe=""))


def movie_record(source, website_root):
    source = Path(source)
    with source.open("rb") as stream:
        header = stream.read(10)
    if len(header) < 10 or header[:6] not in {b"GIF87a", b"GIF89a"}:
        raise SystemExit("Tooltip movie is not a valid GIF: {}".format(source))
    width, height = struct.unpack("<HH", header[6:10])
    if width < 1 or height < 1:
        raise SystemExit("Tooltip movie has invalid dimensions: {}".format(source))
    return {
        "src": versioned_asset(copy_asset(source, website_root, "movies")),
        "width": width,
        "height": height,
    }


def section_items(section, sections):
    for item in section.get("items") or ():
        if not isinstance(item, dict):
            continue
        nested_id = item.get("section")
        if nested_id:
            nested = sections.get(nested_id)
            if nested:
                for child in section_items(nested, sections):
                    yield child
            continue
        if item.get("id"):
            yield item


def regular_tool_record(tool_id, placement, tools, website_root):
    definition = dict(tools[tool_id])
    definition.update(
        (key, value)
        for key, value in placement.items()
        if key not in {"id", "section", "shortcuts", "default"}
    )
    icon = ""
    if definition.get("icon"):
        icon = versioned_asset(copy_asset(definition["icon"], website_root, "icons"))
    movies = [
        movie_record(path, website_root)
        for path in tooltip_movies(definition.get("tooltip"))
    ]
    return {
        "id": tool_id,
        "label": definition.get("label") or tool_id,
        "text": definition.get("text") or "",
        "icon": icon,
        "tooltip": tooltip_text(definition.get("tooltip")),
        "movies": movies,
    }


def slider_tool_records(section, standard_pins, website_root):
    records = []
    prefix = section.get("slider_type")
    for mode in section.get("modes") or ():
        if mode == "separator":
            continue
        tool_id = "{}_{}".format(prefix, mode.key)
        if tool_id not in standard_pins:
            continue
        icon_path = mode.resolved_icon()
        records.append(
            {
                "id": tool_id,
                "label": mode.label,
                "text": mode.text or "",
                "icon": versioned_asset(copy_asset(icon_path, website_root, "icons")) if icon_path else "",
                "tooltip": tooltip_text(mode.tooltip),
                "movies": [
                    movie_record(path, website_root)
                    for path in tooltip_movies(mode.tooltip)
                ],
                "slider": True,
            }
        )
    return records


def build_tool_catalog(website_root):
    section_order, tools, sections, standard_pins = load_registry_metadata()
    records = []
    groups = []
    seen = set()

    for section_id in section_order:
        section = sections.get(section_id)
        if not section or section.get("toolbar") is False or section.get("hotkeys"):
            continue

        group_records = []
        if section.get("type") == "slider":
            group_records = slider_tool_records(section, standard_pins, website_root)
        else:
            for placement in section_items(section, sections):
                placement_id = placement["id"]
                tool_id = placement_id if placement_id in standard_pins else None
                # A compatibility command can remain in a saved workspace
                # after its visible section item is renamed.  The registry's
                # i18n_key identifies that alias (currently
                # delete_all_animation -> clear_animation), so export the
                # pinned identity in the visible item's position.
                if tool_id is None:
                    tool_id = next(
                        (
                            candidate_id
                            for candidate_id in standard_pins - seen
                            if (tools.get(candidate_id) or {}).get("i18n_key") == placement_id
                        ),
                        None,
                    )
                if tool_id is None or tool_id in seen:
                    continue
                if tool_id not in tools:
                    raise SystemExit("Standard workspace references unknown tool: {}".format(tool_id))
                group_records.append(regular_tool_record(tool_id, placement, tools, website_root))

        group_records = [record for record in group_records if record["id"] not in seen]
        if not group_records:
            continue
        records.extend(group_records)
        seen.update(record["id"] for record in group_records)
        groups.append(
            {
                "id": section_id,
                "label": section.get("label") or section_id,
                "color": section.get("color") or "#787878",
                "tools": [record["id"] for record in group_records],
            }
        )

    missing = sorted(standard_pins - seen)
    if missing:
        raise SystemExit("Standard workspace tools were not exported: {}".format(", ".join(missing)))
    return records, groups


def write_tools_json(website_root, tools, groups):
    payload = {
        "version": CURRENT_VERSION,
        "workspace": "standard",
        "tools": tools,
        "groups": groups,
    }
    path = website_root / TOOLS_JSON
    # Keep the version-keyed browser payload compact. The readable source
    # metadata remains in the application package.
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def prune_stale_assets(website_root, tools):
    """Remove only assets owned by the previous generated catalog."""
    path = website_root / TOOLS_JSON
    if not path.is_file():
        return
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return

    def references(tool_records):
        result = set()
        for tool in tool_records or ():
            icon = tool.get("icon")
            if icon:
                result.add(icon.partition("?")[0])
            for movie in tool.get("movies") or ():
                value = movie.get("src") if isinstance(movie, dict) else movie
                if value:
                    result.add(value.partition("?")[0])
        return result

    stale = references(previous.get("tools")) - references(tools)
    asset_roots = {(website_root / name).resolve() for name in ("icons", "movies")}
    for relative in stale:
        candidate = (website_root / relative).resolve()
        if not any(asset_root in candidate.parents for asset_root in asset_roots):
            continue
        if candidate.is_file():
            candidate.unlink()


def update_toolbar_javascript(website_root):
    path = website_root / "toolbar.js"
    if not path.is_file():
        raise SystemExit("Missing website file: {}".format(path))
    text = path.read_text(encoding="utf-8")
    replacement = """/* ---------------------------------------------------------------------
   * Data: loaded from generated tools.json
   * ------------------------------------------------------------------- */
  let standardToolbarTools = [];
  let standardToolbarGroups = [];
  let standardToolbarToolMap = new Map();

  async function loadStandardToolbarData() {
    const response = await fetch('tools.json?v=__VERSION__');
    if (!response.ok) throw new Error(`Unable to load tools.json (${response.status})`);
    const payload = await response.json();
    standardToolbarTools = Array.isArray(payload.tools) ? payload.tools : [];
    standardToolbarGroups = Array.isArray(payload.groups) ? payload.groups : [];
    standardToolbarToolMap = new Map(standardToolbarTools.map((tool) => [tool.id, tool]));
  }
  /* End generated tool data */""".replace("__VERSION__", quote(CURRENT_VERSION, safe=""))
    pattern = r"/\* -+\n\s*\* Data:.*?\n\s*\* -+ \*/.*?(?:/\* End generated tool data \*/|const standardToolbarToolMap = new Map\(standardToolbarTools\.map\(\(tool\) => \[tool\.id, tool\]\)\);)"
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit("Could not find generated toolbar data block in {}".format(path))

    lazy_show_tip = """function showTip(trigger) {
    const entry = tipRegistry.get(trigger);
    if (!entry || trigger === activeTrigger) return;
    if (!entry.tip) {
      entry.tip = createStandardToolbarTip(entry.config);
      document.body.append(entry.tip);
    }
    if (activeTip) activeTip.classList.remove('is-visible');
    activeTrigger = trigger;
    activeTip = entry.tip;
    positionTip(trigger, entry.tip);
    entry.tip.classList.add('is-visible');
  }"""
    updated, show_count = re.subn(
        r"function showTip\(trigger\) \{.*?\n  \}",
        lazy_show_tip,
        updated,
        count=1,
        flags=re.DOTALL,
    )
    if show_count != 1:
        raise SystemExit("Could not find tooltip display function in {}".format(path))

    lazy_register_tip = """function registerTip(trigger, tipConfig) {
    tipRegistry.set(trigger, { config: tipConfig, tip: null });
    trigger.dataset.tipTrigger = '';
  }"""
    updated, register_count = re.subn(
        r"function registerTip\(trigger, tipConfig\) \{.*?\n  \}",
        lazy_register_tip,
        updated,
        count=1,
        flags=re.DOTALL,
    )
    if register_count != 1:
        raise SystemExit("Could not find tooltip registration function in {}".format(path))

    movie_block = """(tool.movies || []).forEach((movie) => {
      const media = document.createElement('img');
      const movieData = typeof movie === 'string' ? { src: movie } : movie;
      media.className = 'standard-toolbar-tip-movie';
      media.src = movieData.src;
      media.alt = '';
      media.loading = 'lazy';
      media.decoding = 'async';
      if (movieData.width && movieData.height) {
        media.width = movieData.width;
        media.height = movieData.height;
        media.style.aspectRatio = `${movieData.width} / ${movieData.height}`;
      }
      tip.append(media);
    });"""
    updated, movie_count = re.subn(
        r"\(tool\.movies \|\| \[\]\)\.forEach\(\(movie\) => \{.*?\n    \}\);",
        movie_block,
        updated,
        count=1,
        flags=re.DOTALL,
    )
    if movie_count != 1:
        raise SystemExit("Could not find tooltip movie block in {}".format(path))

    init_replacement = """async function init() {
    try {
      await loadStandardToolbarData();
      ensureStandardToolbarMock();
    } catch (error) {
      console.error('TheKeyMachine toolbar data could not be loaded.', error);
    }
  }"""
    updated, init_count = re.subn(
        r"(?:async\s+)?function init\(\) \{.*?\n  \}",
        init_replacement,
        updated,
        count=1,
        flags=re.DOTALL,
    )
    if init_count != 1:
        raise SystemExit("Could not find toolbar initializer in {}".format(path))
    path.write_text(updated, encoding="utf-8")


def update_website_cache_keys(website_root):
    path = website_root / "index.html"
    if not path.is_file():
        raise SystemExit("Missing website file: {}".format(path))
    text = path.read_text(encoding="utf-8")
    replacement = 'src="toolbar.js?v={}"'.format(quote(CURRENT_VERSION, safe=""))
    updated, count = re.subn(
        r'src="toolbar\.js(?:\?v=[^"]*)?"',
        replacement,
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not find toolbar script tag in {}".format(path))
    path.write_text(updated, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("website_root", help="Checkout path for the website branch")
    args = parser.parse_args()

    website_root = Path(args.website_root).resolve()
    tools, groups = build_tool_catalog(website_root)
    prune_stale_assets(website_root, tools)
    write_tools_json(website_root, tools, groups)
    update_toolbar_javascript(website_root)
    update_website_cache_keys(website_root)
    print("website_tools={}".format(len(tools)))
    print("website_tool_groups={}".format(len(groups)))


if __name__ == "__main__":
    main()
