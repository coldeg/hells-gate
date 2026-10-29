# Contributing to Hell’s Gate

Contributions are welcome in decoding, receiver compatibility, the UI, translations,
tests and documentation. The evidence behind a change should be reviewable, especially
when a software success indicator and a physical result can differ.

## Source map

Start with [ARCHITECTURE.md](docs/ARCHITECTURE.md), then choose the relevant layer:
firmware under `src/`, bridge/model under `addon/easywave_gateway/`, readable UI sources
under `frontend/src/`, language packs under `frontend/translations/`, and offline
validation/generation under `tools/`.

Edit the sources, not the generated frontend bundle or generated transport headers. Keep
RF waveform changes, bridge behavior, UI work and an actual hardware test in separate
reviewable steps. Tests must not flash hardware as a side effect.

## Local checks

```sh
python -m pip install -r addon/easywave_gateway/requirements.txt
python -m pip install websocket-client matplotlib numpy
python -m pip install PyYAML Jinja2
python -m unittest discover -s tools -p 'test_easywave_*.py'
python tools/build_frontend.py
python tools/build_frontend.py --check
node --check frontend/hells-gate-card.js
python tools/easywave_tx_continuous.py
python tools/generate_community_figures.py
python tools/check_community_docs.py
```

For browser checks in the supported local Chrome/Edge harness, run:

```sh
python tools/check_hells_gate_card.py
python tools/check_i18n.py
```

Those browser tests use fake HA service calls. `check_i18n.py` also captures the
fictional public screenshots. The helper discovers common browser paths and supports an explicit
`HELLS_GATE_BROWSER` executable path; Windows was tested in this review. The standalone
`frontend/demo.html` itself works without HA or a broker in a modern browser on other
systems.

Browser checks use only fictional data and mocked actions. Production starts empty;
`tests/fixtures/registry.synthetic.json` supports tests without provisioning the app
or firmware. Set `HELLS_GATE_BROWSER` if browser auto-discovery fails. No HA token or
private host helper is required for the published checks.

For readable JavaScript formatting optionally install `jsbeautifier==1.15.4` and run
`python tools/format_frontend.py`, then rebuild the bundle. The formatter is a
development tool; it is not a browser/runtime dependency.

## Adding a language

Copy `frontend/translations/en.json` to a new language-code JSON file, translate the
values and keep every key and `{placeholder}`. Keep text plain and preserve the `_one` /
`_other` plural pairs. The build discovers JSON packs dynamically, checks
keys/placeholders against English and embeds them in the single resource.

Test a regional tag, an unsupported language, room names, icon labels, an open form, a
learning session and the 320 px layout. Do not translate user-entered names or change
the saved radio/icon identifiers. A locale change must not save metadata, lose a draft,
retarget a selected button or restart a learning session.

## A useful RF report

Read the [security chapter](docs/SECURITY.md) before working on RF control or
reception-triggered automations. Commodity hardware and public code can be adapted for
unauthorized replay; bridge-side checks cannot constrain an independent radio. Report
new device-specific findings through the [security policy](SECURITY.md), with private
household captures excluded from public issues.

Include the board/modem, firmware build environment, receiver family, radio settings,
antenna arrangement, capture tool/version, source of timestamps and the exact variable
changed. Distinguish physical-button traffic from a gateway TX. Include the full
captured frame and tail evidence when discussing learned TX, not only an RSSI peak or a
32-bit prefix.

Identify whether a result is a model, a serial acknowledgement, a captured waveform, or
an observed physical effect. Label uncalibrated measurements and avoid treating a
successful flash or `TX_COMPLETE` as receiver compatibility. Keep installation
identifiers, household names, secrets and raw private captures out of public issues;
provide a deliberately sanitized fixture when possible.

## Useful contribution areas

- A broader documented compatibility matrix based on observed receiver behavior.
- More precise firmware reasons for learned-installation failure and full NVS.
- A reviewed lifecycle for deleting/replacing learned entries, with persistence tests.
- Independent captured-tail and waveform fixtures suitable for public redistribution.
- More browser/platform coverage and native HA accessibility checks.
- More language packs and review of the existing translations.
- A self-contained community installation/release process replacing private workspace
  deployment assumptions, with configurable deployment paths and example registries.
- A state model only where a real receiver feedback channel exists.

Original code and documentation use the [MIT license](LICENSE). External dependencies
retain their own licenses. A contribution should make its provenance and any third-party
material clear.
