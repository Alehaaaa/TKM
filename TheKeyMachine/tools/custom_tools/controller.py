"""Custom-tool manifest access."""

from TheKeyMachine.tools.custom_tools import service as connect_entries
from TheKeyMachine.core import application


KIND = "tools"


def entries(notify=True):
    return connect_entries.load_entries(KIND, notify=notify)


def source_spec():
    return connect_entries.source_spec(KIND)


def open_config():
    spec = source_spec()
    return application.open_file(spec["folder"], spec["file"])
