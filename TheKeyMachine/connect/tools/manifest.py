"""Custom tools shown in TheKeyMachine.

RULES
1. Keep the ``TOOLS`` dictionary name unchanged.
2. Each dictionary key is the visible tool name and its toolbar pin identity.
   Names must be unique; command ids are normalized for Maya hotkeys and shelves.
   Renaming one creates a new pin identity unless an explicit ``id`` is provided.
3. Dictionary order controls the menu and toolbar pin-menu order.
4. Each entry needs either ``run`` for Python or ``mel`` for MEL.
5. ``run`` may contain ``"module:function"`` or a short Python command.
6. ``icon`` is optional but recommended. It may contain ``icons.<tkm_icon>``,
   ``"icons.<tkm_icon>"``, an image path relative to this folder, or a Maya
   Qt resource such as ``":/mel_tab.png"``. Paths beginning with ``:/`` are
   built into Maya, so they need no local image file or path resolution.
   Without an icon, the toolbar button displays the first three letters of
   the name.
7. Add ``"enabled": False`` to keep an entry without displaying it.
8. Add ``"tooltip"`` with a string or list of paragraphs to document the tool.

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
        "icon": icons.add,
        "tooltip": "Create a locator at the current selection.",
        "run": "examples.locators:create_locator",
    },
    "Example: Show Selection Count": {
        "icon": "example_tool.svg",
        "run": "examples.scene_info:show_selection_count",
    },
    # Or write short Python directly. ``cmds`` and ``mel`` are ready to use.
    "Example: Inline Python": {
        "icon": ":/py_tab.png",
        "run": "cmds.warning('Custom tool ran')",
    },
    "Example: Inline MEL": {
        "icon": ":/mel_tab.png",
        "mel": 'warning "Custom MEL tool ran";',
    },
}
