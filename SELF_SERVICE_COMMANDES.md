# Hell’s Gate — using recognized buttons

The interaction rule is **recognized = actionable**. A name, room, display group or
physical effect confirmation does not unlock a command. Global gateway availability and
RF limits still apply. Reproducing a newly learned frame requires complete received
evidence.

## Interface

- **Controls** shows one card per equipment group and independent usable buttons.
- **My buttons** lets you name a button, choose its HA room and optionally group it.
- **Add** shows presses received during the current session without silently choosing
  an unrelated historical candidate.
- **Activity** separates received observations from radio results and diagnostics.

Use **Recognize** for an incomplete historical observation and press the physical switch
again. For a complete learned frame the bridge prepares storage when you actually press
the command, without a separate activation screen. A successful radio result does not
establish the lamp's on/off state.

## Language and locale

The card follows the current HA user's profile language and regional formatting. Bundled
languages are English, French, Dutch and German, with regional-tag resolution and
English fallback. User names and stable identifiers stay unchanged. Changing the profile
language does not discard an open form or restart a learning session.

## Other Home Assistant actions

Use a received button with no Easywave/Nikobus receiver assignment to trigger a native
HA automation for another target integration. See the laundry supplies pair, thermostat
up/down and other examples in [USE_CASES.md](docs/USE_CASES.md). This does not require a
full Nikobus electrical cabinet for that HA event-to-action path. It still requires a
compatible receiver path for the input protocol and a working HA integration for the
target; this gateway does not decode every brand's protocol.

## Documentation and checks

Read the [security chapter](docs/SECURITY.md): replayable radio commands can enable
unauthorized control independently of HA, including repeated nuisance. A received button
identity is not sufficient authorization for a consequential HA action.

Start with the [English README](README.md), then follow the [installation
guide](docs/INSTALLATION.md), [architecture](docs/ARCHITECTURE.md), [modulation
figures](docs/MODULATION.md), [message contracts](docs/PROTOCOL.md) and [contribution
guide](CONTRIBUTING.md). Historical experiments and current limitations are documented
separately from the installation procedure.

```sh
python tools/build_frontend.py --check
python -m unittest discover -s tools -p 'test_easywave_*.py'
python tools/check_hells_gate_card.py
python tools/check_i18n.py
python tools/generate_community_figures.py
```

The browser checks use mocked actions or block services. They do not flash a board,
place an order, modify a thermostat or transmit RF. The project uses the MIT license,
with the [publication boundary](docs/PUBLICATION.md) kept explicit: documentation
preparation is not publication of the private working tree.
