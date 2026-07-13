"""Custom scripts shown in TheKeyMachine.

RULES
1. Keep the ``SCRIPTS`` dictionary name unchanged.
2. Each dictionary key is the visible script name and its toolbar pin identity.
   Names must be unique; renaming one creates a new pin identity.
3. Dictionary order controls the menu and toolbar pin-menu order.
4. Each entry needs either ``run`` for Python or ``mel`` for MEL.
5. ``run`` may contain ``"module:function"`` or a short Python command.
6. ``icon`` is optional but recommended. It may contain ``icons.<tkm_icon>``,
   ``"icons.<tkm_icon>"``, or an image path relative to this folder. Without
   an icon, the toolbar button displays the first three letters of the name.
7. Add ``"enabled": False`` to keep an entry without displaying it.

ADDING A MODULE SCRIPT
1. Add a Python file anywhere inside this folder. Every module subfolder must
   contain an ``__init__.py`` file.
2. Write a function that runs without required arguments.
3. Add an entry whose ``run`` value is ``"subfolder.module:function"``.
4. Open the Custom Scripts menu to load the entry and update pinned scripts.

RELOAD LOGIC
Opening the Custom Scripts menu reloads this manifest. Referenced Python modules
reload immediately before their function runs. Short Python commands receive
Maya ``cmds`` and ``mel`` automatically.
"""

from TheKeyMachine.data import icons


SCRIPTS = {
    # Run a function from any module/subfolder in this package.
    "Example: Show Selection Count": {
        "icon": icons.tangent_spline,
        "run": "examples.scene_info:show_selection_count",
    },
    # Local image filenames resolve from this custom scripts folder.
    "Example: Inline MEL": {
        "icon": "example_script.svg",
        "mel": 'warning "Custom MEL script ran";',
    },
}
