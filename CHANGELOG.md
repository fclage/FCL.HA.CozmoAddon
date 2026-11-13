# Changelog

All notable changes to this project are recorded here. The version matches `custom_components/ha_cozmo/manifest.json` and `companion/__init__.py`.

Each change that lands on `main` gets an entry and a version bump. See [CONTRIBUTING.md](CONTRIBUTING.md).

## 0.2.0

- Speech works on hosts that honor Cozmo's DHCP MTU. Cozmo's access point advertises MTU 576, while each audio frame is about 807 bytes, so Linux split every audio frame into IP fragments. The robot drops fragmented datagrams, never acknowledged the frames, and the send window filled until pings stopped and the link went stale. The companion now sets `802-11-wireless.mtu 1500` on the `cozmo-ap` profile every time it joins. See [docs/wifi.md](docs/wifi.md#mtu-and-speech).
- Speech uses Piper, a local neural voice (default `en_US-amy-medium`, slightly raised pitch). The voice is downloaded on first use and kept loaded, so synthesis takes tens of milliseconds. espeak-ng remains the automatic fallback. New settings: `COZMO_TTS_ENGINE`, `COZMO_PIPER_VOICE`, `COZMO_PIPER_DIR`, `COZMO_TTS_PITCH`, `COZMO_PIPER_AUTO_DOWNLOAD`.
- The u-law encoder clamps full-scale negative samples to 255 instead of wrapping them to 0.
- espeak-ng amplitude lowered from 140 to 100 to stop clipping.

## 0.1.2

- Companion logs drop carriage returns and newlines from the request path and the client address. Responses send `X-Content-Type-Options: nosniff`.
- The debug page names its token, network, password, and speech fields. A failed drive or status refresh shows on the error line, and the say card catches a failed speak call.
- A cube LED color is used only when that color has three channels.
- Unit tests publish a coverage report and a test-execution report so SonarCloud can score new Python lines and count the tests on the main branch.

## 0.1.1

- SonarCloud analyzes every validation run, including pushes, pull requests, and the weekly schedule. The project is `fclage_FCL.HA.CozmoAddon`.

## 0.1.0

First release.

- Home Assistant integration for drive, camera, face, speech, lights, and one light cube.
- Companion process that joins Cozmo’s access point and speaks PyCozmo.
- Camera on/off and color switches. Dim frames are lifted before they are served.
- Power off stops the SDK session so the motors can release. Wake reconnects without driving.
- Installer, Wi-Fi notes, settings, and known-issue recovery.
- Issue and pull-request forms.
