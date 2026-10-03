"""Publish GitHub releases for manifest versions that have no tag yet.

The tag is v<version>, matching v0.1.0. It points at the first commit on
main whose manifest introduced that version. Release notes are the matching
section of CHANGELOG.md.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "custom_components/ha_cozmo/manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_HEADING = re.compile(r"^## (\d+\.\d+\.\d+)\s*$", re.MULTILINE)


def changelog_sections(text: str) -> dict[str, str]:
    """Return each version heading mapped to the notes under it."""
    matches = list(VERSION_HEADING.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        notes = text[start:end].strip()
        version = match.group(1)
        if not notes:
            raise ValueError(f"CHANGELOG.md has an empty section for {version}")
        sections[version] = notes
    return sections


def releases_to_create(
    history: list[tuple[str, str]],
    published_tags: set[str],
    notes: dict[str, str],
) -> list[dict[str, str]]:
    """Return releases for versions that are not tagged yet, oldest first."""
    pending: list[dict[str, str]] = []
    seen: set[str] = set()
    for version, commit in history:
        if version in seen:
            continue
        seen.add(version)
        tag = f"v{version}"
        if tag in published_tags:
            continue
        body = notes.get(version)
        if not body:
            raise ValueError(f"CHANGELOG.md has no notes for {version}")
        pending.append(
            {"version": version, "tag": tag, "commit": commit, "notes": body}
        )
    return pending


def _run(args: list[str]) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def version_history() -> list[tuple[str, str]]:
    """Oldest-first commits on this checkout that change the manifest version."""
    log = _run(["git", "log", "--reverse", "--format=%H", "HEAD", "--", MANIFEST])
    history: list[tuple[str, str]] = []
    for commit in log.split():
        raw = _run(["git", "show", f"{commit}:{MANIFEST}"])
        version = json.loads(raw)["version"]
        history.append((version, commit))
    return history


def published_tags() -> set[str]:
    _run(["git", "fetch", "--tags", "origin"])
    listed = _run(["gh", "release", "list", "--limit", "200", "--json", "tagName"])
    return {item["tagName"] for item in json.loads(listed or "[]")}


def create_release(release: dict[str, str]) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".md", delete=False
    ) as handle:
        handle.write(release["notes"] + "\n")
        notes_path = Path(handle.name)
    try:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                release["tag"],
                "--target",
                release["commit"],
                "--title",
                release["version"],
                "--notes-file",
                str(notes_path),
            ],
            cwd=ROOT,
            check=True,
        )
    finally:
        notes_path.unlink(missing_ok=True)


def main() -> None:
    notes = changelog_sections(CHANGELOG.read_text(encoding="utf-8"))
    pending = releases_to_create(version_history(), published_tags(), notes)
    if not pending:
        print("No new version to release.")
        return
    for release in pending:
        print(f"Releasing {release['tag']} at {release['commit'][:12]}")
        create_release(release)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
