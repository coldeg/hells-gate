# Hell’s Gate — Nikobus & Easywave integration for Home Assistant

**Modernize an existing Nikobus installation and reuse compatible Easywave wall switches
with local Home Assistant automations.** The confirmed target is the Niko
05-300 Easywave RF interface connected to an existing Nikobus installation. Hell’s Gate combines a Heltec WiFi LoRa 32 V3
running FSK, a local Python/MQTT bridge and an HA dashboard card. Recognized buttons are
directly usable; names and room assignments are optional.

**Direct Easywave radio on general-purpose ESP32/SX1262 hardware.** Hell’s Gate
receives, decodes and reconstructs the studied RF frames in its own firmware,
without an ELDAT RX09/RX11 or another dedicated Easywave transceiver on the HA side.
The Heltec board provides the ESP32-S3 and the 868 MHz FSK radio in one device.

This approach is designed to reduce hardware cost and dependence on dedicated
vendor interfaces. For an existing Nikobus installation, its 05-300 receiving
interface remains the link into the wired bus. Easywave button events used only
for third-party HA actions do not require that Nikobus interface.

**Security: captured button commands were retransmitted and operated Nikobus circuits on
the owner's installation.** A third party with compatible radio equipment can
potentially reuse learned commands; the targeted house needs no Home Assistant or
Internet connection. Repeated unauthorized operation can include disturbing bedroom
lighting at night. HA authentication and Hell’s Gate's TX limits do not secure that
independent radio path. Read the [RF replay and security chapter](docs/SECURITY.md)
before using or extending it.

![Hell’s Gate pipeline](docs/assets/pipeline-overview.png)

## Why I built it

I wanted to keep useful existing switches, understand their radio traffic and control
equipment through HA without a cloud-dependent gateway. I also wanted an interface where
an optional name or room assignment does not become a barrier between a recognized
button and its action.

**The principal integration limitation remains output-state feedback:** this
Easywave/Nikobus radio path does not natively report the real output state to HA.
Requested or estimated state stays distinct from independently confirmed state,
including for scenes.

A received physical-button event can trigger a general HA automation, including
equipment outside Easywave/Nikobus. That path requires a compatible input path, HA and
the target's integration, without a full Nikobus cabinet installation. Hell’s Gate is
not a universal decoder for every manufacturer's radio protocol.

## Reuse legacy switches in a modern smart home

- Discover and inspect compatible received button identities and complete frames.
- Press a recognized command directly, with optional names, rooms and grouping.
- Use an unassigned physical button as an HA automation input: shopping-list items,
  thermostat up/down, scenes, blinds, media controls, reminders and other actions.
- Keep processing local, with bounded commands and explicit radio-result feedback.
- Follow each HA user's language and regional preferences independently: English,
  French, Dutch and German are bundled, with English fallback for other languages.
- Study and improve the protocol using offline encoders, synthetic plots and tests.

![Fictional English desktop preview](docs/assets/ui-controls-desktop.png)

Public screenshots use fictional devices. Open
[`frontend/demo.html`](frontend/demo.html) locally for an interactive preview; its
commands and reception button are simulated in memory.

## Read the project in this order

| Question | Guide |
|---|---|
| Which hardware and protocol were studied? | [Compatibility and verified scope](docs/COMPATIBILITY.md) |
| What is useful beyond the original installation? | [Use cases and HA automation examples](docs/USE_CASES.md) |
| How to bridge existing Nikobus and third-party equipment in both directions? | [Interoperability, ON/OFF and state feedback](docs/NIKOBUS_INTEROPERABILITY.md) |
| What changed, and why? | [Project history and decisions](docs/PROJECT_HISTORY.md) |
| Was the selected export reviewed? | [Publication review and remaining limits](docs/PUBLICATION_REVIEW.md) |
| How to install it in another household? | [HA installation guide](docs/INSTALLATION.md) |
| How do the components fit together? | [Architecture and sequence diagrams](docs/ARCHITECTURE.md) |
| What is actually transmitted? | [Manchester, FSK, captured tail and continuous burst](docs/MODULATION.md) |
| What are the MQTT/serial contracts? | [Protocol reference](docs/PROTOCOL.md) |
| What is proven, and what remains open? | [Testing and limitations](docs/TESTING_AND_LIMITS.md) |
| How to improve or translate it? | [Contribution guide](CONTRIBUTING.md) |
| What research comes next? | [Virtual transmitters, scene control and feedback limits](docs/ROADMAP.md) |
| What still needs review before a public source release? | [Publication boundaries](docs/PUBLICATION.md) |
| What can an unauthorized nearby transmitter do? | [Replay, nuisance, critical devices and mitigations](docs/SECURITY.md) |
| How should the project be described and found? | [Keywords, GitHub topics and related work](docs/DISCOVERABILITY.md) |

## A quick offline development loop

```sh
python -m pip install -r addon/easywave_gateway/requirements.txt
python -m pip install websocket-client matplotlib numpy
python -m unittest discover -s tools -p 'test_easywave_*.py'
python tools/build_frontend.py
python tools/build_frontend.py --check
node --check frontend/hells-gate-card.js
python tools/generate_community_figures.py
```

Edit `frontend/src/card.js`, `card.css`, `i18n.js` and the JSON language packs, then
build the single local resource. Build the current firmware explicitly with `python -m
platformio run -e heltec_v87`. The public PlatformIO configuration selects this single current environment by default.

![Manchester and four-sample transport model](docs/assets/manchester-transport.png)

## Current scope

The current integration combines V8.7 learned-command firmware, the 0.4.0 bridge and the
0.4.1 localized frontend. Validation includes 79 passing Python cases and separate
browser/locale checks. Operation was confirmed on several installed circuits, with one
load remaining unconfirmed; receiver compatibility is not universal.

Actual complete-frame evidence is required for a newly learned RF command. The firmware
currently has 32 learned-frame slots. A sent command does not establish a lamp state.
HA-driven actions require HA, MQTT and the target integration to be available; optional
online ordering flows also depend on their external service.

The modulation figures are synthetic illustrations, not antenna measurements.
This community source export contains only the current firmware, local bridge,
frontend, documentation and offline checks. Production command tables are empty;
test identities are fictional and stored separately under `tests/fixtures/`.
See [publication scope](docs/PUBLICATION.md) and the file manifest.

## Related Nikobus projects

[Easywave2MQTT](https://github.com/marcselis/Easywave2MQTT) integrates a dedicated
ELDAT RX09 through its serial interface. [Nikobus-HA](https://github.com/fdebrus/Nikobus-HA)
documents a PC-Link serial/TCP bus path. Hell’s Gate implements the studied RF
reception and frame reconstruction directly on a general-purpose SX1262 radio,
providing a different hardware approach to local HA interoperability.

## License and acknowledgements

Original project code and documentation use the [MIT license](LICENSE). External
components retain their own licenses and attribution, described in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This independent project is not
endorsed by Niko, Easywave, Heltec or Home Assistant.
