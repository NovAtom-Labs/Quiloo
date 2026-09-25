"use strict";

const workspaceForm = document.querySelector("#workspace-form");
const workspacePath = document.querySelector("#workspace-path");
const browseWorkspace = document.querySelector("#browse-workspace");
const workspaceStatus = document.querySelector("#workspace-status");
const gitState = document.querySelector("#git-state");
const repositoryTree = document.querySelector("#repository-tree");
const conversationSelect = document.querySelector("#conversation-select");
const agentPanel = document.querySelector("#agent-panel");
const toggleAgentPanel = document.querySelector("#toggle-agent-panel");
const closeAgentPanel = document.querySelector("#close-agent-panel");
const createConversation = document.querySelector("#create-conversation");
const refreshConversation = document.querySelector("#refresh-conversation");
const conversationDialog = document.querySelector("#conversation-dialog");
const conversationForm = document.querySelector("#conversation-form");
const conversationTitleInput = document.querySelector("#conversation-title-input");
const cancelConversation = document.querySelector("#cancel-conversation");
const conversationMessages = document.querySelector("#conversation-messages");
const agentProgress = document.querySelector("#agent-progress");
const agentProgressText = document.querySelector("#agent-progress-text");
const agentTabs = Array.from(document.querySelectorAll("[data-agent-view]"));
const agentViews = Array.from(document.querySelectorAll("[data-agent-panel]"));
const agentActivity = document.querySelector("#agent-activity");
const agentRunSummary = document.querySelector("#agent-run-summary");
const agentReasoning = document.querySelector("#agent-reasoning");
const agentChanges = document.querySelector("#agent-changes");
const changesState = document.querySelector("#changes-state");
const changesCount = document.querySelector("#changes-count");
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
const fileViewerEdit = document.querySelector("#file-viewer-edit");
const fileViewerSave = document.querySelector("#file-viewer-save");
const fileViewerCancel = document.querySelector("#file-viewer-cancel");
const fileViewerDownload = document.querySelector("#file-viewer-download");
const fileViewerClose = document.querySelector("#file-viewer-close");
const fileEditor = document.querySelector("#file-editor");

let activeWorkspace = null;
let activeConversation = null;
let activeRun = null;
let eventSource = null;
let sendingPrompt = false;
let activeFile = null;
let editingFile = null;
let fileRequestGeneration = 0;
let selectedRunId = null;
let activeChangeSet = null;
const navigationGuard = window.QuilooIDEState.createNavigationGuard();
const repositoryRequests = window.QuilooIDEState.createRepositoryRequestCoordinator();
const submissions = window.QuilooIDEState.createSubmissionTracker();
const runPresentation = window.QuilooIDEEvents.createRunPresentation();
const runChanges = window.QuilooIDEState.createRunResourceCache();

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
  editingFile = null;
  setFileEditing(false);
  fileViewer.classList.add("hidden");
  workspaceWelcome.classList.remove("hidden");
  document.querySelectorAll(".tree-entry.is-selected").forEach((entry) => entry.classList.remove("is-selected"));
}

function setViewerNotice(message = "") {
  fileViewerNotice.textContent = message;
  fileViewerNotice.classList.toggle("hidden", !message);
}

function fileCanBeEdited(preview) {
  const editableKinds = new Set(["text", "markdown", "json", "csv", "tsv"]);
  const protectedPath = /(^|\/)(\.env(?:\.[^/]+)?|\.git|\.git-credentials|\.ssh|\.aws|\.gnupg|\.netrc|\.npmrc|\.pypirc|\.dockerconfigjson|auth\.json|credentials|id_rsa|id_ed25519|secrets)(\/|$)/i;
  const protectedSuffix = /\.(key|pem)$/i;
  return editableKinds.has(preview.kind)
    && !preview.truncated
    && !protectedPath.test(preview.path)
    && !protectedSuffix.test(preview.path);
}

function setFileEditing(isEditing) {
  fileViewerBody.classList.toggle("hidden", isEditing);
  fileEditor.classList.toggle("hidden", !isEditing);
  fileViewerEdit.hidden = isEditing || !activeFile || !fileCanBeEdited(activeFile);
  fileViewerSave.hidden = !isEditing;
  fileViewerCancel.hidden = !isEditing;
  fileViewerRefresh.disabled = isEditing;
  fileViewerModes.hidden = isEditing || !activeFile
    || window.QuilooFileViewer.viewModes(activeFile.kind).length < 2;
  if (activeFile) fileViewerState.textContent = isEditing ? "Editing" : "Read only";
}

async function beginFileEdit() {
  if (!activeWorkspace || !activeFile || !fileCanBeEdited(activeFile)) return;
  const workspaceId = activeWorkspace.id;
  const path = activeFile.path;
  showError();
  fileViewerEdit.disabled = true;
  try {
    const editable = await api(
      `/api/workspaces/${workspaceId}/files/content?path=${encodeURIComponent(path)}`,
    );
    if (activeWorkspace?.id !== workspaceId || activeFile?.path !== path) return;
    editingFile = editable;
    fileEditor.value = editable.content;
    setFileEditing(true);
    fileEditor.focus();
  } catch (error) {
    showError(error.message);
  } finally {
    fileViewerEdit.disabled = false;
  }
}

function cancelFileEdit() {
  editingFile = null;
  fileEditor.value = "";
  setFileEditing(false);
}

async function saveFileEdit() {
  if (!activeWorkspace || !editingFile) return;
  const workspaceId = activeWorkspace.id;
  const path = editingFile.path;
  showError();
  fileViewerSave.disabled = true;
  try {
    await api(`/api/workspaces/${workspaceId}/files/content`, {
      method: "PUT",
      body: JSON.stringify({
        path,
        content: fileEditor.value,
        expected_sha256: editingFile.sha256,
      }),
    });
    if (activeWorkspace?.id !== workspaceId || activeFile?.path !== path) return;
    cancelFileEdit();
    await openFile({path});
  } catch (error) {
    showError(error.message);
  } finally {
    fileViewerSave.disabled = false;
  }
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
  window.QuilooMarkdown.render(article, content || "");
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
  editingFile = null;
  workspaceWelcome.classList.add("hidden");
  fileViewer.classList.remove("hidden");
  fileViewerTitle.textContent = preview.name;
  fileViewerPath.textContent = preview.path;
  fileViewerType.textContent = preview.mime_type;
  fileViewerSize.textContent = window.QuilooFileViewer.formatBytes(preview.size);
  fileViewerState.textContent = "Read only";
  fileViewerRefresh.hidden = false;
  fileViewerEdit.hidden = false;
  fileViewerDownload.hidden = false;
  fileViewerDownload.href = window.QuilooFileViewer.fileUrl(activeWorkspace.id, preview.path, true);
  fileViewerDownload.download = preview.name;
  const modes = window.QuilooFileViewer.viewModes(preview.kind);
  fileViewerModes.hidden = modes.length < 2;
  fileViewerPreview.hidden = !modes.includes("preview");
  fileViewerSource.hidden = !modes.includes("source");
  setFileEditing(false);
  renderFileContent(modes[0]);
}

function showDiff(change) {
  activeFile = null;
  editingFile = null;
  workspaceWelcome.classList.add("hidden");
  fileViewer.classList.remove("hidden");
  fileViewerTitle.textContent = change.label.split("/").at(-1) || change.label;
  fileViewerPath.textContent = change.detail || change.label;
  fileViewerType.textContent = "Unified diff";
  fileViewerSize.textContent = change.delta;
  fileViewerState.textContent = change.diffTruncated ? "Diff truncated" : "Run change";
  fileViewerModes.hidden = true;
  fileViewerRefresh.hidden = true;
  fileViewerEdit.hidden = true;
  fileViewerDownload.hidden = true;
  fileViewerSave.hidden = true;
  fileViewerCancel.hidden = true;
  fileEditor.classList.add("hidden");
  fileViewerBody.classList.remove("hidden");
  clearNode(fileViewerBody);
  setViewerNotice(change.uncertain
    ? "This binary or large-file change cannot be compared line by line."
    : change.diffTruncated ? "This diff was limited to keep the workspace responsive." : "");
  if (change.diff) renderSource(change.diff);
  else fileViewerBody.append(emptyCopy("A line-by-line diff is not available for this change."));
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

async function loadEntries(
  relative = ".",
  routeToken = navigationGuard.currentRoute(),
  {background = false} = {},
) {
  const workspaceId = activeWorkspace.id;
  const request = background
    ? repositoryRequests.beginRefresh()
    : repositoryRequests.beginNavigation(relative);
  if (!request) return;
  try {
    const entries = await api(
      `/api/workspaces/${workspaceId}/entries?path=${encodeURIComponent(request.path)}`,
    );
    if (
      !repositoryRequests.isCurrent(request)
      || !navigationGuard.isCurrent(routeToken)
      || activeWorkspace?.id !== workspaceId
    ) return;
    clearNode(repositoryTree);
    if (request.path !== ".") {
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
  } catch (error) {
    const stale = !repositoryRequests.isCurrent(request)
      || !navigationGuard.isCurrent(routeToken)
      || activeWorkspace?.id !== workspaceId;
    if (!stale) throw error;
  } finally {
    const refreshDeferred = repositoryRequests.finish(request);
    if (refreshDeferred) {
      queueMicrotask(() => {
        if (!activeWorkspace) return;
        void refreshCurrentRepository().catch((error) => showError(error.message));
      });
    }
  }
}

async function refreshCurrentRepository() {
  if (!activeWorkspace) return;
  const relative = repositoryRequests.currentPath();
  try {
    await loadEntries(relative, navigationGuard.currentRoute(), {background: true});
  } catch (error) {
    if (
      relative === "."
      || repositoryRequests.currentPath() !== relative
      || repositoryRequests.hasNavigationPending()
    ) throw error;
    await loadEntries(".");
  }
}

function renderConversationSelect(conversations) {
  clearNode(conversationSelect);
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = conversations.length ? "Select a conversation" : "No conversations";
  placeholder.disabled = conversations.length > 0;
  conversationSelect.append(placeholder);
  if (!conversations.length) {
    conversationSelect.disabled = true;
    return;
  }
  conversations.forEach((conversation) => {
    const option = document.createElement("option");
    option.value = conversation.id;
    option.textContent = conversation.title;
    conversationSelect.append(option);
  });
  conversationSelect.disabled = false;
  conversationSelect.value = activeConversation?.id || "";
}

function appendMessage(message) {
  if (conversationMessages.querySelector(`[data-message-id="${message.id}"]`)) return null;
  const article = document.createElement("article");
  const header = document.createElement("header");
  const role = document.createElement("span");
  const time = document.createElement("time");
  const content = document.createElement("div");
  article.className = `message is-${message.role}`;
  article.dataset.messageId = message.id;
  role.textContent = message.role.toUpperCase();
  if (message.created_at) {
    time.dateTime = message.created_at;
    time.textContent = new Date(message.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
  }
  content.className = "message-body";
  window.QuilooMarkdown.render(content, message.content);
  header.append(role, time);
  article.append(header, content);
  conversationMessages.append(article);
  return article;
}

function scrollConversationToBottom() {
  requestAnimationFrame(() => {
    conversationMessages.scrollTop = conversationMessages.scrollHeight;
  });
}

function isConversationNearBottom() {
  const remaining = conversationMessages.scrollHeight
    - conversationMessages.clientHeight
    - conversationMessages.scrollTop;
  return remaining <= 48;
}

function renderMessages(messages, {forceScroll = false} = {}) {
  const previousLastId = conversationMessages.querySelector(".message:last-of-type")?.dataset.messageId;
  const previousScrollTop = conversationMessages.scrollTop;
  const wasNearBottom = isConversationNearBottom();
  const nextLastId = messages.at(-1)?.id;
  const shouldFollow = window.QuilooIDEState.shouldAutoFollowChat(
    previousLastId,
    nextLastId,
    wasNearBottom,
    forceScroll,
  );
  clearNode(conversationMessages);
  if (!messages.length) {
    conversationMessages.append(emptyCopy("Send the first task for this workspace."));
    return;
  }
  messages.forEach((message) => {
    appendMessage(message);
  });
  if (shouldFollow) scrollConversationToBottom();
  else requestAnimationFrame(() => { conversationMessages.scrollTop = previousScrollTop; });
}

function renderRunIndicator() {
  const controls = window.QuilooIDEState.controlsForState(activeRun?.state);
  agentProgress.hidden = controls.send || !activeRun;
  if (agentProgress.hidden) return;
  const presentation = runPresentation.snapshot(activeRun?.id || selectedRunId);
  const current = window.QuilooAgentView.operationalUpdates(presentation)
    .filter((update) => ["running", "waiting"].includes(update.status))
    .at(-1);
  agentProgressText.textContent = activeRun.state === "waiting_for_approval"
    ? "Waiting for your approval"
    : activeRun.state === "paused"
      ? "Run paused"
      : current
        ? `${current.phase}: ${current.label}`
        : "Working";
}

async function refreshMessages(conversationId = activeConversation?.id, options = {}) {
  if (!conversationId) return;
  const messages = await api(`/api/conversations/${conversationId}/messages`);
  if (activeConversation?.id !== conversationId) return;
  renderMessages(messages, options);
  renderRunIndicator();
}

async function synchronizeConversation(conversationId) {
  if (!conversationId || activeConversation?.id !== conversationId) return;
  const [messages, run, approvals] = await Promise.all([
    api(`/api/conversations/${conversationId}/messages`),
    api(`/api/conversations/${conversationId}/runs/active`),
    api(`/api/conversations/${conversationId}/approvals`),
  ]);
  if (activeConversation?.id !== conversationId) return;
  renderMessages(messages);
  setRun(run);
  renderApprovals(approvals);
}

const refreshCoordinator = window.QuilooIDEState.createRefreshCoordinator(
  synchronizeConversation,
);

async function requestConversationRefresh(conversationId = activeConversation?.id) {
  if (!conversationId) return;
  refreshConversation.disabled = true;
  refreshConversation.textContent = "Refreshing…";
  try {
    await refreshCoordinator.request(conversationId);
  } catch (error) {
    if (activeConversation?.id === conversationId) showError(error.message);
  } finally {
    if (activeConversation?.id === conversationId) {
      refreshConversation.disabled = false;
      refreshConversation.textContent = "Refresh";
    }
  }
}

function setRun(run) {
  activeRun = run;
  if (run?.id) selectRun(run.id, {refresh: true});
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
  refreshConversation.disabled = !activeConversation;
  renderRunIndicator();
}

function activateAgentView(name, {focus = false} = {}) {
  agentTabs.forEach((button) => {
    const active = button.dataset.agentView === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
    if (active && focus) button.focus();
  });
  agentViews.forEach((view) => {
    const active = view.dataset.agentPanel === name;
    view.hidden = !active;
    view.classList.toggle("is-active", active);
  });
}

function renderRunSummary(snapshot) {
  const summary = window.QuilooAgentView.outcomeSummary(snapshot, activeChangeSet);
  clearNode(agentRunSummary);
  agentRunSummary.hidden = !summary.visible;
  if (!summary.visible) return;
  const title = document.createElement("strong");
  const detail = document.createElement("span");
  agentRunSummary.className = `agent-run-summary is-${summary.tone}`;
  title.textContent = summary.title;
  detail.textContent = summary.failedStep
    ? `${summary.failedStep}${summary.failureOutput ? `: ${String(summary.failureOutput).slice(0, 180)}` : ""}`
    : `${summary.completedSteps} actions completed · ${summary.changedFiles} files changed`;
  agentRunSummary.append(title, detail);
  const evidence = [
    ["Phases", summary.phases?.join(" → ")],
    ["Changed files", summary.changedPaths?.join("\n")],
    ["Commands", summary.commands?.join("\n")],
    ["Validation", summary.validationEvidence?.map((item) => `${item.label}${item.output ? `: ${item.output}` : ""}`).join("\n")],
    ["Executed checks, not final evidence", summary.unlinkedValidationChecks?.map((item) => `${item.label}${item.output ? `: ${item.output}` : ""}`).join("\n")],
    ["Artifacts", summary.artifacts?.join("\n")],
    ["Provenance", summary.provenance?.join("\n")],
    ["Warnings", summary.warnings?.join("\n")],
    ["Next", summary.nextActions?.join("\n")],
  ].filter(([, value]) => value);
  if (evidence.length) {
    const details = document.createElement("details");
    const label = document.createElement("summary");
    const list = document.createElement("dl");
    label.textContent = "Run evidence";
    evidence.forEach(([term, value]) => {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = value;
      row.append(dt, dd);
      list.append(row);
    });
    details.append(label, list);
    agentRunSummary.append(details);
  }
}

function renderReasoning(snapshot) {
  clearNode(agentReasoning);
  const updates = window.QuilooAgentView.operationalUpdates(snapshot);
  agentReasoning.hidden = !updates.length;
  if (!updates.length) return;
  const heading = document.createElement("div");
  const title = document.createElement("strong");
  const note = document.createElement("span");
  const list = document.createElement("ol");
  heading.className = "progress-log-heading";
  title.textContent = "Agent progress";
  note.textContent = "Operational summary";
  list.className = "progress-log";
  updates.forEach((update) => {
    const item = document.createElement("li");
    const phase = document.createElement("span");
    const label = document.createElement("strong");
    item.className = `progress-log-entry is-${update.status}`;
    phase.textContent = update.phase;
    label.textContent = update.label;
    item.append(phase, label);
    if (update.detail) {
      const detail = document.createElement("small");
      detail.textContent = update.detail;
      item.append(detail);
    }
    list.append(item);
  });
  heading.append(title, note);
  agentReasoning.append(heading, list);
}

function renderActivity(snapshot) {
  clearNode(agentActivity);
  const rows = window.QuilooAgentView.activityRows(snapshot);
  if (!rows.length && !snapshot.approvalHistory?.length && !snapshot.technicalEvents?.length) {
    agentActivity.append(emptyCopy("Tool activity will appear here when a run starts."));
  }
  rows.forEach((row) => {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const status = document.createElement("span");
    const label = document.createElement("strong");
    const metadata = document.createElement("span");
    const technical = document.createElement("div");
    details.className = `execution-step is-${row.status}`;
    details.setAttribute("data-action-id", row.id);
    status.className = "execution-status";
    status.textContent = row.status === "running" ? "●" : row.status === "failed" ? "×" : "✓";
    label.textContent = row.label;
    metadata.textContent = [row.phase, row.owner, row.duration].filter(Boolean).join(" · ");
    summary.append(status, label, metadata);
    technical.className = "execution-technical";
    if (row.command) {
      const command = document.createElement("code");
      command.textContent = row.command;
      technical.append(command);
    }
    if (row.output) {
      const output = document.createElement("pre");
      output.textContent = String(row.output);
      technical.append(output);
    }
    const affectedPaths = window.QuilooAgentView.affectedFilePaths(row, activeWorkspace?.root);
    affectedPaths.forEach((affectedPath) => {
      const open = document.createElement("button");
      open.type = "button";
      open.textContent = `Affected file: ${affectedPath}`;
      open.addEventListener("click", () => {
        const changed = window.QuilooChanges.toRows(activeChangeSet)
          .find((candidate) => candidate.label === affectedPath);
        if (changed?.diff || (changed && !changed.canOpenFile)) showDiff(changed);
        else void openFile({path: affectedPath});
      });
      technical.append(open);
    });
    if (!technical.childNodes.length) technical.append(emptyCopy("No additional technical output."));
    details.append(summary, technical);
    agentActivity.append(details);
  });
  (snapshot.approvalHistory || []).forEach((approval) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    const state = document.createElement("span");
    row.className = "approval-marker";
    label.textContent = approval.summary;
    state.textContent = approval.decision ? `Decision: ${approval.decision}` : "Waiting for approval";
    row.append(label, state);
    agentActivity.append(row);
  });
  if (snapshot.technicalEvents?.length) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const events = document.createElement("pre");
    details.className = "technical-events";
    summary.textContent = `Technical events (${snapshot.technicalEvents.length})`;
    events.textContent = snapshot.technicalEvents
      .map((event) => `${event.kind}: ${JSON.stringify(event.payload || {})}`)
      .join("\n");
    details.append(summary, events);
    agentActivity.append(details);
  }
}

function renderAgentPresentation() {
  const snapshot = runPresentation.snapshot(selectedRunId);
  renderRunSummary(snapshot);
  renderReasoning(snapshot);
  renderActivity(snapshot);
  renderRunIndicator();
}

function renderChanges(changeSet) {
  const runId = changeSet?.run_id || selectedRunId;
  runChanges.put(runId, changeSet);
  activeChangeSet = runChanges.current();
  const rows = window.QuilooChanges.toRows(changeSet);
  const incomplete = window.QuilooChanges.isIncomplete(changeSet);
  clearNode(agentChanges);
  changesCount.textContent = String(rows.length);
  changesState.textContent = incomplete ? "PARTIAL SCAN" : rows.length ? `${rows.length} CHANGED` : "NO CHANGES";
  if (incomplete) {
    const warning = document.createElement("p");
    warning.className = "change-scan-warning";
    warning.textContent = changeSet.manifest_warning || "The workspace scan reached its safety limit. Modified files shown here are exact, but create, delete, and rename attribution may be incomplete.";
    agentChanges.append(warning);
  }
  if (!rows.length) {
    agentChanges.append(emptyCopy("No workspace changes are attributed to this run."));
    renderRunSummary(runPresentation.snapshot(selectedRunId));
    return;
  }
  rows.forEach((row) => {
    const item = document.createElement("article");
    const button = document.createElement("button");
    const top = document.createElement("span");
    const operation = document.createElement("b");
    const path = document.createElement("strong");
    const delta = document.createElement("code");
    const detail = document.createElement("small");
    button.type = "button";
    item.className = "change-item";
    button.className = `change-row is-${row.operation}`;
    operation.textContent = row.operationLabel;
    path.textContent = row.label;
    delta.textContent = row.delta;
    top.append(operation, path, delta);
    const attribution = row.attributedActionIds.length
      ? `Action ${row.attributedActionIds.join(", ")}${row.attributedSubagents.length ? ` · ${row.attributedSubagents.join(", ")}` : ""}`
      : null;
    detail.textContent = row.detail || attribution || (row.uncertain ? "Exact line changes are unavailable" : "Attribution unavailable · Open run diff");
    button.append(top, detail);
    button.addEventListener("click", () => {
      if (row.diff || !row.canOpenFile) showDiff(row);
      else void openFile({path: row.label});
    });
    item.append(button);
    if (row.validationActionIds.length) {
      const validations = document.createElement("div");
      validations.className = "change-validation-links";
      row.validationActionIds.forEach((actionId, index) => {
        const validation = document.createElement("button");
        validation.type = "button";
        validation.className = "change-validation-link";
        validation.textContent = row.validationActionIds.length === 1
          ? "View validation evidence"
          : `Validation check ${index + 1}`;
        validation.addEventListener("click", () => {
          activateAgentView("activity");
          const target = Array.from(agentActivity.querySelectorAll("[data-action-id]"))
            .find((candidate) => candidate.dataset.actionId === actionId);
          if (!target) return;
          target.open = true;
          target.scrollIntoView({block: "center"});
          target.querySelector("summary")?.focus();
        });
        validations.append(validation);
      });
      item.append(validations);
    }
    agentChanges.append(item);
  });
  renderRunSummary(runPresentation.snapshot(selectedRunId));
}

async function refreshChanges(runId = selectedRunId) {
  if (!runId) {
    activeChangeSet = null;
    runChanges.select(null);
    changesCount.textContent = "0";
    changesState.textContent = "NO RUN";
    clearNode(agentChanges);
    agentChanges.append(emptyCopy("Run changes will appear after the agent starts working."));
    return;
  }
  changesState.textContent = "CHECKING";
  try {
    const changeSet = await api(`/api/runs/${runId}/changes`);
    if (selectedRunId !== runId) return;
    renderChanges(changeSet);
  } catch (_error) {
    if (selectedRunId !== runId) return;
    activeChangeSet = null;
    changesCount.textContent = "0";
    changesState.textContent = "UNAVAILABLE";
    clearNode(agentChanges);
    agentChanges.append(emptyCopy("Changes are unavailable for this historical run."));
  }
}

function selectRun(runId, {refresh = false} = {}) {
  const normalized = runId ? String(runId) : null;
  if (selectedRunId === normalized) return false;
  selectedRunId = normalized;
  activeChangeSet = runChanges.select(normalized);
  if (activeChangeSet) {
    renderChanges(activeChangeSet);
  } else {
    changesCount.textContent = "0";
    changesState.textContent = normalized ? "CHECKING" : "NO RUN";
    clearNode(agentChanges);
    agentChanges.append(emptyCopy(
      normalized
        ? "Changes for this run are being checked."
        : "Run changes will appear after the agent starts working.",
    ));
    renderRunSummary(runPresentation.snapshot(normalized));
  }
  if (refresh && normalized) void refreshChanges(normalized);
  return true;
}

function approvalTarget(approval) {
  const payload = approval.payload || {};
  return payload.path || payload.command || payload.operation || "Review the requested action";
}

async function decideApproval(approval, decision) {
  showError();
  try {
    let endpoint = `/api/approvals/${approval.id}/deny`;
    if (decision === "approve") endpoint = `/api/approvals/${approval.id}/approve`;
    if (decision === "approve-category") endpoint = `/api/approvals/${approval.id}/approve-category`;
    const body = {expected_revision: approval.revision};
    if (decision === "deny") body.reason = "Denied by the user";
    const run = await api(endpoint, {
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

function permissionCategoryLabel(value) {
  return String(value || "unrecognized action").replaceAll("_", " ");
}

function canApproveCategory(value) {
  return !["complex_shell", "unrecognized_action"].includes(value);
}

function renderApprovals(approvals) {
  clearNode(pendingApprovals);
  approvalSection.classList.toggle("hidden", approvals.length === 0);
  approvals.forEach((approval) => {
    const view = window.QuilooAgentView.permissionView(approval);
    const card = document.createElement("article");
    const heading = document.createElement("div");
    const tool = document.createElement("strong");
    const risk = document.createElement("span");
    const summary = document.createElement("p");
    const technical = document.createElement("details");
    const technicalLabel = document.createElement("summary");
    const technicalBody = document.createElement("div");
    const toolDetail = document.createElement("span");
    const categoryDetail = document.createElement("span");
    const riskDetail = document.createElement("span");
    const reversibility = document.createElement("span");
    const argumentsDetail = document.createElement("code");
    const actions = document.createElement("div");
    const deny = document.createElement("button");
    const approve = document.createElement("button");
    const approveCategory = document.createElement("button");
    card.className = "approval-card";
    tool.textContent = "Permission required";
    risk.textContent = "Needs approval";
    heading.append(tool, risk);
    summary.textContent = view.explanation;
    technical.className = "approval-technical";
    technicalLabel.textContent = "Technical details";
    toolDetail.textContent = `Tool: ${view.toolName}`;
    categoryDetail.textContent = `Permission type: ${permissionCategoryLabel(view.permissionCategory)}`;
    riskDetail.textContent = `Risk level: ${view.risk}`;
    reversibility.textContent = `Reversibility: ${view.reversibility}`;
    argumentsDetail.textContent = view.technicalArguments;
    technicalBody.append(toolDetail, categoryDetail, riskDetail, reversibility, argumentsDetail);
    technical.append(technicalLabel, technicalBody);
    deny.type = "button";
    deny.className = "is-deny";
    deny.textContent = "Deny";
    approve.type = "button";
    approve.className = "is-approve";
    approve.textContent = "Approve";
    approveCategory.type = "button";
    approveCategory.className = "is-approve-category";
    approveCategory.textContent = "Approve all like this";
    approveCategory.title = "Allow this permission type for the rest of this run only";
    deny.addEventListener("click", () => void decideApproval(approval, "deny"));
    approve.addEventListener("click", () => void decideApproval(approval, "approve"));
    if (view.canApproveCategory) {
      approveCategory.addEventListener("click", () => void decideApproval(approval, "approve-category"));
      actions.append(deny, approve, approveCategory);
    } else {
      actions.append(deny, approve);
    }
    card.append(heading, summary, technical, actions);
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
  runPresentation.reset();
  runChanges.clear();
  selectedRunId = null;
  activeChangeSet = null;
  selectRun(activeRun?.id || null);
  renderAgentPresentation();
  void refreshChanges(selectedRunId);
  streamState.textContent = "CONNECTING";
  eventSource = new EventSource(`/api/conversations/${conversationId}/events`);
  const receive = (rawEvent) => {
    if (activeConversation?.id !== conversationId) return;
    streamState.textContent = "LIVE";
    const event = JSON.parse(rawEvent.data);
    if (!runPresentation.accept(event)) return;
    const eventRunId = event.payload?.run_id ? String(event.payload.run_id) : null;
    if (eventRunId && ["run_created", "run_started"].includes(event.kind)) {
      selectRun(eventRunId, {refresh: true});
    }
    renderAgentPresentation();
    updateRunFromEvent(event);
    if (event.kind === "message_created") void refreshMessages(conversationId);
    if (event.kind === "approval_requested" || event.kind === "approval_resolved") {
      void loadApprovals(conversationId);
    }
    if (event.kind === "tool_call_completed") void refreshChanges(selectedRunId);
    if (window.QuilooIDEState.shouldRefreshRepository(event.kind)) {
      void refreshCurrentRepository().catch((error) => showError(error.message));
    }
    if (["run_completed", "run_failed", "run_blocked", "run_cancelled"].includes(event.kind)) {
      void refreshChanges(selectedRunId);
      void refreshCoordinator.request(conversationId).catch((error) => showError(error.message));
    }
  };
  [
    "conversation_created", "message_created", "run_created", "run_state_changed",
    "run_started", "tool_call_started", "tool_call_completed", "approval_requested",
    "approval_resolved", "permission_grant_created", "permission_grant_used",
    "run_completed", "run_failed", "run_blocked", "run_paused",
    "run_cancelled", "run_recovered_paused", "agent_error", "runtime_state_changed",
    "thinking_started", "thinking_delta", "thinking_aborted", "change_baseline_warning",
    "agent_progress_started", "agent_progress_interrupted",
  ].forEach((kind) => eventSource.addEventListener(kind, receive));
  eventSource.onopen = () => {
    streamState.textContent = "LIVE";
    void refreshCoordinator.request(conversationId).catch((error) => showError(error.message));
  };
  eventSource.onerror = () => { streamState.textContent = "RECONNECTING"; };
}

async function loadConversation(conversationId, routeToken) {
  const conversation = await api(`/api/conversations/${conversationId}`);
  if (!navigationGuard.isCurrent(routeToken)) return;
  activeConversation = conversation;
  setAgentPanelOpen(true);
  await refreshMessages(conversationId, {forceScroll: true});
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
  selectedRunId = null;
  activeChangeSet = null;
  submissions.reset();
  runPresentation.reset();
  conversationSelect.value = "";
  setRun(null);
  clearNode(conversationMessages);
  conversationMessages.append(emptyCopy("Start or select a conversation."));
  clearNode(agentActivity);
  clearNode(agentReasoning);
  clearNode(agentRunSummary);
  void refreshChanges(null);
  renderApprovals([]);
  streamState.textContent = "OFFLINE";
  refreshConversation.disabled = true;
  if (eventSource) eventSource.close();
  eventSource = null;
}

function setAgentPanelOpen(open) {
  agentPanel.classList.toggle("is-open", open);
  toggleAgentPanel.setAttribute("aria-expanded", String(open));
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
    renderConversationSelect(conversations);
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
      scrollConversationToBottom();
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
refreshConversation.addEventListener("click", () => void requestConversationRefresh());
conversationSelect.addEventListener("change", () => {
  if (!conversationSelect.value || !activeWorkspace) return;
  navigate(`/workspaces/${activeWorkspace.id}/conversations/${conversationSelect.value}`);
});
agentTabs.forEach((button) => {
  button.addEventListener("click", () => activateAgentView(button.dataset.agentView));
  button.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const index = agentTabs.indexOf(button);
    let next = index;
    if (event.key === "ArrowLeft") next = (index - 1 + agentTabs.length) % agentTabs.length;
    if (event.key === "ArrowRight") next = (index + 1) % agentTabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = agentTabs.length - 1;
    activateAgentView(agentTabs[next].dataset.agentView, {focus: true});
    event.preventDefault();
  });
});
toggleAgentPanel.addEventListener("click", () => {
  setAgentPanelOpen(!agentPanel.classList.contains("is-open"));
});
closeAgentPanel.addEventListener("click", () => setAgentPanelOpen(false));
fileViewerPreview.addEventListener("click", () => renderFileContent("preview"));
fileViewerSource.addEventListener("click", () => renderFileContent("source"));
fileViewerEdit.addEventListener("click", () => void beginFileEdit());
fileViewerSave.addEventListener("click", () => void saveFileEdit());
fileViewerCancel.addEventListener("click", cancelFileEdit);
fileViewerRefresh.addEventListener("click", () => {
  if (activeFile) void openFile({path: activeFile.path});
});
fileViewerClose.addEventListener("click", closeFileViewer);
window.addEventListener("popstate", () => void restoreRoute());
window.addEventListener("beforeunload", () => eventSource?.close());
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") void requestConversationRefresh();
});
setInterval(() => {
  if (!activeConversation) return;
  const shouldRefresh = window.QuilooIDEState.isActiveState(activeRun?.state)
    || streamState.textContent === "RECONNECTING";
  if (shouldRefresh) void refreshCoordinator.request(activeConversation.id).catch((error) => showError(error.message));
}, 5000);
void restoreRoute();
