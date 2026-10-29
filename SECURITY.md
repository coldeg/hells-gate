# Reporting security findings

The [RF security notes](docs/SECURITY.md) describe the demonstrated replay of
Easywave commands and the HA/MQTT/serial access boundaries. Captured commands
operated Nikobus circuits in the owner's installation. A target receiver can
accept such RF commands without HA or Internet access in the home.

Use **Report a vulnerability** on the repository's
[Security page](https://github.com/coldeg/hells-gate/security) if private reporting
is available. Otherwise, open an issue asking for a private contact, without
captures, household identities, credentials or sensitive reproduction details.
Wait for a private channel before sharing them. No response-time commitment is
configured for this project.

Include the project version, exact device/model, environment, expected and
observed behavior, impact and a minimal sanitized reproducer. Keep real household
RF identities and location data out of public issues. Physical tests require
ownership or permission.

The tested scope is the legacy frame family described in
[compatibility](docs/COMPATIBILITY.md). It does not cover every Easywave product;
no garage, lock or third-party installation was tested.
