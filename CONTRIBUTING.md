# Contributing

Contributions are welcome. Keep M-Skill small, explicit, and auditable.

## Development workflow

1. Create a branch from `main`.
2. Add or update tests for behavioral changes.
3. Run `python -m unittest discover -s tests -v`.
4. Open a pull request describing the workflow invariant being added or changed.

## Design constraints

- Do not add a transition that bypasses a red-team gate.
- Prefer the Python standard library unless a dependency has clear, durable value.
- State-file changes should remain human-readable and migration-friendly.
- Error messages should explain the violated workflow rule.
