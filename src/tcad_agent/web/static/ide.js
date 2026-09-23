"use strict";

const workspaceForm = document.querySelector("#workspace-form");
const workspacePath = document.querySelector("#workspace-path");
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
const messageForm = document.querySelector("#message-form");
const messageInput = document.querySelector("#message-input");
const sendMessage = document.querySelector("#send-message");
const errorNotice = document.querySelector("#ide-error");
const workspaceWelcome = document.querySelector("#workspace-welcome");

let activeWorkspace = null;
let activeConversation = null;
let eventSource = null;
const navigationGuard = window.QuilooIDEState.createNavigationGuard();

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || "Request failed");
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
  activeWorkspace = workspace;
  workspacePath.value = workspace.root;
  workspaceStatus.textContent = workspace.root;
  gitState.textContent = workspace.git.available
    ? `${workspace.git.branch || "DETACHED"}${workspace.git.dirty ? " · MODIFIED" : " · CLEAN"}`
    : "NO GIT";
  createConversation.disabled = false;
}

function selectEntry(entry) {
  const label = workspaceWelcome.querySelector(".section-label");
  const heading = workspaceWelcome.querySelector("h1");
  const copy = workspaceWelcome.querySelector(":scope > p");
  label.textContent = entry.kind.toUpperCase();
  heading.textContent = entry.name;
  copy.textContent = entry.kind === "file"
    ? "File viewing and editing connect in the next vertical slice. The repository path is already tracked safely."
    : "Select a child entry or return to the repository root.";
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
    button.setAttribute("role", "treeitem");
    marker.className = `entry-marker is-${entry.kind}`;
    marker.textContent = entry.kind === "directory" ? "D" : entry.kind === "file" ? "F" : "L";
    name.textContent = entry.name;
    button.append(marker, name);
    if (entry.kind === "directory") {
      button.addEventListener("click", () => void loadEntries(entry.path).catch((error) => showError(error.message)));
    } else {
      button.addEventListener("click", () => selectEntry(entry));
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

function appendActivity(event) {
  const row = document.createElement("div");
  const kind = document.createElement("strong");
  const time = document.createElement("time");
  row.className = "activity-row";
  kind.textContent = event.kind.replaceAll("_", " ");
  time.textContent = new Date(event.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
  row.append(kind, time);
  agentActivity.append(row);
  agentActivity.scrollTop = agentActivity.scrollHeight;
}

function connectEvents(conversationId) {
  if (eventSource) eventSource.close();
  clearNode(agentActivity);
  streamState.textContent = "CONNECTING";
  eventSource = new EventSource(`/api/conversations/${conversationId}/events`);
  const receive = (rawEvent) => {
    streamState.textContent = "LIVE";
    appendActivity(JSON.parse(rawEvent.data));
  };
  ["conversation_created", "message_created", "status_changed"].forEach((kind) => {
    eventSource.addEventListener(kind, receive);
  });
  eventSource.onopen = () => { streamState.textContent = "LIVE"; };
  eventSource.onerror = () => { streamState.textContent = "RECONNECTING"; };
}

async function loadConversation(conversationId, routeToken) {
  const conversation = await api(`/api/conversations/${conversationId}`);
  if (!navigationGuard.isCurrent(routeToken)) return;
  activeConversation = conversation;
  conversationTitle.textContent = activeConversation.title;
  messageInput.disabled = false;
  sendMessage.disabled = false;
  const messages = await api(`/api/conversations/${conversationId}/messages`);
  if (!navigationGuard.isCurrent(routeToken) || activeConversation?.id !== conversationId) return;
  clearNode(conversationMessages);
  if (!messages.length) conversationMessages.append(emptyCopy("Send the first task for this workspace."));
  messages.forEach(appendMessage);
  connectEvents(conversationId);
}

function clearConversation() {
  activeConversation = null;
  conversationTitle.textContent = "No conversation";
  messageInput.disabled = true;
  sendMessage.disabled = true;
  clearNode(conversationMessages);
  conversationMessages.append(emptyCopy("Start or select a conversation."));
  clearNode(agentActivity);
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

workspaceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError();
  try {
    const workspace = await api("/api/workspaces", {
      method: "POST",
      body: JSON.stringify({path: workspacePath.value}),
    });
    navigate(`/workspaces/${workspace.id}`);
  } catch (error) {
    showError(error.message);
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
  if (!messageInput.value.trim() || !activeConversation) return;
  const conversationId = activeConversation.id;
  const draft = messageInput.value;
  const pending = navigationGuard.captureMessage(
    navigationGuard.currentRoute(),
    conversationId,
    draft,
  );
  try {
    const message = await api(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({content: draft}),
    });
    if (!navigationGuard.canApplyMessage(pending, activeConversation?.id)) return;
    if (conversationMessages.querySelector(".empty-copy")) clearNode(conversationMessages);
    appendMessage(message);
    if (navigationGuard.canClearDraft(pending, activeConversation?.id, messageInput.value)) {
      messageInput.value = "";
    }
  } catch (error) {
    if (navigationGuard.canApplyMessage(pending, activeConversation?.id)) {
      showError(error.message);
    }
  }
});

window.addEventListener("popstate", () => void restoreRoute());
window.addEventListener("beforeunload", () => eventSource?.close());
void restoreRoute();
