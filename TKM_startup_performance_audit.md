# TheKeyMachine Startup Performance Audit
### Main toolbar + Graph Editor toolbar

**Scope.** This audit traces the actual code path executed from `TheKeyMachine.core.toolbar.show()` (main toolbar) and `TheKeyMachine.tools.graph_toolbar` (Graph Editor toolbar) through tool discovery, section resolution, and button/widget construction. All findings are based on direct reading of the current code, with file and line references so each item can be independently verified. No profiler was run against a live Maya session; wall-clock estimates below are qualitative (relative cost), not measured milliseconds — see the *Verification* section for how to get real numbers before/after.

---

## 1. Startup call graph, as it exists today

**Main toolbar** (`core/toolbar.py`)
```
core.toolbar.show()
 -> toolbar.__init__()
    -> selectionSetsApi.get_controller(owner=self)          # cheap
    -> report.install_bug_exception_handler()                 # cheap
    -> graphToolbarApi.sync_graph_toolbar_watch()              # starts a watch timer (see F2)
    -> buildUI()
       -> _populate_toolbar_from_layout("main", new_section)
          -> toolbox.get_toolbar_sections("main", resolve_items=False)   # (see F1)
          -> per section: toolbox.get_tool_section(sec_id, toolbar_id="main")  # resolved a 2nd time, (see F1)
          -> per tool item: toolbox.get_tool(tool_id)  -> cw.create_tool_button_from_data(...)
       -> toolbox.get_tool("TKM") -> separate TKM logo button
    -> QTimer.singleShot(0, _sync_graph_editor_on_startup)     # (see F2)
```
`toolbox.get_toolbar_sections()`/`get_tool_section()`/`get_tool()` are the first callers of `toolbox._collect_package_definitions()`, which walks **every** subpackage under `TheKeyMachine.tools` (37 packages) via `pkgutil.iter_modules` + `importlib.import_module` and imports each one, purely to read its declarative `ToolObject.TOOLS`/`SECTION` dict. Whatever each package's `__init__.py` imports at module scope comes along for free — see F4.

**Graph Editor toolbar** (`tools/graph_toolbar/`)
```
Two independent triggers, both scheduled during the SAME toolbar.__init__():

 A) toolbar.__init__ -> QTimer.singleShot(0, _sync_graph_editor_on_startup)
      -> if "graphEditor1" already visible: QTimer.singleShot(0, graphToolbarApi.create)

 B) graphToolbarApi.sync_graph_toolbar_watch() -> runtimeManager.set_graph_editor_watch_enabled(True)
      -> _schedule_graph_editor_check() -> _ui_watch_timer.start(0)
      -> _check_graph_editor_state(): if "graphEditor1" visible and wasn't tracked as visible yet
         -> QTimer.singleShot(0, _emit_graph_editor_opened) -> graph_editor_opened.emit()
      -> toolbar._on_graph_editor_opened() -> QTimer.singleShot(0, graphToolbarApi.create)

Both paths call graphToolbarApi.create() == controller.create() == widgets.createCustomGraph(),
which is NOT idempotent (see F2) and internally calls:
   -> toolWidgets.populate_graph_toolbar_from_layout(...)     # near-duplicate of the main-toolbar populate function (see F3)
      -> toolbox.get_toolbar_sections("graph", resolve_items=False)
      -> per section: toolbox.get_tool_section(sec_id, toolbar_id="graph")   # re-resolves the ~27 sections shared with "main"
```

---

## 2. Findings, ranked by impact

### F1 — Every tool/section lookup copies the entire registry (HIGH impact, LOW risk)
`core/toolbox.py:348-364`
```python
def _tool_definitions():
    package_tools, _package_sections = _package_definitions()
    return dict(package_tools)          # full shallow copy of ALL tools

def _section_definitions():
    _package_tools, package_sections = _package_definitions()
    return dict(package_sections)       # full shallow copy of ALL sections
```
`get_tool()` (line 415), `is_tool_available()` (line 444), and `get_tool_section()` (line 450) each call one of these helpers, then read out **one** key. `is_tool_available()` is called once per item inside `get_tool_section()`'s resolution loop, and `get_tool()` is called again immediately after for the same item — so a single visible button costs **two** full-registry copies, not one. With on the order of 150-200 registered tool/section entries and on the order of 150-250 button/menu resolutions across both toolbars combined (every shared section is resolved once for "main" and once again for "graph" — see F3), this is tens of thousands of unnecessary dict-entry copies during the startup window alone. Each copy is cheap in isolation (low microseconds), but it's pure waste sitting on the hottest path in the whole tool-registry system, multiplied by every button on both toolbars, every menu build, and every `is_tool_available()`/`get_tool()` call anywhere else in the app afterward (right-click menus, hotkey editor, workspaces editor).

**Fix.** `_collect_package_definitions()` already returns immutable, memoized data (`_PACKAGE_TOOL_DEFINITIONS` / `_PACKAGE_SECTION_DEFINITIONS`) that nothing downstream mutates in place — `get_tool()` already makes its own per-item `dict(definitions[tool_id])` copy before applying overrides, which is the copy that actually matters. Have `_tool_definitions()`/`_section_definitions()` return the cached mapping directly (or a `types.MappingProxyType` wrapper if defensive read-only access is wanted) instead of `dict(...)`. This is a two-line change with no behavior change, since nothing currently relies on the returned dict being a fresh copy.

### F2 — Graph Editor toolbar is built via a non-idempotent path, from two independent triggers (HIGH impact, LOW-MEDIUM risk)
`core/toolbar.py:88,106-160` and `tools/graph_toolbar/widgets.py:235-294`

As traced in section 1, when Maya starts with the Graph Editor panel already open (a very common layout for animators), **two** independent code paths detect this during the same `toolbar.__init__()` and both end up calling `graphToolbarApi.create()`. `createCustomGraph()` has no "already built, skip" guard — it unconditionally calls `removeCustomGraph()` and then rebuilds every section and every button from scratch (line 257-294). The codebase already has the correct entry point for this exact situation, `ensureCustomGraph()` (line 220), which checks `getCustomGraphWidget()` first and only calls `createCustomGraph(force=True)` if nothing valid exists — but neither startup trigger uses it; both call `create()`/`createCustomGraph` directly.

Net effect: on any session where the Graph Editor is already open at startup, the entire Graph Editor toolbar — every section, every button widget, every tooltip, every menu — is very likely built twice in the same startup window, and at minimum the two triggers are racing to do so.

**Fix.** Two independent, complementary changes, either one closes the gap:
1. In `toolbar._sync_graph_editor_on_startup` and `toolbar._on_graph_editor_opened`, call `graphToolbarApi.ensure()` instead of `graphToolbarApi.create()`.
2. Add the same "already exists and valid" short-circuit at the top of `createCustomGraph()` itself (skip the rebuild unless `force=True` or the existing widget is actually gone/invalid), so every current and future caller benefits, not just the ones that happen to call `ensure()`.

Recommend doing both — (2) is the structural fix, (1) removes the redundant scheduling itself.

### F3 — Main and Graph Editor toolbars are populated by two near-duplicate functions (MEDIUM impact, MEDIUM risk)
`core/toolWidgets.py:649-696` (`populate_main_toolbar_from_layout`) and `core/toolWidgets.py:781-820` (`populate_graph_toolbar_from_layout`)

These two ~50-line functions walk sections, handle the `connect_entries`/`slider`/group-menu special cases, and add items — with only cosmetic differences (`add_main_*` vs `add_graph_*` helper names, a settings namespace string, an object-name prefix). `MAIN_SPECIAL_TOOL_KEYS` (line 39) and `GRAPH_SPECIAL_TOOL_KEYS` (line 47) are defined as two separate literals with **identical contents**. This duplication means:
- Any future change to the section-population logic (bug fix, new item type) has to be made twice and kept in sync by hand — the exact anti-pattern `ARCHITECTURE.md` calls out for composition modules ("If two modules need the same implementation, move it to the narrowest common owner... do not copy the function").
- At runtime, the ~27 sections that are on *both* toolbars (`nudge_tools`, `default_tools`, `bake_tools`, `attribute_tools`, `graph_tools`, etc. — compare `TOOLBAR_SECTION_IDS["main"]` and `["graph"]` at `core/toolbox.py:113-137`) go through this resolution logic twice, independently, once per toolbar, with zero sharing between the two passes.

**Fix.** Collapse to one parameterized function, e.g. `populate_toolbar_from_layout(layout_id, new_section_fn, *, add_tool_item_fn, add_widget_item_fn, special_keys, namespace, object_prefix)`, and have the two thin call sites (`toolbar.buildUI`, `graph_toolbar/widgets.createCustomGraph`) supply their differing bits. This removes the duplicated logic outright; it does not by itself avoid resolving shared sections twice (main and graph legitimately need separate widget instances), but it does mean any future caching added to `get_tool_section()` benefits both call sites automatically instead of needing to be threaded through two copies of the loop.

### F4 — Three tool packages eager-import their full window UI at toolbar-build time (MEDIUM-HIGH impact, LOW risk)
`tools/animation_offset/api.py:10`, `tools/attribute_switcher/api.py:15`, `tools/gimbal_fixer/api.py:2`

Because `toolbox._collect_package_definitions()` imports every tool package's `__init__.py` to read its `TOOLS`/`SECTION` metadata (37 packages, `core/toolbox.py:292-328`), and most `__init__.py` files import their own `api.py` to reference callback functions in the `TOOLS` dict (32 of 37 packages do this), whatever `api.py` imports at module scope is paid for at the very first toolbar build — regardless of whether the user ever opens that tool this session. Three packages import their entire `widgets.py` (window/dialog class definitions) directly at the top of `api.py`:
- `attribute_switcher/widgets.py` — 2,253 lines, defines the full popup window, multi-attribute-switch dialog, popups, etc.
- `gimbal_fixer/widgets.py` — 329 lines
- `animation_offset/widgets.py` — 215 lines

Combined, ~2,800 lines of Qt class bodies execute at import time for windows that are opened on demand, not needed to draw a toolbar button.

The fix is already established, working precedent *in this same codebase*: `tools/orbit/api.py:31-33` and `tools/selection_sets/api.py:24-27` both defer their window-class import into a small `_window_class()` function, called only when the window is actually about to be shown:
```python
def _window_class():
    from TheKeyMachine.tools.orbit.widgets import OrbitWindow
    return OrbitWindow
```

**Fix.** Apply the same `_window_class()` (or equivalent local-import) pattern to `attribute_switcher/api.py`, `gimbal_fixer/api.py`, and `animation_offset/api.py`. This is a mechanical, low-risk change — move the top-level `from ...widgets import X` into the one or two functions that actually construct `X`, matching a pattern the codebase already uses successfully elsewhere. It does not change behavior at all when the tool is actually used; it only removes work for the (common) case where it isn't, this session.

*Note:* `slider_blend`, `slider_tangent`, and `slider_tween` also import their `widgets.py` at `__init__.py` scope, but this is not the same issue — sliders are always-visible inline toolbar controls, not on-demand popup windows, so their widgets genuinely are needed at build time. Don't lump these in with the fix above.

### F5 — `graph_toolbar/api.py` is a pure forwarding layer (LOW perf impact, worth cleaning up)
`tools/graph_toolbar/api.py:28-77`

Every function in this file (`create`, `remove`, `ensure`, `get_widget`, `apply_alignment`, `move_dock`, `bind_graph_toolbar_toggle`, etc.) does nothing but call the identically-named function on `controller` with the same arguments:
```python
def create(*args, **kwargs):
    return controller.create(*args, **kwargs)
```
`ARCHITECTURE.md`'s own rule on forwarding functions: *"A function that only returns or invokes another callable with the same arguments is redundant. Replace its callers with the owning callable and delete it."* This file is the textbook case that rule describes. The runtime cost is negligible (one extra frame per call), but it's a genuine, unambiguous redundancy per the project's own documented standard, it adds a module import that has to resolve at startup for zero behavioral benefit, and it's on the exact path this audit was asked to look at (`toolbar.py` imports `graph_toolbar.api`, not `.controller`, directly).

**Fix.** Have `toolbar.py` and other callers import `graph_toolbar.controller` directly (it already exists, is already the real implementation, and already uses the correct lazy-widgets pattern — see `controller.py:21-24`), and delete `api.py`, or keep `api.py` only for the handful of functions that genuinely add behavior (`show_settings_menu`/`show_dock_menu`, which route through `shelfMod`).

### F6 — Icon resolution does live filesystem stats with no caching (LOW-MEDIUM impact, trivial fix)
`data/icons.py:55-71`
```python
def get(name, default=None):
    ...
    for ext in ICON_EXTENSIONS:      # .svg, .png, .jpg, .jpeg
        candidate = path("{}{}".format(name, ext))
        if os.path.isfile(candidate):   # <-- syscall, every call, every time
            return candidate
    return default
```
Tool-level icons are resolved once and cached inside the memoized `_PACKAGE_TOOL_DEFINITIONS` (via `ToolObject._resolve_icons`, `core/toolbox.py:20-40`), so that part is fine. But `toolbox.get_section_icon()` (`core/toolbox.py:486-507`) is **not** cached and is called once per section by both `populate_main_toolbar_from_layout` and `populate_graph_toolbar_from_layout` for every one of the ~30 sections — so the ~27 shared sections get their icon re-resolved (1-4 `os.path.isfile` calls each) on both toolbar builds.

**Fix.** Wrap `icons.get()` (or `get_section_icon()`) with `functools.lru_cache`. Icon files don't change during a running Maya session, so this is safe with no invalidation concerns.

### F7 — ~540 slider dispatch closures are built the first time any menu needs a command name (LOW impact, informational)
`core/trigger.py:153-179`, called from `_discover_commands()` (line 103)

`slider_blend`, `slider_tween`, and `slider_tangent` collectively define 36 slider modes (`grep -c SliderMode` across the three `__init__.py` files: 14+12+10). Each mode is registered for all 15 `SLIDER_BUTTON_VALUES`, i.e. 540 `register_command()` calls, each wrapping a closure via `_make_dispatched_command`. This runs once (`_DISCOVERY_COMPLETE` memoizes it), triggered by the first call to `get_command`/`has_command`/`command_name_for_callback` — which happens early, since `customWidgets.MenuWidget.addAction()` calls `command_name_for_callback()` for any action built with a raw callback (`widgets/customWidgets.py:462`). This is unlikely to be a measurable cost on its own (closure creation is cheap), but it's worth knowing it's on the critical path if the sliders ever grow significantly, and it's a candidate for lazy/on-demand registration (register a slider's 15 value-commands only the first time that slider's mode is actually invoked) if this ever needs to be trimmed further.

---

## 3. What's already good (don't touch)

- **`settingsMod.get_setting()`** (`mods/settingsMod.py:47-82`) is already mtime-cached — repeated reads of the same preferences file skip disk entirely until the file actually changes. The docstring comment even explains the exact problem this audit would otherwise flag. No action needed.
- **Tool package discovery** (`toolbox._collect_package_definitions()`) is memoized after the first call (`_PACKAGE_TOOL_DEFINITIONS`/`_PACKAGE_SECTION_DEFINITIONS`), so the 37-package import scan itself only happens once per session, not once per toolbar.
- **`orbit/api.py` and `selection_sets/api.py`** already use the correct lazy-window-class pattern (F4). Use them as the template when fixing the three offending packages — no new pattern needs to be invented.
- **`graph_toolbar/controller.py`** already defers its own `widgets.py` import via `_widgets()` (line 21-24). Only `api.py`'s forwarding layer (F5) is the loose end here, not the controller.

---

## 4. Recommended order of work

1. **F1** (registry copy) and **F2** (idempotent graph toolbar) first — highest confidence, lowest risk, and F2 in particular is a real duplicate-build bug, not just an inefficiency, on a very common user layout.
2. **F4** (defer the three `widgets.py` imports) — mechanical, precedented, safe, and directly reduces what has to be imported before the first button is drawn.
3. **F6** (`lru_cache` on icon lookups) — five-minute fix, no behavior risk.
4. **F3** (collapse the duplicated populate functions) and **F5** (delete the forwarding layer) — do these together since F3's refactor will touch the same call sites F5 wants to repoint at `controller` directly; treat as one focused cleanup pass rather than two.
5. **F7** — not worth doing in isolation; revisit only if the slider catalog grows substantially.

## 5. Verification

The codebase already has a timing-instrumentation convention for exactly this purpose: `tools/common.py`'s `TKM_DEBUG_TIMING` env var and `debug_timing_log()` helper, currently used to break down `tool_operation()` phases. Before/after each change above, bracket `toolbar.buildUI()` and `graph_toolbar.widgets.createCustomGraph()` with the same `time.perf_counter()` + `debug_timing_log(...)` pattern already used in `tool_operation()` (`tools/common.py:524-635`) rather than introducing a separate ad hoc timing mechanism. That gives a real, comparable millisecond number per change instead of relying on the qualitative impact ratings above.
