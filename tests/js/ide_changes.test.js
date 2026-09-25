"use strict";

function assertEqual(actual, expected, message) {
  if (actual !== expected) throw new Error(`${message}: ${actual}`);
}

const changes = globalThis.AgentKronigChanges;
const rows = changes.toRows({
  files: [
    {path: "src/physics.py", operation: "modified", additions: 8, deletions: 3, uncertain: false, diff: "@@", validation_action_ids: ["validate-1"]},
    {path: "results/new.csv", operation: "created", additions: 12, deletions: 0, uncertain: false, diff: "@@"},
    {path: "old.log", operation: "deleted", additions: 0, deletions: 4, uncertain: false, diff: "@@"},
    {path: "docs/final.md", previous_path: "docs/draft.md", operation: "renamed", additions: null, deletions: null, uncertain: false, diff: null},
    {path: "mesh.bin", operation: "modified", additions: null, deletions: null, uncertain: true, diff: null},
  ],
});
assertEqual(rows[0].label, "src/physics.py", "path is the primary label");
assertEqual(rows[0].delta, "+8 −3", "text line delta is compact");
assertEqual(rows[0].uncertain, false, "exact comparison stays exact");
assertEqual(rows[0].validationActionIds[0], "validate-1", "validation evidence remains navigable");
assertEqual(rows[1].operationLabel, "Created", "created file is named clearly");
assertEqual(rows[2].operationLabel, "Deleted", "deleted file is named clearly");
assertEqual(rows[3].detail, "Renamed from docs/draft.md", "rename keeps the previous path");
assertEqual(rows[4].delta, "Binary or metadata change", "uncertain binary change is explicit");
assertEqual(changes.toRows({files: []}).length, 0, "empty change set stays empty");
assertEqual(changes.toRows(null).length, 0, "unavailable change set is safe");
assertEqual(changes.isIncomplete({baseline_truncated: true}), true, "truncated comparison is visibly incomplete");
assertEqual(changes.isIncomplete({baseline_truncated: false}), false, "complete comparison stays exact");
