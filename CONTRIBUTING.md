# Contributing

Issues and pull requests are welcome.

- Do not include Wi-Fi passwords, companion tokens, packet captures, or filled environment files.
- The robot password belongs in the Home Assistant config entry or in the companion environment, never in git.
- Run `pytest tests -q` before opening a pull request.
- Keep the integration domain `ha_cozmo`. PyCozmo stays in the companion, not in Home Assistant’s `requirements`.
