"use strict";

const workspaceForm = document.querySelector("#workspace-form");
const workspacePath = document.querySelector("#workspace-path");
const browseWorkspace = document.querySelector("#browse-workspace");
const workspaceStatus = document.querySelector("#workspace-status");
const gitState = document.querySelector("#git-state");
const repositoryTree = document.querySelector("#repository-tree");
const conversationList = document.querySelector("#conversation-list");
const createConversation = document.querySelector("#create-conversation");
const conversationDialog = document.querySelector("#conversation-dialog");
const conversationForm = document.querySelector("#conversation-form");
const conversationTitleInput = document.querySelector("#conversation-title-input");
const cancelConversation = document.querySelector("#cancel-conversation");
const conversationTitle = document.querySelector("#conversation-title");
const conversationMessages = document.querySelector("#conversation-messages");
const agentActivity = document.querySelector("#agent-activity");
const streamState = document.querySelector("#stream-state");
const runState = document.querySelector("#run-state");
const runControls = document.querySelector("#run-controls");
const pauseRun = document.querySelector("#pause-run");
const resumeRun = document.querySelector("#resume-run");
const stopRun = document.querySelector("#stop-run");
const approvalSection = document.querySelector("#approval-section");
const pendingApprovals = document.querySelector("#pending-approvals");
const messageForm = document.querySelector("#message-form");
const messageInput = document.querySelector("#message-input");
const sendMessage = document.querySelector("#send-message");
const errorNotice = document.querySelector("#ide-error");
const workspaceWelcome = document.querySelector("#workspace-welcome");
const fileViewer = document.querySelector("#file-viewer");
const fileViewerKind = document.querySelector("#file-viewer-kind");
const fileViewerTitle = document.querySelector("#file-viewer-title");
const fileViewerPath = document.querySelector("#file-viewer-path");
const fileViewerType = document.querySelector("#file-viewer-type");
const fileViewerSize = document.querySelector("#file-viewer-size");
const fileViewerState = document.querySelector("#file-viewer-state");
const fileViewerNotice = document.querySelector("#file-viewer-notice");
const fileViewerBody = document.querySelector("#file-viewer-body");
const fileViewerModes = document.querySelector("#file-viewer-modes");
const fileViewerPreview = document.querySelector("#file-viewer-preview");
const fileViewerSource = document.querySelector("#file-viewer-source");
const fileViewerRefresh = document.querySelector("#file-viewer-refresh");
const fileViewerDownload = document.querySelector("#file-viewer-download");
const fileViewerClose = document.querySelector("#file-viewer-close");

let activeWorkspace = null;
let activeConversation = null;
let activeRun = null;
let eventSource = null;
let sendingPrompt = false;
let activeFile = null;
let fileRequestGeneration = 0;
const navigationGuard = window.QuilooIDEState.createNavigationGuard();
const submissions = window.QuilooIDEState.createSubmissionTracker();
const eventLedger = window.QuilooIDEState.createEventLedger();

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail && typeof data.detail === "object"
      ? data.detail.message
      : data.detail;
    throw new Error(data.message || detail || "Request failed");
  }
  return data;
}

function showError(message = "") {
  errorNotice.textContent = message;
  errorNotice.classList.toggle("hidden", !message);
}

function parseRoute() {
  const conversation = window.location.pathname.match(
    /^\/workspaces\/([0-9a-f-]{36})\/conversations\/([0-9a-f-]{36})$/i,
  );
  if (conversation) return {workspaceId: conversation[1], conversationId: conversation[2]};
  const workspace = window.location.pathname.match(/^\/workspaces\/([0-9a-f-]{36})$/i);
  return workspace ? {workspaceId: workspace[1], conversationId: null} : {workspaceId: null, conversationId: null};
}

function navigate(path) {
  window.history.pushState({}, "", path);
  void restoreRoute();
}

function clearNode(node) {
  node.replaceChildren();
}

function emptyCopy(text) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty-copy";
  paragraph.textContent = text;
  return paragraph;
}

function renderWorkspace(workspace) {
  const changedWorkspace = activeWorkspace?.id !== workspace.id;
  activeWorkspace = workspace;
  workspacePath.value = workspace.root;
  workspaceStatus.textContent = workspace.root;
  gitState.textContent = workspace.git.available
    ? `${workspace.git.branch || "DETACHED"}${workspace.git.dirty ? " · MODIFIED" : " · CLEAN"}`
    : "NO GIT";
  createConversation.disabled = false;
  if (changedWorkspace) closeFileViewer();
}

function closeFileViewer() {
  fileRequestGeneration += 1;
  activeFile = null;
  fileViewer.classList.add("hidden");
  workspaceWelcome.classList.remove("hidden");
  document.querySelectorAll(".tree-entry.is-selected").forEach((entry) => entry.classList.remove("is-selected"));
}

function setViewerNotice(message = "") {
  fileViewerNotice.textContent = message;
  fileViewerNotice.classList.toggle("hidden", !message);
}

function renderSource(content) {
  const source = document.createElement("ol");
  const lines = window.QuilooFileViewer.sourceLines(content || "");
  const displayLines = lines.slice(0, 20000);
  source.className = "file-source";
  displayLines.forEach((line) => {
    const row = document.createElement("li");
    const code = document.createElement("code");
    code.textContent = line || " ";
    row.append(code);
    source.append(row);
  });
  if (lines.length > displayLines.length) {
    setViewerNotice(`Preview limited to ${displayLines.length.toLocaleString()} lines.`);
  }
  fileViewerBody.append(source);
}

function renderMarkdown(content) {
  const article = document.createElement("article");
  article.className = "markdown-preview";
  window.QuilooFileViewer.markdownBlocks(content || "").forEach((block) => {
    let element;
    if (block.type === "heading") {
      element = document.createElement(`h${block.level}`);
      element.textContent = block.text;
    } else if (block.type === "code") {
      element = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = block.text;
      if (block.language) code.dataset.language = block.language;
      element.append(code);
    } else if (block.type === "list") {
      element = document.createElement("ul");
      block.items.forEach((item) => {
        const row = document.createElement("li");
        row.textContent = item;
        element.append(row);
      });
    } else if (block.type === "quote") {
      element = document.createElement("blockquote");
      element.textContent = block.text;
    } else {
      element = document.createElement("p");
      element.textContent = block.text;
    }
    article.append(element);
  });
  fileViewerBody.append(article);
}

function renderJsonValue(value, label, depth = 0, budget = {remaining: 2500}) {
  budget.remaining -= 1;
  if (budget.remaining < 0) {
    const limited = document.createElement("span");
    limited.className = "json-value is-muted";
    limited.textContent = "Preview limit reached";
    return limited;
  }
  if (value !== null && typeof value === "object") {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const entries = Object.entries(value);
    details.open = depth < 2;
    summary.textContent = `${label}${Array.isArray(value) ? ` [${entries.length}]` : ` {${entries.length}}`}`;
    details.append(summary);
    const children = document.createElement("div");
    children.className = "json-children";
    entries.forEach(([key, child]) => children.append(renderJsonValue(child, key, depth + 1, budget)));
    details.append(children);
    return details;
  }
  const row = document.createElement("div");
  const key = document.createElement("span");
  const scalar = document.createElement("code");
  row.className = "json-scalar";
  key.textContent = `${label}:`;
  scalar.textContent = typeof value === "string" ? `"${value}"` : String(value);
  row.append(key, scalar);
  return row;
}

function renderJson(content) {
  try {
    const tree = document.createElement("div");
    tree.className = "json-tree";
    tree.append(renderJsonValue(JSON.parse(content), "root"));
    fileViewerBody.append(tree);
  } catch (_error) {
    setViewerNotice("This JSON is not valid, so the source view is shown.");
    renderSource(content);
  }
}

function renderTable(content, delimiter) {
  const parsed = window.QuilooFileViewer.parseDelimited(content || "", delimiter);
  const limited = window.QuilooFileViewer.limitTable(parsed, 500, 100);
  const wrap = document.createElement("div");
  const table = document.createElement("table");
  const head = table.createTHead();
  const body = table.createTBody();
  wrap.className = "data-table-wrap";
  table.className = "data-table";
  limited.rows.forEach((row, rowIndex) => {
    const tableRow = document.createElement("tr");
    row.forEach((cell) => {
      const element = document.createElement(rowIndex === 0 ? "th" : "td");
      element.textContent = cell;
      tableRow.append(element);
    });
    (rowIndex === 0 ? head : body).append(tableRow);
  });
  if (limited.truncated) setViewerNotice("Table preview limited to 500 rows and 100 columns.");
  wrap.append(table);
  fileViewerBody.append(wrap);
}

function renderImage(preview) {
  const stage = document.createElement("div");
  const controls = document.createElement("div");
  const image = document.createElement("img");
  let zoom = 1;
  stage.className = "image-stage";
  controls.className = "image-controls";
  image.alt = preview.name;
  image.src = window.QuilooFileViewer.fileUrl(activeWorkspace.id, preview.path, false);
  const setZoom = (next) => {
    zoom = Math.min(4, Math.max(0.25, next));
    image.style.transform = `scale(${zoom})`;
    controls.querySelector("span").textContent = `${Math.round(zoom * 100)}%`;
  };
  [["−", () => setZoom(zoom - 0.25)], ["Reset", () => setZoom(1)], ["+", () => setZoom(zoom + 0.25)]].forEach(([label, action]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", action);
    controls.append(button);
  });
  const scale = document.createElement("span");
  scale.textContent = "100%";
  controls.append(scale);
  image.addEventListener("load", () => {
    fileViewerState.textContent = `${image.naturalWidth} × ${image.naturalHeight} px · Read only`;
  });
  stage.append(controls, image);
  fileViewerBody.append(stage);
}

function renderPdf(preview) {
  const frame = document.createElement("iframe");
  frame.className = "pdf-viewer";
  frame.title = preview.name;
  frame.src = window.QuilooFileViewer.fileUrl(activeWorkspace.id, preview.path, false);
  fileViewerBody.append(frame);
}

function renderBinary(preview) {
  const card = document.createElement("div");
  const title = document.createElement("strong");
  const copy = document.createElement("p");
  card.className = "binary-preview";
  title.textContent = "Preview unavailable";
  copy.textContent = "This binary format is not rendered in the workspace. Download it to open it with a compatible application.";
  card.append(title, copy);
  fileViewerBody.append(card);
}

function renderFileContent(mode = "preview") {
  if (!activeFile) return;
  clearNode(fileViewerBody);
  setViewerNotice(activeFile.truncated ? "This is a truncated preview of a large file." : "");
  fileViewerPreview.classList.toggle("is-active", mode === "preview");
  fileViewerSource.classList.toggle("is-active", mode === "source");
  if (mode === "source") {
    renderSource(activeFile.content);
  } else if (activeFile.kind === "markdown") {
    renderMarkdown(activeFile.content);
  } else if (activeFile.kind === "json") {
    renderJson(activeFile.content);
  } else if (activeFile.kind === "csv" || activeFile.kind === "tsv") {
    renderTable(activeFile.content, activeFile.kind === "csv" ? "," : "\t");
  } else if (activeFile.kind === "image") {
    renderImage(activeFile);
  } else if (activeFile.kind === "pdf") {
    renderPdf(activeFile);
  } else if (activeFile.kind === "binary") {
    renderBinary(activeFile);
  } else {
    renderSource(activeFile.content);
  }
}

function showFile(preview) {
  activeFile = preview;
  workspaceWelcome.classList.add("hidden");
  fileViewer.classList.remove("hidden");
  fileViewerKind.textContent = preview.kind.toUpperCase();
  fileViewerTitle.textContent = preview.name;
  fileViewerPath.textContent = preview.path;
  fileViewerType.textContent = preview.mime_type;
  fileViewerSize.textContent = window.QuilooFileViewer.formatBytes(preview.size);
  fileViewerState.textContent = "Read only";
  fileViewerDownload.href = window.QuilooFileViewer.fileUrl(activeWorkspace.id, preview.path, true);
  fileViewerDownload.download = preview.name;
  const modes = window.QuilooFileViewer.viewModes(preview.kind);
  fileViewerModes.hidden = modes.length < 2;
  fileViewerPreview.hidden = !modes.includes("preview");
  fileViewerSource.hidden = !modes.includes("source");
  renderFileContent(modes[0]);
}

async function openFile(entry) {
  const requestGeneration = ++fileRequestGeneration;
  const workspaceId = activeWorkspace.id;
  showError();
  fileViewerRefresh.disabled = true;
  try {
    const preview = await api(
      `/api/workspaces/${workspaceId}/files/preview?path=${encodeURIComponent(entry.path)}`,
    );
    if (requestGeneration !== fileRequestGeneration || activeWorkspace?.id !== workspaceId) return;
    showFile(preview);
    document.querySelectorAll(".tree-entry.is-selected").forEach((button) => button.classList.remove("is-selected"));
    document.querySelector(`.tree-entry[data-path="${CSS.escape(entry.path)}"]`)?.classList.add("is-selected");
  } catch (error) {
    if (requestGeneration === fileRequestGeneration) showError(error.message);
  } finally {
    if (requestGeneration === fileRequestGeneration) fileViewerRefresh.disabled = false;
  }
}

async function loadEntries(relative = ".", routeToken = navigationGuard.currentRoute()) {
  const workspaceId = activeWorkspace.id;
  const entries = await api(`/api/workspaces/${workspaceId}/entries?path=${encodeURIComponent(relative)}`);
  if (!navigationGuard.isCurrent(routeToken) || activeWorkspace?.id !== workspaceId) return;
  clearNode(repositoryTree);
  if (relative !== ".") {
    const rootButton = document.createElement("button");
    rootButton.type = "button";
    rootButton.className = "tree-entry tree-back";
    rootButton.textContent = "← Repository root";
    rootButton.addEventListener("click", () => void loadEntries(".").catch((error) => showError(error.message)));
    repositoryTree.append(rootButton);
  }
  if (!entries.length) repositoryTree.append(emptyCopy("This directory is empty."));
  entries.forEach((entry) => {
    const button = document.createElement("button");
    const marker = document.createElement("span");
    const name = document.createElement("span");
    button.type = "button";
    button.className = "tree-entry";
    button.dataset.path = entry.path;
    button.setAttribute("role", "treeitem");
    marker.className = `entry-marker is-${entry.kind}`;
    marker.textContent = entry.kind === "directory" ? "D" : entry.kind === "file" ? "F" : "L";
    name.textContent = entry.name;
    button.append(marker, name);
    if (entry.kind === "directory") {
      button.addEventListener("click", () => void loadEntries(entry.path).catch((error) => showError(error.message)));
    } else {
      button.addEventListener("click", () => void openFile(entry));
    }
    repositoryTree.append(button);
  });
}

function renderConversationList(conversations) {
  clearNode(conversationList);
  const heading = document.createElement("p");
  heading.className = "list-label";
  heading.textContent = "CONVERSATIONS";
  conversationList.append(heading);
  if (!conversations.length) conversationList.append(emptyCopy("No conversations yet."));
  conversations.forEach((conversation) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = conversation.id === activeConversation?.id ? "is-active" : "";
    button.textContent = conversation.title;
    button.addEventListener("click", () => navigate(`/workspaces/${activeWorkspace.id}/conversations/${conversation.id}`));
    conversationList.append(button);
  });
}

function appendMessage(message) {
  if (conversationMessages.querySelector(`[data-message-id="${message.id}"]`)) return;
  const article = document.createElement("article");
  const role = document.createElement("span");
  const content = document.createElement("p");
  article.className = `message is-${message.role}`;
  article.dataset.messageId = message.id;
  role.textContent = message.role.toUpperCase();
  content.textContent = message.content;
  article.append(role, content);
  conversationMessages.append(article);
  conversationMessages.scrollTop = conversationMessages.scrollHeight;
}

function renderRunIndicator() {
  document.querySelector("#agent-running")?.remove();
  const controls = window.QuilooIDEState.controlsForState(activeRun?.state);
  if (controls.send || !activeRun) return;
  const indicator = document.createElement("article");
  indicator.id = "agent-running";
  indicator.className = "message is-agent-status";
  const label = document.createElement("span");
  const copy = document.createElement("p");
  label.textContent = "AGENT";
  copy.textContent = activeRun.state === "waiting_for_approval"
    ? "Waiting for your approval"
    : activeRun.state === "paused"
      ? "Run paused"
      : "Working in the repository";
  indicator.append(label, copy);
  conversationMessages.append(indicator);
}

async function refreshMessages(conversationId = activeConversation?.id) {
  if (!conversationId) return;
  const messages = await api(`/api/conversations/${conversationId}/messages`);
  if (activeConversation?.id !== conversationId) return;
  clearNode(conversationMessages);
  if (!messages.length) conversationMessages.append(emptyCopy("Send the first task for this workspace."));
  messages.forEach(appendMessage);
  renderRunIndicator();
}

function setRun(run) {
  activeRun = run;
  const state = run?.state || "idle";
  const controls = window.QuilooIDEState.controlsForState(state);
  runState.textContent = state.replaceAll("_", " ").toUpperCase();
  pauseRun.hidden = !controls.pause;
  resumeRun.hidden = !controls.resume;
  stopRun.hidden = !controls.stop;
  runControls.hidden = !controls.pause && !controls.resume && !controls.stop;
  messageInput.disabled = !activeConversation || !controls.send || sendingPrompt;
  sendMessage.disabled = messageInput.disabled;
  sendMessage.textContent = sendingPrompt ? "Starting…" : "Send";
  renderRunIndicator();
}

function activityDescription(event) {
  const payload = event.payload || {};
  if (event.kind === "tool_call_started") return payload.summary || payload.tool_name || "Tool call";
  if (event.kind === "tool_call_completed") {
    const owner = payload.subagent ? `${payload.subagent} · ` : "";
    const output = String(payload.output || "Completed").replaceAll("\n", " ").slice(0, 260);
    return `${owner}${output}`;
  }
  if (event.kind === "approval_requested") return `${payload.risk || "HIGH"} · ${payload.summary || "Approval required"}`;
  if (payload.state) return String(payload.state).replaceAll("_", " ");
  if (payload.detail) return String(payload.detail).slice(0, 260);
  return event.kind.replaceAll("_", " ");
}

function appendActivity(event) {
  const row = document.createElement("div");
  const body = document.createElement("div");
  const kind = document.createElement("strong");
  const detail = document.createElement("span");
  const time = document.createElement("time");
  row.className = `activity-row is-${event.kind}`;
  kind.textContent = event.kind.replaceAll("_", " ");
  detail.textContent = activityDescription(event);
  time.textContent = new Date(event.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
  body.append(kind, detail);
  row.append(body, time);
  agentActivity.append(row);
  agentActivity.scrollTop = agentActivity.scrollHeight;
}

function approvalTarget(approval) {
  const payload = approval.payload || {};
  return payload.path || payload.command || payload.operation || "Review the requested action";
}

async function decideApproval(approval, decision) {
  showError();
  try {
    const suffix = decision === "approve" ? "approve" : "deny";
    const body = {expected_revision: approval.revision};
    if (decision === "deny") body.reason = "Denied by the user";
    const run = await api(`/api/approvals/${approval.id}/${suffix}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    setRun(run);
    await loadApprovals();
  } catch (error) {
    showError(error.message);
    await loadApprovals();
  }
}

function renderApprovals(approvals) {
  clearNode(pendingApprovals);
  approvalSection.classList.toggle("hidden", approvals.length === 0);
  approvals.forEach((approval) => {
    const card = document.createElement("article");
    const heading = document.createElement("div");
    const tool = document.createElement("strong");
    const risk = document.createElement("span");
    const summary = document.createElement("p");
    const target = document.createElement("code");
    const actions = document.createElement("div");
    const deny = document.createElement("button");
    const approve = document.createElement("button");
    card.className = "approval-card";
    tool.textContent = approval.tool_name;
    risk.textContent = approval.risk;
    heading.append(tool, risk);
    summary.textContent = approval.summary;
    target.textContent = approvalTarget(approval);
    deny.type = "button";
    deny.className = "is-deny";
    deny.textContent = "Deny";
    approve.type = "button";
    approve.className = "is-approve";
    approve.textContent = "Approve once";
    deny.addEventListener("click", () => void decideApproval(approval, "deny"));
    approve.addEventListener("click", () => void decideApproval(approval, "approve"));
    actions.append(deny, approve);
    card.append(heading, summary, target, actions);
    pendingApprovals.append(card);
  });
}

async function loadApprovals(conversationId = activeConversation?.id) {
  if (!conversationId) return;
  const approvals = await api(`/api/conversations/${conversationId}/approvals`);
  if (activeConversation?.id === conversationId) renderApprovals(approvals);
}

function updateRunFromEvent(event) {
  const terminalStates = {
    run_completed: "completed",
    run_failed: "failed",
    run_blocked: "blocked",
    run_cancelled: "cancelled",
    run_paused: "paused",
    run_recovered_paused: "paused",
  };
  if (event.kind === "run_state_changed" && event.payload?.state) {
    setRun({...activeRun, id: event.payload.run_id, state: event.payload.state});
  } else if (event.kind === "approval_requested") {
    setRun({...activeRun, id: event.payload?.run_id, state: "waiting_for_approval"});
  } else if (terminalStates[event.kind]) {
    setRun({...activeRun, id: event.payload?.run_id, state: terminalStates[event.kind]});
  }
}

function connectEvents(conversationId) {
  if (eventSource) eventSource.close();
  clearNode(agentActivity);
  eventLedger.reset();
  streamState.textContent = "CONNECTING";
  eventSource = new EventSource(`/api/conversations/${conversationId}/events`);
  const receive = (rawEvent) => {
    if (activeConversation?.id !== conversationId) return;
    streamState.textContent = "LIVE";
    const event = JSON.parse(rawEvent.data);
    if (!eventLedger.accept(event.id)) return;
    appendActivity(event);
    updateRunFromEvent(event);
    if (event.kind === "message_created") void refreshMessages(conversationId);
    if (event.kind === "approval_requested" || event.kind === "approval_resolved") {
      void loadApprovals(conversationId);
    }
  };
  [
    "conversation_created", "message_created", "run_created", "run_state_changed",
    "run_started", "tool_call_started", "tool_call_completed", "approval_requested",
    "approval_resolved", "run_completed", "run_failed", "run_blocked", "run_paused",
    "run_cancelled", "run_recovered_paused", "agent_error", "runtime_state_changed",
  ].forEach((kind) => eventSource.addEventListener(kind, receive));
  eventSource.onopen = () => { streamState.textContent = "LIVE"; };
  eventSource.onerror = () => { streamState.textContent = "RECONNECTING"; };
}

async function loadConversation(conversationId, routeToken) {
  const conversation = await api(`/api/conversations/${conversationId}`);
  if (!navigationGuard.isCurrent(routeToken)) return;
  activeConversation = conversation;
  conversationTitle.textContent = activeConversation.title;
  await refreshMessages(conversationId);
  if (!navigationGuard.isCurrent(routeToken) || activeConversation?.id !== conversationId) return;
  const run = await api(`/api/conversations/${conversationId}/runs/active`);
  if (!navigationGuard.isCurrent(routeToken) || activeConversation?.id !== conversationId) return;
  setRun(run);
  await loadApprovals(conversationId);
  if (!navigationGuard.isCurrent(routeToken) || activeConversation?.id !== conversationId) return;
  connectEvents(conversationId);
}

function clearConversation() {
  activeConversation = null;
  activeRun = null;
  submissions.reset();
  conversationTitle.textContent = "No conversation";
  setRun(null);
  clearNode(conversationMessages);
  conversationMessages.append(emptyCopy("Start or select a conversation."));
  clearNode(agentActivity);
  renderApprovals([]);
  streamState.textContent = "OFFLINE";
  if (eventSource) eventSource.close();
  eventSource = null;
}

async function restoreRoute() {
  const routeToken = navigationGuard.beginRoute();
  showError();
  const route = parseRoute();
  if (!route.workspaceId) return;
  try {
    const workspace = await api(`/api/workspaces/${route.workspaceId}`);
    if (!navigationGuard.isCurrent(routeToken)) return;
    renderWorkspace(workspace);
    await loadEntries(".", routeToken);
    if (!navigationGuard.isCurrent(routeToken)) return;
    if (route.conversationId) await loadConversation(route.conversationId, routeToken);
    else clearConversation();
    if (!navigationGuard.isCurrent(routeToken)) return;
    const conversations = await api(`/api/workspaces/${route.workspaceId}/conversations`);
    if (!navigationGuard.isCurrent(routeToken)) return;
    renderConversationList(conversations);
  } catch (error) {
    if (navigationGuard.isCurrent(routeToken)) showError(error.message);
  }
}

async function openWorkspace(path) {
  const workspace = await api("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({path}),
  });
  navigate(`/workspaces/${workspace.id}`);
}

workspaceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError();
  try {
    await openWorkspace(workspacePath.value);
  } catch (error) {
    showError(error.message);
  }
});

browseWorkspace.addEventListener("click", async () => {
  showError();
  browseWorkspace.disabled = true;
  browseWorkspace.textContent = "Choosing folder…";
  try {
    const selection = await api("/api/system/directories/select", {method: "POST"});
    if (!selection.path) return;
    workspacePath.value = selection.path;
    await openWorkspace(selection.path);
  } catch (error) {
    showError(error.message);
  } finally {
    browseWorkspace.disabled = false;
    browseWorkspace.textContent = "Open folder";
  }
});

createConversation.addEventListener("click", () => {
  conversationTitleInput.value = "Repository task";
  conversationDialog.showModal();
  conversationTitleInput.select();
});

cancelConversation.addEventListener("click", () => conversationDialog.close());

conversationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const conversation = await api(`/api/workspaces/${activeWorkspace.id}/conversations`, {
      method: "POST",
      body: JSON.stringify({title: conversationTitleInput.value}),
    });
    conversationDialog.close();
    navigate(`/workspaces/${activeWorkspace.id}/conversations/${conversation.id}`);
  } catch (error) {
    showError(error.message);
  }
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const draft = messageInput.value.trim();
  if (!draft || !activeConversation || sendingPrompt) return;
  if (!window.QuilooIDEState.controlsForState(activeRun?.state).send) return;
  const conversationId = activeConversation.id;
  const submission = submissions.begin(conversationId, draft);
  sendingPrompt = true;
  setRun(activeRun);
  showError();
  try {
    let messageId = submission.messageId;
    if (!messageId) {
      const message = await api(`/api/conversations/${conversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({content: draft}),
      });
      submissions.recordMessage(submission, message.id);
      messageId = message.id;
      if (conversationMessages.querySelector(".empty-copy")) clearNode(conversationMessages);
      appendMessage(message);
    }
    const run = await api(`/api/conversations/${conversationId}/runs`, {
      method: "POST",
      body: JSON.stringify({message_id: messageId}),
    });
    submissions.recordRun(submission, run.id);
    if (activeConversation?.id !== conversationId) return;
    messageInput.value = "";
    setRun(run);
  } catch (error) {
    if (activeConversation?.id === conversationId) showError(error.message);
  } finally {
    sendingPrompt = false;
    if (activeConversation?.id === conversationId) setRun(activeRun);
  }
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    messageForm.requestSubmit();
  }
});

async function controlRun(action) {
  if (!activeRun) return;
  showError();
  try {
    const run = await api(`/api/runs/${activeRun.id}/${action}`, {method: "POST"});
    setRun(run);
  } catch (error) {
    showError(error.message);
  }
}

pauseRun.addEventListener("click", () => void controlRun("pause"));
resumeRun.addEventListener("click", () => void controlRun("resume"));
stopRun.addEventListener("click", () => void controlRun("stop"));
fileViewerPreview.addEventListener("click", () => renderFileContent("preview"));
fileViewerSource.addEventListener("click", () => renderFileContent("source"));
fileViewerRefresh.addEventListener("click", () => {
  if (activeFile) void openFile({path: activeFile.path});
});
fileViewerClose.addEventListener("click", closeFileViewer);
window.addEventListener("popstate", () => void restoreRoute());
window.addEventListener("beforeunload", () => eventSource?.close());
void restoreRoute();
