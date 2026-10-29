# Project history and design decisions

## The problem I wanted to solve

I wanted to keep my Easywave/Nikobus switches and use them with local Home
Assistant automations. Naming a button should help me find it, without becoming
a separate step needed to make it work.

The radio is a Heltec WiFi LoRa 32 V3 with its SX1262 running in FSK mode.
The work covers the Easywave traffic used by this installation.

## How the work progressed

Reception came first: RSSI activity, possible packets, Manchester levels and
recurring patterns. That led to the 32-bit identity/integrity model and two
observed integrity classes. Passive discovery then kept recurring candidates,
timestamps and counts without continuously printing raw traffic.

The first MQTT gateway connected the radio to HA and exposed a small set of known
commands. Transmission needed more work. Early experiments tried truncated
frames, partial hardware synchronization and polarity variants. A successful
radio API return did not explain what the receiver actually accepted.

The byte-aligned transport kept all 66 Manchester chips by representing each chip
with four transport bits. Three frames and their held levels were then combined
into one 111-byte transmit call, avoiding radio-off gaps between separate calls.

V8.7 added the captured final data bit to learned commands. The 32-bit prefix
alone was insufficient: learning needed the actual received tail.

Later work added a dynamic catalogue, direct unnamed-button controls and language
packs following each HA user's profile. The public documentation and synthetic
figures were added so another user could build and inspect the project.

## Decisions I changed

I initially separated naming, activation and physical confirmation in the UI.
That made a button look unfinished even when its command was ready to send.
The current rule is simple: a recognized button is usable. An incomplete
observation still needs another reception; a name cannot supply a missing bit.

I also changed the feedback to say "command sent" instead of implying a confirmed
physical result. On my installation, about 99% of button commands respond as
expected. The radio still provides no feedback confirming the output state.

Earlier experiments remain in the private development workspace. The public
PlatformIO configuration contains the current `heltec_v87` environment.

## Remaining work

The offline encoders and synthetic plots help compare bits, timing and transport
payloads. They do not measure antenna power or spectrum. Receiver compatibility
outside the original installation and regulatory compliance need their own checks.

See [testing and limits](TESTING_AND_LIMITS.md) and
[contribution areas](../CONTRIBUTING.md) for the remaining technical work.
