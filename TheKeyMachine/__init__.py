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

__version__ = "0.1.84"
__stage__ = "beta"
__build__ = "313"
__codename__ = "Iced Coffee"


def reload():
    import sys

    try:
        from importlib import reload
    except ImportError:
        from imp import reload
    except ImportError:
        pass

    try:
        import TheKeyMachine.core.runtime_manager as runtime

        runtime.shutdown_runtime_manager()
    except Exception:
        pass

    try:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets

        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.property("tkm_floating_widget"):
                widget.close()
                try:
                    widget.deleteLater()
                except Exception:
                    pass
    except Exception:
        pass

    modules_to_delete = [m for m in list(sys.modules.keys()) if m.startswith("TheKeyMachine")]

    for mod_name in modules_to_delete:
        del sys.modules[mod_name]

    import TheKeyMachine.core.toolbar as t

    reload(t)

    tb = t.get_toolbar()
    if tb:
        tb.reload()
    else:
        t.show()


def toggle():
    import TheKeyMachine.core.toolbar as t

    t.toggle()
