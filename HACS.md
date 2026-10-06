# HACS installation and updates

## Publication status

The source is public at [goncalox/fibergateway-phone-detector](https://github.com/goncalox/fibergateway-phone-detector).

Version [v0.3.0](https://github.com/goncalox/fibergateway-phone-detector/releases/tag/v0.3.0) is published with an installable ZIP.

All 61 core tests, 13 Home Assistant runtime checks, HACS validation and Home Assistant manifest validation pass on GitHub.

## Install

1. Open HACS and choose **Custom repositories** from its menu.
2. Enter `https://github.com/goncalox/fibergateway-phone-detector` and choose **Integration** as the type.
3. Add and download **FiberGateway Phone Detector**.
4. Restart Home Assistant.
5. Add or continue using the integration under **Settings → Devices & services**.

The domain remains `wifi_phone_detector`, so an existing manual installation keeps its integration entry, credentials and keyword configuration when HACS manages the same folder.

Remove neither the integration entry nor its stored configuration during the switch.

Future published releases will appear through HACS's update management; restart Home Assistant after installing integration updates.

This uses a custom repository and does not require inclusion in the default HACS catalog.

## Release process

Use a public repository with description, enabled issues and topics such as `home-assistant`, `hacs`, `presence-detection` and `meo`.

Push only this project's integration source, documentation, tests and workflows.

Keep router reports, packet captures, local environments and credentials outside the repository.

A push to `main` publishes the manifest version when it has no existing release; version tags and manual workflow runs are also supported.

The release workflow validates the manifest, runs the source tests, checks the version, builds a manual-install ZIP and publishes a full GitHub release from the tested commit.

HACS reads the integration files from the release's source tree; it does not use the manual-install ZIP.

References: [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/), [public repository and release requirements](https://www.hacs.xyz/docs/publish/start/).
