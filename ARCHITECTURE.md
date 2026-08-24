# TheKeyMachine command architecture

## One invocation, one operation

Every registered callback is executed by `core.trigger`. The dispatcher owns
the single `ToolOperation` for that user intention. A controller may report a
work total, status, affected time range, success, or cancellation through the
operation it receives; it must not create a competing execution path.

Widget-owned actions that are not registered commands enter through
`tools.common.run_tool_callback()`. `MenuWidget` does this automatically.
Raw Qt signal connections are reserved for view state and signal forwarding;
they do not call scene-mutating controllers directly.

Operation behavior is declared beside the tool metadata. A `ToolObject` may
set package-wide `OPERATION` defaults and an individual tool may override them
with its own `operation` mapping. This keeps policy out of widget code and
makes toolbar, menu, hotkey, shelf, and Search execution equivalent.

All actionable commands are timed. Progress remains hidden for the first
500 ms. If work continues, the shared adaptive progress display uses a known
work total or the command's learned duration to report an ETA. UI-only and
continuous interactive callbacks explicitly opt out.

## Animation context

Animation command packages declare `capture_animation_context`. Dispatch then
captures one immutable `SelectionSnapshot` before the command changes Maya:

- ordered objects
- Channel Box channels
- selected Graph Editor keys and tangent handles
- selected Graph Editor curves and outliner items
- highlighted Time Slider range
- current time
- playback range

Every later `animation.resolve_context()` call in that invocation reuses the
same snapshot. Controllers may request different target policies, but they do
not re-read changing UI selection state mid-command.

Resolved state is consumed through the `ToolContext` public properties
(`objects`, `plugs`, `curves`, `channels`, `selected_keys`, `time`,
`layer_scope`, `selection_snapshot`, and `source`). A tool that needs a
derived scope calls `ToolContext.replace(...)`; it does not convert the
context to a plain dictionary, mutate internal storage keys, or invent a new
field name.

## Execution threads

Maya commands and OpenMaya scene access remain on Maya's main thread. Long
operations run only their coordinator or I/O work on a worker. Scene queries
and edits cross back through `ToolOperation.run_on_main()` in bounded batches.
This keeps painting, delayed progress, ETA updates, and cancellation responsive
without pretending Maya scene work is thread-safe.

Known-small coordinators run inline through the same `run_worker()` entry point
to avoid thread startup and signal-marshalling overhead. Unknown workloads and
I/O remain threaded. Controllers batch scene work before crossing to Maya;
threading is selected for responsiveness, while batching and OpenMaya provide
the actual scene-processing speedup.

Because a worker-backed operation keeps Qt responsive, another toolbar or
hotkey invocation can arrive before it finishes. Dispatch queues that command
FIFO and starts it only after the active operation has completed all undo,
refresh, tint, and selection cleanup. Ordinary queued invocations remain
separate undo steps and capture animation context only when they start after
cleanup, so they cannot snapshot a transient selection from the active edit.
Operations are never nested.

Commands may explicitly declare a signed accumulation group. Nudge starts its
first edit immediately with no debounce or settle delay. Compatible input that
arrives while it runs is reduced in the pending queue in O(1), and opposite
input cancels. The pending net movement starts immediately after cleanup and
resolves a fresh context, never a transient mid-edit selection. Nudge suspends
viewport refresh within each edit, so collision resolution and that edit's
movement are presented as one redraw.

Time Slider paint suppression uses the Qt widget's `setUpdatesEnabled()`;
it never toggles Maya `timeControl(manage)`, which would hide the control and
change its layout. Nudge playhead changes use `currentTime(update=False)` to
avoid an intermediate model/display evaluation. When Graph Editor keys are
active and editable, nudge submits Maya's complete active keyset through one
native `keyframe(animation="keys")` edit rather than updating each curve and
its editor selection connection separately.

Repeated scene work enters through `ToolOperation.process()`. A controller
passes immutable work items, one batch-edit function, a batch size, and an
execution strategy. The operation owns workload sizing, adaptive thread use,
main-thread crossings, cancellation, and progress. Maya-only commands may use
the `main` strategy for minimum wall time; long operations use bounded `worker`
coordination so delayed ETA and cancellation remain responsive.

Update metadata and archive transfer use this same path: network and file I/O
run on a worker, while progress updates are marshalled through the operation.

## Interactive tools

Sliders and persistent tools use a longer lifecycle than a one-shot command:
begin, snapshot, update, and commit or cancel. They still share the animation
resolver and timing rules, but must not start a worker for every mouse event.
Slow live updates fall back to apply-on-release through `SlowOperationGuard`.

Only three implementation paths own these non-dispatch lifecycles:
Animation Offset while enabled, a slider session during one gesture, and a
Global Curve edit originating from Maya. Every one-shot tool uses dispatch.

Maya-originated edit callbacks such as Global Curve are also operation
boundaries when no command is active. If they fire during an existing command,
they reuse that command's operation instead of nesting another lifecycle.

## Saved-data boundaries

Pose, animation, and animation-layer payloads accept only their declared
current schema. Readers do not carry transitional layouts or silently migrate
old files. Cross-tool conversion that remains a product feature is explicit;
Selection Sets' animBot conversion is a named import path, not a general
legacy-data fallback.
