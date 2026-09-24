"use strict";

(() => {
  function durationText(startedAt, completedAt) {
    if (!startedAt || !completedAt) return null;
    const elapsed = new Date(completedAt).getTime() - new Date(startedAt).getTime();
    if (!Number.isFinite(elapsed) || elapsed < 0) return null;
    if (elapsed < 60_000) return `${(elapsed / 1_000).toFixed(1)}s`;
    const minutes = Math.floor(elapsed / 60_000);
    const seconds = Math.round((elapsed % 60_000) / 1_000);
    return `${minutes}m ${seconds}s`;
  }

  function technicalCommand(step) {
    const argumentsValue = step.arguments || {};
    return argumentsValue.command || argumentsValue.path || argumentsValue.operation || null;
  }

  function activityRows(snapshot) {
    return (snapshot?.steps || []).map((step) => ({
      id: step.id,
      label: step.summary || step.toolName || "Agent action",
      status: step.status || "running",
      toolName: step.toolName || "tool",
      owner: step.subagent || "Quiloo",
      duration: durationText(step.startedAt, step.completedAt),
      command: technicalCommand(step),
      output: step.output || null,
      isError: Boolean(step.isError),
      path: step.arguments?.path || null,
      taskStatus: step.taskStatus || null,
    }));
  }

  function outcomeSummary(snapshot, changeSet) {
    const steps = snapshot?.steps || [];
    const failed = steps.find((step) => step.status === "failed");
    const successful = steps.filter((step) => step.status === "completed");
    const state = snapshot?.runState || "idle";
    const terminal = ["completed", "failed", "blocked", "cancelled"].includes(state);
    const titles = {
      completed: "Run completed",
      failed: "Run failed",
      blocked: "Run blocked",
      cancelled: "Run cancelled",
    };
    const tones = {
      completed: "success",
      failed: "danger",
      blocked: "warning",
      cancelled: "muted",
    };
    return {
      visible: terminal,
      state,
      tone: tones[state] || "neutral",
      title: titles[state] || snapshot?.currentOperation || "Run activity",
      changedFiles: changeSet?.files?.length || 0,
      completedSteps: successful.length,
      failedStep: failed?.summary || failed?.label || null,
      failureOutput: failed?.output || null,
      lastSuccessfulStep: successful.at(-1)?.summary || successful.at(-1)?.label || null,
    };
  }

  function permissionView(approval) {
    const payload = approval?.payload || {};
    const permissionCategory = approval?.permission_category
      || approval?.permissionCategory
      || "unrecognized_action";
    return {
      explanation: approval?.summary || approval?.explanation || "Review the requested action.",
      target: payload.path || payload.command || payload.operation || approval?.target
        || "Review the technical details.",
      toolName: approval?.tool_name || approval?.toolName || "tool",
      permissionCategory,
      risk: approval?.risk || "HIGH",
      canApproveCategory: !["complex_shell", "unrecognized_action"].includes(
        permissionCategory,
      ),
    };
  }

  globalThis.QuilooAgentView = {
    activityRows,
    durationText,
    outcomeSummary,
    permissionView,
  };
})();
