import logging
from pathlib import Path

from companion.server import CompanionHandler, _log_text

ROOT = Path(__file__).resolve().parents[1]
LABELED_FIELDS = ("token", "ssidSelect", "ssid", "psk", "say")


def test_log_text_strips_line_breaks() -> None:
    assert _log_text("ok") == "ok"
    assert _log_text("a\r\nb\nc") == "abc"


def test_access_log_strips_line_breaks(caplog) -> None:
    handler = CompanionHandler.__new__(CompanionHandler)
    handler.client_address = ("127.0.0.1\nFORGED", 1)

    with caplog.at_level(logging.INFO, logger="ha_cozmo.http"):
        handler.log_message("GET %s", "/ui\r\nFORGED")

    message = caplog.records[0].getMessage()
    assert "\n" not in message
    assert "\r" not in message
    assert "127.0.0.1FORGED - GET /uiFORGED" == message


def test_rejected_request_cannot_forge_a_log_line(caplog) -> None:
    handler = CompanionHandler.__new__(CompanionHandler)
    handler.command = "GET"
    handler.path = "/v1/health\nFORGED"
    handler.client_address = ("10.1.1.1\nFORGED", 9)
    handler.allow = "local"
    handler._send = lambda *_args: None

    with caplog.at_level(logging.WARNING, logger="ha_cozmo.http"):
        assert handler._check_allow() is False

    assert caplog.records
    message = caplog.records[0].getMessage()
    assert "\n" not in message
    assert "\r" not in message
    assert "FORGED" in message


def test_send_sets_nosniff() -> None:
    handler = CompanionHandler.__new__(CompanionHandler)
    handler.command = "GET"
    headers: dict[str, str] = {}
    handler.send_response = lambda _status: None
    handler.send_header = lambda name, value: headers.__setitem__(name, value)
    handler.end_headers = lambda: None
    written = bytearray()

    class _Body:
        def write(self, data: bytes) -> None:
            written.extend(data)

    handler.wfile = _Body()
    handler._send(200, b"{}", "application/json")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Type"] == "application/json"
    assert written == b"{}"


def test_debug_page_labels_its_inputs() -> None:
    html = (ROOT / "companion" / "static" / "index.html").read_text(encoding="utf-8")
    for field in LABELED_FIELDS:
        assert f'for="{field}"' in html
        assert f'id="{field}"' in html
