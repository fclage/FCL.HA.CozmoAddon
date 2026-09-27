"""NetworkManager helpers to scan and join Cozmo APs.

Rules:

- Only a dedicated Wi-Fi iface (USB dongle). Never the LAN / default-route NIC.
- `ipv4.never-default yes` plus a high route metric (Ethernet stays default).
- Disable radio power save — otherwise the robot shows **COZMO 01**.
- Optional `sudo -n` retry when polkit blocks nmcli.
- Do not call bare `nmcli device wifi connect`.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from typing import Optional

log = logging.getLogger("ha_cozmo.wifi")

PROFILE = "cozmo-ap"
SSID_RE = re.compile(r"^Cozmo_[0-9A-Fa-f]{4,}$", re.IGNORECASE)
ROUTE_METRIC = 600


def is_cozmo_ssid(ssid: str) -> bool:
    return bool(SSID_RE.match((ssid or "").strip()))


def _needs_elevation(stderr: str, stdout: str) -> bool:
    err = f"{stderr}\n{stdout}".lower()
    needles = (
        "permission",
        "privileges",
        "privilege",
        "not authorized",
        "authorization",
        "polkit",
        "not allowed",
        "access denied",
        "only root",
        "as root",
        "insufficient",
    )
    return any(n in err for n in needles)


def _run(cmd: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    """Run *cmd*. Prefer `sudo -n` for nmcli/iw so PSK lands in the system profile."""
    is_nm = bool(cmd) and (cmd[0].endswith("nmcli") or cmd[0].endswith("iw") or cmd[0] in {"nmcli", "iw"})
    if is_nm and shutil.which("sudo"):
        proc = subprocess.run(
            ["sudo", "-n", *cmd],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0 or not _sudo_missing(proc):
            return proc
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
    if proc.returncode == 0:
        return proc
    if is_nm or _needs_elevation(proc.stderr or "", proc.stdout or ""):
        if not shutil.which("sudo"):
            return proc
        log.info("Retrying with sudo -n: %s", " ".join(cmd[:6]))
        return subprocess.run(
            ["sudo", "-n", *cmd],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    return proc


def _sudo_missing(proc: subprocess.CompletedProcess) -> bool:
    err = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()
    return "password is required" in err or "a password is required" in err


def _nmcli(*args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return _run(["nmcli", *args], timeout=timeout)


def parse_nmcli_devices(text: str) -> list[dict]:
    """Parse `nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device` output."""
    rows = []
    for line in (text or "").splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        rows.append(
            {
                "iface": parts[0],
                "type": parts[1],
                "state": parts[2],
                "connection": parts[3] or None,
            }
        )
    return rows


def parse_default_route_iface(text: str) -> Optional[str]:
    """Parse `ip -4 route show default` — first `dev <iface>`."""
    for line in (text or "").splitlines():
        parts = line.split()
        if "dev" in parts:
            i = parts.index("dev")
            if i + 1 < len(parts):
                return parts[i + 1]
    return None


def default_route_iface() -> Optional[str]:
    if not shutil.which("ip"):
        return None
    proc = _run(["ip", "-4", "route", "show", "default"], timeout=5)
    return parse_default_route_iface(proc.stdout or "")


def list_wifi_devices() -> list[dict]:
    if shutil.which("nmcli"):
        proc = _nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device")
        return [r for r in parse_nmcli_devices(proc.stdout or "") if r["type"] == "wifi"]
    # Fallback: sysfs wireless dirs
    import pathlib

    found = []
    root = pathlib.Path("/sys/class/net")
    if not root.is_dir():
        return found
    for path in sorted(root.iterdir()):
        if (path / "wireless").exists() or (path / "phy80211").exists():
            found.append(
                {"iface": path.name, "type": "wifi", "state": "unknown", "connection": None}
            )
    return found


def filter_unbound_wifi(devices: list[dict], default_if: Optional[str]) -> list[dict]:
    """Wi-Fi NICs that are safe to use for Cozmo.

    Skips the interface that owns the default route (LAN / HA uplink).
    Skips radios already associated to a non-Cozmo SSID.
    """
    unbound = []
    for row in devices:
        iface = row["iface"]
        if default_if and iface == default_if:
            continue
        conn = row.get("connection") or ""
        state = (row.get("state") or "").lower()
        if state in {"connected", "connecting"} and conn and conn != PROFILE and not is_cozmo_ssid(conn):
            continue
        unbound.append(row)
    return unbound


def list_unbound_wifi() -> list[dict]:
    return filter_unbound_wifi(list_wifi_devices(), default_route_iface())


def reject_default_route_iface(iface: str, default_if: Optional[str]) -> Optional[str]:
    """Return an error if *iface* is the host default-route NIC."""
    if iface and default_if and iface == default_if:
        return (
            f"{iface} owns the default route; refusing to join Cozmo on the LAN/uplink NIC. "
            "Use a USB Wi-Fi dongle (never the default-route interface)."
        )
    return None


def pick_wifi_iface(preferred: str = "") -> str:
    """Use *preferred* if set; otherwise the first unbound Wi-Fi NIC."""
    wanted = (preferred or "").strip()
    if wanted:
        return wanted
    unbound = list_unbound_wifi()
    if not unbound:
        raise RuntimeError(
            "No unbound Wi-Fi interface found. Plug in a USB Wi-Fi dongle "
            "(not the NIC that carries the default route) or set wifi_device."
        )
    return unbound[0]["iface"]


def wifi_status(iface: str) -> dict:
    """Return nmcli device state for *iface* (or a stub if nmcli is missing)."""
    if not iface:
        return {"iface": "", "state": "unconfigured", "connection": None}
    if not shutil.which("nmcli"):
        return {"iface": iface, "state": "nmcli-missing", "connection": None}
    try:
        proc = _nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device")
        out = proc.stdout or ""
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {"iface": iface, "state": f"error:{exc}", "connection": None}
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[0] == iface:
            return {
                "iface": iface,
                "type": parts[1],
                "state": parts[2],
                "connection": parts[3] or None,
            }
    return {"iface": iface, "state": "not-found", "connection": None}


def scan_cozmo_networks(iface: str = "", rescan: bool = True) -> list[dict]:
    """List nearby `Cozmo_*` APs."""
    if not shutil.which("nmcli"):
        raise RuntimeError("nmcli not found")
    if rescan:
        cmd = ["device", "wifi", "rescan"]
        if iface:
            cmd += ["ifname", iface]
        _nmcli(*cmd, timeout=15)
        time.sleep(1.2)
    cmd = ["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
    if iface:
        cmd += ["ifname", iface]
    proc = _nmcli(*cmd, timeout=20)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "wifi scan failed").strip())
    seen: dict[str, dict] = {}
    for line in proc.stdout.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        in_use = parts[0] in {"*", "yes"}
        ssid = parts[1]
        if not is_cozmo_ssid(ssid):
            continue
        try:
            signal = int(parts[2] or 0)
        except ValueError:
            signal = 0
        security = ":".join(parts[3:])
        prev = seen.get(ssid)
        if prev is None or signal > int(prev["signal"]):
            seen[ssid] = {
                "ssid": ssid,
                "signal": signal,
                "security": security,
                "in_use": in_use,
            }
        elif in_use:
            seen[ssid]["in_use"] = True
    return sorted(seen.values(), key=lambda n: (-int(n["signal"]), n["ssid"]))


def _profile_exists() -> bool:
    proc = _nmcli("-t", "-f", "NAME", "connection", "show")
    if proc.returncode != 0:
        return False
    return any(line.strip() == PROFILE for line in proc.stdout.splitlines())


def _disable_power_save(iface: str) -> None:
    """Cozmo shows COZMO 01 if the STA radio sleeps."""
    if not iface or not shutil.which("iw"):
        return
    _run(["iw", "dev", iface, "set", "power_save", "off"], timeout=5)


def _set_psk(password: str) -> tuple[bool, str]:
    """Store the PSK as root without putting it in sudo's command log."""
    script = (
        "import subprocess, sys\n"
        "psk = sys.stdin.read()\n"
        "cmd = ['nmcli','connection','modify','cozmo-ap',"
        "'802-11-wireless-security.key-mgmt','wpa-psk',"
        "'802-11-wireless-security.proto','rsn',"
        "'802-11-wireless-security.pairwise','ccmp,tkip',"
        "'802-11-wireless-security.group','tkip',"
        "'802-11-wireless-security.psk-flags','0',"
        "'802-11-wireless-security.psk', psk]\n"
        "proc = subprocess.run(cmd, check=False, capture_output=True, text=True)\n"
        "sys.stderr.write((proc.stderr or proc.stdout or '').replace(psk, ''))\n"
        "sys.exit(proc.returncode)\n"
    )
    proc = subprocess.run(
        ["sudo", "-n", "python3", "-c", script],
        input=password,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    err = (proc.stderr or proc.stdout or "").replace(password, "")
    return proc.returncode == 0, err.strip()


def _ensure_profile(iface: str, ssid: str, password: str) -> tuple[bool, str]:
    """Create or update a never-default, iface-bound Cozmo AP profile."""
    if not _profile_exists():
        proc = _nmcli(
            "connection",
            "add",
            "type",
            "wifi",
            "ifname",
            iface,
            "con-name",
            PROFILE,
            "ssid",
            ssid,
            "autoconnect",
            "no",
        )
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or "nmcli connection add failed").strip()
    mods = [
        "connection",
        "modify",
        PROFILE,
        "connection.interface-name",
        iface,
        "802-11-wireless.ssid",
        ssid,
        "802-11-wireless.mode",
        "infrastructure",
        "802-11-wireless.band",
        "bg",
        "802-11-wireless.powersave",
        "2",
        "ipv4.method",
        "auto",
        "ipv4.never-default",
        "yes",
        "ipv4.route-metric",
        str(ROUTE_METRIC),
        "ipv6.method",
        "ignore",
        "ipv6.never-default",
        "yes",
        "connection.autoconnect",
        "no",
    ]
    proc = _nmcli(*mods)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "nmcli connection modify failed").strip()
    if password:
        # psk-flags 0 stores the PSK in the system connection so root nmcli
        # can activate it. The secret is passed on stdin, not on the sudo
        # command line (sudo logs argv).
        ok, err = _set_psk(password)
        if not ok:
            return False, err or "nmcli psk failed"
    return True, "profile ready"


def join_ap(iface: str, ssid: str, password: str) -> tuple[bool, str]:
    """Associate *iface* with Cozmo's AP. Never uses the default-route NIC.

    Empty *iface* selects the first unbound Wi-Fi radio. Returns (ok, message).
    """
    if not iface:
        try:
            iface = pick_wifi_iface("")
            log.info("auto-selected wifi iface %s", iface)
        except RuntimeError as exc:
            return False, str(exc)
    conflict = reject_default_route_iface(iface, default_route_iface())
    if conflict:
        log.warning("%s", conflict)
        return False, conflict
    ssid = (ssid or "").strip()
    if not ssid:
        return False, "SSID is empty"
    if ssid and not is_cozmo_ssid(ssid):
        log.warning("SSID %r does not look like Cozmo_XXXX — continuing anyway", ssid)
    if not shutil.which("nmcli"):
        return False, "nmcli not found; join the AP out of band"

    # Rewriting or reactivating the profile drops a live association.
    # Cozmo then leaves SDK mode and hides its access point.
    live = _iw_ssid(iface)
    if live == ssid:
        _disable_power_save(iface)
        return True, f"already on {ssid} ({iface})"

    ok, msg = _ensure_profile(iface, ssid, password)
    if not ok:
        log.warning("nmcli profile: %s", msg)
        return False, msg

    try:
        proc = _nmcli("connection", "up", PROFILE, "ifname", iface, timeout=45)
    except subprocess.TimeoutExpired:
        return False, "nmcli timed out joining the Cozmo AP"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "nmcli connection up failed").strip()
        log.warning("nmcli join failed: %s", err)
        return False, err
    _disable_power_save(iface)
    return True, f"joined {ssid} on {iface} (profile {PROFILE}, never-default, metric {ROUTE_METRIC})"


def _iw_ssid(iface: str) -> Optional[str]:
    if not iface or not shutil.which("iw"):
        return None
    proc = _run(["iw", "dev", iface, "link"], timeout=5)
    if proc.returncode != 0:
        return None
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("SSID:"):
            return stripped.split(":", 1)[1].strip() or None
    return None


def current_ssid(iface: str) -> Optional[str]:
    info = wifi_status(iface)
    if info.get("state") == "connected":
        return info.get("connection")
    return None
