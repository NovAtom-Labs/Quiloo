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
    return step.command || argumentsValue.command || argumentsValue.path
      || argumentsValue.operation || null;
  }

  function phaseForStep(step) {
    const text = `${step.toolName || ""} ${step.summary || step.label || ""} ${technicalCommand(step) || ""}`.toLowerCase();
    if (/pytest|mypy|ruff|validate|validation|check|test\b/.test(text)) return "Validate";
    if (/simulate|devsim|sentaurus|execute|run\b/.test(text)) return "Execute";
    if (/file_editor/.test(text) && /create|str_replace|insert|edit|write/.test(text)) return "Edit";
    if (/task_tracker|plan|todo/.test(text)) return "Plan";
    if (/\btask\b|delegate|subagent/.test(text)) return "Delegate";
    if (/finish|report|summar/.test(text)) return "Report";
    if (/file_editor|view|read|inspect|search|find|grep|rg\b/.test(text)) return "Inspect";
    return "Execute";
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
      phase: phaseForStep(step),
    }));
  }

  function unique(values) {
    return Array.from(new Set(values.filter(Boolean)));
  }

  function outcomeSummary(snapshot, changeSet) {
    const steps = activityRows(snapshot);
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
    const changedPaths = (changeSet?.files || []).map((change) => change.path);
    const validationEvidence = successful
      .filter((step) => step.phase === "Validate")
      .map((step) => ({label: step.label, output: step.output || null}));
    const warnings = [];
    if (changeSet?.baseline_truncated) {
      warnings.push("The workspace scan reached its safety limit. Create, delete, and rename attribution may be incomplete.");
    }
    if (failed) warnings.push(`Failed action: ${failed.label}`);
    (snapshot?.technicalEvents || [])
      .filter((event) => ["agent_error", "change_baseline_warning"].includes(event.kind))
      .forEach((event) => warnings.push(String(event.payload?.detail || event.kind)));
    const nextActions = [];
    if (state === "completed") nextActions.push("Review changed files and validation evidence.");
    else if (failed) nextActions.push("Inspect the failed action output before retrying.");
    else if (state === "blocked") nextActions.push("Resolve the reported blocker before continuing.");
    return {
      visible: terminal,
      state,
      tone: tones[state] || "neutral",
      title: titles[state] || snapshot?.currentOperation || "Run activity",
      changedFiles: changedPaths.length,
      changedPaths,
      completedSteps: successful.length,
      failedStep: failed?.label || null,
      failureOutput: failed?.output || null,
      lastSuccessfulStep: successful.at(-1)?.label || null,
      phases: unique(steps.map((step) => step.phase)),
      commands: unique(steps.map((step) => step.command)),
      validationEvidence,
      artifacts: changedPaths.filter((path) => /(^|\/)(artifacts?|results?|reports?)(\/|$)/i.test(path)),
      warnings,
      nextActions,
    };
  }

  function sanitizeArguments(value, key = "") {
    if (/(token|secret|password|credential|api[_-]?key|authorization)/i.test(key)) {
      return "[redacted]";
    }
    if (Array.isArray(value)) return value.map((item) => sanitizeArguments(item));
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value).map(([childKey, child]) => [
          childKey,
          sanitizeArguments(child, childKey),
        ]),
      );
    }
    return value;
  }

  function reversibilityFor(permissionCategory, payload) {
    const command = String(payload.command || "").trim().toLowerCase();
    if (["external_file_access", "sensitive_file_access"].includes(permissionCategory)
      && /^(cat|head|tail|grep|rg|find|ls|sed\s+-n)\b/.test(command)) {
      return "Read-only. No workspace data is changed.";
    }
    if (["network_access"].includes(permissionCategory)) {
      return "May send or retrieve external data. The external effect may not be reversible.";
    }
    if (["git_mutation", "destructive_command", "system_change", "package_installation", "remote_execution"].includes(permissionCategory)) {
      return "May change local or external state. Reversal is not guaranteed.";
    }
    if (payload.path) return "May change a file. Version control may allow reversal.";
    return "Reversibility is not guaranteed. Review the exact arguments before approval.";
  }

  function permissionView(approval) {
    const payload = approval?.payload || {};
    const permissionCategory = approval?.permission_category
      || approval?.permissionCategory
      || "unrecognized_action";
    const sanitized = sanitizeArguments(payload);
    return {
      explanation: approval?.summary || approval?.explanation || "Review the requested action.",
      target: sanitized.path || sanitized.command || sanitized.operation || approval?.target
        || "Review the technical details.",
      toolName: approval?.tool_name || approval?.toolName || "tool",
      permissionCategory,
      risk: approval?.risk || "HIGH",
      canApproveCategory: !["complex_shell", "unrecognized_action"].includes(
        permissionCategory,
      ),
      technicalArguments: JSON.stringify(sanitized, null, 2),
      reversibility: reversibilityFor(permissionCategory, sanitized),
    };
  }

  globalThis.QuilooAgentView = {
    activityRows,
    durationText,
    outcomeSummary,
    permissionView,
    phaseForStep,
    sanitizeArguments,
  };
})();
