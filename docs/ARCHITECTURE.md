# Local Nikobus/Easywave pipeline architecture

Hell’s Gate consists of a radio endpoint, a local MQTT bridge, a presentation model and
a Home Assistant card. A received signal, a human name, a UI group and an actual
physical effect represent separate facts.

![Local pipeline overview](assets/pipeline-overview.png)

```mermaid
flowchart LR
    Button[Physical Easywave switch] -->|RF levels| Radio[Heltec V3 / SX1262]
    Radio -->|Manchester + integrity + captured tail| Serial[USB serial evidence]
    Serial --> Bridge[Python gateway]
    Bridge -->|retained catalogue and observations| MQTT[Local MQTT broker]
    MQTT --> HA[Home Assistant MQTT integration]
    HA --> Card[Hell's Gate card]
    Card -->|explicit non-retained PRESS + request ID| MQTT
    MQTT --> Queue[Bounded bridge queue]
    Queue -->|INSTALL_TX when needed| Store[Observed frame / NVS]
    Store -->|ARM_TX + TX with one-shot nonce| Radio
    Radio -->|RF command| Receiver[Existing receiver / Nikobus installation]
    Radio -->|correlated radio result| Bridge
```

## Component responsibilities

| Component | Files | Responsibility |
|---|---|---|
| Firmware | `src/main_gateway_v8.cpp` | Configure the SX1262, scan RX profiles, validate observations, enforce one-shot TX and restore RX. |
| Captured-frame encoder | `src/easywave_learned_tx.h` | Retain the actual final bit and encode a complete continuous burst. |
| Offline transport reference | `tools/easywave_tx_frame.py`, `easywave_tx_continuous.py` | Model line coding, compare known references and generate timing/payload artefacts without RF I/O. |
| Runtime bridge | `addon/easywave_gateway/gateway.py` | Own serial access, MQTT discovery, observations, command queues and durable airtime accounting. |
| Labels | `addon/easywave_gateway/identification.py` | Store optional names/icons and resolve command capability from received evidence. |
| Catalogue | `addon/easywave_gateway/catalogue.py` | Join the data model, select one reference per group and apply atomic metadata requests. |
| Card | `frontend/src/card.js` | Handle navigation, local drafts, explicit presses and correlated feedback. |
| Presentation | `frontend/src/card.css`, `frontend/src/i18n.js`, `frontend/translations/` | Keep visual rules and per-user locale handling independent of RF logic. |
| Browser bundle | `frontend/hells-gate-card.js` | Deploy one generated local resource. No CDN or translation service is needed. |

## Data model

**Radio identity** is `SERIAL22_key2_side_variant`. The 22-bit serial comes from `word
>> 10`; the two-bit key field comes from `(word >> 8) & 3`. The side is the integrity
class recognized by the decoder. Those fields do not establish a wall position, room,
owner or physical target.

**Observation** adds the word, first/last reception, counters and, when available, the
actually received tail bit plus its confirmation count. An old 32-bit discovery is
enough to display a candidate; it is not enough to reproduce a new 33-bit frame.

**Labels** add the user's switch name, button name, room ID, icon identifier and
optional group. Naming does not change the identity or physical receiver pairing.

**Group** is a display association. Each group has one selected reference button;
pressing that group sends one command through that reference, rather than sending to
every associated identity. Room names come from HA's registry through stable `area_id`
values.

**Capability** is computed from native command definitions or complete received evidence
on compatible firmware. A recognized button is usable without a name, room, group,
activation flag or confirmation of the physical effect. The global gateway TX option,
connection status and RF budget still apply.

## Browser request ID and serial nonce

```mermaid
sequenceDiagram
    actor User
    participant Card
    participant Bridge
    participant Firmware
    User->>Card: Press recognized button
    Card->>Bridge: PRESS JSON with browser request_id
    opt Dynamic command
        Bridge->>Firmware: INSTALL_TX observed word, tail, install nonce
        Firmware-->>Bridge: TX_INSTALLED / rejection
    end
    Bridge->>Bridge: Reserve persistent airtime budget
    Bridge->>Firmware: ARM_TX serial nonce
    Firmware-->>Bridge: TX_ARMED matching nonce
    Bridge->>Firmware: TX alias and same serial nonce
    Firmware-->>Bridge: TX_COMPLETE matching nonce and RX result
    Bridge-->>Card: MQTT result with client_request
    Card-->>User: Command sent / precise failure
```

The browser request ID prevents another user's result from completing the current click.
A separate serial nonce correlates the one-shot firmware exchange. Neither ID
establishes that a lamp changed state. An unexpected serial RX/status line is still
processed while the bridge waits for a matching acknowledgement.

## Concurrency boundaries

The MQTT callback validates and enqueues work. The main bridge loop is the single serial
owner. Callbacks, browsers and other serial clients must not compete for reads. The
firmware IRQ signals that work is pending; packet decoding happens outside the ISR.

A form stays in its browser tab. Its save request contains the complete edit, identity,
expected metadata revision and request ID. The bridge validates a copy, persists once
and returns a correlated receipt. New receptions do not change the metadata revision. A
genuine concurrent edit produces a conflict with a recovery choice.

## State boundaries

```mermaid
stateDiagram-v2
    [*] --> Candidate: signal observed
    Candidate --> Recognized: complete concordant frame received
    Candidate --> NamedCandidate: optional name saved
    NamedCandidate --> Recognized: complete concordant frame received
    Recognized --> NamedRecognized: optional name / room / group saved
    Recognized --> Sending: manual press
    NamedRecognized --> Sending: manual press
    Sending --> RadioResult: correlated reply or timeout
    RadioResult --> Recognized: capability retained
```

This state diagram does not contain an inferred on/off state for a lamp. A radio result
is an observation about transmission; a human observation of the load is separate
evidence.

This feedback gap remains the central integration limitation. Virtual transmitter
identities, explicit ON/OFF commands and HA scenes do not remove it. That next direction
is described in [ROADMAP.md](ROADMAP.md), with requested, estimated and independently
confirmed state kept separate.

## Persistence

The app stores discovery, labels and airtime reservations under `/data`, with a
user-accessible mirror and bounded event log under `/share/heltec_easywave`. The
firmware stores installed learned frames in NVS. Access tokens, MQTT passwords and
browser drafts belong outside documentation and public example files.

The observation cache is separate from NVS: after a reboot, an old complete discovery
that was never installed may require a new physical press before the firmware accepts
installation. Installed matching entries are idempotent.

Further reading: [message contracts](PROTOCOL.md), [modulation](MODULATION.md),
[installation](INSTALLATION.md), [validation and limits](TESTING_AND_LIMITS.md), and [RF
trust boundaries and replay](SECURITY.md). Bridge-side request correlation and TX limits
do not authenticate the legacy over-the-air command. An independent radio can bypass the
HA/MQTT/serial path. The reverse path from third-party HA inputs, explicit ON/OFF
commands and actual state feedback are discussed in [Nikobus
interoperability](NIKOBUS_INTEROPERABILITY.md).
