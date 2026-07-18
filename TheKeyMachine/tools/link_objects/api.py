"""Public entry points for Copy Relationship."""

from TheKeyMachine.tools.link_objects import controller


def copy_relationship(*args, **kwargs):
    return controller.copy_relationship(*args, **kwargs)


def paste_relationship(*args, **kwargs):
    return controller.paste_relationship(*args, **kwargs)


def paste_relationship_to_range(*args, **kwargs):
    return controller.paste_relationship_to_range(*args, **kwargs)


def is_auto_link_enabled():
    return controller.is_auto_link_enabled()


def set_auto_link_enabled(enabled, *args, **kwargs):
    return controller.set_auto_link_enabled(enabled, *args, **kwargs)


def shutdown():
    return controller.disable_auto_link()
