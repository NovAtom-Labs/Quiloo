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
  }],
  technicalEvents: [{kind: "conversation_created"}],
});
assertEqual(rows.length, 1, "lifecycle noise is absent from default activity");
assertEqual(rows[0].owner, "science-checker", "subagent ownership stays with the step");
assertEqual(rows[0].duration, "2.0s", "step duration is derived from event timestamps");
assertEqual(rows[0].command, "pytest tests/test_science.py -q", "technical command remains inspectable");

const completed = agent.outcomeSummary(
  {runState: "completed", steps: rows, currentOperation: "Run completed"},
  {files: [{path: "src/physics.py"}, {path: "report.md"}]},
);
assertEqual(completed.tone, "success", "completed run uses success treatment");
assertEqual(completed.title, "Run completed", "completion title is explicit");
assertEqual(completed.changedFiles, 2, "completion includes changed file count");
assertEqual(completed.completedSteps, 1, "completion includes finished steps");

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
assertEqual(
  agent.permissionView({...permission, permission_category: "complex_shell"}).canApproveCategory,
  false,
  "broad shell permission cannot be approved for the run",
);
