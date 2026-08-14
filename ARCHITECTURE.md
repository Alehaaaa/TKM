# TheKeyMachine architecture

This document is the contract for new code and refactors. Every responsibility has one
canonical owner; internal compatibility modules and forwarding imports are not retained.

## Package roles

### `data`

Declarative values and asset lookup only. `data` is a leaf package: it may use the Python
standard library and import another `data` module, but it must not import Maya, Qt, `core`,
`maya`, `ui`, or `tools`. Color definitions and lightweight media references
belong here; widgets that render them do not.

### `core`

Application infrastructure and cross-feature policy. `application` owns installation paths,
version information, startup integration, and uninstall behavior; `settings` owns persistence;
`runtime` owns application lifecycle; `trigger` owns command dispatch; `i18n` owns translation
lookup; and `workspaces` owns global workspace state. Presentation does not live in `core`.

### `maya`

Focused integration with Maya APIs and scene state. Selection queries, shelf integration, and
shared animation context, curve, graph, and animation-layer behavior live here. These modules
provide domain operations to features without owning feature-specific commands or dialogs.

### `ui`

Shared interface infrastructure. `ui.widgets` owns reusable Qt components, `ui.sliders` owns
slider presentation models, `ui.tooltips` owns tooltip presentation, and `ui.toolbar_modes`
owns toolbar display policy. Shared interface translations live in `ui/lang.json`.
Feature-specific dialogs and widgets stay inside their `tools/<feature>` package; shared slider
targeting, writing, session, and math behavior lives in `tools/sliders`.

### `tools/<feature>`

Feature implementations. A feature keeps its command callbacks, controllers, dialogs,
widgets, constants, and private helpers together. `api.py` is reserved for actual external
commands or callback adaptation; it must not mirror its controller. Application composition
may call a feature controller directly when that controller owns the required state.

## Dependency rules

The intended dependency flow is:

```text
data <- core / maya <- ui / tools <- application composition
```

The arrows mean “may be imported by.” Feature UI can depend on shared widgets, and composition
modules can depend on every feature they assemble. The following rules are stricter than the
diagram:

- `data` is dependency-free as defined above.
- Focused low-level `core` services do not import feature command implementations.
- `tools/<feature>` packages do not import internals from sibling features.
- `maya` modules expose focused Maya-domain operations and do not own feature UI.
- Shared Qt infrastructure belongs under `ui`; feature UI belongs with its tool.
- Local imports may break a real UI ownership cycle, but must resolve the canonical module.
- Import the module that owns the behavior, not a transitive re-export.

Dependency violations are defects. Fix them atomically; do not introduce forwarding wrappers
or duplicate implementations.

## Naming and public APIs

- Modules, packages, functions, methods, and variables use `snake_case`.
- Classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- Private implementation names start with `_`; public names describe behavior, not UI labels.
- Feature packages expose external commands from `api.py` without mirroring controllers.
- Shared modules use domain names such as `maya.animation` or `maya.runtime`, not generic
  buckets such as `utils2`, `misc`, or `helpers`.
- Shelf and hotkey commands use command IDs in `core.trigger`, separate from Python function
  names.
- Rename a Python symbol only when all repository call sites are updated in the same change.
  Do not leave a function whose body only calls the renamed function.

### Boundary functions

Call the owning function directly. A forwarding function is allowed only when it adds at least
one real boundary behavior:

- binds arguments, configuration, or a feature owner;
- adapts a callback protocol or public signature;
- applies validation, lifecycle, undo, dispatch, or error policy; or
- resolves an active application instance for a stable external command ID.

A function that only returns or invokes another callable with the same arguments is redundant.
Replace its callers with the owning callable and delete it. If the forwarded implementation has
the wrong public name, rename that implementation instead of adding a second entry point.

All project-owned module paths use `snake_case`. Host-specific Maya and Qt adaptation may remain;
project-internal compatibility paths may not.

## Animation context contract

Animation target selection and time selection are related but distinct. Commands use
`maya.animation.context` instead of querying Maya UI elements independently.

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

`ui.widgets.timeline.TimeContext` represents the result. Command ranges are inclusive. Slider
sampling intentionally retains its existing end-exclusive timeline policy; any future unification
must select the range policy explicitly rather than changing either behavior implicitly.

Commands that rebuild curves or disturb active keys must use
`maya.animation.context.preserve_key_selection`. Channel-specific commands must operate on resolved
plugs, not every attribute on the selected object. Batch Maya calls where their semantics are
identical, and isolate failures per curve only as a fallback.

## Scene nodes

Any tool that needs a persistent node in the scene creates and looks it up through
`maya.runtime.TkmSceneNode` instead of hand-rolling its own `objExists` / `createNode` /
`parent` / attribute-locking calls.

`TkmSceneNode.root()` returns TheKeyMachine's single root node, creating it if missing.
The root **only ever parents other tools' nodes** and must never carry tool-owned data or be
deleted by a tool: `set_attr` and `delete` on the root both raise. A tool that needs its own
persistent node or a scene-scoped attribute creates a child with `root().child(name, ...)` and
reads/writes that child instead — see `tools.animation_recovery.controller` for the pattern
(its scene-ID attribute lives on its own `Animation_Recovery` child node, not on the root).

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
2. Reusable Qt presentation or interaction: `ui`.
3. Reusable Maya/domain behavior used by multiple features: focused `maya` module.
4. Behavior owned by one feature: `tools/<feature>`.
5. Toolbar, menu, hotkey, or feature assembly: composition module.
6. Stable external command entry point: `core.trigger`.

If two modules need the same implementation, move it to the narrowest common owner. Do not copy
the function, reach through one command module into another, or create a compatibility reroute.

## Refactoring and verification

Each architectural refactor must:

1. Move one coherent responsibility.
2. Update all repository imports and callbacks directly.
3. Remove the old implementation in the same change.
4. Preserve stable trigger command IDs when user-facing commands are renamed.
5. Compile the package, inspect imports affected by the move, and check the diff.

Future refactors should reduce cross-layer imports by moving behavior to its narrowest owner,
not by introducing forwarding modules or compatibility packages.
