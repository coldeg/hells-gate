# Publication review — 29 October 2026

## Outcome

The selected community source export is suitable for technical review and manual
installation by a Home Assistant user familiar with USB firmware flashing and local
apps. Its software checks and firmware build are verified. It is not yet a one-click
installer or a separately commissioned fresh household deployment.

Only current firmware, the HA app, frontend, documentation, fictional assets and
offline tests belong in that export. Development captures, iteration history,
private host helpers and installed household data are outside its selection.
The publication manifest is the authoritative file list; the development folder
must not be uploaded wholesale.

## Hardware and protocol identification

The owner confirmed **Niko 05-300**, an Easywave RF interface into an existing
Nikobus installation. The reproduced layer is the studied legacy unidirectional
Easywave command family: FSK near 868.3 MHz, Manchester coding and a complete
observed frame. The 05-300 performs the conversion into wired Nikobus telegrams.
This does not implement the wired Nikobus protocol or certify every Niko product.
Exact wall-transmitter product references remain unspecified in the public record.
See [compatibility](COMPATIBILITY.md) and the manufacturer's
[05-300 description](https://products.niko.eu/fr-fr/article/05-300).

## Blank first installation

- The app's production registry has zero buttons and zero actions.
- The public firmware has zero native preconfigured RF commands. Observation and
  learned-command handling remain available.
- New observations populate the catalogue without automatic RF transmission.
- Users may observe normal household activity for about 24 hours or press their
  buttons individually. Waiting cannot reveal a transmitter that never emits.
- Names, rooms and grouping are optional. Global TX availability, complete-frame
  evidence, learned storage capacity and airtime limits still apply.
- Updates preserve existing app/NVS data. Installing a blank source image is not
  an instruction to erase an already configured board.

The separate fictional registry is only a test fixture. It is not copied into
the installed app and does not provision radio commands. Two additional regression
cases verify empty production initialization and passive discovery with serial and
MQTT mocked. The fixtures require no setup step from an end user.

## Evidence and installation usability

Validation covers 79 Python test executions, the bridge self-test, frontend bundle
consistency and JavaScript syntax, two example automations, synthetic figure
generation, four-language browser checks and the current firmware build. The
reviewed firmware selects one pinned PlatformIO environment. Historical RF
branches and private deployment scripts are excluded.

The instructions explain the USB connection, source build/upload, local HA app,
MQTT discovery, dashboard resource, entity placeholders and both discovery paths.
They require no credentials, helpers or directory layout from the original home.
Browser executable discovery includes an override; only Windows browser execution
was validated here. ARM64 container execution and a fresh third-party HA
commissioning were not performed by this review.

The documented app path targets 64-bit Home Assistant OS. Home Assistant Container
needs a separate host/container adaptation; the older Core/Supervised installation
methods are no longer supported by HA. See the
[official comparison](https://www.home-assistant.io/faq/ha-vs-hassio).

The canonical repository is [coldeg/hells-gate](https://github.com/coldeg/hells-gate).
The installation guide uses that URL and the reporting policy explains private
coordination. Fresh commissioning on another supported HA host remains to be
validated. The app retains its existing compatibility build metadata;
current [HA documentation](https://contributors.home-assistant.io/apps/reference/configuration/)
deprecates separate `build.yaml`. A future packaging update should be tested on the
target Supervisor/container build path before being advertised.

## Security construction and historical context

The security chapter correctly separates a demonstrated physical replay capability
from hypothetical abuses, and RF receiver acceptance from HA/MQTT protection.
It explicitly states that the target needs no HA or Internet connection. It also
covers consequential HA automations, private RF data, critical devices, finite
range evidence and the absence of output-state feedback.

The long legitimate history of Easywave does not establish malicious prevalence
or immunity. The bounded public-source search found no verified malicious campaign
against this specific 05-300 path. This is not evidence that none has occurred.
Hypothetical lighting nuisance and garage/access scenarios must remain identified
as scenarios rather than claimed past incidents or tests.

Earlier interoperability work exists: Marc Selis publicly announced
[Easywave2MQTT on 28 January 2022](https://community.home-assistant.io/t/new-add-on-to-add-support-for-easywave-devices/385609),
using an ELDAT RX09; [Nikobus-HA](https://github.com/fdebrus/Nikobus-HA) uses another
bus-interface path. Hell’s Gate receives and reconstructs the studied RF frames
directly on generic ESP32/SX1262 hardware, eliminating the dedicated Easywave
transceiver on the HA side. Its positioning emphasizes this hardware independence
and intended lower cost. The existing 05-300 remains the Nikobus receiving interface.

Security limits remain: this is not an exhaustive penetration test; host discovery
storage has no demonstrated adversarial resource-exhaustion bound; no cryptographic
anti-replay was added to the 05-300; no garage or third-party premises were tested.
Source sanitization protects publication privacy and does not repair legacy RF
acceptance. See [security](SECURITY.md).

## Sanitization and reproducibility

Selection is explicit. Installed RF identities/words and household aliases are
removed or replaced with fictional fixtures; the production tables are empty.
Private backups, raw captures, flash images, SSH keys, HA tokens and household
dashboards are excluded. Known household RF values, credential patterns and local
workspace paths are checked without printing their values. Manual review also
covers the selected source and fictional assets.

File hashes in the manifest are public integrity checksums, not secret keys.
The archive contains only manifest-listed files and the manifest itself. Cache,
build and test output generated during verification do not become release files.
Pattern checks complement the selection and review; they do not prove the absence
of every possible unknown secret. The technical review involved no RF emission,
hardware upload or HA connection. Source publication is a separate step following
that review.
