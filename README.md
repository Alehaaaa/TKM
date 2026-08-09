<p align="center">
  <img width="269px" align="center" src="./TheKeyMachine/data/icons/TheKeyMachine_logo_500.png" alt="TheKeyMachine Logo" />
</p>

# TheKeyMachine, animation toolbar

![Version](https://img.shields.io/badge/version-0.1.36-blue.svg)

Maintained by <b>Alehaaaa</b> at <a href="https://alehaaaa.github.io">alehaaaa.github.io</a>. Originally developed by <b>Rodrigo Torres</b> at <a href="https://www.rodritorres.com">rodritorres.com</a>.

This is an independent fork. Issues and support apply only to this version.

TheKeyMachine (TKM) is an open-source animation toolset for Autodesk Maya, designed to speed up keyframe editing, improve selection workflows, simplify copy-and-paste operations, provide floating tools, and support timeline-aware animation tasks.

Supports Maya 2022+ on Windows, Linux, and macOS.

<a href="https://www.thekeymachine.xyz">thekeymachine.xyz</a>


<img src="./TheKeyMachine/data/icons/toolbar_example.png" />

## Main Tool Areas

<details>
<summary><b>Key Editing</b></summary>

| Tool | What it does |
|---|---|
| `Nudge Left / Nudge Right` | Move selected keys in time, including insert/remove inbetween variants |
| `Share Keys` | Unify keyed times across selected objects |
| `reBlock` | Rebuild selected animation onto a shared stepped timing structure |
| `Bake on Ones / Twos / Threes / Fours / Custom` | Fixed or custom sampling |
| `Clear Selection` | Remove key selection quickly |
| `Select Scene Anim` | Collect animation curves from the scene |
| `Anim Curve Tools` | Use selected objects and animation layers, prioritize highlighted Time Slider ranges, and include layer-weight animation |
| Copy / Cut / Crop | Share a tangent-aware clipboard; paste supports Graph Editor anchors, channel remapping, and relative value offsets |
| `Set Smart Key` | For animated curves, selected channels, Graph Editor keys, highlighted ranges, exact subframes, and unanimated objects in mixed selections |
| `Smart Euler Filter` | Redundant-key removal and static-curve cleanup that respect the active selection context |
| `Snap Keys` | Uses selected objects and animation layers (including layer-weight keys), prioritizes the highlighted Time Slider range, and merges multiple subframe keys into the closest whole-frame key |

Nudge, inbetween, bake, tangent, and background-runner actions use clearer toolbar icons.

</details>

<details>
<summary><b>Tangents</b></summary>

- Tangent buttons support modifier-click variants for Maya default tangent and all-keys operations
- Stepped tangent menus focus on stepped-safe actions
- Slider mode menus stay connected to visible modes, including torn-off menus and live pin/default changes

</details>

<details>
<summary><b>Selection And Scene Tools</b></summary>

| Tool | What it does |
|---|---|
| `Select Rig Controls` | Includes animated-controls-only variants |
| `Isolate` | Bookmark support and down-one-level options |
| `Create Locator` | Quick temporary setup work |
| `Align` | Translation, rotation, scale, full transform, and matching only the reference object's real keys across a selected range |
| `Tracer` | Animation tracing, refresh, visibility, and style switching |
| `Default Values` | On the current frame, selected keys, or ranges |
| `Clear Animation` | In the active time context |
| `Selector` | A live selection list window |
| `Select Opposite` / `Mirror` | Side-based workflows |
| `Select Hierarchy` | Deeper rig selection |

</details>

<details>
<summary><b>Copy / Paste</b></summary>

| Tool | What it does |
|---|---|
| `Copy Pose / Paste Pose` | Current-frame value transfer |
| `Copy Animation / Paste Animation` | Between matching controls |
| `Paste Insert` | Place copied animation at the current time |
| `Paste Opposite` | Mirrored transfers |
| `Paste To` | Chosen target sets |

</details>

<details>
<summary><b>Offset And Pivot</b></summary>

| Tool | What it does |
|---|---|
| `Animation Offset` | Protect the current frame while offsetting the surrounding range |
| `Temp Pivot` | Create or reuse a temporary manipulation pivot |
| `Micro Move` | Live, object-oriented precision translation and rotation with cursor acceleration |
| `Depth Mover` | Push selected controls toward or away from the camera with drag-adjusted sensitivity |

</details>

<details>
<summary><b>Linking And Space</b></summary>

| Tool | What it does |
|---|---|
| `Link Objects` | Relative links and optional auto-link behavior |
| `World Space` | Samples every frame in the selected or visible playback range, supports one-to-many pastes, and preserves animation outside the pasted range |
| `Attribute Switcher` | Enum and attribute-driven switching, drag-release popup choices, and compact scrolling that expands only when the screen-limited content requires it |

</details>

<details>
<summary><b>Animation Recovery</b></summary>

`Animation Recovery` is an optional background runner that keeps lightweight, scene-specific checkpoints when animation, transform channels, enum controls, or hierarchy changes are detected. It also creates a distinct checkpoint whenever the Maya scene is saved.

The recovery window lists the newest changes first with their source scene, date, reason, current frame, playback and animation ranges, and selection count. Recover with nothing selected to restore all captured animation and channel values, or select controls first to restore only those controls and their animation. Recovery runs through the standard cancellable operation system with automatic ETA feedback and does not create another checkpoint when a saved point is applied.

Most checkpoints store only their changed data. Periodic complete baselines bound replay time, while parent-linked checkpoints detect missing history instead of silently producing an incomplete result. The newest 20 complete baseline generations are retained per scene, keeping history bounded without orphaning deltas. When a point is recovered, the shortest complete chain is merged to rebuild the requested animation state. Each scene keeps a persistent recovery identity across Save, Save As, and incremental saves, with compact recovery files stored separately under `TheKeyMachine_user_data/animation_recovery/`.

When a scene is opened with the same recovery identity but an older saved-file time than its newest checkpoint, the recovery window opens automatically so the newer animation can be reviewed or restored.

</details>

<details>
<summary><b>Floating Windows</b></summary>

- `Selection Sets`
- `Orbit`
- `Search`
- `Graph Editor Toolbar`
- `Isolate Bookmarks`

</details>

## Timeline Feedback

Many tools tint the Maya time slider while they run. Full-range tools tint the full slider holder, while range-based tools tint only the working range. Tints inherit the owning toolbar section color, keeping related operations visually consistent.

## Tooltips And Menus

Tooltips use the active tool labels and icons, including torn-off menus and shelf buttons. Menu actions keep their full rich tooltip content while hovering, so videos, media, and multi-line help remain available from menu-driven tools.

The `Custom Tools` menu loads manifest-defined commands, folders, Maya resource icons, toolbar pins, hotkeys, and shelf buttons.

## Selection Sets

Selection Sets support:

- quick creation from the current selection
- duplicate-content detection
- inline rename
- multiple color families
- scene import/export and quick-file import/export
- floating window and toolbar integration

---

**AI disclosure:** Portions of this codebase, including this README, have been written with the assistance of AI coding tools (Claude and Codex), with all changes reviewed by the maintainer.
