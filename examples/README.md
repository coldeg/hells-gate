# Configuration examples

Use `registry.empty.json` only when preparing a new household's source copy. Do not
overwrite existing labels or receiver assignments. Replace the entity IDs in
`dashboard.yaml` with the IDs actually discovered by HA.

The two complete automation examples are explained in
[USE_CASES.md](../docs/USE_CASES.md): laundry supplies through a to-do list and a
bounded thermostat setpoint adjustment. The extracted [laundry](automation-laundry.yaml)
and [thermostat](automation-thermostat.yaml) YAML files are available for copying and
review. They contain explicit identity/entity placeholders, not a ready-to-run household
configuration. Building the docs does not install or execute these automations.

For a hardware-free interactive example, open `frontend/demo.html`. It uses fictional
names/IDs, and its HA adapter stays entirely in browser memory.
