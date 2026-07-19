"""Scene-query examples for the custom tools manifest."""

from maya import cmds


def show_selection_count():
    """Report the current Maya selection count."""
    count = len(cmds.ls(selection=True) or [])
    cmds.warning("Selected objects: {}".format(count))
    return count
