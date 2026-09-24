"use strict";

function assertEqual(actual, expected, message) {
  if (actual !== expected) throw new Error(`${message}: ${actual}`);
}

function event(id, kind, payload = {}) {
  return {id, kind, payload, created_at: `2026-09-25T10:00:${String(id).padStart(2, "0")}Z`};
}

function toolStarted(id, actionId, toolName, summary, subagent = null) {
  return event(id, "tool_call_started", {
    action_id: actionId,
    tool_call_id: `call-${actionId}`,
    tool_name: toolName,
    summary,
    subagent,
  });
}

function toolCompleted(id, actionId, toolName, output, subagent = null) {
  return event(id, "tool_call_completed", {
    action_id: actionId,
    tool_call_id: `call-${actionId}`,
    tool_name: toolName,
    output,
    subagent,
    is_error: false,
  });
}

const view = globalThis.QuilooIDEEvents.createRunPresentation();
view.accept(event(1, "conversation_created"));
view.accept(toolStarted(11, "action-1", "terminal", "Run focused tests"));
view.accept(toolCompleted(12, "action-1", "terminal", "2 passed"));
view.accept(toolCompleted(12, "action-1", "terminal", "2 passed"));

let snapshot = view.snapshot();
assertEqual(snapshot.steps.length, 1, "start and completion form one step");
assertEqual(snapshot.steps[0].status, "completed", "completion closes step");
assertEqual(snapshot.steps[0].output, "2 passed", "tool evidence is retained");
assertEqual(snapshot.lastEventId, 12, "duplicate replay is ignored");
assertEqual(snapshot.technicalEvents.length, 1, "low-value lifecycle event stays technical");

view.accept(toolStarted(13, "action-2", "task", "Delegate validation", "science-checker"));
snapshot = view.snapshot();
assertEqual(snapshot.steps[1].subagent, "science-checker", "subagent ownership is retained");

view.accept(event(14, "thinking_started", {item_id: "reason-1"}));
view.accept(event(15, "thinking_delta", {item_id: "reason-1", content: "Checking units. "}));
view.accept(event(16, "thinking_delta", {item_id: "reason-1", content: "Comparing evidence."}));
view.accept(event(17, "thinking_aborted", {item_id: "reason-1", reason: "redirected"}));
snapshot = view.snapshot();
assertEqual(snapshot.reasoning[0].content, "Checking units. Comparing evidence.", "reasoning deltas join in order");
assertEqual(snapshot.reasoning[0].status, "interrupted", "aborted reasoning is explicit");

view.accept(event(18, "approval_requested", {approval_id: "approval-1", summary: "Allow network access"}));
assertEqual(view.snapshot().pendingApprovals.length, 1, "pending approval survives in presentation state");
view.accept(event(19, "approval_resolved", {approval_id: "approval-1", decision: "deny"}));
assertEqual(view.snapshot().pendingApprovals.length, 0, "resolved approval leaves pending state");
assertEqual(view.snapshot().approvalHistory.length, 1, "approval remains visible in run activity");
assertEqual(view.snapshot().approvalHistory[0].decision, "deny", "approval outcome is retained");

view.accept(event(20, "run_state_changed", {run_id: "run-1", state: "running"}));
view.accept(event(21, "run_failed", {run_id: "run-1", detail: "validation failed"}));
snapshot = view.snapshot();
assertEqual(snapshot.runState, "failed", "terminal event determines run state");
assertEqual(snapshot.runId, "run-1", "run identity survives event restoration");
assertEqual(snapshot.currentOperation, "Run failed", "terminal state has a useful operation label");

const restored = globalThis.QuilooIDEEvents.createRunPresentation();
[
  event(1, "conversation_created"),
  toolStarted(11, "action-1", "terminal", "Run focused tests"),
  toolCompleted(12, "action-1", "terminal", "2 passed"),
].forEach((item) => restored.accept(item));
assertEqual(
  JSON.stringify(restored.snapshot().steps),
  JSON.stringify(view.snapshot().steps.slice(0, 1)),
  "restored and live events reduce to the same step shape",
);

view.reset();
assertEqual(view.snapshot().lastEventId, 0, "reset clears the cursor");
assertEqual(view.snapshot().steps.length, 0, "reset clears steps");
