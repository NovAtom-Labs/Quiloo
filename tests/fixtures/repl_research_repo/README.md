# Junction Lab

This repository is a small but realistic semiconductor research handoff. It models an abrupt, uniformly doped silicon p-n junction at equilibrium using analytical depletion-approximation checks. The code is intentionally incomplete and currently fails scientific and provenance checks.

## Reproduce the current state

Requirements: Git and Python 3.11 or newer. No network access or third-party packages are required.

```bash
python scripts/check.py
python scripts/run_study.py --output artifacts
```

Read `RESEARCH_TASK.md` for the requested work. Do not change the tests, input deck, or reference data.

## Repository map

- `experiment.toml`: researcher-owned experiment definition
- `src/junction_lab/`: calculations, validation, and reporting
- `data/reference_profile.csv`: reviewed reference points
- `tests/`: visible acceptance checks
- `docs/physics-notes.md`: assumptions and unit conventions
- `scripts/check.py`: deterministic validation entrypoint
- `scripts/run_study.py`: artifact generation entrypoint
