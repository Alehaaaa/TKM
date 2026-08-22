"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io


"""

__version__ = "0.1.43"
__stage__ = "beta"
__build__ = "342"
__codename__ = "Cortado"


def reload():
    import importlib
    import sys

    try:
        from TheKeyMachine.core import runtime

        runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
    except Exception:
        try:
            from TheKeyMachine.core import debug

            if debug.is_enabled():
                from maya import cmds

                cmds.warning("TheKeyMachine.reload(): pre-reload cleanup raised; continuing anyway.")
        except Exception:
            pass

    for module_name in tuple(sys.modules):
        if module_name.startswith("TheKeyMachine."):
            sys.modules.pop(module_name, None)

    importlib.invalidate_caches()
    toolbar = importlib.import_module("TheKeyMachine.ui.widgets.toolbar")

    # The sys.modules purge above always resets toolbar's module-level
    # _toolbar_instance to None, so a get_toolbar() check here can never
    # find the widget torn down by cleanup_for_reload() a few lines up --
    # it would always fall through to this same show() call anyway, just
    # after a second, redundant instance.reload() -> import_module/reload
    # round trip on modules that were just freshly imported.
    #
    # cleanup_for_reload() above has already removed the previous toolbar,
    # its callbacks, and its workspaceControl, so show()'s own
    # cleanup_existing=True pass would only repeat that work -- and, per
    # toolbar.reload()'s own comment on this exact hazard, risks queuing
    # deletion of the workspace-control child this call is about to create.
    toolbar.show(cleanup_existing=False)


def toggle():
    from TheKeyMachine.ui.widgets import toolbar as t
    from TheKeyMachine.tools.graph_toolbar import controller as graph_toolbar

    visible = t.toggle()
    graph_toolbar.set_graph_toolbar_enabled(visible, apply=True)
    return visible


def welcome():
    from TheKeyMachine.ui.widgets import toolbar as t

    t.welcome()
