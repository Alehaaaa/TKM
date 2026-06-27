import os
from xml.sax.saxutils import escape as xml_escape, quoteattr


CHANGE_KIND_LABELS = {
    "new": "New",
    "feature": "New",
    "functionality": "New",
    "bugfix": "Bugfix",
    "fix": "Bugfix",
    "change": "Changed",
    "changed": "Changed",
    "ui": "UI",
    "polish": "Polish",
    "performance": "Performance",
}
MAX_CHANGELOG_ENTRIES = 6


def local_changelog_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "changelog")


def read_local_changelog():
    try:
        with open(local_changelog_path(), "r") as handle:
            return handle.read()
    except (IOError, OSError):
        return ""


def change_kind_icon(kind):
    try:
        from TheKeyMachine.data import icons
    except ImportError:
        return ""

    normalized = str(kind or "").strip().lower()
    if normalized in {"bugfix", "fix"}:
        return icons.bugfix
    if normalized in {"new", "feature", "functionality"}:
        return icons.new
    if normalized in {"ui", "polish"}:
        return icons.color
    if normalized == "performance":
        return icons.system
    return icons.refresh


def change_kind_label(kind):
    normalized = str(kind or "").strip().lower()
    return CHANGE_KIND_LABELS.get(normalized, normalized.title() if normalized else "Changed")


def escape_text(text):
    return xml_escape(str(text or ""))


def parse_changelog_sections(raw):
    sections = []
    current = None

    for raw_line in str(raw or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.endswith(":") and not line.startswith("-"):
            current = {"version": line[:-1].strip(), "entries": []}
            sections.append(current)
            continue

        if line.startswith("-") and current:
            item = line[1:].strip()
            if ":" not in item:
                continue
            kind, description = [part.strip() for part in item.split(":", 1)]
            if description:
                current["entries"].append({"kind": kind, "description": description})

    return sections


def get_local_changelog_sections():
    return parse_changelog_sections(read_local_changelog())


def parse_changelog_entries(raw, version):
    entries = []
    target_version = str(version or "").strip()

    for section in parse_changelog_sections(raw):
        if section.get("version") == target_version:
            entries.extend(section.get("entries", []))

    for line in str(raw or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        parts = [part.strip() for part in stripped.split("|", 2)]
        if len(parts) != 3:
            continue

        entry_version, kind, description = parts
        if entry_version == target_version and description:
            entries.append({"kind": kind, "description": description})

    return entries


def changelog_template(raw, version, max_entries=MAX_CHANGELOG_ENTRIES):
    entries = parse_changelog_entries(raw, version)
    if not entries:
        return "<text>No changelog available for new version.</text>\n"

    template = "<separator/><text><b>What's changed</b></text>\n"
    for entry in entries[:max_entries]:
        kind = entry.get("kind", "")
        icon = change_kind_icon(kind)
        label = escape_text(change_kind_label(kind))
        description = escape_text(entry.get("description", ""))
        icon_html = ""
        if icon:
            icon_html = '<img src={} width="20" height="20" align="middle"/> '.format(quoteattr(icon))
        template += "<text>{}<b>{}</b> {}</text>\n".format(icon_html, label, description)

    if len(entries) > max_entries:
        template += "<text>And {} more changes.</text>\n".format(len(entries) - max_entries)

    return template
