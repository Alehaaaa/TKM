"""Custom-tool manifest access."""

from TheKeyMachine.core import connectEntries
from TheKeyMachine.mods import generalMod


KIND = "tools"


def entries(notify=True):
    return connectEntries.load_entries(KIND, notify=notify)


def source_spec():
    return connectEntries.source_spec(KIND)


def open_config():
    spec = source_spec()
    return generalMod.open_file(spec["folder"], spec["file"])
