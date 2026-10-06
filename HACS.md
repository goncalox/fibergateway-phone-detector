# HACS installation and updates

## Publication status

The repository layout, brand icon, manifests, test workflow, HACS validation and release workflow are prepared.

Publishing to a public GitHub repository is still required before HACS can install or update this integration.

The proposed repository is `goncalox/fibergateway-phone-detector`; documentation and issue links currently target that proposed repository.

HACS repository validation and the GitHub release workflow can only be verified after publication.

## Once published

1. Open HACS and choose **Custom repositories** from its menu.
2. Enter the published GitHub repository URL and choose **Integration** as the type.
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

After repository checks pass, tag the matching version, for example `v0.3.0`.

The release workflow checks the source, confirms the tag matches the manifest version, builds a manual-install ZIP and publishes a full GitHub release.

HACS reads the integration files from the release's source tree; it does not use the manual-install ZIP.

References: [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/), [public repository and release requirements](https://www.hacs.xyz/docs/publish/start/).
