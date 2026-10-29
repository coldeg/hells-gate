# Verified hardware and protocol scope

The tested receiving interface is the Niko 05-300. It connects compatible wireless transmitters to an existing
Nikobus installation. Niko's [05-300 product description](https://products.niko.eu/en/article/05-300)
and [French technical description](https://products.niko.eu/fr-fr/article/05-300)
describe reception at 868.3 MHz and conversion into Nikobus telegrams.

## What was reproduced

On the HA side, a general-purpose Heltec ESP32-S3/SX1262 board runs the open-source
radio firmware. This provides an alternative to a dedicated Easywave transceiver
or vendor RF gateway, with lower hardware cost as a goal. The existing 05-300
still receives commands for Nikobus. For button events used only by another HA
integration, neither the 05-300 nor a Nikobus cabinet is needed.

| Layer | Established scope |
|---|---|
| Original input | Observed two-button and four-button wall controls in the owner's installation. Their exact product references are not yet confirmed in this public record. |
| Air protocol | The studied legacy, unidirectional Easywave command family used with the Nikobus RF interface. |
| Radio implementation | Binary FSK with Manchester coding on Heltec WiFi LoRa 32 V3 / SX1262. Current configured carrier: 868.314 MHz; no LoRa modulation. |
| Reconstructed frame | A 32-bit identity/integrity prefix plus the actually observed final data bit; three continuous repetitions in a bounded burst. |
| Receiving path | Compatible reproduced RF command → Niko 05-300 → existing Nikobus mapping → physical load. |
| Physical validation | The owner reports that about 99% of button commands respond as expected in the original installation. Other receivers require compatibility testing. |
| Feedback | This implemented radio path does not natively provide independently confirmed Nikobus output state to HA. |

Commands enter Nikobus through its Easywave RF interface. The firmware does not
send native wired-bus telegrams. The receiver's existing programming determines
what a particular button command does.

## Other product families

- **Wired Nikobus / PC-Link:** a separate integration path; not implemented by this
  Heltec RF firmware. Optional bus feedback needs its own supported interface.
- **Niko Home Control:** not a validated target merely because some products use
  Easywave. The confirmed installation here uses the 05-300 Nikobus interface.
- **Easywave neo:** ELDAT documents bidirectional operation and backward-compatible
  legacy functions. No neo acknowledgement or state-feedback implementation is
  provided here. See the [ELDAT catalogue](https://www.eldat.de/_katalog/ELDAT_Katalog_en.pdf).
- **secwave:** ELDAT documents AES-128 and a different telegram structure,
  incompatible with Easywave. It is outside this decoder's scope. See
  [secwave](https://www.eldat.de/secwave_en.html).
- **Other 868 MHz protocols:** matching frequency, radio chipset or manufacturer
  does not establish frame compatibility, successful replay or a security weakness.

Receiver modes, ON/OFF mapping, hold times and existing pairing remain relevant.
See [interoperability](NIKOBUS_INTEROPERABILITY.md), [modulation](MODULATION.md)
and [security](SECURITY.md). A received identity is not authenticated authorization.

## Useful compatibility reports

Record transmitter and receiving-interface model, firmware build, command type,
receiver mode and physical observation. Use fictional replacements for household
identities in public examples. A successful TX API return alone is not a receiver
test. Testing belongs on owned equipment or with permission.
