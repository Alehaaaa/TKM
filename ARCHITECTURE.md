# TheKeyMachine architecture

This document is the contract for new code and incremental refactors. It describes the
target architecture while identifying legacy boundaries that cannot be renamed safely in an
ordinary cleanup. Favor small migrations that leave the dependency graph better than before.

## Package roles

### `data`

Declarative values and asset lookup only. `data` is a leaf package: it may use the Python
standard library and import another `data` module, but it must not import Maya, Qt, `core`,
`widgets`, `tools`, `sliders`, or `mods`. Color definitions and lightweight media references
belong here; widgets that render them do not.

### `core`

Cross-feature Maya services and application infrastructure. Focused services such as
`euler_filter`, `animlayers`, and `openMayaUtils` own reusable behavior. Context bridges such
as `animation_context` may read Maya UI state through the existing selection and timeline
adapters, but they own the precedence policy and must not import command modules.

Some existing `core` modules (`toolbar`, `toolbox`, `toolMenus`, `toolWidgets`, `trigger`, and
`backgroundRunners`) are application-composition modules rather than low-level services. They
may wire features together. Do not use their broad dependency access as precedent for focused
service modules; move composition into an `app` package in a coordinated future migration.

### `widgets`

Reusable Qt presentation and interaction components. Widgets may consume `data` and focused
`core` services. Feature-specific dialogs and widgets stay inside their `tools/<feature>`
package. Widgets must not contain animation algorithms or import legacy command modules to
execute feature behavior.

### `tools/<feature>` and `sliders`

Feature implementations. A feature keeps its `api.py`, controllers, dialogs, widgets,
constants, and private helpers together. Its supported external command surface lives in
`api.py`. Cross-feature calls go through the destination feature's `api.py` or through a
shared focused service; never import another feature's controller or private helper.

### `mods`

Legacy Maya command and compatibility surfaces. Existing Maya shelves and user scripts may
import these module paths, so module renames require a coordinated release. Do not add new
reusable algorithms or UI classes here. Move reusable behavior to `core`, `widgets`, or a
feature package, then update every internal caller directly. Stable command IDs belong in
`core.trigger`; do not add pass-through Python functions to preserve alternate spellings.

## Dependency rules

The intended dependency flow is:

```text
data <- focused core services <- widgets / tools / sliders <- composition and legacy entry points
```

The arrows mean “may be imported by.” Feature UI can depend on shared widgets, and composition
modules can depend on every feature they assemble. The following rules are stricter than the
diagram:

- `data` is dependency-free as defined above.
- Focused low-level `core` services never import `mods` command modules or
  application-composition modules. A named context bridge may depend on legacy state adapters
  until those adapters are migrated, but never on command implementations.
- `tools/<feature>` packages do not import internals from sibling features.
- `mods` modules do not import sibling `mods` modules to share implementation; extract a service.
- Imports used only to break a legacy cycle must be local and carry a migration note. Do not
  create new top-level cycles.
- Import the module that owns the behavior, not a transitive re-export.

Existing violations are migration work, not exceptions for new code. Fix them atomically when
their feature is touched; do not introduce forwarding wrappers or duplicate implementations.

## Naming and public APIs

- Modules, packages, functions, methods, and variables use `snake_case`.
- Classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- Private implementation names start with `_`; public names describe behavior, not UI labels.
- Feature packages expose supported calls from `api.py`.
- Shared modules use domain names such as `animation_context` or `euler_filter`, not generic
  buckets such as `utils2`, `misc`, or `helpers`.
- Stable shelf and hotkey compatibility is provided by command IDs in `core.trigger`, separate
  from Python function names.
- Rename a Python symbol only when all repository call sites are updated in the same change.
  Do not leave a function whose body only calls the renamed function.

### Forwarding functions

Call the owning function directly. A forwarding function is allowed only when it adds at least
one real boundary behavior:

- binds arguments, configuration, or a feature owner;
- adapts a callback protocol or public signature;
- applies validation, lifecycle, undo, dispatch, or error policy; or
- resolves an active application instance for a stable external command ID.

A function that only returns or invokes another callable with the same arguments is redundant.
Replace its callers with the owning callable and delete it. If the forwarded implementation has
the wrong public name, rename that implementation instead of adding a second entry point.

Legacy camelCase module paths are currently public. New modules must use `snake_case`; legacy
module-path migration requires updating shelves, hotkeys, user-facing scripts, and release notes.

## Animation context contract

Animation target selection and time selection are related but distinct. Commands use
`core.animation_context` instead of querying Maya UI elements independently.

Target precedence is:

1. Explicitly selected Graph Editor keys.
2. Selected Channel Box attributes.
3. Graph Editor outliner curves or attributes.
4. Selected scene objects and their keyable attributes.

Time precedence is:

1. Times of explicitly selected Graph Editor keys.
2. Selected timeline range.
3. Current frame for commands whose default mode is `current_frame`.
4. Playback range for commands whose default mode is `all_animation`.

`widgets.timeline.TimeContext` represents the result. Command ranges are inclusive. Slider
sampling intentionally retains its existing end-exclusive timeline policy; any future unification
must select the range policy explicitly rather than changing either behavior implicitly.

Commands that rebuild curves or disturb active keys must use
`animation_context.preserve_key_selection`. Channel-specific commands must operate on resolved
plugs, not every attribute on the selected object. Batch Maya calls where their semantics are
identical, and isolate failures per curve only as a fallback.

## Command lifecycle

- User-facing mutations run inside `tools.common.tool_operation` or the trigger dispatcher so
  undo, progress, cancellation, refresh suspension, and timeline tinting remain consistent.
- Query helpers do not open undo chunks or mutate selection.
- UI windows do not keep an undo chunk open while waiting for input.
- Runtime callbacks are registered and disconnected through the runtime manager and tracked
  connection helpers; owners must clean them up deterministically.
- Maya API 2.0 code belongs in a focused `core` service. Command modules orchestrate it rather
  than duplicating API math.

## Placement checklist

Before adding a function, choose its owner in this order:

1. Pure declarative value or asset path: `data`.
2. Reusable Qt presentation: `widgets`.
3. Reusable Maya/domain behavior used by multiple features: focused `core` module.
4. Behavior owned by one feature: `tools/<feature>` or `sliders`.
5. Toolbar, menu, hotkey, or feature assembly: composition module.
6. Existing external Maya entry point only: `mods` or `core.trigger`.

If two modules need the same implementation, move it to the narrowest common owner. Do not copy
the function, reach through one command module into another, or create a compatibility reroute.

## Migration and verification

Each architectural refactor must:

1. Move one coherent responsibility.
2. Update all repository imports and callbacks directly.
3. Remove the old implementation in the same change.
4. Preserve stable trigger command IDs when user-facing commands are renamed.
5. Compile the package, inspect imports affected by the move, and check the diff.

High-value remaining migrations are animation clipboard/bake behavior in `keyToolsMod`, tangent
commands split between `barMod` and `keyToolsMod`, composition modules currently under `core`,
and feature UI still embedded in legacy modules. These require focused follow-up changes rather
than forwarding layers.
