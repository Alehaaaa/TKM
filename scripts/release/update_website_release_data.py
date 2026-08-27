#!/usr/bin/env python3
"""
Update the static website release surfaces from the main package metadata.

Source of truth:
  - TheKeyMachine/version
  - TheKeyMachine/changelog
  - GitHub release metadata, passed as JSON from gh release list

The website branch stays simple static HTML, but its "latest release" panel,
release history, and releases.json are generated instead of hand-maintained.
"""

import argparse
import html
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_MODULE_PATH = REPO_ROOT / "TheKeyMachine" / "tools" / "update" / "changelog.py"
CHANGELOG_FILE = REPO_ROOT / "TheKeyMachine" / "changelog"
VERSION_FILE = REPO_ROOT / "TheKeyMachine" / "version"
DEFAULT_REPOSITORY = "Alehaaaa/TKM"
RELEASE_TAG_PREFIX = "TKM-"
RELEASES_JSON = "releases.json"


def load_changelog_module():
    spec = importlib.util.spec_from_file_location(
        "thekeymachine_changelog", CHANGELOG_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_iso_datetime(value):
    if not value:
        return None
    normalized = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_publish_date(value):
    published = parse_iso_datetime(value)
    if not published:
        return "Release date pending"
    published = published.astimezone(timezone.utc)
    return published.strftime("%B {}, %Y").format(published.day)


def version_key(version):
    parts = []
    for part in str(version or "").split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def release_url(repository, version):
    return "https://github.com/{}/releases/tag/{}{}".format(
        repository, RELEASE_TAG_PREFIX, version
    )


def download_url(repository, version):
    return "https://github.com/{}/releases/download/{}{}/TKM-{}.zip".format(
        repository, RELEASE_TAG_PREFIX, version, version
    )


def expected_asset_name(version):
    return "TKM-{}.zip".format(version)


def find_release_asset(release, version):
    expected_name = expected_asset_name(version)
    for asset in release.get("assets") or []:
        if asset.get("name") == expected_name:
            return asset
    return None


def asset_download_url(release, repository, version):
    asset = find_release_asset(release, version)
    if asset:
        if asset.get("browser_download_url"):
            return asset["browser_download_url"]
        if asset.get("url"):
            return asset["url"]
    return download_url(repository, version)


def load_release_metadata(path):
    if not path:
        return {}
    metadata_path = Path(path)
    if not metadata_path.is_file():
        return {}
    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    releases = raw if isinstance(raw, list) else raw.get("releases", [])
    by_version = {}
    for release in releases:
        tag = str(
            release.get("tagName")
            or release.get("tag_name")
            or release.get("tag")
            or ""
        )
        if not tag.startswith(RELEASE_TAG_PREFIX):
            continue
        by_version[tag[len(RELEASE_TAG_PREFIX) :]] = release
    return by_version


def build_release_records(repository, metadata_path, current_version):
    changelog_module = load_changelog_module()
    changelog_raw = CHANGELOG_FILE.read_text(encoding="utf-8")
    metadata = load_release_metadata(metadata_path)
    sections = changelog_module.parse_changelog_sections(changelog_raw)

    records = []
    for section in sections:
        version = str(section.get("version", "")).strip()
        if not version:
            continue
        if changelog_module.compare_versions(version, current_version) > 0:
            continue
        release = metadata.get(version) or {}
        has_download = bool(find_release_asset(release, version))
        entries = [
            {
                "kind": str(entry.get("kind", "")).strip().lower() or "changed",
                "label": changelog_module.change_kind_label(entry.get("kind", "")),
                "description": str(entry.get("description", "")).strip(),
            }
            for entry in section.get("entries", [])
            if str(entry.get("description", "")).strip()
        ]
        records.append(
            {
                "version": version,
                "tag": "{}{}".format(RELEASE_TAG_PREFIX, version),
                "publishedAt": release.get("publishedAt") or release.get("published_at") or "",
                "publishedLabel": format_publish_date(
                    release.get("publishedAt") or release.get("published_at") or ""
                ),
                "url": release.get("html_url") or release.get("url") or release_url(repository, version),
                # No verified release asset yet (not released, or the upload
                # step failed) -- keep the version listed, but the template
                # renders its download link/label disabled instead of dead.
                "hasDownload": has_download,
                "downloadUrl": asset_download_url(release, repository, version) if has_download else None,
                "entries": entries,
            }
        )

    records.sort(key=lambda item: version_key(item["version"]), reverse=True)
    for index, record in enumerate(records):
        previous = records[index + 1]["version"] if index + 1 < len(records) else ""
        record["compareUrl"] = (
            "https://github.com/{}/compare/{}{}...{}{}".format(
                repository, RELEASE_TAG_PREFIX, previous, RELEASE_TAG_PREFIX, record["version"]
            )
            if previous
            else record["url"]
        )
    return records


def replace_block(text, pattern, replacement, label):
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise SystemExit("Could not find {} block to update".format(label))
    return updated


def render_latest_panel(latest):
    version = html.escape(latest["version"])
    if latest["hasDownload"]:
        download_action = '<a class="primary-button" href="{download}">Download latest · {version}</a>'.format(
            download=html.escape(latest["downloadUrl"], quote=True), version=version
        )
        context_note = "Universal package · ZIP"
    else:
        download_action = (
            '<span class="primary-button is-disabled" aria-disabled="true">'
            "Download latest · {version}</span>"
        ).format(version=version)
        context_note = "Build not uploaded yet"
    return """<section class="download-panel" aria-labelledby="latest-download">
      <div>
        <p class="section-kicker">Latest release</p>
        <h2 id="latest-download">{version}</h2>
        <p>{published}. Supports Maya 2022 through 2027 on Windows, Linux and macOS.</p>
      </div>
      <div class="download-actions">
        {download_action}
        <span class="download-context" data-platform-note>{context_note}</span>
        <a class="secondary-link" href="changelog/">View changelog</a>
      </div>
    </section>""".format(
        version=version,
        published=html.escape(published_phrase(latest)),
        download_action=download_action,
        context_note=context_note,
    )


def published_phrase(record):
    label = record.get("publishedLabel") or "Release date pending"
    if label == "Release date pending":
        return label
    return "Published {}".format(label)


def render_release_card(record):
    entries = "\n".join(
        "          <li><strong>{}:</strong> {}.</li>".format(
            html.escape(entry["label"]),
            html.escape(entry["description"]).rstrip("."),
        )
        for entry in record["entries"]
    )
    if not entries:
        entries = "          <li>No changelog entries recorded for this version.</li>"

    version = html.escape(record["version"])
    if record["hasDownload"]:
        heading = '<a href="{download}">{version}</a>'.format(
            download=html.escape(record["downloadUrl"], quote=True), version=version
        )
    else:
        heading = '<span class="is-disabled" aria-disabled="true">{version}</span>'.format(
            version=version
        )

    return """      <article class="release-card" id="release-{anchor}">
        <h2>{heading}</h2>
        <p class="release-date">{date}</p>
        <ul>
{entries}
        </ul>
        <a class="release-compare" href="{compare}" target="_blank" rel="noopener">Full changelog</a>
      </article>""".format(
        heading=heading,
        anchor=html.escape(record["version"].replace(".", "-"), quote=True),
        date=html.escape(published_phrase(record)),
        entries=entries,
        compare=html.escape(record["compareUrl"], quote=True),
    )


def render_release_list(records):
    cards = "\n\n".join(render_release_card(record) for record in records)
    return """<section class="release-list" aria-label="TheKeyMachine releases">
{cards}
    </section>""".format(cards=cards)


def write_json(path, records, latest_version):
    payload = {
        "latest": latest_version,
        "generatedFrom": {
            "versionFile": "TheKeyMachine/version",
            "changelog": "TheKeyMachine/changelog",
        },
        "releases": records,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_website(website_root, records):
    if not records:
        raise SystemExit("No changelog releases found to publish to the website")

    index_path = website_root / "index.html"
    changelog_path = website_root / "changelog" / "index.html"
    for path in (index_path, changelog_path):
        if not path.is_file():
            raise SystemExit("Missing website file: {}".format(path))

    index_html = index_path.read_text(encoding="utf-8")
    index_html = replace_block(
        index_html,
        r"<section class=\"download-panel\"[^>]*>.*?</section>",
        render_latest_panel(records[0]),
        "latest release",
    )
    index_path.write_text(index_html, encoding="utf-8")

    changelog_html = changelog_path.read_text(encoding="utf-8")
    changelog_html = replace_block(
        changelog_html,
        r"<section class=\"release-list\"[^>]*>.*?</section>",
        render_release_list(records),
        "release list",
    )
    changelog_path.write_text(changelog_html, encoding="utf-8")

    write_json(website_root / RELEASES_JSON, records, records[0]["version"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("website_root", help="Checkout path for the website branch")
    parser.add_argument(
        "--release-metadata",
        help="JSON file produced by gh api repos/<owner>/<repo>/releases",
    )
    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help="GitHub repository slug used for fallback release links",
    )
    args = parser.parse_args()

    website_root = Path(args.website_root).resolve()
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    records = build_release_records(args.repository, args.release_metadata, version)
    if not records or records[0]["version"] != version:
        raise SystemExit(
            "{} does not contain a changelog section for current version {}".format(
                CHANGELOG_FILE, version
            )
        )
    update_website(website_root, records)
    print("website_version={}".format(version))
    print("website_releases={}".format(len(records)))


if __name__ == "__main__":
    main()
