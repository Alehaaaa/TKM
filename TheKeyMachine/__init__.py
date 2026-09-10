"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io


"""

__version__ = "1.0.0"
__stage__ = "beta"
__build__ = "356"
__codename__ = "Cortado"
__website__ = "https://alehaaaa.github.io/TKM/"


def reload():
    import importlib
    import sys

    package = sys.modules.get(__name__)
    if getattr(package, "_reload_in_progress", False):
        return
    package._reload_in_progress = True
    try:
        from TheKeyMachine.core import runtime

        if getattr(runtime, "_CLEANING_UP", False):
            return
        runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        for module_name in tuple(sys.modules):
            if module_name.startswith("TheKeyMachine."):
                module = sys.modules.pop(module_name, None)
                
                parent_name, _, child = module_name.rpartition(".")
                if parent_name == __name__ and getattr(package, child, None) is module:
                    delattr(package, child)

        importlib.invalidate_caches()
        importlib.reload(package)
        
        toolbar = importlib.import_module("TheKeyMachine.ui.widgets.toolbar")
        toolbar.show(cleanup_existing=False)

    finally:
        package._reload_in_progress = False


def unload():
    from TheKeyMachine.core import runtime
    return runtime.cleanup_for_reload(delete_workspace=True, process_events=True)


def toggle():
    from TheKeyMachine.ui.widgets import toolbar as t
    from TheKeyMachine.tools.graph_toolbar import controller as graph_toolbar

    visible = t.toggle()
    graph_toolbar.set_graph_toolbar_enabled(visible, apply=True)
    return visible


def welcome():
    from TheKeyMachine.ui.widgets import toolbar as t
    t.welcome()
