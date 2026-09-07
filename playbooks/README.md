# SHE Engineering Playbooks

Playbooks turn repository work into evidence that can be reviewed, repeated, and rolled back.

## Routing

- `changes/`: one record for each independently reviewable logical change.
- `incidents/`: reproducible failures, their root cause, and verified recovery.
- `decisions/`: architecture decisions and rejected alternatives.
- `releases/`: operational checklists, including steps that still need real hardware.
- `templates/`: the required shape of each record.

Before changing code, identify its architecture layer and search `skills/` and `playbooks/incidents/` for the same situation. After the change, ship its change record in the same commit. Promote a playbook to a skill only when the procedure is reusable, stable, and verifiable.

Never place credentials, raw child audio/video, child utterances, database dumps, or production payloads in a playbook.
