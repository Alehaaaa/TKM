"""Viewport 2.0 render override used by the Onion Skin tool.

The override caches the selected objects into per-frame color targets, then
composites requested relative and absolute frames over Maya's normal scene.
It deliberately uses the API surface available in Maya 2019 and avoids Qt.

The render-target approach is adapted from OnionSkinRenderer, copyright 2017
Viele, used under the MIT license included with this package.
"""

from __future__ import absolute_import

import collections
import os

import six
from maya.api import OpenMaya as om  # type: ignore
from maya.api import OpenMayaRender as omr  # type: ignore

from TheKeyMachine.maya import maya_api
from TheKeyMachine.tools.onion_skin import diagnostics


DISPLAY_STYLES = {"shaded": 0, "shape": 1, "outline": 2}
BUFFER_MEMORY_BUDGET = 256 * 1024 * 1024
MIN_BUFFER_FRAMES = 5
# In-between ghosts fade toward the key they lead into; this keeps the
# brightest one still visibly softer than the key ghost itself.
INBETWEEN_DAMPEN = 0.65
MAX_INBETWEEN_COUNT = 4


def _refresh_viewport():
    try:
        renderer = omr.MRenderer.theRenderer()
        if renderer is not None:
            renderer.setGeometryDrawDirty(None)
    except Exception:
        pass
    try:
        from maya import cmds

        cmds.refresh(force=True)
    except Exception:
        pass


class _TargetOperationMixin(object):
    def _init_target(self):
        self._target = None

    def targetOverrideList(self):
        return [self._target] if self._target is not None else None

    def set_render_target(self, target):
        self._target = target


class ClearOperation(_TargetOperationMixin, omr.MClearOperation):
    def __init__(self, name):
        omr.MClearOperation.__init__(self, name)
        self._init_target()


class HudOperation(_TargetOperationMixin, omr.MHUDRender):
    def __init__(self):
        omr.MHUDRender.__init__(self)
        self._init_target()


class PresentOperation(_TargetOperationMixin, omr.MPresentTarget):
    def __init__(self, name):
        omr.MPresentTarget.__init__(self, name)
        self._init_target()


class SceneOperation(_TargetOperationMixin, omr.MSceneRender):
    def __init__(self, name, clear_mask, selection_only=False):
        omr.MSceneRender.__init__(self, name, "Onion Skin")
        self._init_target()
        self._clear_mask = clear_mask
        self._selection_only = bool(selection_only)
        self._objects = om.MSelectionList()

    def objectSetOverride(self):
        return self._objects if self._selection_only else None

    def set_objects(self, objects):
        self._objects = objects

    def clearOperation(self):
        operation = self.mClearOperation
        operation.setClearColor((0.0, 0.0, 0.0, 0.0))
        operation.setMask(self._clear_mask)
        return operation

    def renderFilterOverride(self):
        return omr.MSceneRender.kRenderShadedItems if self._selection_only else omr.MSceneRender.kNoSceneFilterOverride


class BlendOperation(_TargetOperationMixin, omr.MQuadRender):
    _EXTENSIONS = {
        omr.MRenderer.kOpenGL: ".cgfx",
        omr.MRenderer.kOpenGLCoreProfile: ".ogsfx",
        omr.MRenderer.kDirectX11: ".fx",
    }

    def __init__(self, name, frame_key, owner):
        omr.MQuadRender.__init__(self, name)
        self._init_target()
        self.frame_key = int(frame_key)
        self.owner = owner
        self.opacity = 0.5
        self.tint = (1.0, 1.0, 1.0, 1.0)
        self.active = False
        self._inputs = [None, None]
        self._stencil = None
        self._shader = None
        self._shader_attempted = False
        self._parameter_error = False

    def release(self):
        if self._shader is None:
            return
        try:
            manager = omr.MRenderer.getShaderManager()
            if manager is not None:
                manager.releaseShader(self._shader)
        except Exception:
            pass
        self._shader = None

    def shader(self):
        if not self.active:
            return None
        if self._shader is None and not self._shader_attempted:
            extension = self._EXTENSIONS.get(omr.MRenderer.drawAPI(), ".ogsfx")
            shader_name = "onion_skin{}".format(extension)
            self._shader_attempted = True
            try:
                manager = omr.MRenderer.getShaderManager()
                self._shader = manager.getEffectsFileShader(
                    shader_name, "Main", useEffectCache=False
                )
                diagnostics.log(
                    "shader loaded",
                    operation=self.frame_key,
                    shader=shader_name,
                    success=self._shader is not None,
                )
            except Exception as exc:
                diagnostics.log_error(
                    "shader load failed",
                    exc,
                    operation=self.frame_key,
                    shader=shader_name,
                )
                return None
        if self._shader is None:
            return None
        try:
            self._shader.setParameter("gSourceTex", self._inputs[0])
            self._shader.setParameter("gSourceTex2", self._inputs[1])
            self._shader.setParameter("gStencilTex", self._stencil)
            self._shader.setParameter("gBlendSrc", self.opacity * self.owner.global_opacity)
            self._shader.setParameter("gTint", self.tint)
            self._shader.setParameter("gType", self.owner.display_style)
            self._shader.setParameter("gOutlineWidth", self.owner.outline_width)
            self._shader.setParameter("gDrawBehind", int(self.owner.draw_behind))
            self._parameter_error = False
        except Exception as exc:
            if not self._parameter_error:
                diagnostics.log_error(
                    "shader parameter update failed", exc, operation=self.frame_key
                )
            self._parameter_error = True
            return None
        return self._shader

    def clearOperation(self):
        self.mClearOperation.setMask(omr.MClearOperation.kClearNone)
        return self.mClearOperation

    def configure(self, scene_target, onion_target, stencil_target, opacity, tint):
        self._inputs = [scene_target, onion_target]
        self._stencil = stencil_target
        self.opacity = float(opacity)
        self.tint = tuple(tint)
        self.active = onion_target is not None


class OnionSkinRenderOverride(omr.MRenderOverride):
    """One reload-safe VP2 override shared by the Onion Skin manager."""

    def __init__(self, name):
        omr.MRenderOverride.__init__(self, name)
        self._override_name = six.text_type(name)
        self._registered = False
        self._operation_index = 0
        self._callbacks = []
        self._camera_callbacks = []
        self._object_names = []
        self._object_list = om.MSelectionList()
        self._targets = {}
        self._target_queue = collections.deque()
        self._relative_blends = {}
        self._absolute_blends = {}
        self._inbetween_blends = {}

        self.relative_frames = [-2, -1, 1, 2]
        self.relative_opacities = {}
        self.absolute_frames = []
        self.absolute_opacities = {}
        self.past_color = (0.28, 0.82, 0.59, 1.0)
        self.future_color = (0.93, 0.39, 0.39, 1.0)
        self.absolute_color = (0.39, 0.59, 0.96, 1.0)
        self.display_style = 1
        self.global_opacity = 0.7
        self.outline_width = 3
        self.draw_behind = True
        self.relative_to_keys = False
        self.relative_step = 1
        self.max_buffer_size = 200
        self.auto_clear_buffer = True
        self.ghost_inbetweens = False
        self.inbetween_count = 1

        self._clear = ClearOperation("tkmOnionClear")
        # Preserve the model panel's gradient or solid background color.
        self._clear.setOverridesColors(False)
        self._scene = SceneOperation("tkmOnionScene", omr.MClearOperation.kClearNone)
        self._capture = SceneOperation(
            "tkmOnionCapture", omr.MClearOperation.kClearAll, selection_only=True
        )
        self._hud = HudOperation()
        self._present = PresentOperation("tkmOnionPresent")
        self._operations = [self._clear, self._scene, self._capture, self._hud, self._present]

        self._scene_description = omr.MRenderTargetDescription()
        self._scene_description.setName("tkmOnionSceneTarget")
        self._scene_description.setRasterFormat(omr.MRenderer.kR8G8B8A8_UNORM)
        self._frame_description = omr.MRenderTargetDescription()
        self._frame_description.setName("tkmOnionFrameTarget")
        self._frame_description.setRasterFormat(omr.MRenderer.kR8G8B8A8_UNORM)
        self._target_manager = None
        self._scene_target = None
        self._last_debug_setup = None
        self._target_size = None
        self._effective_buffer_size = self.max_buffer_size
        self._capture_pending = True
        self._relative_target_cache_key = None
        self._relative_target_cache = None

    def uiName(self):
        return "TKM Onion Skin"

    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def is_registered(self):
        return bool(self._registered)

    def register(self):
        if self._registered:
            diagnostics.log("register skipped", reason="already registered")
            return
        shader_path = os.path.join(os.path.dirname(__file__), "shaders")
        diagnostics.log(
            "register started",
            draw_api=omr.MRenderer.drawAPI(),
            shader_path=shader_path,
        )
        try:
            self._ensure_resources()
            shader_manager = omr.MRenderer.getShaderManager()
            shader_manager.addShaderPath(shader_path)
        except Exception as exc:
            diagnostics.log_error("render resources unavailable", exc)
            raise
        try:
            existing = omr.MRenderer.findRenderOverride(self._override_name)
            if existing is not None and existing is not self:
                diagnostics.log("stale override removed", override=self._override_name)
                omr.MRenderer.deregisterOverride(existing)
        except Exception as exc:
            diagnostics.log_error("stale override check failed", exc)
        try:
            omr.MRenderer.registerOverride(self)
        except Exception as exc:
            diagnostics.log_error("override registration failed", exc)
            raise
        self._registered = True
        self._install_callbacks()
        diagnostics.log("override registered", override=self._override_name)

    def deregister(self):
        if self._registered:
            try:
                omr.MRenderer.deregisterOverride(self)
            except Exception as exc:
                diagnostics.log_error("override deregistration failed", exc)
        self._registered = False
        self._remove_callbacks()
        self.clear_buffer(refresh=False)
        for blend in (
            list(self._relative_blends.values())
            + list(self._absolute_blends.values())
            + list(self._inbetween_blends.values())
        ):
            blend.release()
        self._relative_blends.clear()
        self._absolute_blends.clear()
        self._inbetween_blends.clear()
        if self._scene_target is not None and self._target_manager is not None:
            try:
                self._target_manager.releaseRenderTarget(self._scene_target)
            except Exception:
                pass
        self._scene_target = None
        diagnostics.log("override deregistered", override=self._override_name)

    def setup(self, _destination):
        self._ensure_resources()
        size = omr.MRenderer.outputTargetSize()
        self._update_target_size(size)

        current_time = maya_api.current_time()
        if current_time is None:
            diagnostics.log("setup skipped", reason="current time unavailable")
            return
        current_frame = float(current_time)
        targets = self._resolve_relative_targets(current_frame)
        inbetweens = self._resolve_inbetween_targets(current_frame, targets)
        for target_frame in targets.values():
            self._touch_target(target_frame)
        for frame in self.absolute_frames:
            self._touch_target(float(frame))
        for target_frame, _fraction in inbetweens.values():
            self._touch_target(target_frame)

        current_target, capture_pending = self._target_for_frame(current_frame)
        if current_target is None:
            diagnostics.log(
                "setup skipped", frame=current_frame, reason="frame target unavailable"
            )
            return
        self._capture.set_render_target(current_target)
        self._capture.set_objects(self._object_list)

        active_relative = []
        missing_relative = []
        for frame_key, target_frame in targets.items():
            blend = self._relative_blends.get(frame_key)
            if blend is None:
                continue
            tint = self.past_color if target_frame < current_frame else self.future_color
            target = self._targets.get(target_frame)
            if target is None:
                missing_relative.append(target_frame)
            else:
                active_relative.append(target_frame)
            opacity = self.relative_opacities.get(frame_key, 50) / 100.0
            blend.configure(self._scene_target, target, current_target, opacity, tint)

        active_absolute = []
        missing_absolute = []
        for frame, blend in self._absolute_blends.items():
            target = self._targets.get(float(frame))
            if target is None:
                missing_absolute.append(frame)
            else:
                active_absolute.append(frame)
            opacity = self.absolute_opacities.get(frame, 50) / 100.0
            blend.configure(self._scene_target, target, current_target, opacity, self.absolute_color)

        active_inbetween = []
        missing_inbetween = []
        for key, (target_frame, fraction) in inbetweens.items():
            blend = self._inbetween_blends.get(key)
            if blend is None:
                continue
            side, _index = key
            tint = self.past_color if side < 0 else self.future_color
            target = self._targets.get(target_frame)
            if target is None:
                missing_inbetween.append(target_frame)
            else:
                active_inbetween.append(target_frame)
            base_opacity = self.relative_opacities.get(side, 50) / 100.0
            opacity = base_opacity * fraction * INBETWEEN_DAMPEN
            blend.configure(self._scene_target, target, current_target, opacity, tint)

        self._capture_pending = capture_pending
        self._compose_operations()

        if diagnostics.enabled():
            debug_signature = (
                current_frame,
                tuple(self._object_names),
                tuple(active_relative),
                tuple(missing_relative),
                tuple(active_absolute),
                tuple(missing_absolute),
                tuple(active_inbetween),
                tuple(missing_inbetween),
                size[0],
                size[1],
            )
            if debug_signature != self._last_debug_setup:
                self._last_debug_setup = debug_signature
                cached_frames = sorted(self._targets)
                diagnostics.log(
                    "frame setup",
                    frame=current_frame,
                    objects=self._object_names,
                    viewport="{}x{}".format(size[0], size[1]),
                    cached_frame_count=len(cached_frames),
                    cached_frame_range=(
                        (cached_frames[0], cached_frames[-1]) if cached_frames else None
                    ),
                    target_frames=dict(sorted(targets.items())),
                    buffer_capacity=self._effective_buffer_size,
                    captured_current=capture_pending,
                    active_relative=active_relative,
                    waiting_relative=missing_relative,
                    active_held=active_absolute,
                    waiting_held=missing_absolute,
                    active_inbetween=active_inbetween,
                    waiting_inbetween=missing_inbetween,
                )

    def cleanup(self):
        return None

    def startOperationIterator(self):
        self._operation_index = 0
        return True

    def renderOperation(self):
        return self._operations[self._operation_index]

    def nextRenderOperation(self):
        self._operation_index += 1
        return self._operation_index < len(self._operations)

    def _target_for_frame(self, frame):
        frame = float(frame)
        target = self._targets.get(frame)
        self._frame_description.setName("tkmOnionFrame{}".format(str(frame).replace("-", "m").replace(".", "_")))
        created = target is None
        if target is None:
            target = self._target_manager.acquireRenderTarget(self._frame_description)
            if target is None:
                diagnostics.log("frame target failed", frame=frame)
                return None, False
            self._targets[frame] = target
            self._touch_target(frame)
            while len(self._target_queue) > self._effective_buffer_size:
                self._release_oldest_target()
        else:
            self._touch_target(frame)
        return target, created

    def _update_target_size(self, size):
        size = (max(1, int(size[0])), max(1, int(size[1])))
        if size == self._target_size:
            return
        previous_size = self._target_size
        self._target_size = size
        self._scene_description.setWidth(size[0])
        self._scene_description.setHeight(size[1])
        self._frame_description.setWidth(size[0])
        self._frame_description.setHeight(size[1])
        self._scene_target.updateDescription(self._scene_description)
        bytes_per_frame = size[0] * size[1] * 4
        memory_capacity = max(
            MIN_BUFFER_FRAMES,
            int(BUFFER_MEMORY_BUDGET / float(max(1, bytes_per_frame))),
        )
        self._effective_buffer_size = max(
            1, min(self.max_buffer_size, memory_capacity)
        )
        if previous_size is not None:
            self.clear_buffer(refresh=False)
        diagnostics.log(
            "viewport targets resized",
            viewport="{}x{}".format(size[0], size[1]),
            buffer_capacity=self._effective_buffer_size,
            memory_budget_mb=int(BUFFER_MEMORY_BUDGET / (1024 * 1024)),
        )

    def _touch_target(self, frame):
        frame = float(frame)
        if frame not in self._targets:
            return
        try:
            self._target_queue.remove(frame)
        except ValueError:
            pass
        self._target_queue.append(frame)

    def _ensure_resources(self):
        if self._target_manager is None:
            self._target_manager = omr.MRenderer.getRenderTargetManager()
            diagnostics.log(
                "target manager acquired", success=self._target_manager is not None
            )
        if self._scene_target is None:
            self._scene_target = self._target_manager.acquireRenderTarget(self._scene_description)
            if self._scene_target is None:
                raise RuntimeError("Maya did not provide the Onion Skin scene target")
            for operation in (self._clear, self._scene, self._hud, self._present):
                operation.set_render_target(self._scene_target)
            for blend in (
                list(self._relative_blends.values())
                + list(self._absolute_blends.values())
                + list(self._inbetween_blends.values())
            ):
                blend.set_render_target(self._scene_target)
            diagnostics.log("scene target acquired")

    def _release_oldest_target(self):
        if not self._target_queue:
            return
        frame = self._target_queue.popleft()
        self._release_target(frame, remove_from_queue=False)

    def _release_target(self, frame, remove_from_queue=True):
        frame = float(frame)
        target = self._targets.pop(frame, None)
        if remove_from_queue:
            try:
                self._target_queue.remove(frame)
            except ValueError:
                pass
        if target is not None:
            self._target_manager.releaseRenderTarget(target)
        return target is not None

    def invalidate_frame(self, frame, refresh=True):
        released = self._release_target(frame)
        self._last_debug_setup = None
        diagnostics.log("frame invalidated", frame=float(frame), released=released)
        if refresh:
            _refresh_viewport()
        return released

    def clear_buffer(self, refresh=True):
        released = len(self._targets)
        if self._target_manager is not None:
            for target in list(self._targets.values()):
                try:
                    self._target_manager.releaseRenderTarget(target)
                except Exception:
                    pass
        self._targets.clear()
        self._target_queue.clear()
        self._last_debug_setup = None
        self._capture_pending = True
        self._relative_target_cache_key = None
        self._relative_target_cache = None
        diagnostics.log("buffer released", frames=released, refresh=refresh)
        if refresh:
            _refresh_viewport()

    @staticmethod
    def _normalized_color(value):
        values = list(value or (255, 255, 255))[:3]
        while len(values) < 3:
            values.append(255)
        return tuple(float(channel) / 255.0 for channel in values) + (1.0,)

    def apply_preferences(self, preferences, refresh=True):
        self.relative_frames = [int(value) for value in preferences.get("relative_frames", []) if int(value) != 0]
        self.relative_opacities = dict((int(key), int(value)) for key, value in (preferences.get("relative_opacities") or {}).items())
        self.absolute_frames = [int(value) for value in preferences.get("absolute_frames", [])]
        self.absolute_opacities = dict((int(key), int(value)) for key, value in (preferences.get("absolute_opacities") or {}).items())
        self.past_color = self._normalized_color(preferences.get("past_color"))
        self.future_color = self._normalized_color(preferences.get("future_color"))
        self.absolute_color = self._normalized_color(preferences.get("absolute_color"))
        self.display_style = DISPLAY_STYLES.get(preferences.get("display_style"), 1)
        self.global_opacity = max(0.0, min(1.0, int(preferences.get("global_opacity", 70)) / 100.0))
        self.outline_width = max(1, int(preferences.get("outline_width", 3)))
        self.draw_behind = bool(preferences.get("draw_behind", True))
        self.relative_to_keys = bool(preferences.get("relative_to_keys", False))
        self.relative_step = max(1, int(preferences.get("relative_step", 1)))
        self.max_buffer_size = max(1, int(preferences.get("max_buffer_size", 200)))
        self.auto_clear_buffer = bool(preferences.get("auto_clear_buffer", True))
        self.ghost_inbetweens = bool(preferences.get("ghost_inbetweens", False))
        self.inbetween_count = max(1, min(MAX_INBETWEEN_COUNT, int(preferences.get("inbetween_count", 1))))
        self._sync_blends()
        if self._target_size is not None:
            bytes_per_frame = self._target_size[0] * self._target_size[1] * 4
            memory_capacity = max(
                MIN_BUFFER_FRAMES,
                int(BUFFER_MEMORY_BUDGET / float(max(1, bytes_per_frame))),
            )
            self._effective_buffer_size = max(
                1, min(self.max_buffer_size, memory_capacity)
            )
        while len(self._target_queue) > self._effective_buffer_size:
            self._release_oldest_target()
        if refresh:
            _refresh_viewport()
        diagnostics.log(
            "preferences applied",
            style=dict((value, key) for key, value in DISPLAY_STYLES.items()).get(
                self.display_style, "shape"
            ),
            opacity=self.global_opacity,
            relative_frames=self.relative_frames,
            held_frames=self.absolute_frames,
            relative_to_keys=self.relative_to_keys,
            step=self.relative_step,
        )

    def _sync_blends(self):
        self._sync_blend_group(self._relative_blends, self.relative_frames, "relative")
        self._sync_blend_group(self._absolute_blends, self.absolute_frames, "absolute")
        self._sync_inbetween_blends()
        self._compose_operations()

    def _compose_operations(self):
        self._operations = [self._clear, self._scene]
        if self._capture_pending:
            self._operations.append(self._capture)
        self._operations.extend(self._relative_blends[key] for key in sorted(self._relative_blends))
        self._operations.extend(self._absolute_blends[key] for key in sorted(self._absolute_blends))
        self._operations.extend(self._inbetween_blends[key] for key in sorted(self._inbetween_blends))
        self._operations.extend([self._hud, self._present])

    def _sync_blend_group(self, mapping, frames, prefix):
        wanted = set(int(frame) for frame in frames)
        for frame in list(mapping):
            if frame not in wanted:
                mapping.pop(frame).release()
        for frame in wanted:
            if frame not in mapping:
                safe = "m{}".format(abs(frame)) if frame < 0 else str(frame)
                blend = BlendOperation("tkmOnion{}{}".format(prefix.title(), safe), frame, self)
                blend.set_render_target(self._scene_target)
                mapping[frame] = blend

    def _sync_inbetween_blends(self):
        # In-betweens bridge the current pose to the nearest shown past/future
        # key ghost (offsets -1 and 1), so the wanted set only ever depends on
        # settings, not on the current frame -- exactly like the relative and
        # absolute groups above. Frames with no neighbor available yet simply
        # render inactive (see BlendOperation.configure), same as a missing
        # relative/absolute target does.
        wanted = set()
        if self.ghost_inbetweens and self.relative_to_keys:
            count = max(1, min(MAX_INBETWEEN_COUNT, int(self.inbetween_count)))
            for side in (-1, 1):
                for index in range(1, count + 1):
                    wanted.add((side, index))
        for key in list(self._inbetween_blends):
            if key not in wanted:
                self._inbetween_blends.pop(key).release()
        for key in wanted:
            if key not in self._inbetween_blends:
                side, index = key
                safe = "{}m{}".format(index, abs(side)) if side < 0 else "{}p{}".format(index, side)
                blend = BlendOperation(
                    "tkmOnionInbetween{}".format(safe), side * 1000 + index, self
                )
                blend.set_render_target(self._scene_target)
                self._inbetween_blends[key] = blend

    def _resolve_relative_targets(self, current_frame):
        cache_key = (
            float(current_frame),
            bool(self.relative_to_keys),
            int(self.relative_step),
            tuple(self.relative_frames),
        )
        if cache_key == self._relative_target_cache_key:
            return dict(self._relative_target_cache)
        if not self.relative_to_keys:
            result = dict(
                (offset, current_frame + offset * self.relative_step)
                for offset in self.relative_frames
            )
            self._relative_target_cache_key = cache_key
            self._relative_target_cache = dict(result)
            return result
        result = {}
        for offset in self.relative_frames:
            target = current_frame
            direction = "next" if offset > 0 else "previous"
            for _index in range(abs(offset)):
                try:
                    from maya import cmds

                    candidate = cmds.findKeyframe(
                        time=(target, target),
                        timeSlider=True,
                        which=direction,
                    )
                    is_not_neighbor = (
                        (offset > 0 and candidate <= target)
                        or (offset < 0 and candidate >= target)
                    )
                    if is_not_neighbor:
                        query_time = target + (0.001 if offset > 0 else -0.001)
                        candidate = cmds.findKeyframe(
                            time=(query_time, query_time),
                            timeSlider=True,
                            which=direction,
                        )
                except Exception:
                    candidate = target
                if (
                    candidate == target
                    or (offset > 0 and candidate < target)
                    or (offset < 0 and candidate > target)
                ):
                    break
                target = float(candidate)
            result[offset] = target
        self._relative_target_cache_key = cache_key
        self._relative_target_cache = dict(result)
        return result

    def _resolve_inbetween_targets(self, current_frame, key_targets):
        """Sample frames between the current pose and its nearest shown key ghosts.

        *key_targets* is the offset->frame map ``_resolve_relative_targets``
        already produced for this same setup() call, so this never
        re-queries Maya. Only bridges to offsets -1/1 (the immediate past and
        future key ghosts) since that is what "in-between" means to an
        animator; if those offsets aren't currently shown, there is nothing
        to bridge. Samples snap to whole frames so they share the same
        integer-keyed render-target cache as every other ghost -- no extra
        float-precision bookkeeping.
        """
        result = {}
        if not (self.ghost_inbetweens and self.relative_to_keys):
            return result
        current_frame = float(current_frame)
        current_whole = round(current_frame)
        count = max(1, min(MAX_INBETWEEN_COUNT, int(self.inbetween_count)))
        for side in (-1, 1):
            target = key_targets.get(side)
            if target is None:
                continue
            target = float(target)
            target_whole = round(target)
            span = target - current_frame
            if abs(span) < 2.0:
                continue  # adjacent frames have no room for a sample between them
            for index in range(1, count + 1):
                fraction = float(index) / float(count + 1)
                frame = round(current_frame + span * fraction)
                if frame == current_whole or frame == target_whole:
                    continue
                result[(side, index)] = (float(frame), fraction)
        return result

    def required_frames(self, current_frame=None):
        """Every frame whose onion texture is needed right now, current frame excluded.

        Shared by ``setup()`` (via the two ``_resolve_*`` helpers above) and
        the auto-update baker in ``api.py``, so "what does the viewport need"
        is computed exactly once. A frame this returns that isn't in
        ``cached_frames()`` yet is exactly what ``missing_required_frames()``
        reports as still needing a capture pass.
        """
        if current_frame is None:
            current_frame = maya_api.current_time()
            if current_frame is None:
                return []
        current_frame = float(current_frame)
        targets = self._resolve_relative_targets(current_frame)
        inbetweens = self._resolve_inbetween_targets(current_frame, targets)
        frames = set(float(value) for value in targets.values())
        frames.update(float(frame) for frame in self.absolute_frames)
        frames.update(float(value) for value, _fraction in inbetweens.values())
        frames.discard(round(current_frame))
        frames.discard(current_frame)
        return sorted(frames)

    def cached_frames(self):
        return set(self._targets.keys())

    def missing_required_frames(self, current_frame=None):
        cached = self.cached_frames()
        return [frame for frame in self.required_frames(current_frame) if frame not in cached]

    def invalidate_required_frames(self, current_frame=None):
        """Evict every currently-needed ghost so a stale pose never lingers.

        Called right when an edit is detected (see api.OnionUpdateController)
        so the affected ghosts disappear immediately instead of showing an
        outdated pose until the debounced background bake gets around to
        recapturing them.
        """
        released = 0
        for frame in self.required_frames(current_frame):
            if self._release_target(frame):
                released += 1
        if released:
            self._last_debug_setup = None
        return released

    def add_objects(self, objects, refresh=True):
        names = list(self._object_names)
        for value in objects or []:
            value = six.text_type(value)
            if value not in names:
                names.append(value)
        return self.set_objects(names, refresh=refresh)

    def remove_objects(self, objects, refresh=True):
        remove = set(six.text_type(value) for value in objects or [])
        return self.set_objects(
            [value for value in self._object_names if value not in remove],
            refresh=refresh,
        )

    def clear_objects(self, refresh=True):
        return self.set_objects([], refresh=refresh)

    def set_objects(self, names, refresh=True, force=False):
        selection = om.MSelectionList()
        valid = []
        for name in names:
            try:
                # Resolve through the shared API helper first so stale DAG names
                # are rejected consistently with the rest of TKM.
                if maya_api.mobject_from_node(name) is None:
                    continue
                selection.add(name)
                valid.append(name)
            except Exception:
                pass
        if valid == self.object_names() and not force:
            return False
        self._object_names = valid
        self._object_list = selection
        diagnostics.log(
            "object filter updated", requested=list(names), accepted=valid
        )
        self.clear_buffer(refresh=refresh)
        return True

    def object_names(self):
        names = []
        try:
            count = self._object_list.length()
        except Exception:
            count = 0
        for index in range(count):
            name = None
            try:
                name = self._object_list.getDagPath(index).fullPathName()
            except Exception:
                try:
                    name = maya_api.mobject_name(
                        self._object_list.getDependNode(index), absolute=True
                    )
                except Exception:
                    pass
            if name and name not in names:
                names.append(six.text_type(name))
        self._object_names = names
        return list(names)

    def _install_callbacks(self):
        self._remove_callbacks()
        try:
            self._callbacks.append(
                om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, self._on_scene_changed)
            )
            self._callbacks.append(
                om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew, self._on_scene_changed)
            )
        except Exception as exc:
            diagnostics.log_error("scene callback installation failed", exc)
        try:
            iterator = om.MItDependencyNodes(om.MFn.kCamera)
            while not iterator.isDone():
                camera = om.MFnDagNode(iterator.thisNode())
                transform = camera.parent(0)
                self._camera_callbacks.append(
                    om.MNodeMessage.addAttributeChangedCallback(transform, self._on_camera_changed)
                )
                iterator.next()
        except Exception as exc:
            diagnostics.log_error("camera callback installation failed", exc)
        diagnostics.log(
            "callbacks installed",
            scene_callbacks=len(self._callbacks),
            camera_callbacks=len(self._camera_callbacks),
        )

    def _remove_callbacks(self):
        for callback_id in self._callbacks:
            maya_api.remove_callback(callback_id)
        self._callbacks = []
        for callback_id in self._camera_callbacks:
            maya_api.remove_callback(callback_id)
        self._camera_callbacks = []

    def _on_scene_changed(self, *_args):
        try:
            from TheKeyMachine.tools.onion_skin import controller

            controller.restore_scene_objects(renderer=self)
        except Exception as exc:
            diagnostics.log_error("scene objects restore failed", exc)
            self.set_objects([], force=True)

    def _on_camera_changed(self, message, plug, _other_plug, _client_data=None):
        if not self.auto_clear_buffer:
            return
        try:
            changed = bool(message & om.MNodeMessage.kAttributeSet)
            interesting = plug.partialName(useLongNames=True) in (
                "translate", "translateX", "translateY", "translateZ",
                "rotate", "rotateX", "rotateY", "rotateZ",
            )
        except Exception:
            changed = interesting = False
        if changed and interesting:
            diagnostics.log("camera moved", plug=plug.partialName(useLongNames=True))
            self.clear_buffer(refresh=False)
