# Public source export scope

The public release contains the current learned-command firmware, HA app and
frontend, with documentation, synthetic figures, fictional screenshots and offline tests.
`PUBLICATION_MANIFEST.json` records the explicitly selected files and content hashes.
The SHA-256 values let you check file integrity.

Production starts empty: `registry.json` contains no devices/actions and the firmware
contains no native household command. The test registry is deliberately fictional,
stored under `tests/fixtures/` and excluded from the app's Docker COPY instructions.
It is used only by the tests.

Historical firmware versions, raw RF captures, private backups, board/NVS dumps,
household dashboards, real HA screenshots, SSH helpers and private host deployment
scripts are excluded. No access token, password, private key or household RF word is
required to build or install this export. Original development files stay private.

The canonical source repository is [coldeg/hells-gate](https://github.com/coldeg/hells-gate).
The MIT license covers original project material; dependencies retain their own
licenses. Installation follows the local-app and manual dashboard-resource guide;
this source release does not supply a HACS package. Follow the
[security-reporting policy](../SECURITY.md) for sensitive findings. A fresh hardware/HA installation still needs a manual check on the target equipment.

Read [compatibility](COMPATIBILITY.md) and [security](SECURITY.md). Publishing the source does not change the legacy receiver's replay behavior.
