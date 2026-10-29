# Configuration examples

Use `registry.empty.json` only when preparing a new household's source copy. Do not
overwrite existing labels or receiver assignments. Replace the entity IDs in
`dashboard.yaml` with the IDs actually discovered by HA.

The two complete automation examples are explained in
[USE_CASES.md](../docs/USE_CASES.md): laundry supplies through a to-do list and a
bounded thermostat setpoint adjustment. The extracted [laundry](automation-laundry.yaml)
and [thermostat](automation-thermostat.yaml) YAML files are available for copying and
review. Replace their identity/entity placeholders before use. The documentation checks
do not install or execute these automations.

Open `frontend/demo.html` from the project root to try the interface without
hardware. It uses fictional names/IDs and simulates HA actions in browser memory.
