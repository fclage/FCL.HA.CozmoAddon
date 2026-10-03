from __future__ import annotations

import pytest

from scripts.create_releases import changelog_sections, releases_to_create

CHANGELOG = """# Changelog

## 0.1.2

- Second change.

## 0.1.1

- First change.

## 0.1.0

First release.
"""


def test_changelog_sections_keep_the_notes() -> None:
    sections = changelog_sections(CHANGELOG)
    assert sections["0.1.2"] == "- Second change."
    assert sections["0.1.1"] == "- First change."
    assert sections["0.1.0"] == "First release."


def test_empty_changelog_section_is_rejected() -> None:
    with pytest.raises(ValueError, match="0.1.1"):
        changelog_sections("## 0.1.1\n\n## 0.1.0\n\nFirst release.\n")


def test_releases_skip_tags_and_keep_the_first_commit() -> None:
    history = [
        ("0.1.0", "aaa"),
        ("0.1.0", "ignored"),
        ("0.1.1", "bbb"),
        ("0.1.2", "ccc"),
    ]
    pending = releases_to_create(history, {"v0.1.0"}, changelog_sections(CHANGELOG))
    assert [(item["tag"], item["commit"]) for item in pending] == [
        ("v0.1.1", "bbb"),
        ("v0.1.2", "ccc"),
    ]
    assert pending[0]["notes"] == "- First change."


def test_missing_changelog_notes_are_rejected() -> None:
    with pytest.raises(ValueError, match="0.9.0"):
        releases_to_create([("0.9.0", "abc")], set(), changelog_sections(CHANGELOG))
