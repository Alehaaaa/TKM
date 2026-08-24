from TheKeyMachine.tools.tangents import controller


CYCLE_MATCH_MODE_ORIENTATION = controller.CYCLE_MATCH_MODE_ORIENTATION
CYCLE_MATCH_MODE_KEY_COPY = controller.CYCLE_MATCH_MODE_KEY_COPY


def set_tangent(tangent_type, *_args, **kwargs):
    handle_mode = kwargs.pop("handle_mode", "both")
    key_scope = kwargs.pop("key_scope", "selection")
    return controller.set_tangent(
        tangent_type,
        handle_mode=handle_mode,
        key_scope=key_scope,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def set_bouncy(*_args, **kwargs):
    handle_mode = kwargs.pop("handle_mode", "both")
    key_scope = kwargs.pop("key_scope", "selection")
    return controller.set_bouncy(
        handle_mode=handle_mode,
        key_scope=key_scope,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def set_maya_default(tangent_type, *_args, **kwargs):
    return controller.set_maya_default(
        tangent_type,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def match_cycle(*_args, **kwargs):
    target_key = kwargs.pop("target_key", "last")
    return controller.match_cycle(
        target_key=target_key,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def get_cycle_match_mode():
    return controller.get_cycle_match_mode()


def set_cycle_match_mode(mode):
    return controller.set_cycle_match_mode(mode)


def cycle_match_mode_choices():
    """Live-translated choice list for the Cycle Matcher menu's mode picker."""
    from TheKeyMachine.core import i18n

    return [
        {
            "value": CYCLE_MATCH_MODE_ORIENTATION,
            "label": i18n.tr("cycle_match_mode_tangents_only", "Tangents Only"),
            "description": i18n.tr(
                "cycle_match_mode_tangents_only_desc",
                "Match tangent orientation only; key values are left untouched.",
            ),
        },
        {
            "value": CYCLE_MATCH_MODE_KEY_COPY,
            "label": i18n.tr("cycle_match_mode_tangents_and_value", "Tangents and Value"),
            "description": i18n.tr(
                "cycle_match_mode_tangents_and_value_desc",
                "Match tangent orientation and copy the key value too.",
            ),
        },
    ]
