# Project description, keywords and related work

## Suggested GitHub description

Local Nikobus/Easywave retrofit on ESP32/SX1262: direct RF reception and reproduction
without a dedicated Easywave transceiver. Designed to lower hardware cost and reuse
wireless buttons with Home Assistant and MQTT.

## Suggested GitHub topics

Select the most relevant topics for the eventual public repository:

`home-assistant`, `nikobus`, `niko`, `easywave`, `mqtt`, `smart-home`,
`home-automation`, `retrofit`, `legacy-hardware`, `wireless-switch`, `868mhz`, `fsk`,
`manchester-encoding`, `heltec`, `esp32-s3`, `sx1262`, `radiolib`, `local-control`,
`interoperability`, `reverse-engineering`.

These are proposed metadata; no public repository settings have been changed. The
board's LoRa product name is mentioned in the hardware guide, but the project uses FSK.
Listing LoRa as its implemented air protocol would be misleading.

## Search terms grounded in the project

| Area | Relevant phrases |
|---|---|
| Modernization | Nikobus modernization; legacy home automation retrofit; upgrade an older Niko installation; connect existing wall switches to a modern smart home; preserve existing wiring and switches. |
| Home Assistant | Nikobus Home Assistant integration; Easywave Home Assistant gateway; local MQTT bridge; MQTT button events; custom Lovelace card; per-user language and locale. |
| Hardware and protocol | Heltec WiFi LoRa 32 V3; ESP32-S3 SX1262; Easywave 868 MHz FSK; Manchester decoding; captured-frame reconstruction; radio interoperability. |
| Practical uses | Unassigned wireless button automation; two-button thermostat control; multi-brand smart-home actions; lighting scenes; ambient lighting; shopping-list button; affordable compatible wall switches. |
| Community research | Reproducible modulation diagrams; offline RF encoder tests; receiver compatibility; RF replay risk; command authentication; output-state feedback limitations. |
| Multilingual discovery | Modernisation Nikobus; passerelle Easywave domotique; Nikobus modernisieren; Easywave Hausautomation; Nikobus moderniseren; Easywave huisautomatisering. |

Use these phrases naturally in titles, descriptions and relevant explanations.
Compatibility and implemented features take priority over keyword volume. Zigbee,
Z-Wave, BLE and Matter targets can be reached through their own HA integrations; Hell’s
Gate does not implement those radio decoders. Virtual transmitters remain [planned
research](ROADMAP.md).

## Positioning and earlier work

Nikobus already provided home automation before today's connected-home platforms. The
aim here is to bring useful older installations and wireless inputs into a current local
HA setup, rather than replace an entire working electrical cabinet.

Other Nikobus integrations exist. For example,
[Nikobus-HA](https://github.com/fdebrus/Nikobus-HA) documents a PC-Link serial/TCP
approach. [Easywave2MQTT](https://github.com/marcselis/Easywave2MQTT) uses a dedicated
ELDAT RX09. Hell’s Gate handles the studied radio frames directly on generic
ESP32/SX1262 hardware, replacing the dedicated Easywave transceiver on the HA side.
The intended benefits are lower hardware cost, accessible components, wall-button
reuse and a local MQTT pipeline. The existing 05-300 remains necessary for the
documented path into Nikobus. Compatibility follows the tested frame family.

The [security chapter](SECURITY.md) is part of that public description: replayable
legacy RF can enable unauthorized control, including repeated nuisance. Modernizing the
HA interface does not modernize the receiver's radio authentication.
