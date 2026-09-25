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
    const labels = {
      plan: "Plan",
      inspect: "Inspect",
      edit: "Edit",
      delegate: "Delegate",
      execute: "Execute",
      validate: "Validate",
      report: "Report",
    };
    if (Object.values(labels).includes(step.phase)) return step.phase;
    return labels[step.phase] || "Unclassified";
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
      evidenceKind: step.evidenceKind || null,
      affectedPaths: step.affectedPaths || [],
      artifactPaths: step.artifactPaths || [],
      provenance: step.provenance || null,
    }));
  }

  function operationalUpdates(snapshot) {
    const state = snapshot?.runState || "idle";
    if (state === "idle") return [];
    const steps = snapshot?.steps || [];
    const updates = [{
      id: "run-start",
      phase: "Plan",
      label: "Understanding the request and preparing an approach",
      detail: null,
      status: !steps.length && ["queued", "running"].includes(state)
        ? "running"
        : "completed",
    }];
    const labels = {
      plan: "Updating the plan",
      inspect: "Inspecting repository evidence",
      edit: "Updating workspace files",
      delegate: "Delegating a focused task",
      execute: "Running a workspace operation",
      validate: "Running validation",
      report: "Preparing the result",
    };
    steps.forEach((step) => {
      const phase = phaseForStep(step);
      const command = technicalCommand(step);
      const tasks = Array.isArray(step.arguments?.tasks) ? step.arguments.tasks : [];
      let label = labels[step.phase] || "Working on the repository";
      let detail = command || step.summary || null;
      if (step.toolName === "think") {
        label = "Reviewing evidence and choosing the next action";
        detail = null;
      } else if (step.toolName === "task_tracker" && tasks.length) {
        label = "Plan updated";
        detail = tasks.map((task) => task.title).filter(Boolean).join(" · ") || null;
      }
      updates.push({
        id: step.id,
        phase,
        label,
        detail,
        status: step.status || "running",
      });
    });
    if (snapshot?.inference) {
      updates.push({
        id: snapshot.inference.id || "agent-inference",
        phase: "Plan",
        label: snapshot.inference.label || "Analyzing context and choosing the next action",
        detail: null,
        status: snapshot.inference.status || "running",
      });
    }
    const pendingApproval = (snapshot?.pendingApprovals || []).at(-1);
    if (pendingApproval || state === "waiting_for_approval") {
      updates.push({
        id: "approval-wait",
        phase: "Approval",
        label: "Waiting for your approval",
        detail: pendingApproval?.summary || null,
        status: "waiting",
      });
    } else if (state === "paused") {
      updates.push({
        id: "run-paused",
        phase: "Paused",
        label: "Run paused",
        detail: null,
        status: "waiting",
      });
    } else if (state === "running"
      && snapshot?.inference?.status !== "running"
      && !steps.some((step) => step.status === "running")) {
      updates.push({
        id: "between-actions",
        phase: "Plan",
        label: "Reviewing results and choosing the next action",
        detail: null,
        status: "running",
      });
    }
    return updates.slice(-6);
  }

  function unique(values) {
    return Array.from(new Set(values.filter(Boolean)));
  }

  function affectedFilePaths(row, workspaceRoot) {
    const evidencePaths = Array.isArray(row?.affectedPaths) && row.affectedPaths.length
      ? row.affectedPaths
      : [row?.path];
    const root = String(workspaceRoot || "").replaceAll("\\", "/").replace(/\/$/, "");
    return unique(evidencePaths.map((value) => {
      const path = String(value || "").replaceAll("\\", "/");
      return root && path.startsWith(`${root}/`) ? path.slice(root.length + 1) : path;
    }));
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
    const validationActionIds = new Set(
      (changeSet?.files || []).flatMap((change) => change.validation_action_ids || []),
    );
    const validationChecks = successful.filter((step) => step.evidenceKind === "validation");
    const validationEvidence = validationChecks
      .filter((step) => validationActionIds.has(step.id))
      .map((step) => ({label: step.label, output: step.output || null}));
    const unlinkedValidationChecks = validationChecks
      .filter((step) => !validationActionIds.has(step.id))
      .map((step) => ({label: step.label, output: step.output || null}));
    const warnings = [];
    if (changeSet?.baseline_truncated) {
      warnings.push(changeSet.manifest_warning || "The workspace scan reached its safety limit. Create, delete, and rename attribution may be incomplete.");
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
      unlinkedValidationChecks,
      artifacts: (changeSet?.files || []).filter((change) => change.artifact).map((change) => change.path),
      provenance: unique(successful.map((step) => step.provenance).filter((item) => typeof item === "string")),
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
    affectedFilePaths,
    activityRows,
    durationText,
    outcomeSummary,
    operationalUpdates,
    permissionView,
    phaseForStep,
    sanitizeArguments,
  };
})();
