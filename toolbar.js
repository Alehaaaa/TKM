(function () {
  'use strict';

  /* ---------------------------------------------------------------------
   * Data: loaded from generated tools.json
   * ------------------------------------------------------------------- */
  let standardToolbarTools = [];
  let standardToolbarGroups = [];
  let standardToolbarToolMap = new Map();

  async function loadStandardToolbarData() {
    const response = await fetch('tools.json?v=0.1.54');
    if (!response.ok) throw new Error(`Unable to load tools.json (${response.status})`);
    const payload = await response.json();
    standardToolbarTools = Array.isArray(payload.tools) ? payload.tools : [];
    standardToolbarGroups = Array.isArray(payload.groups) ? payload.groups : [];
    standardToolbarToolMap = new Map(standardToolbarTools.map((tool) => [tool.id, tool]));
  }
  /* End generated tool data */

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
    });
    return tip;
  }

  // Builds a tip for `trigger`, appends it to <body> (tooltips use
  // position:fixed and must not sit inside a transformed ancestor, which
  // would otherwise become their containing block), and wires it into the
  // delegated show/hide system above.
  function registerTip(trigger, tipConfig) {
    tipRegistry.set(trigger, { config: tipConfig, tip: null });
    trigger.dataset.tipTrigger = '';
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

  async function init() {
    try {
      await loadStandardToolbarData();
      ensureStandardToolbarMock();
    } catch (error) {
      console.error('TheKeyMachine toolbar data could not be loaded.', error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
