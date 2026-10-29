# Publication review: 29 October 2026

## What was checked

The community export contains the current firmware, HA app and frontend, along
with documentation, fictional assets and offline tests. The release checks passed,
including the firmware build. Installation is manual and requires familiarity
with firmware flashing and local HA apps. A fresh installation in another
household has not yet been validated.

`PUBLICATION_MANIFEST.json` lists the release files and their SHA-256 hashes.
Private captures, development history, deployment helpers and installed household
data were excluded from the export.

## Hardware

The receiving interface is a Niko 05-300, confirmed by the owner. It converts the
studied legacy Easywave RF commands into Nikobus bus telegrams. The Heltec firmware
reconstructs those commands using FSK near 868.3 MHz, Manchester coding and the
complete observed frame. It does not implement the wired Nikobus protocol.
Exact wall-switch model references still need to be recorded publicly.
See [compatibility](COMPATIBILITY.md) and
[Niko's 05-300 description](https://products.niko.eu/fr-fr/article/05-300).

## First installation and updates

The app registry and native firmware command tables are empty. Reception can
populate the catalogue without transmitting. Users can press buttons individually
or leave the gateway receiving for about 24 hours of normal use; only buttons
that emit can be discovered.

Names, rooms and groups are optional. Sending still requires global TX to be
enabled, a complete frame and available storage and airtime. Updates preserve
app data and NVS. The empty source defaults do not require erasing an existing
installation.

The fictional registry stays under `tests/fixtures/` and is excluded from the
app's Docker COPY instructions. Two regression cases check empty initialization
and passive discovery with serial and MQTT mocked.

## Software and installation checks

The release validation included 79 passing Python test executions, the bridge
self-test, JavaScript syntax and source/bundle consistency, two example
automations, synthetic figures, four-language browser checks and the firmware
build. The public PlatformIO configuration selects one pinned environment.

The guide covers USB connection, firmware build/upload, the local HA app, MQTT
discovery and the manual dashboard resource. It uses the public
[coldeg/hells-gate repository](https://github.com/coldeg/hells-gate) and needs no
private deployment helper. Browser checks were run on Windows; other browser
platforms and a fresh ARM64 container were not tested in this review.

The app instructions target 64-bit HA OS. Home Assistant Container needs separate
serial/container setup. HA's older Core/Supervised installation methods are no
longer supported; see the [installation comparison](https://www.home-assistant.io/faq/ha-vs-hassio).

The app retains its existing `build.yaml` for compatibility. The current
[HA configuration reference](https://contributors.home-assistant.io/apps/reference/configuration/)
deprecates that separate file. A packaging change should be tested on the target
Supervisor/container path before release.

## RF security

Captured commands operated Nikobus circuits in the owner's installation. An
independent transmitter can exercise the same RF path without HA or Internet
access in the target home. The [security chapter](SECURITY.md) explains this
separately from HA/MQTT protection and from hypothetical misuse scenarios.

The public-source search for the review found no verified malicious campaign
against this specific 05-300 path. It was a limited search, so the result cannot
establish how often abuse occurs. No garage, access-control device or third-party
installation was tested. The review was not an exhaustive penetration test, and
adversarial exhaustion of host discovery storage remains untested.

Earlier integration work includes
[Easywave2MQTT, announced in January 2022](https://community.home-assistant.io/t/new-add-on-to-add-support-for-easywave-devices/385609),
which uses an ELDAT RX09, and [Nikobus-HA](https://github.com/fdebrus/Nikobus-HA),
which uses PC-Link. Hell's Gate handles the studied RF commands directly on the
ESP32/SX1262 board to avoid a dedicated Easywave transceiver on the HA side.
The existing 05-300 still provides the connection into Nikobus.

## Publication privacy

Household RF words, identities and labels were removed or replaced with fictional
fixtures. Raw captures, backups, board/NVS dumps, credentials and household
dashboards were excluded. Checks searched for known private RF values, credential
patterns and local paths without printing them. The selected files and fictional
assets were also reviewed manually.

Those checks reduce the risk of exposing private data; pattern matching cannot
prove that every possible secret is absent. The archive contains only the
manifest-listed files and the manifest itself. Generated caches and build logs
stay outside it.

The review used no RF transmission, hardware upload or HA connection. Publishing
the source does not change the legacy receiver's acceptance of replayed commands.
