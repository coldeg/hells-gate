# MQTT and serial protocol reference

The MQTT prefix is `nikobus/easywave`. The UI and bridge exchange JSON and stable IDs;
the bridge and firmware exchange newline-terminated serial records at 115200 baud.
Examples here contain placeholders or synthetic data, not a household command to paste
into a live transmitter.

## MQTT topics

| Topic | Direction | Retention / purpose |
|---|---|---|
| `nikobus/easywave/status` | Bridge → HA | Retained online/offline availability. |
| `nikobus/easywave/gateway_status` | Bridge → HA | Status and freshness, including RX and global TX availability. |
| `nikobus/easywave/catalogue` | Bridge → HA | Retained versioned catalogue, optional labels, groups and receipts. |
| `nikobus/easywave/rx/<identity>` | Bridge → HA | Latest observation for an identity, retained. |
| `nikobus/easywave/rx/event` | Bridge → subscribers | Non-retained reception events. |
| `nikobus/easywave/tx/<alias>/set` | Card/HA → Bridge | Explicit non-retained manual press. |
| `nikobus/easywave/tx_result` | Bridge → HA | Last radio result, with timestamp and correlation fields. |
| `nikobus/easywave/identify/catalogue/set` | Card → Bridge | Atomic metadata request; no radio emission. |

Retained observations let a reconnecting dashboard display the catalogue. Retained
commands are rejected so a broker reconnect cannot become a fresh press. Repeated
outcomes use the event timestamp rather than HA `last_changed`.

## A manual press

```json
{
  "action": "PRESS",
  "request_id": "example_browser_request_0001"
}
```

The alias comes from a recognized catalogue entry. A learned alias has the form
`rx_<EIGHT_HEX_DIGITS>` and uses the received word; the payload does not supply an
arbitrary word or tail. Historical plain-text `PRESS` commands remain compatible. A
recent browser request ID is accepted only once in the bridge's bounded in-memory
deduplication window. Rebooting the bridge clears that window; retention rejection,
one-shot serial arming, cadence and persistent airtime accounting remain separate.

The result includes the alias, result timestamp, `client_request` from the browser and
the serial `request` nonce when one was used. The current success label is
`transmitted_unconfirmed`; it does not establish a lamp state.

## An atomic naming request

```json
{
  "operation": "save",
  "identity": "012345_0_0",
  "revision": "REVISION_FROM_CURRENT_CATALOGUE",
  "request_id": "example_metadata_request_0001",
  "fields": {
    "source": "Example switch",
    "button": "Desk lamp",
    "area": "Office",
    "area_id": "ACTUAL_HA_AREA_ID",
    "position": "",
    "icon": "Lampe de bureau",
    "section_id": ""
  }
}
```

The icon value above is a legacy stable identifier from the catalogue's `icons` map. Its
display label is translated; its stored key stays unchanged. The bridge validates the
current revision before writing the complete update, then returns a receipt with the
same request ID. A conflict carries `code: "conflict"` and leaves the draft available.

Current UI operations include `save`, `prefer` and `restore`; the protocol also retains
`ignore` and old-card compatibility branches. Legacy activation flags no longer gate
recognized commands. The current card does not expose a receive-only mode, and an old
disable request asks the user to reload the updated card.

## Serial inspection, learning and transmission

| Command / record | Meaning |
|---|---|
| `STATUS` → `GATEWAY_STATUS` | Inspect current firmware/radio state. |
| `PLAN <alias>` → `TX_PLAN` | Inspect the encoded plan without transmitting. |
| `EASYWAVE_EVENT ...` | Report a validated/learned RX observation. |
| `EASYWAVE_FRAME word=... tail=... confirmations=... source=rf` | Report actual received-tail evidence. |
| `INSTALL_TX <word> <tail> <nonce>` → `TX_INSTALLED` | Persist a matching observed frame, without arming or RF. |
| `ARM_TX <nonce>` → `TX_ARMED` | Prepare one short-lived one-shot authorization. |
| `TX <alias> <nonce>` → `TX_COMPLETE` / rejection | Send one bounded burst and report RX restoration. |

A learned installation is accepted only if the frame is valid and was observed with
matching tail evidence in the candidate cache, or the same frame already exists in NVS.
The current firmware can return a generic unsuccessful installation when the cache is
absent or storage is full; it does not distinguish every cause precisely.

Positive terminal serial replies are correlated with the expected nonce. A legacy
uncorrelated `COMMAND_REJECT` is treated as failure, never as a positive
acknowledgement. RX/status records continue to be handled while waiting.

## HA automation boundaries

The installed card already publishes the explicit press. For another HA script, use the
actual alias from the local catalogue and a non-retained `mqtt.publish`. Do not copy
another household's alias as a physical receiver assignment.

For reception-driven automation, start with a harmless notification or log action on
`rx/event` and filter the actual identity. Account for repeated RF observations,
retained-state replay and possible self-reception before adding an action. Do not
forward every received frame back to the TX topic: that can form a feedback loop.

The current project does not supply inferred HA light on/off entities or a complete
generic automation editor. Those require a separate state/behavior design.
