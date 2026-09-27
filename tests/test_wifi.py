from companion.wifi import (
    PROFILE,
    filter_unbound_wifi,
    is_cozmo_ssid,
    parse_default_route_iface,
    parse_nmcli_devices,
    pick_wifi_iface,
    reject_default_route_iface,
)


def test_cozmo_ssid_pattern() -> None:
    assert is_cozmo_ssid("Cozmo_ABCDEF")
    assert is_cozmo_ssid("cozmo_abcd")
    assert not is_cozmo_ssid("HomeLAN")
    assert not is_cozmo_ssid("Cozmo")
    assert not is_cozmo_ssid("")


def test_parse_nmcli_devices() -> None:
    text = "\n".join(
        [
            "eth0:ethernet:connected:Wired",
            "wlan0:wifi:connected:HomeLAN",
            "wlan1:wifi:disconnected:",
        ]
    )
    rows = parse_nmcli_devices(text)
    assert [r["iface"] for r in rows] == ["eth0", "wlan0", "wlan1"]
    assert rows[2]["type"] == "wifi"
    assert rows[2]["connection"] is None


def test_parse_default_route_iface() -> None:
    assert parse_default_route_iface("default via 192.168.1.1 dev eth0 proto dhcp") == "eth0"
    assert parse_default_route_iface("") is None


def test_pick_wifi_iface_prefers_explicit() -> None:
    assert pick_wifi_iface("wlan1") == "wlan1"


def test_filter_unbound_skips_default_route_and_foreign_ssid() -> None:
    devices = [
        {"iface": "wlan0", "type": "wifi", "state": "connected", "connection": "HomeLAN"},
        {"iface": "wlan1", "type": "wifi", "state": "disconnected", "connection": None},
        {"iface": "wlan2", "type": "wifi", "state": "connected", "connection": PROFILE},
        {"iface": "wlan3", "type": "wifi", "state": "connected", "connection": "Cozmo_ABCDEF"},
    ]
    unbound = filter_unbound_wifi(devices, default_if="wlan0")
    assert [r["iface"] for r in unbound] == ["wlan1", "wlan2", "wlan3"]
    skipped_dongle = filter_unbound_wifi(devices, default_if="wlan1")
    assert [r["iface"] for r in skipped_dongle] == ["wlan2", "wlan3"]
    only_uplink = filter_unbound_wifi(
        [{"iface": "wlan0", "type": "wifi", "state": "disconnected", "connection": None}],
        default_if="wlan0",
    )
    assert only_uplink == []


def test_reject_default_route_iface() -> None:
    assert reject_default_route_iface("wlan0", "wlan0")
    assert "default route" in (reject_default_route_iface("wlan0", "wlan0") or "")
    assert reject_default_route_iface("wlan1", "wlan0") is None
    assert reject_default_route_iface("wlan1", None) is None
