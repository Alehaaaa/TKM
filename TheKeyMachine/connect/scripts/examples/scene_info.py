"""Example module referenced by the custom scripts manifest."""

from maya import cmds


def show_selection_count():
    """Report the current selection using normal module-based Python."""
    count = len(cmds.ls(selection=True) or [])
    cmds.warning("Selected objects: {}".format(count))
    return count
