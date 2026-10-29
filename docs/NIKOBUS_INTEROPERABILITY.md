# Connecting Nikobus to a wider Home Assistant smart home

Hell’s Gate provides a local interoperability bridge for an installation previously
isolated from this HA setup. The implemented radio path receives and reproduces observed
**Easywave** signals interpreted by a compatible Nikobus RF interface. Other Nikobus
integration methods already exist; this path does not inject raw frames into the wired
bus.

## Two interoperability directions

| Direction | Path | What it enables |
|---|---|---|
| Existing wireless button → third-party equipment | Easywave press → Heltec RX → MQTT → HA automation → target integration | Reuse a button for a light, thermostat, cover, media action or other device outside the original cabinet ecosystem. |
| Third-party input → existing installation | Input's own HA integration → HA automation → Hell’s Gate TX → existing compatible RF interface → Nikobus load | Allow a different connected button or HA event to reproduce a recognized existing radio command. |

```mermaid
flowchart LR
    A[Compatible Easywave button] --> RX[Hell's Gate RX]
    RX --> HA[Home Assistant]
    HA --> Other[Third-party integrated actuator]
    Input[Third-party input via its own integration] --> HA
    HA --> TX[Hell's Gate reproduces recognized Easywave command]
    TX --> RF[Existing compatible Nikobus RF interface]
    RF --> Bus[Existing Nikobus outputs / loads]
```

“Spoof a Nikobus signal” is informal shorthand here for reproducing a recognized radio
command at the compatible interface. It does not mean that an arbitrary third-party
actuator speaks wired Nikobus or that the decoder accepts every transmitter brand. For
context, Niko's [05-300 product description](https://products.niko.eu/en/article/05-300)
describes an RF interface that brings wireless transmitters into a Nikobus installation;
that reference does not identify the exact interface installed in every household.

An HA action targeting equipment outside Nikobus requires the target's own working HA
integration, without that Nikobus RF interface or a Nikobus output module. The reverse
path into an existing Nikobus installation retains its compatible receiver and
interface.

## The missing information is the load state, not the button identity

A particular button observation or completed radio command is an event. A momentary wall
button is an input, not the load state. Those facts do not establish that an output is
currently energized or that a lamp is lit.

| Information | State classification |
|---|---|
| Physical button event received | Observed input |
| Radio API reported completion | Transmission result |
| Dedicated ON command sent | Requested state: ON |
| Dedicated OFF command sent | Requested state: OFF |
| HA retains the last requested state | Optimistic/estimated state |
| A suitable independent source reports the actual output | Measured/reported state, with the source identified |

An optimistic estimate must remain distinct from a measured state. An RF loss, another
wall button, a local override or a power interruption can make an estimate stale.

## Dedicated ON and OFF sides

Yes, this is a documented possibility for **some Nikobus switching modules**. For
example, the manufacturer's archived [05-000-01/02 switching-unit
manual](https://old.niko.sk/navody/Nikobus_system_inteligentnej_elektroinstalacie/05-000-02_Spinacia_jednotka.pdf)
describes M1 with two button points (upper ON, lower OFF), M2 as forced ON and M3 as
forced OFF. It also supports configurable reaction times for M2/M3. Verify the actual
module, its manual and the RF-interface mapping before applying those mode numbers to an
installation.

Niko's [05-340/05-341 Easywave receiver
manual](https://dam.nikocdn.eu/assets/Niko/Documents/Manuals/PM005-34000.pdf) also
documents a two-key ON/OFF mode, but do not assume that its complete programming
procedure or mode table applies to a different Nikobus module.

If the installed receiving/output configuration supports it, retain two distinct
recognized identities:

- Map the first to an explicit **ON** action.
- Map the second to an explicit **OFF** action.

Repeatedly requesting ON then keeps the same intended state, unlike a toggle that
changes meaning depending on the unknown initial state. This makes HA automation intent
much clearer. It **still does not add a feedback channel** or prove the receiver
accepted each RF command.

Also check reaction time: Hell’s Gate currently sends a short bounded one-shot burst and
does not implement an arbitrary long hold. A module function requiring a sustained
one-to-three-second press must not be assumed to work with that burst. No installed
Nikobus module was reprogrammed and no new ON/OFF pair was verified as part of the
documentation work.

## Clear command semantics in HA

Receiver-side replay is independent of HA: an unauthorized compatible transmitter may
exercise the same RF input even in a home without HA. Dedicated ON/OFF semantics clarify
intent but do not authenticate commands. See [security](SECURITY.md).

Keep ON and OFF as separate scripts/actions backed by the actual recognized aliases,
with their physical meanings confirmed for the target configuration. Keep both button
identities available. The current group card selects one reference command; it does not
yet supply a dedicated paired ON/OFF widget or a stateful HA light entity. Such a
control first needs explicit command semantics, with any assumed state labeled
accordingly.

If actual state is important, investigate a supported feedback interface or a suitable
independent measurement for the circuit. A power reading can support an inference for a
known load, but it does not automatically prove the state of every lamp in a group.
Record the source and uncertainty of that information.

This interoperability preserves useful existing infrastructure while allowing additional
compatible inputs to be chosen by cost and ergonomics. HA can control targets through
different integrations without requiring every new device to belong to a complete
Nikobus cabinet ecosystem.
