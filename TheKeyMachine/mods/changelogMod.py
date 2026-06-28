import os
import re
from xml.sax.saxutils import escape as xml_escape, quoteattr


CHANGE_KIND_LABELS = {
    "new": "New",
    "changed": "Changed",
    "polish": "Polish",
    "bugfix": "Bugfix",
}
CHANGE_KIND_ORDER = ("new", "changed", "polish", "bugfix")
MAX_CHANGELOG_ENTRIES = 6
UPDATE_CHANGELOG_MAX_HEIGHT = 240


def compare_versions(version1, version2):
    def normalize(version):
        return [int(part) for part in re.sub(r"[^0-9.]", "", str(version or "")).split(".") if part]

    v1 = normalize(version1)
    v2 = normalize(version2)
    max_len = max(len(v1), len(v2))
    v1.extend([0] * (max_len - len(v1)))
    v2.extend([0] * (max_len - len(v2)))

    for index in range(max_len):
        if v1[index] > v2[index]:
            return 1
        if v1[index] < v2[index]:
            return -1
    return 0


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
    if normalized == "bugfix":
        return icons.bugfix
    if normalized == "new":
        return icons.new
    if normalized == "polish":
        return icons.color
    return icons.refresh


def change_kind_label(kind):
    normalized = str(kind or "").strip().lower()
    return CHANGE_KIND_LABELS.get(normalized, normalized.title() if normalized else "Changed")


def change_kind_sort_key(entry):
    try:
        return CHANGE_KIND_ORDER.index(str(entry.get("kind", "")).strip().lower())
    except ValueError:
        return len(CHANGE_KIND_ORDER)


def sort_changelog_entries(entries):
    return sorted(list(entries or []), key=change_kind_sort_key)


def group_changelog_entries(entries):
    groups = []
    by_kind = {}
    for entry in sort_changelog_entries(entries):
        kind = str(entry.get("kind", "")).strip().lower()
        if kind not in by_kind:
            by_kind[kind] = []
            groups.append({"kind": kind, "entries": by_kind[kind]})
        by_kind[kind].append(entry)
    return groups


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

    for section in sections:
        section["entries"] = sort_changelog_entries(section.get("entries", []))

    return sections


def get_local_changelog_sections():
    return parse_changelog_sections(read_local_changelog())


def changelog_sections_between(raw, installed_version, latest_version):
    sections = []
    for section in parse_changelog_sections(raw):
        version = section.get("version", "")
        if compare_versions(version, installed_version) > 0 and compare_versions(version, latest_version) <= 0:
            sections.append(section)
    return sections


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

    return sort_changelog_entries(entries)


def _change_group_template(group):
    kind = group.get("kind", "")
    icon = change_kind_icon(kind)
    label = escape_text(change_kind_label(kind))
    if icon:
        header = (
            '<table cellspacing="0" cellpadding="0"><tr>'
            '<td valign="middle"><img src={} width="20" height="20"/></td>'
            '<td width="5"></td>'
            '<td valign="middle"><b>{}</b></td>'
            "</tr></table>"
        ).format(quoteattr(icon), label)
    else:
        header = "<b>{}</b>".format(label)

    template = "<text>{}</text>\n".format(header)
    for entry in group.get("entries", []):
        template += "<text>  {}</text>\n".format(escape_text(entry.get("description", "")))
    return template


def _changelog_version_template(section):
    template = "<text><span style='font-size:14px;'><b>Version {}</b></span></text>\n".format(escape_text(section.get("version", "")))
    for group in group_changelog_entries(section.get("entries", [])):
        template += _change_group_template(group)
    return template


def changelog_template(raw, version, installed_version=None, max_entries=MAX_CHANGELOG_ENTRIES):
    if installed_version:
        sections = changelog_sections_between(raw, installed_version, version)
    else:
        sections = [{"version": version, "entries": parse_changelog_entries(raw, version)}]

    sections = [section for section in sections if section.get("entries")]
    if not sections:
        return "<text>No changelog available for new version.</text>\n"

    template = '<separator/><scroll max_height="{}">\n'.format(UPDATE_CHANGELOG_MAX_HEIGHT)
    if installed_version:
        for index, section in enumerate(sections):
            template += _changelog_version_template(section)
            if index < len(sections) - 1:
                template += '<separator margin="4"/>\n'
    else:
        entries = sections[0].get("entries", [])
        visible_entries = entries[:max_entries]
        for group in group_changelog_entries(visible_entries):
            template += _change_group_template(group)
        if len(entries) > max_entries:
            template += "<text>And {} more changes.</text>\n".format(len(entries) - max_entries)
    template += "</scroll>\n"

    return template
