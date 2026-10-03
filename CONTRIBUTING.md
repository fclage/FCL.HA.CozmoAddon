# Contributing

Contributions are welcome. Issues, fixes, and new behavior from other developers are part of how this project should grow.

## How a change lands

`main` is the published branch. Do not commit directly to it.

1. Open an issue if the change needs a design note. Use the bug or feature form. Leave out the lift password, companion token, packet captures, and filled environment files.
2. Branch from `main` and do the work there.
3. Open a pull request. Describe what changed and how you checked it.
4. A review happens on that pull request. Merge only after the review.
5. The maintainer merges. The merge is what updates `main`. The Release workflow then publishes a GitHub release for every manifest version on `main` that does not already have a `v` tag. The notes are that version's section in `CHANGELOG.md`, and the tag points at the commit that introduced the version.

A pull request that changes the project must also:

- Add an entry under a new version heading in [CHANGELOG.md](CHANGELOG.md).
- Bump the version in `custom_components/ha_cozmo/manifest.json` and set the same value in `companion/__init__.py`. The companion HTTP banner uses that version too.
- Use the next patch number unless the change adds a feature (`0.2.0`) or breaks an existing setup (`1.0.0`). The first release is `0.1.0`.

A workflow on the pull request checks that the changelog and the manifest version both moved.

## Local check

```bash
python3 -m venv .venv
.venv/bin/pip install pytest -r companion/requirements.txt
.venv/bin/pytest tests -q
```

## Boundaries

- The robot password belongs in the Home Assistant config entry or in the companion environment, never in git.
- Keep the integration domain `ha_cozmo`. PyCozmo stays in the companion, not in Home Assistant’s `requirements`.
- Recovery steps for a locked robot are in [docs/known-issues.md](docs/known-issues.md).
