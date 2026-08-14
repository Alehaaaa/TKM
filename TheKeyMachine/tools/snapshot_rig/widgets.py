"""Snapshot Rig-specific prompts."""

from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets import util as wutil


def confirm_current_default_pose(anchor_widget=None):
    """Ask whether a suspicious current pose should become the saved default."""
    save_default = customDialogs.QFlatDialogButton(
        "Yes", value=True, positive=True, icon=icons.apply,
    )
    skip_default = customDialogs.QFlatDialogButton(
        "No", value=False, positive=False, icon=icons.cancel,
    )
    clicked = customDialogs.QFlatTooltipConfirm.question(
        anchor_widget if wutil.is_valid_widget(anchor_widget) else wutil.get_maya_qt(),
        title="Is this the rig's default pose?",
        message=(
            "The selected controls look posed or animated. Save the current pose "
            "as the rig default? Choosing No still snapshots opposites and mirroring."
        ),
        buttons=[save_default, skip_default],
        icon=icons.mirror,
        highlight=save_default,
    )
    return clicked.get("value") if clicked else None
