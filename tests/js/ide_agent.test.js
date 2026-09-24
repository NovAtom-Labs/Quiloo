"use strict";

function assertEqual(actual, expected, message) {
  if (actual !== expected) throw new Error(`${message}: ${actual}`);
}

const agent = globalThis.QuilooAgentView;
const rows = agent.activityRows({
  steps: [{
    id: "action-1",
    toolName: "terminal",
    summary: "Run focused tests",
    status: "completed",
    startedAt: "2026-09-25T10:00:00Z",
    completedAt: "2026-09-25T10:00:02Z",
    output: "2 passed",
    arguments: {command: "pytest tests/test_science.py -q"},
    subagent: "science-checker",
    isError: false,
    phase: "validate",
    evidenceKind: "validation",
  }],
  technicalEvents: [{kind: "conversation_created"}],
});
assertEqual(rows.length, 1, "lifecycle noise is absent from default activity");
assertEqual(rows[0].owner, "science-checker", "subagent ownership stays with the step");
assertEqual(rows[0].duration, "2.0s", "step duration is derived from event timestamps");
assertEqual(rows[0].command, "pytest tests/test_science.py -q", "technical command remains inspectable");
assertEqual(rows[0].phase, "Validate", "test execution is classified as validation evidence");

const completed = agent.outcomeSummary(
  {runState: "completed", steps: rows, currentOperation: "Run completed"},
  {files: [
    {path: "src/physics.py", validation_action_ids: ["action-1"]},
    {path: "report.md"},
  ]},
);
assertEqual(completed.tone, "success", "completed run uses success treatment");
assertEqual(completed.title, "Run completed", "completion title is explicit");
assertEqual(completed.changedFiles, 2, "completion includes changed file count");
assertEqual(completed.completedSteps, 1, "completion includes finished steps");
assertEqual(completed.changedPaths.join(","), "src/physics.py,report.md", "completion names changed files");
assertEqual(completed.validationEvidence.length, 1, "successful validation action becomes evidence");
assertEqual(completed.unlinkedValidationChecks.length, 0, "linked validation is not called stale");
assertEqual(completed.commands[0], "pytest tests/test_science.py -q", "completion retains executed commands");
assertEqual(completed.nextActions.length, 1, "completed runs provide a grounded next action");

const staleCheck = agent.outcomeSummary(
  {runState: "completed", steps: rows, currentOperation: "Run completed"},
  {files: [{path: "src/physics.py", validation_action_ids: []}]},
);
assertEqual(staleCheck.validationEvidence.length, 0, "stale check is not final evidence");
assertEqual(staleCheck.unlinkedValidationChecks.length, 1, "stale check remains visible as executed");

const honest = agent.activityRows({steps: [{
  id: "action-2",
  toolName: "file_editor",
  summary: "Read checks/input.txt",
  status: "completed",
  arguments: {command: "view", path: "checks/input.txt"},
  phase: "inspect",
}]});
assertEqual(honest[0].phase, "Inspect", "phase comes from structured backend metadata, not path keywords");
const noInferredArtifact = agent.outcomeSummary(
  {runState: "completed", steps: honest},
  {files: [{path: "reports/notes.txt", artifact: false}]},
);
assertEqual(noInferredArtifact.artifacts.length, 0, "artifact status is never inferred from a folder name");

const failed = agent.outcomeSummary(
  {
    runState: "failed",
    steps: [
      {status: "completed", summary: "Inspect files"},
      {status: "failed", summary: "Run validation", output: "assertion failed"},
    ],
    currentOperation: "Run failed",
  },
  {files: [{path: "src/physics.py"}]},
);
assertEqual(failed.tone, "danger", "failed run uses failure treatment");
assertEqual(failed.failedStep, "Run validation", "failure keeps the failed step");
assertEqual(failed.lastSuccessfulStep, "Inspect files", "failure keeps partial evidence");

const permission = agent.permissionView({
  summary: "Quiloo wants to access a path outside this repository.",
  tool_name: "terminal",
  permission_category: "external_file_access",
  risk: "HIGH",
  payload: {command: "cat /shared/reference.dat"},
});
assertEqual(permission.explanation.includes("outside this repository"), true, "plain explanation is primary");
assertEqual(permission.target, "cat /shared/reference.dat", "exact technical target is retained");
assertEqual(permission.canApproveCategory, true, "narrow category can be approved for the run");
assertEqual(permission.technicalArguments.includes("cat /shared/reference.dat"), true, "all sanitized arguments remain inspectable");
assertEqual(permission.reversibility.includes("Read-only"), true, "read-only permission explains reversibility");
const redacted = agent.permissionView({
  payload: {command: "curl example.test", api_key: "never-show-this"},
  permission_category: "network_access",
});
assertEqual(redacted.technicalArguments.includes("never-show-this"), false, "sensitive argument values are redacted");
assertEqual(redacted.technicalArguments.includes("[redacted]"), true, "redaction is explicit");
assertEqual(
  agent.permissionView({...permission, permission_category: "complex_shell"}).canApproveCategory,
  false,
  "broad shell permission cannot be approved for the run",
);
