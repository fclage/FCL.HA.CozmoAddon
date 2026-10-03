# Changelog

All notable changes to this project are recorded here. The version matches `custom_components/ha_cozmo/manifest.json` and `companion/__init__.py`.

Each change that lands on `main` gets an entry and a version bump. See [CONTRIBUTING.md](CONTRIBUTING.md).

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
