# Reporting security findings

The [security chapter](docs/SECURITY.md) describes RF replay, the FSK/868 MHz scope,
HA/MQTT/serial trust boundaries, repeated nuisance against lighting, downstream HA
automation abuse, publication risks and critical-device considerations.

Captured button commands were retransmitted and operated owner-controlled Nikobus
circuits. The target of such RF replay does not require Home Assistant, MQTT, Hell’s
Gate or Internet access. Treat learned commands in the supported replayable frame family
as potentially reusable by an unauthorized compatible transmitter.

Use **Report a vulnerability** on the repository's
[Security page](https://github.com/coldeg/hells-gate/security) when private reporting
is available. If that option is unavailable, open an issue containing only a
high-level request for private coordination. Do not include captures, exploitable
household identifiers, credentials or sensitive reproduction details in that issue.
Wait for a private channel before sharing those details. No guaranteed response SLA
is configured by this policy.

A useful report includes the affected project version, exact device/model, environment,
expected/observed behavior, impact and a minimal sanitized reproducer. Keep real
household RF identities, command captures, credentials and location data out of public
issues. Physical tests require ownership or permission.

Do not interpret the documented legacy-RF limitations as a claim that every Easywave
product shares the same security design or that a garage/lock was tested.
