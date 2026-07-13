"""Example module referenced by the custom tools manifest."""

from maya import cmds


def create_locator():
    """Create and select a locator using normal module-based Python."""
    locator = cmds.spaceLocator(name="tkmCustomLocator#")[0]
    cmds.select(locator, replace=True)
    return locator
