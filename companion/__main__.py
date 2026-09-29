"""python -m companion"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from pathlib import Path

from .robot import RobotSession
from .server import serve

log = logging.getLogger("ha_cozmo")


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    parser = argparse.ArgumentParser(prog="python -m companion")
    parser.add_argument(
        "--listen",
        default=os.environ.get("LISTEN", "0.0.0.0:8790"),
        help="host:port to bind (default 0.0.0.0:8790, or LISTEN)",
    )
    parser.add_argument(
        "--allow",
        default=os.environ.get("COZMO_ALLOW", "private"),
        help="who may connect: local, a CIDR, private, or all (default private, or COZMO_ALLOW)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    listen = args.listen
    if ":" in listen:
        host, port_s = listen.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = "0.0.0.0", int(listen)

    settings = {
        "ssid": os.environ.get("COZMO_SSID", ""),
        "password": os.environ.get("COZMO_PASSWORD", ""),
        "wifi_iface": os.environ.get("COZMO_WIFI_IFACE", ""),
        "robot_host": os.environ.get("COZMO_HOST", "172.31.1.1"),
        "robot_port": int(os.environ.get("COZMO_PORT", "5551")),
        "camera_color": _truthy(os.environ.get("CAMERA_COLOR", "0")),
        "dry_run": _truthy(os.environ.get("COZMO_DRY_RUN", "0")),
        "ffmpeg": os.environ.get("FFMPEG_PATH", "ffmpeg"),
    }
    token = os.environ.get("COMPANION_TOKEN", "")

    if not settings["wifi_iface"] and settings["ssid"] and not settings["dry_run"]:
        from .wifi import pick_wifi_iface

        try:
            settings["wifi_iface"] = pick_wifi_iface("")
            log.info("auto-selected wifi iface %s", settings["wifi_iface"])
        except Exception as exc:  # noqa: BLE001
            log.warning("wifi auto-select failed: %s", exc)

    robot = RobotSession(settings)
    robot.start()

    if settings["ssid"] and not settings["dry_run"]:
        robot.submit("wifi_join")
    robot.submit("connect")

    allow = args.allow or "private"
    log.info("HTTP allow policy: %s", allow)
    httpd = serve(robot, host, port, token=token, allow=allow)

    def _shutdown(_signum=None, _frame=None) -> None:
        log.info("shutting down")
        # shutdown() must not run on the serve_forever thread (signal deadlock).
        threading.Thread(target=httpd.shutdown, name="cozmo-http-stop", daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("companion listening on http://%s:%s (dry_run=%s)", host, port, settings["dry_run"])
    try:
        httpd.serve_forever()
    finally:
        robot.stop()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
