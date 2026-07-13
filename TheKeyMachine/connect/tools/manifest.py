"""Custom tools shown in TheKeyMachine.

RULES
1. Keep the ``TOOLS`` dictionary name unchanged.
2. Each dictionary key is the visible tool name and its toolbar pin identity.
   Names must be unique; renaming one creates a new pin identity.
3. Dictionary order controls the menu and toolbar pin-menu order.
4. Each entry needs either ``run`` for Python or ``mel`` for MEL.
5. ``run`` may contain ``"module:function"`` or a short Python command.
6. ``icon`` is optional but recommended. It may contain ``icons.<tkm_icon>``,
   ``"icons.<tkm_icon>"``, or an image path relative to this folder. Without
   an icon, the toolbar button displays the first three letters of the name.
7. Add ``"enabled": False`` to keep an entry without displaying it.

ADDING A MODULE TOOL
1. Add a Python file anywhere inside this folder. Every module subfolder must
   contain an ``__init__.py`` file.
2. Write a function that runs without required arguments.
3. Add an entry whose ``run`` value is ``"subfolder.module:function"``.
4. Open the Custom Tools menu to load the entry and update pinned tools.

RELOAD LOGIC
Opening the Custom Tools menu reloads this manifest. Referenced Python modules
reload immediately before their function runs. Short Python commands receive
Maya ``cmds`` and ``mel`` automatically.
"""

from TheKeyMachine.data import icons


TOOLS = {
    # Run a function from any module/subfolder in this package.
    "Example: Create Locator": {
        "icon": icons.selection_sets,
        "run": "examples.locators:create_locator",
    },
    # Or write short Python directly. ``cmds`` and ``mel`` are ready to use.
    "Example: Inline Python": {
        "icon": "example_tool.svg",
        "run": "cmds.warning('Custom tool ran')",
    },
}
