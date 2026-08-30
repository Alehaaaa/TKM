"""Debug-only Script Editor logging for Onion Skin."""

from __future__ import absolute_import

from TheKeyMachine.core import debug


PREFIX = "[TKM Onion Skin]"
ENABLED = debug.is_enabled()


def enabled():
    return ENABLED


def log(event, **details):
    if not enabled():
        return
    values = " ".join(
        "{}={!r}".format(key, details[key]) for key in sorted(details)
    )
    message = "{} {}".format(PREFIX, event)
    if values:
        message = "{} {}".format(message, values)
    print(message)


def log_error(event, error, **details):
    details = dict(details)
    details["error"] = "{}: {}".format(type(error).__name__, error)
    log(event, **details)
