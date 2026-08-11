from TheKeyMachine.tools.tangents import controller
from TheKeyMachine.tools import common as toolCommon


CYCLE_MATCH_MODE_ORIENTATION = controller.CYCLE_MATCH_MODE_ORIENTATION
CYCLE_MATCH_MODE_KEY_COPY = controller.CYCLE_MATCH_MODE_KEY_COPY


def _run(tool_id, callback):
    with toolCommon.tool_operation(tool_id=tool_id, undo=True, progress=False):
        return callback()


def set_tangent(tangent_type, *_args, **kwargs):
    handle_mode = kwargs.pop("handle_mode", "both")
    key_scope = kwargs.pop("key_scope", "selection")
    return _run(
        "tangent_{}".format(tangent_type),
        lambda: controller.set_tangent(tangent_type, handle_mode=handle_mode, key_scope=key_scope),
    )


def set_bouncy(*_args, **kwargs):
    handle_mode = kwargs.pop("handle_mode", "both")
    key_scope = kwargs.pop("key_scope", "selection")
    return _run("tangent_bouncy", lambda: controller.set_bouncy(handle_mode=handle_mode, key_scope=key_scope))


def set_maya_default(tangent_type, *_args, **_kwargs):
    return _run("tangent_{}_default".format(tangent_type), lambda: controller.set_maya_default(tangent_type))


def match_cycle(*_args, **kwargs):
    target_key = kwargs.pop("target_key", "last")
    return _run("tangent_cycle_matcher", lambda: controller.match_cycle(target_key=target_key))


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
