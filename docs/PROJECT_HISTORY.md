# Project history and design decisions

## The problem I wanted to solve

I wanted to keep an existing Easywave/Nikobus installation usable through local Home
Assistant. I did not want a cloud account, a replacement for every wall switch, or an
interface that confused naming a button with making it usable.

The bridge uses a Heltec WiFi LoRa 32 V3 board with the SX1262 in FSK mode; the board's
LoRa branding does not make the Easywave traffic LoRa. The project reconstructs the
radio behavior studied for this installation rather than every Niko/Easywave product.

## The progression of the work

| Stage | Result | Purpose |
|---|---|---|
| Reception and signal exploration | Compared RSSI activity, packet candidates, Manchester levels and recurrence. | Evidence was needed about framing and timing before attempting reconstruction. |
| Integrity and identity | Reconstructed a 32-bit word and two observed integrity classes, then exposed serial/key/side identities. | Stable identities and rejection of unrelated structures. |
| Passive discovery | Retained recurring candidates, first/last observations and counts. | Discover switches without continuously printing raw radio traffic. |
| Initial MQTT gateway | Added local serial ownership, MQTT discovery and a limited set of known commands. | A reliable path between the radio endpoint and HA. |
| Transport experiments | Examined truncated frames, partial hardware synchronization and polarity variants. | A software TX completion alone did not explain physical receiver behavior. |
| Full byte-aligned transport | Retained all 66 Manchester chips using four transport bits per chip. | Send complete frames through a byte-oriented packet API. |
| Continuous burst | Encoded three repetitions and held levels into one 111-byte radio call. | Preserve the burst envelope rather than introduce radio-off gaps between separate calls. |
| Learned commands, V8.7 | Captured the final data bit and stored exact learned frames. | The final bit must come from evidence, not a guess based on the 32-bit prefix. |
| Dynamic catalogue and direct controls | Made recognized buttons usable independently of optional names and groups. | A button called “receive only” after attribution was an unnecessary usability dead end. |
| Locale and community documentation | Separated language packs, inherited HA profile preferences and added reproducible figures. | Help another household or contributor understand and extend the work without private deployment knowledge. |

## Decisions I changed

I initially kept naming, activation and physical confirmation as separate user steps.
That made newly attributed buttons look incomplete even when their command could already
be reproduced. I changed the rule to **recognized = actionable**. An incomplete
historical observation remains distinct from a complete frame, because a missing bit
cannot be repaired by a different label.

I also stopped treating a successful radio API return as proof of physical success. The
UI exposes “command sent”; physical receiver behavior requires separate validation.
Several installed circuits were confirmed, with one load remaining unconfirmed. That
result does not establish compatibility with every receiver family.

Earlier experiments remain in the development workspace for research traceability. The
current learned-command build explicitly selects `heltec_v87`; the old PlatformIO
default is historical.

## What the current project is useful for

The gateway observes compatible switch traffic, identifies recurring buttons, stores
optional names and existing HA rooms, and sends explicit one-shot commands from a local
dashboard. Reception and radio results remain separate from the real state of the
controlled load.

Research tools include offline encoders, source-derived timing checks, a documented
serial/MQTT boundary and synthetic plots. Those let a contributor discuss a bit, chip,
byte, burst, nonce or timestamp precisely instead of changing multiple layers at once
and judging success from a green button.

## Limits of these results

The work has not established universal Easywave compatibility, a calibrated antenna
power/spectrum, a regulatory certification, or an end-to-end guarantee for every load.
The model spectrum in the documentation is synthetic. The publication work does not add
a new RF test or flash the installed gateway.

Remaining questions are documented in [testing and limits](TESTING_AND_LIMITS.md) and
the concrete contribution paths in [CONTRIBUTING.md](../CONTRIBUTING.md).
