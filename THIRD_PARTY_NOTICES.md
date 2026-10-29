# Third-party components and acknowledgements

Hell’s Gate's original code and documentation use the MIT license. Dependencies and
third-party contributions retain their own licenses; trademarks remain with their
respective owners.

| Component | Use in the project | Upstream reference |
|---|---|---|
| Home Assistant | MQTT integration, room registry, dashboard and profile locale | [Home Assistant](https://github.com/home-assistant/core), [frontend](https://github.com/home-assistant/frontend) |
| Arduino framework / Espressif platform | ESP32-S3 firmware runtime and build support | [Arduino ESP32](https://github.com/espressif/arduino-esp32) |
| RadioLib | SX1262 configuration and packet I/O | [RadioLib](https://github.com/jgromes/RadioLib) |
| U8g2 | On-board OLED output | [U8g2](https://github.com/olikraus/u8g2) |
| PlatformIO | Firmware build orchestration | [PlatformIO](https://github.com/platformio/platformio-core) |
| paho-mqtt | Python MQTT client in the bridge | [Paho MQTT Python](https://github.com/eclipse-paho/paho.mqtt.python) |
| pyserial | Host serial transport | [pyserial](https://github.com/pyserial/pyserial) |
| websocket-client | Local browser and HA inspection tools | [websocket-client](https://github.com/websocket-client/websocket-client) |
| Matplotlib / NumPy | Offline synthetic documentation figures | [Matplotlib](https://github.com/matplotlib/matplotlib), [NumPy](https://github.com/numpy/numpy) |
| js-beautify | Optional local development formatting | [js-beautify](https://github.com/beautifier/js-beautify) |

Keep upstream attribution/license files with redistributed dependencies and review the
actual versions included in a release. The installed card uses HA's native icon
component; the standalone demo's simple SVG placeholders are part of this project.

Easywave, Nikobus, Niko, Heltec and Home Assistant identify technologies and
compatibility targets; their mention does not imply affiliation or endorsement.
