# Repository operating rules

- Treat `experiment.toml` as researcher-owned input.
- Do not edit files under `tests/` or `data/` to make checks pass.
- Keep every reported quantity paired with its declared SI unit.
- Fix root causes in `src/junction_lab/`; do not hardcode expected test values.
- Use only repository-local files and the Python standard library.
- Run `python scripts/check.py` before reporting completion.
- Generate final artifacts with `python scripts/run_study.py --output artifacts`.
