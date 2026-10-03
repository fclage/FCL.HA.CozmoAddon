# Changelog

All notable changes to this project are recorded here. The version matches `custom_components/ha_cozmo/manifest.json` and `companion/__init__.py`.

Each change that lands on `main` gets an entry and a version bump. See [CONTRIBUTING.md](CONTRIBUTING.md).

## 0.1.3

- A push to `main` publishes a GitHub release for each manifest version that does not already have a tag. The notes come from this changelog, and the tag points at the commit that introduced the version.

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
