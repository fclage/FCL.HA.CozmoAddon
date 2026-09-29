from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "custom_components" / "ha_cozmo" / "manifest.json").read_text())
HACS_JSON = json.loads((ROOT / "hacs.json").read_text())
BRAND_ICON = ROOT / "custom_components" / "ha_cozmo" / "brand" / "icon.png"

HACS_JSON_KEYS = {
    "content_in_root",
    "country",
    "filename",
    "hacs",
    "hide_default_branch",
    "homeassistant",
    "persistent_directory",
    "render_readme",
    "zip_release",
    "name",
}


def test_manifest_required_fields() -> None:
    assert MANIFEST["domain"] == "ha_cozmo"
    assert MANIFEST["config_flow"] is True
    assert MANIFEST["iot_class"] == "local_polling"
    assert MANIFEST["integration_type"] == "hub"
    assert MANIFEST["quality_scale"] == "custom"
    assert MANIFEST["requirements"] == []
    assert MANIFEST["version"]
    init = (ROOT / "companion" / "__init__.py").read_text()
    server = (ROOT / "companion" / "server.py").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    version = MANIFEST["version"]
    assert f'__version__ = "{version}"' in init
    assert f"ha-cozmo-companion/{version}" in server
    assert f"## {version}\n" in changelog
    assert MANIFEST["documentation"].endswith("FCL.HA.CozmoAddon")
    assert MANIFEST["issue_tracker"].endswith("/issues")


def test_no_private_network_in_defaults() -> None:
    const = (ROOT / "custom_components" / "ha_cozmo" / "const.py").read_text()
    assert 'DEFAULT_URL = "http://127.0.0.1:8790"' in const
    assert "192.168." not in const
    env = (ROOT / ".env.example").read_text()
    assert "Cozmo_XXXXXX" in env
    assert "COZMO_ALLOW" in env


def test_hacs_json_is_a_valid_hacs_manifest() -> None:
    assert isinstance(HACS_JSON, dict)
    assert HACS_JSON["name"]
    extra = set(HACS_JSON) - HACS_JSON_KEYS
    assert not extra, f"unknown hacs.json keys: {sorted(extra)}"


def test_brand_icon_png() -> None:
    assert BRAND_ICON.is_file()
    data = BRAND_ICON.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert BRAND_ICON.stat().st_size > 100
