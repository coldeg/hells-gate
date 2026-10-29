# Test results and limitations

The checks below cover software behavior, RF encoding and observations on the
original installation. Each supports a different conclusion.

| Evidence | Supported conclusion | Unsupported conclusion |
|---|---|---|
| Syntax / unit tests | A checked software path satisfies the tested conditions. | That the radio or receiver works in another installation. |
| Encoder/reference comparison | The represented bits/chips/payload match that reference. | Antenna power, oscillator accuracy or physical load response. |
| Firmware upload verification | The written flash matches the binary. | Correct serial boot behavior or an RF effect. |
| Matching `TX_COMPLETE` | The radio operation ended with the reported result. | The intended receiver acted or a lamp is currently on. |
| Independent RF capture | The observer recorded the signal under the stated setup. | Universal protocol compatibility or calibrated radiated power. |
| Observed load response | The intended load reacted during that test. | Every receiver, environment or later command will behave identically. |

## Software checks for the current work

The release validation included 79 passing Python test cases for naming, catalogue grouping, atomic
requests, direct unnamed commands, persistence, serial correlation and rejection paths.
JavaScript syntax and source/bundle consistency were also checked.

The browser regression covers an unnamed recognized button, one explicit mocked press,
unrelated result rejection, draft preservation during reception, concurrent edit
recovery, room changes, group reference choice, learning candidates, connection loss,
saving failure, touch targets and 320/390 px layouts.

The locale regression covers English, French, Dutch and German; regional variants;
English fallback; unchanged user labels; language changes during an edit or learning
session; date order, 12/24-hour format and number formatting. These tests make no real
HA or radio command calls.

The installed card was checked against real HA data and in the real HA frontend using a
browser with all service calls blocked. Verification covered the original deployment's
data/IDs, served source hashes, RX status and unchanged TX counters/nonces. In the UI
refactor the catalogue went from five exposed commands to twenty directly actionable
entries; that count is a deployment observation, not a product capacity or a
compatibility guarantee.

The explanatory Python comments were checked for an unchanged AST, and firmware comments
for unchanged executable tokens. The UI/localization/documentation work involved no
firmware flash or new RF test.

## Known limitations

1. **Incomplete old observations.** The actual tail is required before reproducing a new
   learned frame. A new physical press can complete recognition.
2. **Observation cache versus persistence.** After reboot, a never-installed frame
   from an old discovery may need to be observed again. An already-installed exact
   NVS entry is idempotent.
3. **Learned capacity.** Firmware currently retains 32 learned frames. The current
   UI does not implement deletion/compaction of those slots.
4. **Failure detail.** The firmware does not reliably distinguish every full-storage,
   stale-cache or mismatching-tail installation failure in its reply.
5. **Physical compatibility.** The owner reports that about 99% of button commands
   respond as expected in the original installation. Other receiver models and
   installations still need their own compatibility checks.
6. **State feedback.** The integration exposes momentary commands and radio results,
   without inferring lamp on/off states.
7. **Airtime.** The software reserves 110,917 µs per burst, a minimum one-second
   interval and a persistent 35-second rolling hourly bridge budget. Firmware also
   enforces its own limits. Those values do not establish regulatory compliance.
8. **Figures.** The published modulation figures are synthetic source-derived models,
   not original private recordings or calibrated RF measurements.
9. **Packaging.** This is a selected community source export with empty production
   tables and separate fictional fixtures. A fresh HA container installation
   on another household has not yet been physically validated.
10. **Translations.** Application text and known validation messages are translated.
    User text stays as entered, and unexpected upstream diagnostics can remain in
    their original language.

11. **Security.** Recognized RF identities are not authenticated users. Replayed
    commands may operate a compatible legacy receiver or trigger an HA automation.
    No adversarial garage/access test or comprehensive security audit was performed.
    See [RF replay, repeated nuisance and action boundaries](SECURITY.md).

## Reports and reproducibility

Local reports live under `frontend/` and private rollback folders; real household
screenshots and raw installation backups stay outside the community docs. Public figures
and fictional screenshots live under `docs/assets/` and can be regenerated with the
commands in [CONTRIBUTING.md](../CONTRIBUTING.md).

Regenerate plots from their generator and parameter manifest to keep timing labels
consistent. For a hardware change, include the source diff, an offline reference comparison
and a manual test with one changed variable. Record the software result and the
physical observation separately.
