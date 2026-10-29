# Describing Hell's Gate

Hell's Gate connects compatible legacy Easywave switches and Nikobus installations
to Home Assistant through a local MQTT bridge. Its open-source firmware receives
and reconstructs the studied RF commands on general-purpose ESP32-S3/SX1262 hardware.

## Short description

Nikobus & Easywave integration for Home Assistant using ESP32/SX1262: local
868 MHz FSK gateway, MQTT bridge and wireless switch reuse.

## Hardware and compatibility

The HA side uses a Heltec WiFi LoRa 32 V3 board in FSK mode. Its commercial name
includes LoRa, but LoRa is not the air protocol used here. For commands into an
existing Nikobus installation, the Niko 05-300 remains the receiving interface.
Using a compatible button to trigger another HA integration does not require it.

The goal is to reduce hardware cost and dependence on dedicated Easywave
transceivers while keeping useful existing switches. Compatibility is limited to
the frame family tested; see [the hardware notes](COMPATIBILITY.md).

HA can connect button events to Zigbee, Z-Wave, BLE or Matter devices through their
own integrations. Those radio decoders are not part of Hell's Gate. Virtual
transmitters are [planned work](ROADMAP.md).

## Earlier projects

[Easywave2MQTT](https://github.com/marcselis/Easywave2MQTT) uses a dedicated ELDAT
RX09. [Nikobus-HA](https://github.com/fdebrus/Nikobus-HA) uses a PC-Link serial/TCP
connection to the bus. Hell's Gate takes the direct SX1262 radio route.

The [security notes](SECURITY.md) describe replay of the studied legacy commands.
A new HA interface does not change the authentication accepted by an old RF receiver.
