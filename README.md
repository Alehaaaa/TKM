<p align="center">
  <img width="269px" align="center" src="./TheKeyMachine/data/icons/TheKeyMachine_logo_500.png" alt="TheKeyMachine Logo" />
</p>

# TheKeyMachine

**The Open Source Animation toolbar for Autodesk Maya.**

![Version](https://img.shields.io/badge/version-0.1.39-blue.svg)

TheKeyMachine (TKM) is a Maya toolbar for Animation. Change timing, posing, curve editing, selection, mirroring, pivots, and space switches.

Supports Maya 2022+ on Windows, Linux, and macOS.

[Website](https://www.thekeymachine.xyz) · [Documentation](https://thekeymachine.gitbook.io/base) · [Discord](https://discord.gg/G2J5yyjz)

This independent fork is maintained by [Alehaaaa](https://alehaaaa.github.io). The original tool was created by [Rodrigo Torres](https://www.rodritorres.com). Issues and support here apply to this version.

<img src="./TheKeyMachine/data/icons/toolbar_example.png" />

## Complete Tool Reference

This list follows the toolbar from left to right. Clicking runs the main action. Menus and modifier keys provide additional modes. Tools can also be pinned, assigned a hotkey, or added to a Maya shelf.

The **TKM menu** comes first: layout and docking, Workspaces, Hotkeys, languages, tooltips, Start with Maya, toolbar toggle/reload/unload/uninstall, shelf setup, updates, Bug Report, Version History, About, Donate, documentation, community links, and debug tools.

<details>
<summary><b>Timing & Keys</b>: Nudge, Default, Bake, Key Sync</summary>

- **Nudge:** Nudge Left/Right, all-keys and scene modes, plus Insert/Remove Inbetween.
- **Default:** Reset the full pose or only translate, rotate, scale, or TRS. Saved defaults can be removed per selection or cleared entirely.
- **Bake:** Bake on ones, twos, threes, fours, a custom step, or the timing of the last selected control.
- **Key Sync:** Share Keys, Share From Last Selected, Reblock, and Reblock Insert.

</details>

<details>
<summary><b>Sliders</b>: Blend, Tween, Tangent</summary>

- **Blend Sliders:** Connect to Neighbors, Ease, Gap Stitcher, Noise/Wave, Pull/Push, Simplify/Bake, Smooth/Rough, Time Offset, Stagger, and scaling from the average, default, frame, or either neighbor.
- **Tween Sliders:** Tweener; blends to Buffer, Default, Ease, Frame, Neighbors, Infinity, or Undo; plus World Space versions of Tweener, Frame, Neighbors, and Infinity.
- **Tangent Sliders:** Blend toward Best Guess, Polished, Flow, Bounce, Auto, Spline, Clamped, Linear, Flat, or Plateau.

</details>

<details>
<summary><b>Selection & Scene Setup</b>: Isolate, Locators, Selection</summary>

- **Isolate:** Isolate controls, step down a hierarchy level, and save isolate bookmarks.
- **Locators:** Create, select, and remove temporary locators.
- **Selection:** Selector, Select Hierarchy, Select Rig Controls, and Select Animated Rig Controls.

</details>

<details>
<summary><b>Opposites, Mirror & Align</b></summary>

- **Opposite:** Select, add, or copy the matching control on the other side.
- **Mirror:** Mirror poses or animation, send motion left/right, mirror all keys, and manage Invert/Keep exceptions.
- **Align:** Match the full transform, translation, rotation, or scale in the current context or across all keys.

</details>

<details>
<summary><b>Pose, Animation & Tangents</b></summary>

- **Pose & Animation:** Copy/Paste Pose, Mirror Pose, Pose To, Copy Animation, Replace, Insert, Mirror Animation, Animation To, and clip import/export.
- **Tangents:** Bouncy, Auto, Spline, Clamped, Linear, Flat, Step, and Plateau, with handle, endpoint, all-key, and Maya-default modes. Cycle Matcher closes values, tangents, or both.
- **Manipulators:** Smart Rotation and Smart Translation.

</details>

<details>
<summary><b>Movement, Pivots & Cameras</b></summary>

- **Animation Offset:** Keep the current pose while offsetting the animation around it.
- **Movers:** Micro Move for precise translate/rotate work; Depth Mover for pushing controls toward or away from camera.
- **Temp Pivot:** Last Object, Centered, World Space, Edit, and Reset.
- **Follow Cam:** Create or remove a camera that follows translation, rotation, or both.

</details>

<details>
<summary><b>Relationships & Rig Switching</b></summary>

- **Relationships & Worldspace:** Copy/Paste Relationship, Paste to Range, Auto Link, and World Space copy/paste for a frame or animation range.
- **Attribute Switcher:** Switch enum and driven attributes without pops. The same section includes Gimbal Fixer.

</details>

<details>
<summary><b>Selection Sets</b></summary>

Colored sets, inline rename, duplicate checks, clear all, and quick or regular import/export.

</details>

<details>
<summary><b>Viewport & Tracing</b>: Orbit, Tracer</summary>

- **Orbit:** Quick orbit mode and a floating Orbit window.
- **Tracer:** Create, refresh, show/hide, recolor, offset, auto-update, or remove a motion tracer.

</details>

<details>
<summary><b>Graph & Curve Tools</b></summary>

- **Global Tools:** Auto Euler Filter, Overshoot Sliders, and the Graph Editor Toolbar.
- **Graph Tools:** Select Object from Curve, Isolate, Flip, Overlap, Mute, Lock, Match Curves, and Graph Filter controls.
- **Anim Curve Tools:** Smart Key, Smart Key All Channels, Smart Euler Filter, Snap, Reverse, Clear, Crop, redundant/static cleanup, Copy/Cut/Delete/Paste/Paste Relative, key/frame navigation, scene animation selection, and delete-before/after-current-frame.

</details>

<details>
<summary><b>Custom, Safety & Search</b></summary>

- **Custom Tools:** Add commands and folders, then pin them, assign hotkeys, or add shelf buttons.
- **Snapshot:** Capture the rig's Default, Opposite, and Mirror behavior.
- **Background Runners:** Optional Channel Box highlighting/clearing, camera orbit, static-curve hiding, recovery, anim-layer weights, and selected-object display.
- **Animation Recovery:** Automatic shot checkpoints. Restore the full checkpoint or only selected controls.
- **Search:** Search and run any registered tool.

</details>

Floating windows include Selection Sets, Orbit, Search, Graph Editor Toolbar, Isolate Bookmarks, Attribute Switcher, Gimbal Fixer, Workspaces, Hotkeys, and Animation Recovery.

## Timeline Feedback

Tools that operate over time tint the affected part of the Time Slider. Full-animation operations tint the full range. Selected-range operations tint only the affected frames. The tint color matches the toolbar section.

## Tooltips And Menus

Tooltips explain what each tool does, which modifier shortcuts and modes are available, and anything worth knowing before running it. Some tools also include short demo clips and extra usage notes.

The same information is available from toolbar buttons, menus, torn-off menus, and shelf buttons.

---

**AI disclosure:** Portions of this codebase, including this README, have been written with the assistance of AI tools (Claude and Codex), with all changes reviewed
