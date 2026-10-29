# Using recognized buttons

A recognized button is ready to use. You can add a name, room or group later.
Sending still requires an available gateway, global TX enabled and enough RF
budget. A new learned command also needs a complete received frame.

## Interface

**Controls** shows equipment groups and usable buttons. **My buttons** lets you
name them, assign an HA room and group them. **Add** shows receptions from the
current learning session. **Activity** lists receptions, radio results and
diagnostics separately.

For an incomplete observation, choose **Recognize** and press the physical switch
again. Once a complete frame is available, the bridge prepares learned storage
when you press the command; there is no separate activation screen. A "command
sent" result reports transmission, not the lamp's actual on/off state.

## Language and locale

The card follows the HA user's language and regional settings. English, French,
Dutch and German are included, with regional-tag matching and English fallback.
User names and stored identifiers stay unchanged. Switching language preserves
an open form or learning session.

## Other Home Assistant actions

A compatible button can trigger an HA automation without being assigned to an
Easywave receiver or Nikobus output. The target uses its own HA integration;
no Nikobus cabinet is needed for that use. See the
[shopping-list and thermostat examples](docs/USE_CASES.md).

Received identities can be replayed. Read the [security notes](docs/SECURITY.md)
before assigning actions that need authorization.

## Documentation and checks

Start with the [README](README.md) and [installation guide](docs/INSTALLATION.md).
The [architecture](docs/ARCHITECTURE.md), [modulation notes](docs/MODULATION.md)
and [message reference](docs/PROTOCOL.md) describe the implementation.
Development commands are in [CONTRIBUTING.md](CONTRIBUTING.md).

```sh
python tools/build_frontend.py --check
python -m unittest discover -s tools -p 'test_easywave_*.py'
python tools/check_hells_gate_card.py
python tools/check_i18n.py
python tools/generate_community_figures.py
```

These checks use mocked or blocked actions. They do not flash hardware, transmit
RF or execute the example automations. The MIT-licensed public export excludes
private installation data; see [what is included](docs/PUBLICATION.md).
