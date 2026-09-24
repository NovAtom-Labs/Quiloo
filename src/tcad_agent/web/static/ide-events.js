"use strict";

(() => {
  const terminalStates = {
    run_completed: "completed",
    run_failed: "failed",
    run_blocked: "blocked",
    run_cancelled: "cancelled",
    run_paused: "paused",
    run_recovered_paused: "paused",
  };

  function createRunPresentation() {
    const seen = new Set();
    const steps = [];
    const stepsByKey = new Map();
    const reasoning = [];
    const reasoningById = new Map();
    const pendingApprovals = new Map();
    const approvalHistory = [];
    const approvalsById = new Map();
    const technicalEvents = [];
    let lastEventId = 0;
    let runId = null;
    let runState = "idle";
    let currentOperation = "Idle";

    function eventKey(event) {
      return String(event.id);
    }

    function actionKey(payload, event) {
      return String(payload.action_id || payload.tool_call_id || `event-${event.id}`);
    }

    function closeLiveReasoning() {
      reasoning.forEach((entry) => {
        if (entry.status === "live") entry.status = "complete";
      });
    }

    function startTool(event) {
      const payload = event.payload || {};
      const key = actionKey(payload, event);
      let step = stepsByKey.get(key);
      if (!step) {
        step = {
          id: key,
          actionId: payload.action_id || null,
          toolCallId: payload.tool_call_id || null,
          toolName: payload.tool_name || "tool",
          summary: payload.summary || payload.tool_name || "Tool call",
          status: "running",
          startedAt: event.created_at || null,
          completedAt: null,
          output: null,
          isError: false,
          arguments: payload.arguments || null,
          subagent: payload.subagent || null,
          taskStatus: null,
        };
        stepsByKey.set(key, step);
        steps.push(step);
      }
      currentOperation = step.summary;
    }

    function completeTool(event) {
      const payload = event.payload || {};
      const key = actionKey(payload, event);
      let step = stepsByKey.get(key);
      if (!step && payload.tool_call_id) {
        step = steps.find((item) => item.toolCallId === payload.tool_call_id);
      }
      if (!step) {
        step = {
          id: key,
          actionId: payload.action_id || null,
          toolCallId: payload.tool_call_id || null,
          toolName: payload.tool_name || "tool",
          summary: payload.summary || payload.tool_name || "Tool call",
          status: "running",
          startedAt: null,
          completedAt: null,
          output: null,
          isError: false,
          arguments: null,
          subagent: null,
          taskStatus: null,
        };
        stepsByKey.set(key, step);
        steps.push(step);
      }
      step.completedAt = event.created_at || null;
      step.output = payload.output || "";
      step.isError = Boolean(payload.is_error);
      step.status = step.isError ? "failed" : "completed";
      step.subagent = payload.subagent || step.subagent;
      step.taskStatus = payload.task_status || null;
      currentOperation = step.isError ? `${step.summary} failed` : step.summary;
    }

    function beginReasoning(event) {
      const payload = event.payload || {};
      const itemId = String(payload.item_id || `reason-${event.id}`);
      if (reasoningById.has(itemId)) return;
      const entry = {id: itemId, content: "", status: "live", reason: null};
      reasoningById.set(itemId, entry);
      reasoning.push(entry);
      currentOperation = "Reviewing evidence";
    }

    function appendReasoning(event) {
      const payload = event.payload || {};
      const itemId = String(payload.item_id || `reason-${event.id}`);
      if (!reasoningById.has(itemId)) beginReasoning(event);
      const entry = reasoningById.get(itemId);
      entry.content = `${entry.content}${String(payload.content || "")}`.slice(-4_000);
    }

    function abortReasoning(event) {
      const payload = event.payload || {};
      const itemId = String(payload.item_id || `reason-${event.id}`);
      const entry = reasoningById.get(itemId);
      if (!entry) return;
      entry.status = "interrupted";
      entry.reason = payload.reason || null;
    }

    function updateRunState(event) {
      const payload = event.payload || {};
      if (event.kind === "run_state_changed" && payload.state) {
        runState = String(payload.state);
      } else if (terminalStates[event.kind]) {
        runState = terminalStates[event.kind];
      } else if (event.kind === "run_started") {
        runState = "running";
      } else if (event.kind === "approval_requested") {
        runState = "waiting_for_approval";
      }
      const labels = {
        completed: "Run completed",
        failed: "Run failed",
        blocked: "Run blocked",
        cancelled: "Run cancelled",
        paused: "Run paused",
        waiting_for_approval: "Waiting for approval",
        waiting_for_user: "Waiting for input",
      };
      if (labels[runState]) currentOperation = labels[runState];
    }

    function accept(event) {
      if (!event || event.id === undefined || seen.has(eventKey(event))) return false;
      seen.add(eventKey(event));
      const numericId = Number(event.id);
      if (Number.isFinite(numericId)) lastEventId = Math.max(lastEventId, numericId);
      if (event.payload?.run_id) runId = String(event.payload.run_id);
      if (!["thinking_started", "thinking_delta", "thinking_aborted"].includes(event.kind)) {
        closeLiveReasoning();
      }
      if (event.kind === "tool_call_started") startTool(event);
      else if (event.kind === "tool_call_completed") completeTool(event);
      else if (event.kind === "thinking_started") beginReasoning(event);
      else if (event.kind === "thinking_delta") appendReasoning(event);
      else if (event.kind === "thinking_aborted") abortReasoning(event);
      else if (event.kind === "approval_requested") {
        const payload = event.payload || {};
        const approvalId = String(payload.approval_id || event.id);
        const entry = {
          id: approvalId,
          summary: payload.summary || "Permission required",
          risk: payload.risk || "HIGH",
          decision: null,
          requestedAt: event.created_at || null,
          resolvedAt: null,
        };
        pendingApprovals.set(approvalId, payload);
        approvalsById.set(approvalId, entry);
        approvalHistory.push(entry);
      } else if (event.kind === "approval_resolved") {
        const payload = event.payload || {};
        const approvalId = String(payload.approval_id || "");
        pendingApprovals.delete(approvalId);
        const entry = approvalsById.get(approvalId);
        if (entry) {
          entry.decision = payload.decision || "resolved";
          entry.resolvedAt = event.created_at || null;
        }
      } else if (![
        "run_created", "run_started", "run_state_changed", "run_completed", "run_failed",
        "run_blocked", "run_cancelled", "run_paused", "run_recovered_paused",
        "message_created", "permission_grant_created", "permission_grant_used",
        "agent_error", "change_baseline_warning",
      ].includes(event.kind)) {
        technicalEvents.push(event);
      }
      updateRunState(event);
      return true;
    }

    function snapshot() {
      return JSON.parse(JSON.stringify({
        lastEventId,
        runId,
        runState,
        currentOperation,
        steps,
        reasoning,
        pendingApprovals: Array.from(pendingApprovals.values()),
        approvalHistory,
        technicalEvents,
      }));
    }

    function reset() {
      seen.clear();
      steps.splice(0);
      stepsByKey.clear();
      reasoning.splice(0);
      reasoningById.clear();
      pendingApprovals.clear();
      approvalHistory.splice(0);
      approvalsById.clear();
      technicalEvents.splice(0);
      lastEventId = 0;
      runId = null;
      runState = "idle";
      currentOperation = "Idle";
    }

    return {accept, reset, snapshot};
  }

  globalThis.QuilooIDEEvents = {createRunPresentation};
})();
