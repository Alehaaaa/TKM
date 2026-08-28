(function () {
  'use strict';

  /* ---------------------------------------------------------------------
   * Data: tool definitions + toolbar groups
   * ------------------------------------------------------------------- */
  const standardToolbarTools = [
    { id: 'nudge_left', label: 'Nudge Left', text: '', icon: 'icons/nudge_left.svg', tooltip: 'Move the targeted keys left by the Nudge Value.', movies: ['movies/nudge_left.gif'] },
    { id: 'nudge_right', label: 'Nudge Right', text: '', icon: 'icons/nudge_right.svg', tooltip: 'Move the targeted keys right by the Nudge Value.', movies: ['movies/nudge_right.gif'] },
    { id: 'nudge_value', label: 'Nudge Value', text: 'NV', icon: '', tooltip: 'Set the frame count used by every Nudge and Inbetween command.', movies: [] },
    { id: 'default_object_values', label: 'Default Pose', text: '', icon: 'icons/default.svg', tooltip: "Reset targeted attributes to saved defaults or Maya's native defaults.", movies: ['movies/default_values.gif'] },
    { id: 'bake_animation_1', label: 'Bake on Ones', text: '', icon: 'icons/bake_animation_1.svg', tooltip: 'Bake the active animation context on every frame.', movies: [] },
    { id: 'share_keys', label: 'Share Keys', text: 'sK', icon: 'icons/share_keys.svg', tooltip: 'Add missing shared key times across the active animation channels.', movies: ['movies/share_keys.gif'] },
    { id: 'blend_connect_neighbors', label: 'Connect to Neighbors', text: 'CN', icon: 'icons/slider_blend/connect_neighbors.svg', tooltip: 'Smoothly connect the selected curve segment to its surrounding keys. Click and drag the slider to scrub the blend live.', movies: [], slider: true },
    { id: 'tween_tweener', label: 'Tweener', text: 'TW', icon: 'icons/slider_tween/tweener.svg', tooltip: 'Blend values between the previous and next keys. Click and drag the slider to scrub the blend live.', movies: [], slider: true },
    { id: 'isolate_master', label: 'Isolate', text: '', icon: 'icons/isolate.svg', tooltip: 'Isolate the selected character or asset in the active viewport.', movies: ['movies/isolate.gif'] },
    { id: 'selector', label: 'Selector', text: '', icon: 'icons/selector.svg', tooltip: 'Open the current selection as a compact list for quick re-selection.', movies: [] },
    { id: 'select_rig_controls', label: 'Select Rig Controls', text: '', icon: 'icons/select_rig_controls.svg', tooltip: 'Select all curve and joint controls in the selected rig hierarchy.', movies: [] },
    { id: 'mirror', label: 'Mirror', text: '', icon: 'icons/mirror.svg', tooltip: 'Mirror the selected controls to their opposite-side equivalents. Mirror exceptions can be configured per rig and are saved for reuse.', movies: [] },
    { id: 'align_objects', label: 'Align Objects', text: '', icon: 'icons/align.svg', tooltip: 'Match the selected source objects to the last selected target. Uses translation, rotation, and scale. A selected time range aligns every frame in that range.', movies: ['movies/align_objects.gif'] },
    { id: 'copy_pose', label: 'Copy Pose', text: '', icon: 'icons/copy_pose.svg', tooltip: 'Copy the current pose from the selected controls. The pose remains available across Maya sessions.', movies: [] },
    { id: 'copy_animation', label: 'Copy Animation', text: '', icon: 'icons/copy_animation.svg', tooltip: 'Copy animation from the selected objects or controls. The animation remains available across Maya sessions.', movies: [] },
    { id: 'tangent_bouncy', label: 'Bouncy Tangent', text: 'BO', icon: 'icons/slider_tangent/tangent_bouncy.svg', tooltip: 'Fit exaggerated tangent angles that add controlled overshoot around the targeted keys.', movies: [] },
    { id: 'tangent_auto', label: 'Auto Tangent', text: 'AU', icon: 'icons/slider_tangent/tangent_auto.svg', tooltip: 'Set automatic tangents on the targeted keys.', movies: [] },
    { id: 'tangent_spline', label: 'Spline Tangent', text: 'SP', icon: 'icons/slider_tangent/tangent_spline.svg', tooltip: 'Set smooth spline tangents on the targeted keys.', movies: [] },
    { id: 'tangent_linear', label: 'Linear Tangent', text: 'LI', icon: 'icons/slider_tangent/tangent_linear.svg', tooltip: 'Set straight linear interpolation through the targeted keys.', movies: [] },
    { id: 'tangent_step', label: 'Step Tangent', text: 'ST', icon: 'icons/slider_tangent/tangent_step.svg', tooltip: 'Hold each key value until the following key.', movies: [] },
    { id: 'animation_offset', label: 'Animation Offset', text: '', icon: 'icons/animation_offset.svg', tooltip: "Offset animated controls without changing the shape of their motion. Select animated controls, enable the tool, then transform them with Maya's manipulators.", movies: ['movies/animation_offset.gif'] },
    { id: 'micro_move', label: 'Micro Move', text: 'MM', icon: 'icons/ruler.svg', tooltip: "Move and rotate selected controls with fine viewport precision. Disable the tool to restore Maya's normal move and rotate contexts.", movies: [] },
    { id: 'depth_mover', label: 'Depth Mover', text: '', icon: 'icons/depth_mover.svg', tooltip: "Drag selected transforms toward or away from the active camera while preserving their screen position. Disable the tool to restore Maya's previous interaction context.", movies: [] },
    { id: 'temp_pivot', label: 'Temp Pivot', text: 'TP', icon: 'icons/temp_pivot.svg', tooltip: 'Create a temporary pivot that drives the selected controls as one transform. Run the tool again to finish the active pivot session.', movies: ['movies/temp_pivot.gif', 'movies/temp_pivot_chain.gif'] },
    { id: 'follow_cam', label: 'Follow Cam', text: '', icon: 'icons/follow_cam.svg', tooltip: 'Create a camera that follows the selected object in translation and rotation. Useful for stabilizing a moving control in view while polishing its animation.', movies: ['movies/follow_cam.gif'] },
    { id: 'link_copy', label: 'Copy Relationship', text: '', icon: 'icons/link_relative.svg', tooltip: 'Copy the world-space relationship between selected objects. Select followers first and the driver last.', movies: [] },
    { id: 'ws_copy_frame', label: 'Copy World Space', text: '', icon: 'icons/worldspace_copy_frame.svg', tooltip: 'Copy world-space transforms from the selected time range or keys, or from the current frame when nothing is selected.', movies: [] },
    { id: 'attribute_switcher', label: 'Attribute Switcher', text: 'SSw', icon: 'icons/attribute_switcher.svg', tooltip: 'Switch configured attributes across selected controls from a compact floating window. Hold Ctrl and click attribute rows to select multiple channels and switch them together. Rotation-order changes can be Euler-filtered automatically.', movies: [] },
    { id: 'gimbal', label: 'Gimbal Fixer', text: 'Gim', icon: 'icons/reblock.svg', tooltip: "Analyze the selected control's animated rotation and rank all six rotation orders by gimbal risk. Choose an order to convert the animation while preserving the visible motion.", movies: [] },
    { id: 'selection_sets', label: 'Selection Sets', text: 'SS', icon: 'icons/selection_sets.svg', tooltip: 'Create, organize, rename, and recall persistent selection sets stored with the Maya scene.', movies: [] },
    { id: 'orbit', label: 'Orbit', text: 'Orb', icon: 'icons/orbit_ui.svg', tooltip: 'Open the configurable Orbit command palette near the cursor. Use its radial arrangement for fast access to frequently repeated animation tools.', movies: [] },
    { id: 'create_tracer', label: 'Tracer', text: '', icon: 'icons/tracer.svg', tooltip: 'Click to create a viewport tracer for the selected object; click again to remove all tracers. Shift-click creates another tracer. Right-click opens tracer settings.', movies: ['movies/tracer.gif'] },
    { id: 'attribute_switcher_euler_filter', label: 'Auto Euler Filter', text: 'EF', icon: 'icons/euler_filter.svg', tooltip: 'Automatically apply an Euler filter after Attribute Switcher changes rotation order.', movies: [] },
    { id: 'graph_extra_tools', label: 'Graph Extras', text: 'E', icon: '', tooltip: 'Open the Graph Editor utility commands.', movies: [] },
    { id: 'animation_tools', label: 'Anim Curve Tools', text: 'AT', icon: '', tooltip: 'Open animation editing, cleanup, Smart Key, and snapping commands.', movies: [] },
    { id: 'delete_all_animation', label: 'Clear Animation', text: '', icon: 'icons/delete_animation.svg', tooltip: 'Delete animation from the selected objects and animation layers. A highlighted Time Slider range limits which keys are deleted.', movies: ['movies/delete_all_animation.gif', 'movies/delete_all_animation_selection.gif'] },
    { id: 'snap', label: 'Snap Keys', text: 'SpK', icon: 'icons/snap.svg', tooltip: 'Move sub-frame keys on the selected objects and animation layers, including layer weights, onto whole frames.', movies: ['movies/snap.gif'] },
    { id: 'remove_redundant_keys', label: 'Remove Redundant Keys', text: '', icon: 'icons/remove_redundant_keys.svg', tooltip: 'Remove redundant keys from the selected objects and animation layers using the mode selected from the right-click menu.', movies: [] },
    { id: 'background_runners', label: 'Background Runners', text: '', icon: 'icons/background_runners_0.svg', tooltip: 'Toggle persistent automatic helpers and background tool runners.', movies: [] },
    { id: 'animation_recovery', label: 'Animation Recovery', text: '', icon: 'icons/animation_recovery.svg', tooltip: 'Browse automatic animation and channel snapshots, with alerts when an older scene file is opened. Recover with nothing selected to restore everything, or select objects to restore only those objects.', movies: [] },
    { id: 'search_window', label: 'Search', text: '', icon: 'icons/search.svg', tooltip: 'Find and run any registered TheKeyMachine command by name. Type to filter, use Up or Down to select a result, then press Enter to run it.', movies: [] }
  ];

  const standardToolbarGroups = [
    { id: 'nudge_tools', label: 'Nudge', color: '#72DBB8', tools: ['nudge_left', 'nudge_right', 'nudge_value'] },
    { id: 'default_tools', label: 'Default', color: '#72DBB8', tools: ['default_object_values'] },
    { id: 'bake_tools', label: 'Bake', color: '#72DBB8', tools: ['bake_animation_1'] },
    { id: 'key_sync_tools', label: 'Key Sync', color: '#72DBB8', tools: ['share_keys'] },
    { id: 'slider_blend', label: 'Blend Sliders', color: '#72DBB8', tools: ['blend_connect_neighbors'] },
    { id: 'slider_tween', label: 'Tween Sliders', color: '#d4d361', tools: ['tween_tweener'] },
    { id: 'isolate_tools', label: 'Isolate', color: '#787878', tools: ['isolate_master'] },
    { id: 'selection_tools', label: 'Selection', color: '#72DBB8', tools: ['selector', 'select_rig_controls'] },
    { id: 'mirror_tools', label: 'Mirror', color: '#72DBB8', tools: ['mirror'] },
    { id: 'align_tools', label: 'Align Objects', color: '#72DBB8', tools: ['align_objects'] },
    { id: 'pose_animation_section', label: 'Pose & Animation', color: '#72DBB8', tools: ['copy_pose', 'copy_animation'] },
    { id: 'tangents', label: 'Tangents', color: '#DB8072', tools: ['tangent_bouncy', 'tangent_auto', 'tangent_spline', 'tangent_linear', 'tangent_step'] },
    { id: 'animation_offset_tools', label: 'Animation Offset', color: '#B172DB', tools: ['animation_offset'] },
    { id: 'movers_tools', label: 'Movers', color: '#B172DB', tools: ['micro_move', 'depth_mover'] },
    { id: 'temp_pivot_tools', label: 'Temp Pivot', color: '#B172DB', tools: ['temp_pivot'] },
    { id: 'follow_cam_tools', label: 'Follow Cam', color: '#B172DB', tools: ['follow_cam'] },
    { id: 'link_tools', label: 'Relationships & Worldspace', color: '#72DBB8', tools: ['link_copy', 'ws_copy_frame'] },
    { id: 'attribute_tools', label: 'Attribute Switcher', color: '#72DBB8', tools: ['attribute_switcher', 'gimbal'] },
    { id: 'selection_set_tools', label: 'Selection Sets', color: '#787878', tools: ['selection_sets'] },
    { id: 'orbit_tools', label: 'Orbit', color: '#787878', tools: ['orbit'] },
    { id: 'tracer_tools', label: 'Tracer', color: '#DB7274', tools: ['create_tracer'] },
    { id: 'global_tools', label: 'Global Tools', color: '#787878', tools: ['attribute_switcher_euler_filter'] },
    { id: 'graph_tools', label: 'Graph Tools', color: '#DB8072', tools: ['graph_extra_tools'] },
    { id: 'animation_tools', label: 'Anim Curve Tools', color: '#72DBB8', tools: ['animation_tools', 'snap', 'remove_redundant_keys'] },
    { id: 'background_runner_tools', label: 'Background Runners', color: '#787878', tools: ['background_runners'] },
    { id: 'animation_recovery_tools', label: 'Animation Recovery', color: '#787878', tools: ['animation_recovery'] },
    { id: 'search_tools', label: 'Search', color: '#787878', tools: ['search_window'] }
  ];

  const standardToolbarToolMap = new Map(standardToolbarTools.map((tool) => [tool.id, tool]));

  function clampNumber(value, min, max) {
    return Math.max(min, Math.min(value, max));
  }

  /* ---------------------------------------------------------------------
   * Tooltip system
   *
   * A single delegated pointerover/pointerout/focusin/focusout listener
   * (plus one resize/scroll listener) drives every tooltip in the mock,
   * instead of each of the ~40 triggers registering its own set. Each
   * trigger just needs a [data-tip-trigger] marker and an entry in
   * tipRegistry; showTip/hideTip look up the right tip and reposition
   * only the one that is currently active.
   * ------------------------------------------------------------------- */
  const tipRegistry = new WeakMap();
  let activeTrigger = null;
  let activeTip = null;

  function positionTip(trigger, tip) {
    const triggerRect = trigger.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();
    const edge = 5;
    const gap = 10;
    const targetX = triggerRect.left + triggerRect.width / 2;
    const maxLeft = Math.max(edge, window.innerWidth - tipRect.width - edge);
    const left = clampNumber(targetX - tipRect.width / 2, edge, maxLeft);
    let top = triggerRect.top - tipRect.height - gap;
    let below = false;
    if (top < edge && window.innerHeight - triggerRect.bottom > triggerRect.top) {
      below = true;
      top = triggerRect.bottom + gap;
    }
    tip.classList.toggle('is-below', below);
    tip.style.setProperty('--tooltip-left', `${Math.round(left)}px`);
    tip.style.setProperty('--tooltip-top', `${Math.round(Math.max(edge, top))}px`);
    tip.style.setProperty('--tooltip-arrow-x', `${Math.round(targetX - left)}px`);
  }

  function showTip(trigger) {
    const tip = tipRegistry.get(trigger);
    if (!tip || trigger === activeTrigger) return;
    if (activeTip) activeTip.classList.remove('is-visible');
    activeTrigger = trigger;
    activeTip = tip;
    positionTip(trigger, tip);
    tip.classList.add('is-visible');
  }

  function hideTip(trigger) {
    if (trigger !== activeTrigger) return;
    if (activeTip) activeTip.classList.remove('is-visible');
    activeTrigger = null;
    activeTip = null;
  }

  function findTrigger(node) {
    return node instanceof Element ? node.closest('[data-tip-trigger]') : null;
  }

  document.addEventListener('pointerover', (event) => {
    const trigger = findTrigger(event.target);
    if (trigger) showTip(trigger);
  });
  document.addEventListener('pointerout', (event) => {
    const trigger = findTrigger(event.target);
    if (!trigger || trigger !== activeTrigger) return;
    const to = event.relatedTarget;
    if (!(to instanceof Node) || !trigger.contains(to)) hideTip(trigger);
  });
  document.addEventListener('focusin', (event) => {
    const trigger = findTrigger(event.target);
    if (trigger) showTip(trigger);
  });
  document.addEventListener('focusout', (event) => {
    const trigger = findTrigger(event.target);
    if (trigger) hideTip(trigger);
  });
  window.addEventListener('resize', () => {
    if (activeTrigger && activeTip) positionTip(activeTrigger, activeTip);
  });
  window.addEventListener('scroll', () => {
    if (activeTrigger && activeTip) positionTip(activeTrigger, activeTip);
  }, { passive: true });

  function createStandardToolbarTip(tool) {
    const tip = document.createElement('span');
    tip.className = 'standard-toolbar-tip';
    tip.setAttribute('role', 'tooltip');
    const header = document.createElement('span');
    header.className = 'standard-toolbar-tip-header';
    if (tool.icon) {
      const headerIcon = document.createElement('img');
      headerIcon.className = 'standard-toolbar-tip-icon';
      headerIcon.src = tool.icon;
      headerIcon.alt = '';
      header.append(headerIcon);
    }
    const title = document.createElement('strong');
    title.textContent = tool.label;
    header.append(title);
    const body = document.createElement('span');
    body.className = 'standard-toolbar-tip-body';
    body.textContent = tool.tooltip;
    tip.append(header, body);
    (tool.movies || []).forEach((movie) => {
      const media = document.createElement('img');
      media.className = 'standard-toolbar-tip-movie';
      media.src = movie;
      media.alt = '';
      media.loading = 'lazy';
      tip.append(media);
    });
    return tip;
  }

  // Builds a tip for `trigger`, appends it to <body> (tooltips use
  // position:fixed and must not sit inside a transformed ancestor, which
  // would otherwise become their containing block), and wires it into the
  // delegated show/hide system above.
  function registerTip(trigger, tipConfig) {
    const tip = createStandardToolbarTip(tipConfig);
    document.body.append(tip);
    tipRegistry.set(trigger, tip);
    trigger.dataset.tipTrigger = '';
    return tip;
  }

  /* ---------------------------------------------------------------------
   * Nudge value control
   * ------------------------------------------------------------------- */
  function clampNudgeValue(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) return 1;
    return clampNumber(parsed, 1, 99999);
  }

  function closeNudgePresetMenus(exceptMenu = null) {
    document.querySelectorAll('.standard-toolbar-nudge-menu').forEach((menu) => {
      if (menu !== exceptMenu) menu.remove();
    });
  }

  document.addEventListener('pointerdown', (event) => {
    if (!event.target.closest('.standard-toolbar-nudge-menu, .standard-toolbar-nudge-control')) {
      closeNudgePresetMenus();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeNudgePresetMenus();
  });

  function createNudgeValueControl(tool) {
    const control = document.createElement('div');
    control.className = 'standard-toolbar-button standard-toolbar-nudge-control';
    control.dataset.toolId = tool.id;
    control.setAttribute('aria-label', tool.label);

    const input = document.createElement('input');
    input.className = 'standard-toolbar-nudge-input';
    input.type = 'text';
    input.inputMode = 'numeric';
    input.pattern = '[0-9]*';
    input.value = window.localStorage.getItem('tkm_nudge_value') || '1';
    input.setAttribute('aria-label', tool.label);
    input.setAttribute('role', 'spinbutton');
    input.setAttribute('aria-valuemin', '1');
    input.setAttribute('aria-valuemax', '99999');

    const setValue = (nextValue) => {
      const value = String(clampNudgeValue(nextValue));
      input.value = value;
      input.setAttribute('aria-valuenow', value);
      window.localStorage.setItem('tkm_nudge_value', value);
    };

    setValue(input.value);

    input.addEventListener('input', () => {
      input.value = input.value.replace(/[^\d]/g, '');
    });
    input.addEventListener('blur', () => setValue(input.value));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        setValue(input.value);
        input.blur();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        setValue(clampNudgeValue(input.value) + 1);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        setValue(clampNudgeValue(input.value) - 1);
      }
    });
    input.addEventListener('wheel', (event) => {
      if (!control.matches(':hover, :focus-within')) return;
      event.preventDefault();
      setValue(clampNudgeValue(input.value) + (event.deltaY < 0 ? 1 : -1));
    }, { passive: false });

    const arrows = document.createElement('span');
    arrows.className = 'standard-toolbar-nudge-arrows';
    [['up', 1], ['down', -1]].forEach(([direction, step]) => {
      const arrow = document.createElement('button');
      arrow.type = 'button';
      arrow.className = `standard-toolbar-nudge-arrow standard-toolbar-nudge-arrow-${direction}`;
      arrow.setAttribute('aria-label', direction === 'up' ? 'Increase nudge value' : 'Decrease nudge value');
      arrow.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        input.focus();
      });
      arrow.addEventListener('click', () => {
        setValue(clampNudgeValue(input.value) + step);
        input.focus();
      });
      arrows.append(arrow);
    });

    control.addEventListener('contextmenu', (event) => {
      event.preventDefault();
      closeNudgePresetMenus();
      const menu = document.createElement('div');
      menu.className = 'standard-toolbar-nudge-menu';
      menu.setAttribute('role', 'menu');
      [1, 2, 3, 4, 5, 10, 20, 50, 100].forEach((value, valueIndex) => {
        if (valueIndex === 5) {
          const separator = document.createElement('span');
          separator.className = 'standard-toolbar-nudge-menu-separator';
          menu.append(separator);
        }
        const item = document.createElement('button');
        item.type = 'button';
        item.setAttribute('role', 'menuitem');
        item.textContent = value;
        item.addEventListener('click', () => {
          setValue(value);
          closeNudgePresetMenus();
          input.focus();
        });
        menu.append(item);
      });
      document.body.append(menu);
      const rect = control.getBoundingClientRect();
      const menuRect = menu.getBoundingClientRect();
      const left = clampNumber(rect.left, 6, window.innerWidth - menuRect.width - 6);
      const top = rect.top - menuRect.height - 6;
      menu.style.left = `${Math.round(left)}px`;
      menu.style.top = `${Math.round(Math.max(6, top))}px`;
    });

    control.append(input, arrows);
    registerTip(control, tool);
    return control;
  }

  /* ---------------------------------------------------------------------
   * Slider control (Blend-to-Neighbor / Tween / Tangent sliderWidget mock)
   * ------------------------------------------------------------------- */
  const SLIDER_STOPS = [-100, -50, -25, -10, 0, 10, 25, 50, 100];
  const SLIDER_MIN = SLIDER_STOPS[0];
  const SLIDER_MAX = SLIDER_STOPS[SLIDER_STOPS.length - 1];
  const SLIDER_SEGMENTS = SLIDER_STOPS.length - 1;
  const SLIDER_CENTER_STOP = (SLIDER_STOPS.length - 1) / 2;

  function sliderValueFromRatio(ratio) {
    const scaled = clampNumber(ratio, 0, 1) * SLIDER_SEGMENTS;
    const segment = clampNumber(Math.floor(scaled), 0, SLIDER_SEGMENTS - 1);
    const t = scaled - segment;
    return SLIDER_STOPS[segment] + (SLIDER_STOPS[segment + 1] - SLIDER_STOPS[segment]) * t;
  }

  function createSliderControl(tool) {
    let ratio = 0.5;
    let dragging = false;

    const control = document.createElement('div');
    control.className = 'standard-toolbar-button standard-toolbar-slider-control';
    control.dataset.toolId = tool.id;
    control.setAttribute('role', 'slider');
    control.setAttribute('tabindex', '0');
    control.setAttribute('aria-label', tool.label);
    control.setAttribute('aria-valuemin', String(SLIDER_MIN));
    control.setAttribute('aria-valuemax', String(SLIDER_MAX));

    const bg = document.createElement('span');
    bg.className = 'standard-toolbar-slider-bg';

    const track = document.createElement('span');
    track.className = 'standard-toolbar-slider-track';

    SLIDER_STOPS.forEach((stopValue, stopIndex) => {
      if (stopIndex === SLIDER_CENTER_STOP) return;
      const stopRatio = stopIndex / SLIDER_SEGMENTS;
      const isEdge = stopIndex === 0 || stopIndex === SLIDER_STOPS.length - 1;
      const preset = document.createElement('button');
      preset.type = 'button';
      preset.className = 'standard-toolbar-slider-preset';
      if (isEdge) preset.classList.add('standard-toolbar-slider-preset--edge');
      preset.style.left = `${stopRatio * 100}%`;
      preset.setAttribute('aria-label', `${tool.label}: fire ${stopValue}`);
      registerTip(preset, {
        icon: tool.icon,
        label: `${tool.label}: ${stopValue > 0 ? '+' : ''}${stopValue}`,
        tooltip: tool.tooltip,
        movies: tool.movies || []
      });
      preset.addEventListener('pointerdown', (event) => event.stopPropagation());
      preset.addEventListener('click', (event) => {
        event.stopPropagation();
      });
      track.append(preset);
    });

    const readout = document.createElement('span');
    readout.className = 'standard-toolbar-slider-readout';

    const handle = document.createElement('span');
    handle.className = 'standard-toolbar-slider-handle';
    if (tool.icon) {
      const handleIcon = document.createElement('img');
      handleIcon.className = 'standard-toolbar-slider-handle-icon';
      handleIcon.src = tool.icon;
      handleIcon.alt = '';
      handleIcon.draggable = false;
      handle.append(handleIcon);
    } else {
      const handleLabel = document.createElement('span');
      handleLabel.className = 'standard-toolbar-slider-handle-label';
      handleLabel.textContent = tool.text || tool.label;
      handle.append(handleLabel);
    }

    control.append(bg, track, readout, handle);

    const positionHandle = () => {
      const trackRect = track.getBoundingClientRect();
      const controlRect = control.getBoundingClientRect();
      if (!trackRect.width || !controlRect.width) return;
      const left = (trackRect.left - controlRect.left) + ratio * trackRect.width;
      handle.style.left = `${left}px`;
    };

    const setRatio = (nextRatio) => {
      ratio = clampNumber(nextRatio, 0, 1);
      const value = sliderValueFromRatio(ratio);
      control.setAttribute('aria-valuenow', value.toFixed(2));
      readout.textContent = value.toFixed(2);
      readout.classList.toggle('is-value-left', ratio >= 0.5);
      readout.classList.toggle('is-value-right', ratio < 0.5);
      positionHandle();
    };

    const ratioFromClientX = (clientX) => {
      const rect = track.getBoundingClientRect();
      if (!rect.width) return ratio;
      return clampNumber((clientX - rect.left) / rect.width, 0, 1);
    };

    const startDrag = (event) => {
      if (event.target.closest('.standard-toolbar-slider-preset')) return;
      if (event.button !== undefined && event.button !== 0) return;
      dragging = true;
      control.classList.add('is-dragging');
      control.setPointerCapture?.(event.pointerId);
      setRatio(ratioFromClientX(event.clientX));
      control.focus();
      event.preventDefault();
    };

    const moveDrag = (event) => {
      if (!dragging) return;
      setRatio(ratioFromClientX(event.clientX));
    };

    const endDrag = (event) => {
      if (!dragging) return;
      dragging = false;
      control.classList.remove('is-dragging');
      control.releasePointerCapture?.(event.pointerId);
      setRatio(0.5);
    };

    control.addEventListener('pointerdown', startDrag);
    control.addEventListener('pointermove', moveDrag);
    control.addEventListener('pointerup', endDrag);
    control.addEventListener('pointercancel', endDrag);
    window.addEventListener('resize', positionHandle);

    setRatio(ratio);
    window.requestAnimationFrame(positionHandle);
    registerTip(handle, tool);
    return control;
  }

  /* ---------------------------------------------------------------------
   * Standard button + mock assembly
   * ------------------------------------------------------------------- */
  function createStandardToolbarButton(tool, index) {
    if (tool.id === 'nudge_value') return createNudgeValueControl(tool);
    if (tool.slider) return createSliderControl(tool);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'standard-toolbar-button';
    button.dataset.toolId = tool.id;
    button.setAttribute('aria-label', tool.label);

    if (tool.icon) {
      const image = document.createElement('img');
      image.src = tool.icon;
      image.alt = '';
      image.loading = 'lazy';
      image.draggable = false;
      button.append(image);
    } else {
      const text = document.createElement('span');
      text.className = 'standard-toolbar-command-text';
      text.textContent = tool.text || tool.label;
      button.append(text);
    }

    registerTip(button, tool);
    return button;
  }

  function ensureStandardToolbarMock() {
    if (document.querySelector('[data-standard-toolbar-mock]')) return;
    const footer = document.querySelector('.footer-container');
    if (!footer) return;

    const dock = document.createElement('section');
    dock.className = 'standard-toolbar-mock';
    dock.dataset.standardToolbarMock = '';
    dock.setAttribute('aria-label', 'Standard workspace pinned toolbar mock');

    const menuButton = document.createElement('button');
    menuButton.type = 'button';
    menuButton.className = 'standard-toolbar-button standard-toolbar-main-button';
    menuButton.setAttribute('aria-label', 'TheKeyMachine');
    const menuIcon = document.createElement('img');
    menuIcon.src = 'icons/tkm_main.svg';
    menuIcon.alt = '';
    menuIcon.draggable = false;
    menuButton.append(menuIcon);
    registerTip(menuButton, {
      icon: menuIcon.src,
      label: 'TheKeyMachine',
      tooltip: 'Open TheKeyMachine preferences, docking, maintenance, updates, and help.',
      movies: []
    });

    const scroller = document.createElement('div');
    scroller.className = 'standard-toolbar-scroll';
    scroller.setAttribute('role', 'toolbar');
    scroller.setAttribute('aria-label', 'Pinned Standard workspace tools');

    let buttonIndex = 0;
    let colorRun = null;
    let previousColor = null;
    standardToolbarGroups.forEach((section) => {
      const buttons = section.tools
        .map((toolId) => standardToolbarToolMap.get(toolId))
        .filter(Boolean)
        .map((tool) => createStandardToolbarButton(tool, buttonIndex++));
      if (!buttons.length) return;

      if (section.color !== previousColor) {
        colorRun = document.createElement('div');
        colorRun.className = 'standard-toolbar-color-group';
        colorRun.style.setProperty('--tool-group-color', section.color);
        scroller.append(colorRun);
        previousColor = section.color;
      }

      const group = document.createElement('div');
      group.className = 'standard-toolbar-group';
      group.dataset.sectionId = section.id;
      group.style.setProperty('--tool-group-color', section.color);
      group.setAttribute('aria-label', section.label);
      group.append(...buttons);
      colorRun.append(group);
    });

    dock.append(menuButton, scroller);
    footer.before(dock);
  }

  function init() {
    ensureStandardToolbarMock();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
