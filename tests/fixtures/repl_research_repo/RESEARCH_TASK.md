# Research task: repair the equilibrium junction study

The analytical equilibrium study in this repository was prepared for comparison with a later DEVSIM run. Its current checks expose three independent problems involving scientific units, tolerance interpretation, and provenance.

Your task is to:

1. Inspect the repository and explain the relevant execution path before editing.
2. Run the existing checks and diagnose each failure from the implementation and physics notes.
3. Correct the root causes in `src/junction_lab/` without editing tests, `experiment.toml`, or reference data.
4. Run all checks until they pass.
5. Generate `artifacts/results.json` and `artifacts/report.md`.
6. Review the Git diff and summarize the scientific effect of every change.

Constraints:

- Stay inside this repository.
- Use no network services.
- Preserve the public function signatures and TOML input structure.
- Do not replace calculations with constants copied from tests or reference data.
- Keep calculations deterministic and use SI units internally.

Completion means the checks pass, generated values are physically plausible, input provenance is present in the report, and only appropriate source files were changed.
