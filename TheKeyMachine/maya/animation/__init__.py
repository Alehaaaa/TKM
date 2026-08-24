"""Unified animation workflow API."""

from .context import (
    SelectionSnapshot,
    ToolContext,
    capture_selection_snapshot,
    current_selection_snapshot,
    capture_time_slider_selection,
    notify_empty,
    preserve_key_selection,
    resolve_context,
    restore_time_slider_selection,
    selection_time_kwargs,
)
from .curves import (
    apply_smart_euler_filter,
    apply_key_tangent_snapshot,
    apply_key_tangent_snapshots,
    apply_weighted_tangents,
    apply_curve_shape,
    bouncy_tangent_angles,
    capture_curve_shape,
    detail_priority_with_scores,
    euler_full_turn,
    euler_turn_groups,
    key_tangent_snapshots,
    sample_times,
)
from .graph import LayerGraph, layer_graph, root_layer_name, scene_layer_objects
from .layers import (
    AnimationLayer,
    BASE_LAYER_ID,
    LayerCache,
    LayerContext,
    has_anim_layers,
    layer_cache,
    layer_id_for_name,
    restore_created_layer_states,
    scene_layer_names,
    weight_curves,
)
