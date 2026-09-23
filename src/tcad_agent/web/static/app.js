const promptInput = document.querySelector("#prompt");
const backendInput = document.querySelector("#backend");
const backendDescription = document.querySelector("#backend-description");
const submitButton = document.querySelector("#submit");
const answerButton = document.querySelector("#answer");
const approveButton = document.querySelector("#approve");
const runButton = document.querySelector("#run");
const statusPanel = document.querySelector("#status-panel");
const resultsPanel = document.querySelector("#results-panel");
const stateLabel = document.querySelector("#state");
const warning = document.querySelector("#warning");
const questionsSection = document.querySelector("#questions-section");
const questions = document.querySelector("#questions");
const planSection = document.querySelector("#plan-section");
const planSummary = document.querySelector("#plan-summary");
const planDigest = document.querySelector("#plan-digest");
const plan = document.querySelector("#plan");
const validationStatus = document.querySelector("#validation-status");
const validationList = document.querySelector("#validation-list");
const validationDetails = document.querySelector("#validation-details");
const validation = document.querySelector("#validation");
const artifacts = document.querySelector("#artifacts");
const artifactLinks = document.querySelector("#artifact-links");
const progressStages = [...document.querySelectorAll("#workflow-progress li")];

let current = null;

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || "Request failed");
  return data;
}

function setHidden(element, hidden) {
  element.classList.toggle("hidden", hidden);
}

function showNotice(message, kind = "warning") {
  warning.textContent = message || "";
  warning.dataset.kind = kind;
  setHidden(warning, !message);
  if (message) statusPanel.classList.remove("hidden");
}

function formatLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatQuantity(value) {
  if (value && typeof value === "object" && "magnitude" in value && "unit" in value) {
    return `${value.magnitude} ${value.unit}`;
  }
  if (value && typeof value === "object" && "magnitude_si" in value && "si_unit" in value) {
    return `${value.magnitude_si} ${value.si_unit}`;
  }
  return formatLabel(value);
}

function activeStage(state) {
  if (state === "needs_clarification") return "clarify";
  if (["spec_drafted", "spec_validated", "user_confirmation_required", "compiled"].includes(state)) return "review";
  if (["running", "validating", "completed", "failed"].includes(state)) return "results";
  return "request";
}

function renderProgress(state) {
  const order = ["request", "clarify", "review", "results"];
  const currentIndex = order.indexOf(activeStage(state));
  for (const item of progressStages) {
    const index = order.indexOf(item.dataset.stage);
    item.classList.toggle("is-active", index === currentIndex);
    item.classList.toggle("is-complete", index < currentIndex);
  }
}

function summaryCard(label, value, detail = "") {
  const card = document.createElement("article");
  card.className = "summary-card";
  const name = document.createElement("span");
  name.textContent = label;
  const primary = document.createElement("strong");
  primary.textContent = value;
  card.append(name, primary);
  if (detail) {
    const secondary = document.createElement("small");
    secondary.textContent = detail;
    card.appendChild(secondary);
  }
  return card;
}

function renderPlan(view) {
  const spec = view.spec || view.plan?.spec;
  planSummary.replaceChildren();
  if (!spec) {
    setHidden(planSection, true);
    return;
  }
  const regions = spec.regions || [];
  const contacts = spec.contacts || [];
  const models = spec.physics?.models || [];
  const study = spec.study || {};
  planSummary.append(
    summaryCard("Backend", String(view.backend).toUpperCase(), view.backend === "devsim" ? "Local deterministic runner" : "Licensed remote runner"),
    summaryCard("Structure", `${regions.length} silicon region${regions.length === 1 ? "" : "s"}`, `${spec.dimension || 1}D · ${contacts.length} contacts`),
    summaryCard("Physics", formatQuantity(spec.physics?.temperature || "Not specified"), `${models.length} declared models`),
    summaryCard("Study", formatLabel(study.kind || "Not specified"), study.kind === "equilibrium" ? "No external bias sweep" : "Bounded bias study"),
  );
  const limitation = spec.metadata?.limitation;
  if (limitation) planSummary.append(summaryCard("Declared limitation", "Approximation in use", limitation));
  planDigest.textContent = view.plan_digest || "Not generated";
  plan.textContent = JSON.stringify(view.plan || {spec}, null, 2);
  setHidden(planSection, false);
}

function renderQuestions(view) {
  questions.replaceChildren();
  for (const item of view.questions || []) {
    const wrapper = document.createElement("label");
    wrapper.className = "question-field";
    const label = document.createElement("span");
    label.textContent = item.prompt;
    const input = document.createElement("input");
    input.dataset.field = item.field;
    input.name = item.field;
    input.autocomplete = "off";
    input.placeholder = `Enter ${formatLabel(item.field.split(".").at(-1))}`;
    wrapper.append(label, input);
    questions.appendChild(wrapper);
  }
  const needsAnswers = view.state === "needs_clarification";
  setHidden(questionsSection, !needsAnswers);
  setHidden(answerButton, !needsAnswers);
  updateAnswerReadiness();
}

function collectAnswers() {
  return [...questions.querySelectorAll("input")]
    .filter((input) => input.value.trim())
    .map((input) => ({field: input.dataset.field, value: input.value.trim()}));
}

function updateAnswerReadiness() {
  const inputs = [...questions.querySelectorAll("input")];
  answerButton.disabled = inputs.length === 0 || inputs.some((input) => !input.value.trim());
}

function renderValidation(view) {
  validationList.replaceChildren();
  const report = view.validation;
  const states = ["running", "validating", "completed", "failed"];
  const showResults = Boolean(report || view.bundle_path || states.includes(view.state));
  setHidden(resultsPanel, !showResults);
  if (!showResults) return;

  validationStatus.textContent = report?.overall ? formatLabel(report.overall) : formatLabel(view.state);
  validationStatus.dataset.status = report?.overall || view.state;
  if (report?.checks?.length) {
    for (const check of report.checks) {
      const row = document.createElement("article");
      row.className = "validation-row";
      const indicator = document.createElement("span");
      indicator.className = "check-indicator";
      indicator.dataset.status = check.status;
      const content = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = formatLabel(check.id);
      const message = document.createElement("p");
      message.textContent = check.message;
      content.append(title, message);
      const status = document.createElement("span");
      status.className = "check-status";
      status.textContent = formatLabel(check.status);
      row.append(indicator, content, status);
      validationList.appendChild(row);
    }
    validation.textContent = JSON.stringify(report, null, 2);
    setHidden(validationDetails, false);
  } else {
    const pending = document.createElement("p");
    pending.className = "empty-state";
    pending.textContent = view.error_message || "The simulation record is being prepared.";
    validationList.appendChild(pending);
    setHidden(validationDetails, true);
  }

  setHidden(artifacts, !view.bundle_path);
  artifactLinks.replaceChildren();
  if (view.bundle_path) {
    const files = [
      ["Research report", "report.md"],
      ["Canonical results", "results/canonical.json"],
      ["Validation record", "validation/report.json"],
      ["Evidence manifest", "manifest.json"],
      ["Event ledger", "events.jsonl"],
    ];
    for (const [label, path] of files) {
      const link = document.createElement("a");
      link.textContent = label;
      link.href = `/api/requests/${view.id}/artifacts/${path}`;
      if (path === "report.md") link.id = "report";
      artifactLinks.appendChild(link);
    }
  }
}

function render(view) {
  current = view;
  statusPanel.classList.remove("hidden");
  stateLabel.textContent = formatLabel(view.state);
  stateLabel.dataset.status = view.state;
  renderProgress(view.state);
  renderQuestions(view);
  renderPlan(view);
  renderValidation(view);
  setHidden(approveButton, view.state !== "user_confirmation_required");
  setHidden(runButton, view.state !== "compiled");

  const messages = [...(view.warnings || [])].map(formatLabel);
  if (view.error_message) messages.push(view.error_message);
  showNotice(messages.join(" · "), view.error_message ? "error" : "warning");
}

async function perform(button, pendingText, operation) {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = pendingText;
  showNotice("");
  try {
    render(await operation());
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    button.innerHTML = original;
    if (button === answerButton) updateAnswerReadiness();
    else button.disabled = false;
  }
}

function renderBackendDescription() {
  const sentaurus = backendInput.value === "sentaurus";
  backendDescription.textContent = sentaurus ? "Compilation ready · Licensed execution required" : "Ready for local execution";
  document.querySelector(".backend-dot").dataset.backend = backendInput.value;
}

backendInput.addEventListener("change", renderBackendDescription);
questions.addEventListener("input", updateAnswerReadiness);

submitButton.addEventListener("click", async () => {
  if (!promptInput.value.trim()) {
    statusPanel.classList.remove("hidden");
    showNotice("Describe the requested device study before building a plan.", "error");
    return;
  }
  await perform(submitButton, "Building plan…", () => request("/api/requests", {
    method: "POST",
    body: JSON.stringify({prompt: promptInput.value.trim(), backend: backendInput.value}),
  }));
});

answerButton.addEventListener("click", async () => {
  const answers = collectAnswers();
  const count = questions.querySelectorAll("input").length;
  if (!current || current.state !== "needs_clarification" || answers.length !== count) return;
  await perform(answerButton, "Preparing plan…", () => request(`/api/requests/${current.id}/answers`, {
    method: "POST",
    body: JSON.stringify({answers}),
  }));
});

approveButton.addEventListener("click", async () => {
  if (!current?.plan_digest) return;
  await perform(approveButton, "Compiling…", () => request(`/api/requests/${current.id}/approve`, {
    method: "POST",
    body: JSON.stringify({plan_digest: current.plan_digest}),
  }));
});

runButton.addEventListener("click", async () => {
  await perform(runButton, "Running simulation…", () => request(`/api/requests/${current.id}/run`, {method: "POST"}));
});

renderBackendDescription();
