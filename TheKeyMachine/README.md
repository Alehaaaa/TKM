# TheKeyMachine

TheKeyMachine is a Maya animation toolset focused on fast key editing, selection workflows, copy/paste utilities, floating tools, and timeline-aware operations.

## Main Tool Areas

### Key Editing
- `Nudge Left / Nudge Right`: move selected keys in time, with insert/remove inbetween variants.
- `Share Keys`: unify keyed times across the selected objects.
- `reBlock`: rebuild selected animation onto a shared stepped timing structure.
- `Bake on Ones / Twos / Threes / Fours / Custom`: bake animation using fixed or custom sampling intervals.
- `Clear Selection`: clear selected keys.
- `Select Scene Anim`: select animation curves in the scene.

### Selection And Scene Tools
- `Select Rig Controls`: select rig controls, with animated-controls-only variant.
- `Isolate`: isolate current selection, with bookmark support and down-one-level option.
- `Create Locator`: create temporary locators, reselect them, or remove them.
- `Align`: match translation, rotation, scale, or full transforms, including range matching.
- `Tracer`: create and manage animation tracers, refresh them, toggle visibility, select offset objects, and switch styles.
- `Reset Values`: restore default values on current frame, selected keys, or ranges.
- `Delete Anim`: delete keys in the active time context.
- `Selector`: open a live selection list window.
- `Select Opposite`: select, add, or copy opposite-side naming matches.
- `Mirror`: mirror animation and manage mirror exceptions.
- `Select Hierarchy`: select hierarchy below the current object.

### Copy / Paste
- `Copy Pose / Paste Pose`: store and restore keyed values on the current frame.
- `Copy Animation / Paste Animation`: copy full animation data between matching controls.
- `Paste Insert`: insert copied animation at the current time.
- `Paste Opposite`: paste onto opposite-side controls.
- `Paste To`: paste copied animation onto a chosen target set.

### Offset And Pivot
- `Animation Offset`: keep a protected current frame and offset the rest of the keyed range.
- `Temp Pivot`: create a temporary manipulation pivot or reuse the last pivot.
- `Micro Move`: small transform stepping tool for precise adjustments.

### Linking And Space
- `Link Objects`: copy/paste relative links and optional auto-link callback behavior.
- `World Space`: copy or paste single-frame and range-based world-space motion.
- `Attribute Switcher`: floating tool for enum / attribute-based switching workflows.

### Floating Windows
- `Selection Sets`: create, recolor, rename, import/export, and manage scene selection sets.
- `Orbit`: floating orbit utility window with pinnable tools.
- `Graph Editor Toolbar`: compact tool window for key editing directly around Graph Editor workflows.
- `Custom Tools`: launch user tool integrations.
- `Custom Scripts`: launch user scripts integrations.
- `iBookmarks`: scene bookmark window.

## Timeline Feedback

Many tools tint the Maya time slider while they work. The tint color is driven by the section color, and the same color is also used for the pressed / checked state of section toolbuttons. Full-range tools tint the full slider holder, while range tools tint only the working range.

## Selection Sets

Selection Sets support:
- quick creation from the current selection
- automatic duplicate-content detection
- inline rename
- color families including gray, red, orange, yellow, green, blue, teal, purple, and pink
- scene import/export and quick-file import/export
- floating window and toolbar integration

## Integrated Tools Package

The codebase also includes dedicated tool modules under `tools/` for:
- `animation_offset`
- `attribute_switcher`
- `graph_toolbar`
- `ibookmarks`
- `micro_move`
- `orbit`
- `selection_sets`

These modules keep tool logic separated from the main toolbar assembly.

## Version

Current version: `0.1.83`

### 0.1.83 Highlights

- Added a centralized `TheKeyMachine.core.trigger` command layer for hotkeys, runtime commands, and scripted access.
- Added a dedicated hotkeys manager UI grouped by tool sections, with trigger-backed command assignment and Maya hotkey conflict detection.
- Expanded slider triggers to cover all button values, including `0%`.
- Unified tangent tools and graph-toolbar reset tools, including reset translations, rotations, scales, and full translation/rotation/scale reset.
- Improved timeline tint feedback for tangent and reset workflows.
