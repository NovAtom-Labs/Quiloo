# Quiloo REPL end-to-end evaluation

This evaluation creates a disposable Git repository that resembles a researcher handoff rather than a product-specific demo. It exercises repository discovery, scientific reasoning, cross-file repair, command execution, artifact generation, Git review, persistence, and approval boundaries.

## Create a fresh workspace

From the Quiloo project root:

```bash
python scripts/create_repl_test_repo.py --include-external-fixture
```

The command creates:

- `test-workspaces/pn-junction-research/`, the repository Quiloo should open
- `test-workspaces/external-calibration.csv`, an optional file outside that repository for approval testing

The generated repository starts on `main`, has one deterministic baseline commit, has no uncommitted changes, and intentionally has three failing checks.

## Grade the main repair case

```bash
python evaluations/repl/grade_workspace.py \
  --workspace test-workspaces/pn-junction-research
```

The baseline score is 25/100. A correct repair scores 100/100. The independent grader verifies:

- researcher-owned tests, inputs, and reference data were not changed
- all visible checks pass
- generated scientific artifacts contain correct SI values and provenance
- the calculation generalizes to an unseen asymmetric, 325 K junction

## Reset

Delete the disposable `test-workspaces/pn-junction-research/` directory and run the creation command again. Never reset the main Quiloo repository to reset this fixture.

## What can be tested today

The current foundation can open this repository, show its Git state and file tree, create a stable conversation URL, persist a prompt, restore it after reload, and stream durable activity events.

The full repair case becomes executable when repository file reads, search, bounded terminal execution, atomic edits, diffs, and checkpoints are connected to the OpenHands runtime. The fixture is already structured to test those capabilities without redesign.

See `prompts.md` for copy-paste scenarios in increasing order of difficulty.
