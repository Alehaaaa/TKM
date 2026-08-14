"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Modified by: Alehaaaa / alehaaaa.github.io



"""

from TheKeyMachine.core.Qt import QtCore
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets.util import is_valid_widget

_workspaces_window = None


def show_workspaces_window(*_args, parent=None):
    """Open the Workspaces editor, reusing the existing window if already open."""
    global _workspaces_window

    if _workspaces_window is not None and is_valid_widget(_workspaces_window):
        _workspaces_window.show()
        _workspaces_window.raise_()
        _workspaces_window.activateWindow()
        return _workspaces_window

    from TheKeyMachine.tools.workspaces import widgets

    dlg = widgets.WorkspacesWindow(parent=parent)
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def _clear_ref():
        global _workspaces_window
        _workspaces_window = None

    toolCommon.invalidate_cached_window_on_language_change(dlg, _clear_ref)
    _workspaces_window = dlg
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg
