"use strict";

(() => {
  const operationLabels = {
    created: "Created",
    modified: "Modified",
    deleted: "Deleted",
    renamed: "Renamed",
  };

  function delta(change) {
    if (change.uncertain) return "Binary or metadata change";
    if (change.additions === null || change.additions === undefined) return "No line delta";
    const deletions = change.deletions || 0;
    return `+${change.additions} −${deletions}`;
  }

  function toRows(changeSet) {
    if (!changeSet || !Array.isArray(changeSet.files)) return [];
    return changeSet.files.map((change) => ({
      label: change.path,
      operation: change.operation,
      operationLabel: operationLabels[change.operation] || "Changed",
      delta: delta(change),
      detail: change.operation === "renamed" && change.previous_path
        ? `Renamed from ${change.previous_path}`
        : null,
      uncertain: Boolean(change.uncertain),
      diff: change.diff || null,
      diffTruncated: Boolean(change.diff_truncated),
      canOpenFile: change.operation !== "deleted",
      attributedActionIds: change.attributed_action_ids || [],
      attributedTools: change.attributed_tools || [],
      attributedSubagents: change.attributed_subagents || [],
      validationActionIds: change.validation_action_ids || [],
      artifact: Boolean(change.artifact),
    }));
  }

  function isIncomplete(changeSet) {
    return Boolean(changeSet?.baseline_truncated);
  }

  globalThis.AgentKronigChanges = {isIncomplete, toRows};
})();
