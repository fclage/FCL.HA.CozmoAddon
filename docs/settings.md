# Companion settings

The installer writes `/etc/ha-cozmo-companion.env`. The example in the repository is [`.env.example`](../.env.example). The file is root-only because it holds the lift password.

Home Assistant switches override the camera, personality, auto, and auto-sleep values while the companion is running. The environment file is the value used at startup.

| Variable | Default | What it does |
| --- | --- | --- |
| `COZMO_SSID` | empty | Access point name printed on the lift, `Cozmo_` plus the id |
| `COZMO_PASSWORD` | empty | Password printed on the lift |
| `COZMO_WIFI_IFACE` | empty | Linux interface that joins Cozmo. Empty picks a Wi-Fi interface that is not the default route |
| `COZMO_HOST` | `172.31.1.1` | Robot address on its own access point. Do not change this for a normal Cozmo |
| `COZMO_PORT` | `5551` | UDP port of the robot protocol |
| `LISTEN` | `0.0.0.0:8790` | Address and port of the companion HTTP API |
| `COZMO_ALLOW` | `private` | Who may call that API. See below |
| `CAMERA_COLOR` | `0` | Starting camera mode. `0` is black and white, `1` is color. The **Color camera** switch changes it after startup |
| `COMPANION_TOKEN` | empty | If set, callers must send `Authorization: Bearer <token>` or `X-Api-Key` |
| `COZMO_DRY_RUN` | `0` | `1` runs the HTTP API with no robot. Useful for tests |
| `FFMPEG_PATH` | `ffmpeg` | Used when playing audio |

`COZMO_ALLOW` accepts `local`, `private`, `all`, or a CIDR such as `192.168.1.0/24`. Several rules combine with commas: `local,192.168.1.0/24`. `private` allows loopback, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, and IPv6 unique-local addresses. `all` accepts any address. Leave it at `private` unless Home Assistant is outside those ranges.

The same allow list is `--allow` on the command line. `LISTEN` is `--listen`.

After editing the file:

```bash
sudo systemctl restart ha-cozmo-companion
```

## Home Assistant fields

| Field | Meaning |
| --- | --- |
| Companion URL | `http://127.0.0.1:8790` when the companion runs on the Home Assistant machine, otherwise `http://<companion-host>:8790` |
| Wi-Fi adapter | Interface name on the companion host. It must not be your normal uplink |
| SSID and password | Printed on the lift. Stored in the config entry and sent to the companion when joining |
| Companion token | Only if `COMPANION_TOKEN` is set |

The integration does not need a route to `172.31.1.1`. It only needs to reach port `8790`.

## Switches that are not in the environment file

| Switch | Behavior |
| --- | --- |
| Camera | Stream on or off. Off clears the last frame |
| Color camera | Color or black and white. Color is more likely to stall the engine. See [known issues](known-issues.md) |
| IR headlight | Light at the camera for a dim room |
| Personality | Face updates while idle |
| Auto | After 30 seconds with no taps, small motions and expressions |
| Auto-sleep | After 5 minutes with no taps, sleep and then power off, including on the charger |

**Camera** and **Color camera** stay available while the robot is off. The choice is applied on the next connection.
